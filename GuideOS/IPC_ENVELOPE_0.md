# GuideOS IPC Envelope 0

Status: local protocol baseline accepted; development-host compatibility,
production-preparation and ARM64 runtime-image verification passed 25 September
2026. The live trusted Supervisor/broker integration and physical Deck acceptance
remain pending. See `IPC_PRE_ARM64_REPORT_0.md` and
`docs/IPC_ARM64_IMAGE_VERIFICATION_0.md`.

## Purpose and authority boundary

Envelope 0 is the common bounded local message container used among supervised
applications, the shell, the Supervisor and trusted Guide brokers. It identifies,
correlates and bounds messages. It does not grant authority. OS-authenticated
connection state, installed agreements, Supervisor instance records and opaque
broker grants decide what an operation may do.

Envelope 0 is local IPC. It does not define remote Node transport, individual
broker operations or a central system bus.

## Transport

- Unix-domain `SOCK_SEQPACKET`.
- Shared brokers expose separate filesystem sockets under
  `/run/guideos/brokers/`, created by systemd `ListenSequentialPacket=` units.
- The Supervisor supplies a private `SOCK_SEQPACKET` socketpair for an
  application's lifecycle channel.
- `SOCK_STREAM` is a fallback only if native target evidence establishes a
  specific sequential-packet failure.
- D-Bus, datagrams and Linux abstract sockets are not the Envelope 0 baseline.
- File and resource handles use `SCM_RIGHTS`; paths do not substitute for handles.

The initial socket directory is owned by root with mode 0755. Broker sockets use
root ownership, the dedicated supervised-application group and mode 0660. These
permissions are a coarse connection boundary only; they never replace peer and
grant validation.

## Connection identity

On acceptance a broker obtains `SO_PEERCRED`, opens a `pidfd` for the peer and
asks the trusted Supervisor registry to resolve the live process against its
systemd unit/cgroup, registered instance, component membership, launch generation
and installed package. The broker stores the returned immutable context with the
connection. Ordinary messages carry no application identity.

Unknown processes and unavailable/unreconciled Supervisor state are rejected
before the first request. Peer exit closes the connection and releases pending
work. Broker restart requires reconnection and grant revalidation. Supervisor
restart reconciles surviving systemd units before brokers accept new instances.

## Fixed header

Every packet begins with this 24-byte big-endian header. Encoders and decoders use
explicit byte operations rather than compiler-native structures.

| Offset | Size | Field | Rule |
| ---: | ---: | --- | --- |
| 0 | 4 | magic | ASCII `GIPC` |
| 4 | 1 | envelope major | `1` for this format |
| 5 | 1 | envelope minor | `0` for this format |
| 6 | 1 | class | 1 request, 2 reply, 3 event, 4 cancel |
| 7 | 1 | flags | zero |
| 8 | 2 | interface major | broker interface major |
| 10 | 2 | interface minor | exact schema minor used |
| 12 | 8 | request ID | nonzero except events |
| 20 | 2 | payload bytes | CBOR payload length |
| 22 | 1 | descriptor count | received `SCM_RIGHTS` count |
| 23 | 1 | reserved | zero |

Packet bytes equal 24 plus the declared payload length. `MSG_TRUNC`, `MSG_CTRUNC`,
length mismatch, unexpected ancillary data or descriptor mismatch invalidates the
complete packet and closes all received descriptors.

## CBOR profile and limits

One deterministic definite-length CBOR map follows the header.

Allowed values are signed/unsigned integers up to 64 bits, booleans, null, valid
UTF-8 text, byte strings, arrays and maps with strictly ascending nonnegative
integer keys. Floating point, tags, indefinite lengths, arbitrary simple values,
text map keys, duplicate/out-of-order keys, nonminimal integer/length forms and
trailing objects are forbidden.

| Resource | Limit |
| --- | ---: |
| Payload | 32 KiB |
| Complete packet | 32,792 bytes |
| Attached descriptors | 4 |
| Nesting depth | 6 |
| Entries in one map | 32 |
| Elements in one array | 64 |
| Total decoded values | 256 |
| One text or byte string | 24 KiB |
| UI/diagnostic error text | 256 UTF-8 bytes |
| Outstanding ordinary requests per connection | 1 |
| Queued service events per connection | 16 |
| Default application connections per broker | 32 |

A maximum-size Notepad document may travel inline. Media, archives, databases and
other bulk data use brokered descriptors. Providers validate the raw profile
before generic object decoding or operation dispatch.

## Common payload maps

Request:

```text
{0: operation, 1: arguments, 2: deadline, ?3: retry_token}
```

Deadline is absolute Linux `CLOCK_BOOTTIME` nanoseconds and no more than five
minutes ahead. Retry token is exactly 16 bytes and appears only for operations
whose interface defines durable idempotent retry.

Reply:

```text
{0: outcome, 1: body}
```

Event:

```text
{0: event, 1: body}
```

Cancel is `{}`; its header repeats the active request ID. Grant, object, revision,
transaction and descriptor-role fields are defined by the selected interface.

## Outcomes

0 `OK`; 1 `CANCELLED`; 2 `INVALID_ARGUMENT`; 3 `UNSUPPORTED_OPERATION`;
4 `INCOMPATIBLE_INTERFACE`; 5 `FAILED_PRECONDITION`; 6 `DENIED`; 7 `REVOKED`;
8 `NOT_FOUND`; 9 `ALREADY_EXISTS`; 10 `CONFLICT`; 11 `STALE`; 12 `BUSY`;
13 `QUOTA_EXCEEDED`; 14 `RESOURCE_EXHAUSTED`; 15 `UNAVAILABLE`;
16 `DEADLINE_EXCEEDED`; 17 `PROVIDER_FAILED`; 18 `INTERNAL_ERROR`.

A non-OK body may use key 0 detail code, key 1 UI message identifier, key 2 bounded
parameters, key 3 retry delay milliseconds and key 4 diagnostic reference. It does
not expose stack traces, credentials, ambient paths or reflected private content.

Malformed framing, unsupported envelope major, truncation, reserved bits,
descriptor mismatch, invalid/profile-violating CBOR, request-ID misuse or a second
ordinary request closes the connection without reply. A valid but incompatible
interface receives one typed reply before close.

## Concurrency, events and cancellation

One ordinary request is active on a broker connection. Cancellation for that
request and system events may interleave. Separate connections and applications
remain concurrent. Replies are therefore ordered without client response tables.

Replaceable state events may coalesce. Loss of meaningful event history emits one
`resnapshot required` event. Replies and revocations are never silently dropped.
A cancellation produces `CANCELLED` only when completion was prevented.

## Grants and descriptors

Runtime grants use random opaque 128-bit IDs and authoritative records binding
instance/generation, provider/interface, operations, scope, sharing, expiry and
revocation. Providers verify them against authenticated connection context and
may cache by capability-registry revision.

Application restart invalidates grants. Reconnection by the same live instance
requires revalidation. Grant IDs, request IDs and retry tokens are not
interchangeable authority.

Passed descriptors are close-on-exec, least-access and recorded as leases. New
operations stop immediately on revocation. A passed descriptor cannot generally
be recalled; immediate revocation or safe eject gives a bounded release deadline
and may require Supervisor termination of a noncompliant application. Direct
writable external files are not passed; external writes remain broker transactions.

## Request and retry lifecycle

States are `RECEIVED`, `VALIDATING`, `RUNNING`, optional `COMMITTING`, and
`COMPLETED`, with terminal rejection, cancellation and failure paths. No
operation-specific side effect precedes complete validation.

Mutation enters `COMMITTING` only after temporary output is complete, a durable
transaction record exists and restart reconciliation is defined. Commit is bounded
and reports its actual result even when cancellation or deadline arrives too late.
An accepted request has at most one terminal reply.

A retryable mutation records token, operation, normalized-argument digest,
grant/object scope, transaction state and terminal result. Same token plus same
operation returns or continues that result; changed arguments produce `CONFLICT`.
Disconnect cancels reads and pre-commit work. Bounded commit may finish and retain
its result. Longer work returns a supervised job handle.

## Interface evolution

Each broker socket exposes one interface family. No negotiation handshake is
required. Receiver accepts matching major and supported declared minor; reply uses
the request version. Minor adds compatible operations/events/optional fields;
major changes existing meaning, types, requirements or transaction behavior.
Identifiers are never reused.

The declared minor is strict: required fields exist and unknown fields are
rejected. Operation 0 is invalid. Operations, events and detail codes have
independent 1-through-65,535 spaces per interface.

One checked-in CDDL schema and registry generate C constants/validation tables,
Python constants/validators, fixtures and readable documentation. Generated output
must reproduce exactly in validation.

## Codec and implementation choice

Use Debian's maintained `libcbor` for C object conversion and `python3-cbor2` for
Python object conversion. A small Guide-owned raw-byte profile validator runs
before either generic decoder. It enforces the narrower deterministic profile,
while the maintained libraries handle allocation, object conversion and ordinary
CBOR mechanics. This avoids a full custom binary codec and avoids vendoring a
second CBOR implementation.

Persistent brokers should use the C library path. Python applications and fixtures
may use the Python path; Envelope 0 introduces no separate Python daemon. Receive
buffers are allocated once per active connection and bounded; applications transfer
bulk data outside the envelope.

## Diagnostics

Record bounded categories, interface/version, message class, outcome, duration,
packet size, descriptor count and an opaque diagnostic reference. Do not log
payload bytes, document text, credentials, grant IDs, retry tokens, selected keys
or complete private filenames. Apply journald rate limiting. Protocol violations
log a category, not reflected attacker-controlled input.

## Evidence boundary

`package/guide-ipc/` contains the development-host spike and production-preparation
implementation. The C runtime subsequently passed bounded ARM64 image verification
inside a copied staging filesystem. This does not establish live Supervisor-registry
enforcement, production grant handling, service restart behavior or physical
RG35XX H behavior. Those remain required before Envelope 0 is an enabled GuideOS
service contract.
