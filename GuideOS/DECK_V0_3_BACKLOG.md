# Deck prototype v0.3 development backlog

Status: initial general-planning backlog accepted 25 September 2026.

This is the first ordered set of ten development tasks for the handheld Deck
prototype. It supplements the design contracts; it does not replace them. A
task is complete only when its user-visible behavior is physically exercised on
the RG35XX H where hardware behavior is material. Source tests, virtual tests,
image verification and physical evidence must be reported separately.

## Product theme

The handheld Deck is intended to become a useful person-owned portable
computer: a coherent suite of software for ordinary tasks while away from
home, not merely a launcher or single-purpose appliance. Applications should
work offline where reasonable, share the Guide's input, presentation,
lifecycle and resource contracts, and preserve battery life and owner control.

## Initial ten tasks

1. **Physically validate the staged 0.3.2 build.** Test the boot animation,
   speaker output, volume, local audio playback, Bluetooth pairing, earbud loss,
   navigation under load and orderly shutdown.

2. **Finish the shared input revision.** Integrate and physically tune the stick
   keyboard controls, menu pointer, radial context menus, drift handling and
   focus-loss recovery.

3. **Complete Unicode rendering.** Provide shaped international text, fallback
   fonts and color emoji across menus, Wi-Fi labels and shared text entry.

4. **Deploy lightweight diagnostics.** Collect bounded CPU, memory, process-tree,
   navigation-latency, audio and boot-animation evidence without recording
   private input or user content.

5. **Implement network-delivered updates.** Support resumable packages,
   integrity checking, transactional activation, diagnostic return and automatic
   rollback while preserving the independent recovery path.

6. **Build the common application lifecycle contract.** Define and implement
   stable application and instance identity, admission, pause, resume,
   checkpoint, stop, crash recovery and worker ownership above systemd.

7. **Connect real resource enforcement.** Apply the accepted priority tiers and
   CPU, memory and I/O ceilings to whole applications and their workers, with
   playback prioritized over downloads under contention.

8. **Implement the live capability registry and broker.** Keep discovery,
   authorization, compatibility, resource allocation, leases and revocation
   distinct and observable.

9. **Prototype the semantic Guide View renderer.** Implement portable menus,
   lists, status, forms, offline and stale states, predictable focus and
   640-by-480 conformance fixtures. The accepted shell migration sequence and
   shared visible/hit-geometry requirement are recorded in
   `SHELL_UI_SCHEMA_MIGRATION_0.md`.

10. **Begin the Guide Recipe creator path.** Let an ordinary user connect events,
    conditions, information, devices and actions; inspect and test the result;
    and package it without requiring Linux-administration knowledge.

## Working sequence

The initial dependency path is:

1. physical 0.3.2 validation;
2. diagnostics and input completion;
3. network deployment;
4. GuideOS IPC Envelope 0;
5. lifecycle and resource enforcement proof;
6. capability brokering;
7. Guide View and Recipe work.

### Promoted foundation task: Supervisor and Capability Foundation 0

Approved 25 September 2026. Implement the common lifecycle/identity contract, a
small privileged C Supervisor above systemd, a separate unprivileged C capability
broker, the harmless health/probe integration and their development-host and
ARM64 verification. Capability registry and grant records initially share one
broker process while remaining logically distinct. Applications do not depend on
the new services until the probe foundation passes physical acceptance.

The governing decisions, implementation stages, failure rules, verification
matrix and installation gates are in
`SUPERVISOR_CAPABILITY_FOUNDATION_0_PROPOSAL.md`. Despite its historical filename,
that document is now approved architecture. A raw card write remains a separate
gated installation action.
### Promoted foundation task: GuideOS IPC Envelope 0

Before integrating the common application lifecycle or live capability broker,
define and implement one bounded authenticated local message envelope shared by
applications, the shell, Supervisor and broker services. The envelope identifies
and bounds communication; it does not grant authority. Connection authentication,
installed agreements, broker state and opaque grants determine what an instance
may do.

Required work:

- bind each connection to an OS-authenticated application instance and launch
  generation rather than trusting a sender-provided identity;
- define envelope and service-interface versions, request/reply/event/cancel
  classes, request correlation, monotonic deadlines and typed errors;
- define strict bounds for frames, fields, nesting, lists, attached handles,
  outstanding work and event queues;
- define ordering, concurrency, backpressure, cancellation, idempotency, stale
  generation and service-restart reconciliation behavior;
- carry only opaque grant references, never self-asserted permissions;
- correlate Unix file-descriptor transfer safely with a single message;
- exclude credentials and user content from ordinary diagnostics; and
- reject malformed or incompatible input before side effects.

Deliverables are a normative schema and field table, a transport/encoding
decision record, shared encoder/decoder and authentication library, reference
client/service fixtures, adversarial and fuzz tests, and one real harmless Guide
service integration. The task is not complete merely because two programs can
exchange JSON or socket bytes.

Service-specific storage, input, display and capability operations remain outside
the common envelope. Cross-device and remote-Node networking are also outside
Envelope 0.

### Accepted Envelope 0 local transport baseline

The initial local transport uses Unix-domain `SOCK_SEQPACKET`. Shared brokers use
separate filesystem socket endpoints beneath `/run/guideos/`, created and activated
by systemd. A central message-routing bus is not required. The Supervisor creates
a private `SOCK_SEQPACKET` socketpair for each application lifecycle channel and
passes the application end during launch.

Services authenticate connected peers using OS-provided credentials and bind the
connection to Supervisor-held instance state. Sender-provided identity fields do
not establish authority. Unix `SCM_RIGHTS` descriptor passing supplies authorized
file or resource handles, with every descriptor correlated to exactly one complete
envelope. Abstract-namespace sockets are not the default because they lack the
filesystem ownership and visibility of the accepted `/run/guideos/` endpoints.

`SOCK_STREAM` remains a fallback only if physical Debian integration exposes a
specific sequential-packet limitation. `SOCK_DGRAM` is not the primary broker
channel. D-Bus is not adopted for Envelope 0; it may still be evaluated for a
later component with a demonstrated need.

The compatibility work must verify C and Python clients, systemd socket activation,
peer credentials, disconnect behavior, bounded message truncation detection,
`SCM_RIGHTS` transfer and Deck Debian support. This verification can reject a
broken implementation, but it does not silently replace the accepted transport.

### Accepted Envelope 0 wire-format baseline

Every `SOCK_SEQPACKET` message consists of a small fixed binary envelope header
followed by a strictly profiled CBOR payload. Universal routing, correlation,
version and bounds fields belong in the fixed header. Service-specific request,
reply and event data belong in the CBOR payload.

Transferred Unix file descriptors remain out of band through `SCM_RIGHTS`. The
header declares their expected count, and the service-specific schema defines the
meaning and access mode of each position. A descriptor is never represented by a
filesystem path in the payload.

Envelope 0 does not accept unrestricted CBOR. The profile will bound supported
value types, nesting, maps, arrays, strings and byte strings; require deterministic
encoding where stored or hashed; reject duplicate keys and indefinite-length
items; and validate the complete packet before side effects. Unknown-field and
minor-version behavior must be defined explicitly rather than delegated to a CBOR
library.

### Accepted identity and request concurrency

An ordinary application message does not carry an application-instance identity.
At connection acceptance, the broker binds the OS-authenticated peer to immutable
Supervisor-held instance identity, launch generation, package identity and grant
state. Restart or reconnection creates a new connection epoch; old requests,
replies and grants do not transfer to it. Trusted administrative operations may
name a target instance in their service-specific payload when that identity is
the object of the operation.

Each application connection to a broker permits at most one outstanding ordinary
request. The corresponding reply completes that request before another ordinary
request is accepted. A cancellation message for the active request and
system-originated events such as removal or revocation may interleave. Separate
application connections still run concurrently, and bulk data moves through
brokered descriptors rather than repeated envelope messages. A later interface
may add pipelining only for a demonstrated need.

### Accepted Envelope 0 fixed header

Envelope 0 uses a 24-byte fixed binary header. Multibyte integers use big-endian
byte order. Implementations encode and decode fields explicitly rather than
sending compiler-dependent in-memory structures.

| Offset | Size | Field | Envelope 0 rule |
| ---: | ---: | --- | --- |
| 0 | 4 | Magic | ASCII `GIPC` |
| 4 | 1 | Envelope major | Incompatible envelope revision |
| 5 | 1 | Envelope minor | Compatible envelope extension level |
| 6 | 1 | Message class | 1 request, 2 reply, 3 event, 4 cancel |
| 7 | 1 | Flags | Must be zero |
| 8 | 2 | Interface major | Broker-interface compatibility |
| 10 | 2 | Interface minor | Compatible interface extension level |
| 12 | 8 | Request ID | Request/reply/cancel correlation |
| 20 | 2 | Payload length | CBOR bytes following the header |
| 22 | 1 | Descriptor count | Attached `SCM_RIGHTS` descriptors |
| 23 | 1 | Reserved | Must be zero |

The magic, supported envelope major, message class, zero flags and reserved byte,
interface version, packet length and descriptor count are validated before the
payload can produce side effects. Total packet bytes equal 24 plus the declared
payload length. Requests use nonzero IDs; replies and cancellations repeat the
active request ID; events use ID zero. Normal-data truncation, ancillary-data
truncation or a descriptor-count mismatch rejects the complete packet and closes
all received descriptors.

The header carries no application identity, service name, timestamp, checksum,
path or permission claim. The authenticated connection supplies identity; the
per-service socket supplies destination; the payload supplies operation-specific
meaning.

### Accepted Envelope 0 CBOR profile and limits

The maximum CBOR payload is 32 KiB, making the maximum complete packet 32,792
bytes including the fixed header. At most four `SCM_RIGHTS` descriptors accompany
one packet. Each active connection uses one reusable bounded receive buffer.
Individual broker interfaces may impose smaller limits.

The profile permits signed and unsigned integers up to 64 bits, booleans, null,
valid UTF-8 text strings, byte strings, arrays and maps with nonnegative integer
keys. It prohibits floating point, tags, indefinite-length values, duplicate map
keys, arbitrary simple values, text map keys and multiple top-level objects. Each
payload contains exactly one top-level map.

Structural limits are six levels of nesting, 32 entries in one map, 64 elements
in one array, 256 total decoded values and 24 KiB for one text or byte string.
Ordinary diagnostic and human-readable error strings are limited to 256 UTF-8
bytes. A maximum-size Notepad document can travel inline; bulk media, archives,
databases and similar content use brokered descriptors.

Senders use definite lengths, shortest integer and length representations,
numerically ordered keys and deterministic encoding. Receivers reject duplicate
keys, invalid UTF-8, nonminimal encodings, structural-limit violations and bytes
remaining after the single top-level map before operation dispatch.

A connection has one active ordinary request and at most 16 queued service events.
Replaceable state events may be coalesced. Loss of meaningful event history
produces one `resnapshot required` event; replies and revocations are not silently
discarded. The initial default maximum is 32 application connections per broker,
which a narrower broker may lower explicitly.

### Accepted Envelope 0 common payload maps

A request payload is `{0: operation, 1: arguments, 2: deadline}` with optional
`3: retry_token`. Operation is an unsigned interface-defined integer; arguments
is a service-specific map even when empty; deadline is an absolute Linux
`CLOCK_BOOTTIME` value in nanoseconds. A deadline is no more than five minutes in
the future, and an interface may impose a shorter maximum. Longer work becomes a
supervised job rather than holding one IPC request open.

A retry token is exactly 16 bytes. It is distinct from the connection-local
request ID and is required only by interface operations that define durable,
idempotent retry behavior. It may support reconciliation after reconnection but
does not itself grant authority.

A reply payload is `{0: outcome, 1: body}`. Outcome is a universal typed result
or error code and body is the service-specific result or bounded error detail.
One accepted request produces exactly one terminal reply.

An event payload is `{0: event, 1: body}` using an interface-defined integer
event code and service-specific body. Events carry request ID zero. A cancellation
payload is the empty map; the header's request ID identifies the one active
request. Its eventual terminal reply establishes the outcome, including whether
cancellation succeeded or the operation had already committed.

Operation and event codes are numeric interface constants rather than arbitrary
strings. Grant references, object identities, names, revisions and descriptor
roles remain service-specific arguments. Descriptor positions are defined by the
selected operation schema. Fields unavailable in the negotiated minor version
are rejected, and a reply cannot combine a successful result with contradictory
error details.

### Accepted Envelope 0 outcomes and failure boundary

Universal terminal outcomes are: 0 `OK`, 1 `CANCELLED`, 2 `INVALID_ARGUMENT`,
3 `UNSUPPORTED_OPERATION`, 4 `INCOMPATIBLE_INTERFACE`, 5 `FAILED_PRECONDITION`,
6 `DENIED`, 7 `REVOKED`, 8 `NOT_FOUND`, 9 `ALREADY_EXISTS`, 10 `CONFLICT`,
11 `STALE`, 12 `BUSY`, 13 `QUOTA_EXCEEDED`, 14 `RESOURCE_EXHAUSTED`,
15 `UNAVAILABLE`, 16 `DEADLINE_EXCEEDED`, 17 `PROVIDER_FAILED` and
18 `INTERNAL_ERROR`.

A non-OK reply body may contain integer key 0 interface-specific detail code,
key 1 optional UI message identifier, key 2 optional bounded parameter map, key 3
optional retry delay in milliseconds and key 4 optional bounded diagnostic
reference. It contains no stack trace, ambient path, credential or reflected
private content.

A trustworthy envelope receives a typed reply for service-level failures such as
unknown operation, bad operation arguments, expiry, denial, revocation, stale
state, conflict, quota, unavailable provider or provider failure. Wrong magic,
unsupported envelope major, normal or ancillary truncation, length or descriptor
mismatch, invalid class or reserved bits, invalid/profile-violating CBOR,
request-ID misuse or a second ordinary request while one is active closes the
connection without a reply. All received descriptors are closed and only a
bounded diagnostic category is recorded.

A valid envelope with an incompatible broker-interface major receives one
`INCOMPATIBLE_INTERFACE` reply before close. Cancellation returns `CANCELLED` only
when it actually prevents completion. Once an operation enters its declared
commit phase, the terminal reply reports the real commit outcome.

### Accepted Envelope 0 connection-to-instance binding

On acceptance, a broker obtains the peer PID, UID and GID through `SO_PEERCRED`
and immediately opens a Linux `pidfd` for the peer. It asks the trusted Supervisor
registry to resolve that live process against the current systemd unit/cgroup,
registered Guide instance, permitted component membership, launch generation and
installed package record. Failure or unavailable Supervisor state rejects the
connection before its first request.

The Supervisor returns immutable connection context containing instance ID,
launch generation, package ID, component role, resource agreement and the
reference needed for grant lookup. The broker stores it with the socket; ordinary
messages contain no identity field and perform no repeated identity lookup. UID,
PID, socket permissions or an application claim is never sufficient alone.

The `pidfd` prevents PID reuse from changing the connection's identity and lets
the broker observe peer exit, close the socket and release pending work. Approved
workers resolve through their supervised application membership. Applications do
not receive reusable bootstrap authentication tokens.

Broker restart destroys its connections; reconnection repeats binding and grant
revalidation. Supervisor restart reconciles surviving systemd units before new
broker connections are accepted. Filesystem permissions remain a coarse first
boundary rather than the authorization system.

### Accepted Envelope 0 opaque grants and revocation

A runtime grant has a random 128-bit opaque ID and an authoritative broker record
binding it to application instance and launch generation, provider/interface,
allowed operations, object or collection scope, sharing mode, expiration and
revocation state. An authority-requiring operation carries that 16-byte ID in its
service-specific arguments. The ID is not a self-describing or self-authorizing
token.

The provider checks the grant against authenticated connection identity, provider,
interface, operation, object scope, expiry, revocation and required resource lease.
It may cache a validated record by grant ID and capability-registry revision.
Revocation or revision change invalidates the cache, avoiding a central lookup on
every unchanged request without weakening enforcement.

A grant belongs to one launch generation. The same live instance may revalidate it
after reconnection; application restart invalidates it. Grant IDs are not durable
future authority, and request IDs or retry tokens never substitute for grants.

On revocation, the Capability Broker first notifies the provider. The provider
marks the grant revoked, rejects new operations, cancels safely cancellable work,
sends a typed event, requests release of descriptor leases and reports whether
release was acknowledged.

Every passed descriptor is tracked as a lease, uses the narrowest access mode and
is close-on-exec. Direct writable external files are not passed; writes use broker
transactions. Because an already transferred descriptor cannot generally be
recalled by changing a grant record, immediate revocation gives the application a
bounded release deadline and the Supervisor terminates a noncompliant instance so
the kernel closes its descriptors. Safe eject applies the same honest boundary.
Already read data cannot be made unknown. A resource needing revocation without
process termination remains broker-mediated or uses a specifically revocable
mechanism.

### Accepted Envelope 0 request lifecycle and retry model

Accepted requests move through `RECEIVED`, `VALIDATING`, `RUNNING`, optional
`COMMITTING` and `COMPLETED`, with terminal rejection, cancellation or failure
paths. Framing, schema, deadline, interface, operation, authenticated identity,
grant scope, resource availability and any retry token are validated before
operation-specific side effects.

During `RUNNING`, a declared cancellable operation may stop on cancel or deadline;
temporary work remains invisible and failure cleans it up. Read-only work normally
completes without a commit phase. A mutation enters `COMMITTING` only after input
and temporary output are complete, its durable transaction record exists and
startup reconciliation is defined. Commit then runs for a declared bounded time;
cancel or deadline cannot falsely claim that it did not happen. The terminal
reply or durable record reports the actual result.

An accepted request produces at most one terminal reply. A cancel message changes
the active request rather than creating a second reply, and `CANCELLED` is used
only when completion was actually prevented.

Retryable mutations record the 16-byte retry token, operation, normalized-argument
digest, grant/object scope, transaction state and known terminal outcome. Reuse
with the same operation returns or continues that outcome; reuse with different
arguments is `CONFLICT`; completed side effects are not repeated. Service recovery
contracts bound retention. Expiry or revocation prevents new work without erasing
results needed to reconcile an earlier authorized commit.

Connection loss cancels read-only and pre-commit work. A bounded commit may finish
and retain its result. Provider restart reconciles durable transactions before
retry. Unknown commit state is reported as requiring reconciliation, never guessed.
Work exceeding the five-minute IPC ceiling returns a supervised job handle rather
than occupying one request indefinitely.

### Accepted Envelope 0 interface evolution

Each broker socket exposes one interface family. Messages declare interface major
and minor without a separate negotiation handshake. Major begins at 1 and minor
at 0. A receiver accepts a matching major and a minor it supports; the reply uses
the request's version. Unsupported versions receive `INCOMPATIBLE_INTERFACE`
before close. A client may deliberately send an older schema it implements.

Backward-compatible operations, events, optional fields or detail codes increment
the minor version. Changed types, meanings, requirements, transaction semantics
or removal of relied-upon behavior require a new major. Numeric identifiers are
never reused.

The declared minor is strict: its required fields must exist and fields unknown
to that minor are rejected. Operation 0 is invalid; operations, events and detail
codes each have independent 1-through-65,535 spaces within an interface. Argument
and result integer field keys are scoped independently to their operation.

Each interface has one checked-in CDDL schema and registry covering endpoint,
name/version, operations, events, fields, descriptor positions, required grants,
retry/cancellation behavior and detail codes. The build generates C constants and
validation tables, Python constants and validators, deterministic valid fixtures,
malformed/version fixtures and readable documentation. Generated outputs are not
edited independently, and validation fails when regeneration differs.

The Envelope 0 design baseline is now sufficient for the compatibility spike.
The selected implementation uses `libcbor` for C object conversion and
`python3-cbor2` for Python object conversion, preceded in both cases by a small
Guide-owned raw-byte profile validator. This keeps the common wire rules under
Guide control, catches duplicate keys and nonminimal encodings before a generic
decoder normalizes them, and avoids a custom general-purpose CBOR codec or an
additional resident translation daemon. Persistent brokers should use the C
path; Python remains suitable for applications, fixtures and lower-rate tools.

The WSL development-host compatibility spike now passes bidirectional C/Python
exchange, peer credentials, pidfds, descriptor passing, systemd sequential-packet
activation, malformed-input rejection, sanitizer runs and deterministic mutation
testing. These are implementation-development results, not ARM64 or physical Deck
proof. The normative baseline is `IPC_ENVELOPE_0.md`; runnable fixtures and the
bounded evidence record are under `package/guide-ipc/`.

The checked-in generator, generated C/Python metadata, shared C transport,
bounded Supervisor-resolution reference, authoritative grant-store reference and
grant-enforced health service now pass development-host production-preparation
tests. `IPC_PRE_ARM64_REPORT_0.md` recommends the installable process topology and
records the chosen process topology. The C runtime and generated registry now pass
ARM64 image verification in a preserved staging-image copy; see
`docs/IPC_ARM64_IMAGE_VERIFICATION_0.md`. No service is enabled. Remaining work is
to embed the authority behavior in the trusted Supervisor/capability-broker
process, package and test its socket/service, prove real restart reconciliation,
then perform physical Deck testing. The Python reference authority is not the
recommended resident Deck service.

Later planning may split, reorder or add tasks when physical evidence or a
documented dependency requires it. Such changes should be recorded here rather
than silently changing what a numbered task means.

## Short-term planning tasks

- **Design the Node concept in full.** Owner direction, 26 September 2026:
  develop the Node concept and eventual prototype design so future project
  designs can take them into account. Record this as a task only; design work
  has not started. The PS3 Fat and existing Raspberry Pi hardware project
  remains a separate far-future task.

## Unordered future tasks

These tasks have no assigned priority or implementation sequence yet.

### External storage

- **Implement External Storage 0.** Add native exFAT and UTF-8 support, create
  one shared card-mount and access service, adopt the accepted `GUIDE/` root
  structure, migrate direct cartridge, media and emulation access to logical
  collections and direct read handles, add cached incremental indexing, and
  validate concurrent access, removal, reinsertion and safe eject on the 256 GB
  microSD card. Begin read-only; mediated writing remains a later explicit
  capability and transaction layer. See `EXTERNAL_STORAGE_0.md`.

### Emulation

- **Expand the Libretro integration after the shared runtime contracts are
  ready.** GuideOS already contains a six-core ARM64 Libretro prototype; future
  work is to make core selection, game-data access, save/state storage, input,
  audio/video providers, lifecycle recovery and license/provenance handling
  conform to the shared GuideOS application and external-storage contracts.
  Add cores only through explicit compatibility, resource and licensing review;
  no game data or proprietary firmware is implied.

### Power management

- **Establish a repeatable battery benchmark.** Measure full-charge runtime and
  average battery current for screen-on idle at several brightness levels,
  screen-off idle, wired local audio, Bluetooth local audio, Wi-Fi plus
  Bluetooth streaming, representative Genesis and PlayStation emulation,
  native video, sustained processing and eventual true suspend. Run each
  workload long enough to stabilize, record battery age and test conditions,
  and distinguish current telemetry from percentage-gauge estimates.

- **Pocket Mode.** This is the adopted name for the Deck's low-power inactive
  state. After a configurable period of inactivity or an explicit user action,
  Pocket Mode allows selected audio to continue over the active output,
  including Bluetooth, while quiescing everything not required for that use.
  Retain only power and safety supervision, deliberate wake handling, the
  active audio decoder and route, required Bluetooth services, volume controls,
  and anything the user expressly permitted to continue. Turn off the display
  and backlight, stop unnecessary drawing, scanning and polling, pause or defer
  nonessential work, and allow unused hardware and processors to enter their
  lowest practical idle states. Prevent accidental pocket input and define
  entry and wake controls, per-application continuation requests, network
  behavior, Bluetooth loss behavior, low-battery policy and measurable power
  acceptance criteria. Pocket Mode is application and service quiescence, not
  whole-device Linux suspend.

- **Display and backlight policy.** Add owner-controlled brightness, staged
  dimming, automatic backlight shutoff and restoration of the previous level.
  Stop interface rendering when the display is off, and allow bounded
  application-specific timeout requests for reading and video use.

- **Dynamic processor policy.** Validate frequency and idle-state support on
  the H700, select a responsive low-power governor, permit low frequencies for
  reading, audio and waiting, and grant temporary higher-performance profiles
  only to workloads that need them. Measure responsiveness, heat and energy use
  before adopting any governor or frequency limits.

- **Application update-rate classes.** Redraw static interfaces only after
  events, reduce update rates for ordinary text and status views, stop all
  background drawing, and reserve continuous high-rate presentation for video,
  games or other applications with a demonstrated need.

- **Radio power management.** Power down Wi-Fi and Bluetooth when unused, avoid
  continuous discovery, batch scans, back off failed reconnection attempts and
  define owner-visible keep-connected and disconnect-while-inactive policies.
  Avoid repeated weak-signal connection attempts and preserve explicit trust
  and capability boundaries when a radio wakes.

- **Batch background activity.** Coordinate downloads, synchronization, feed
  refreshes, indexing and maintenance so they share bounded wake periods rather
  than maintaining independent frequent timers. Allow expensive optional work
  to be restricted to charging, external power or an explicit user request.

- **Unused hardware and service shutdown.** Inventory and safely idle or power
  down unused HDMI, USB-host power, audio amplifier, vibration, wireless,
  secondary storage, GPU and video-decoder functions where the hardware and
  drivers permit it. Each change requires resume and failure-path testing on
  the physical Deck.

- **Reduce background storage writes.** Batch expendable state and telemetry,
  bound journals and logs, remove unnecessary normal-use debug output and avoid
  repeated storage wakeups, while still saving user-authored data and critical
  recovery state promptly.

- **Battery-aware scheduling and shutdown.** Define measured thresholds for
  deferring optional work, reducing brightness and performance, checkpointing
  applications, warning the owner and performing orderly shutdown with enough
  energy reserved to complete required writes. Do not assume the reported
  percentage is sufficiently accurate until the gauge is characterized.

- **True suspend and rapid restoration.** Separately investigate whole-device
  suspend for periods when no continued audio or background function is
  required. Validate wake sources, controls, SD cards, display, audio, radios,
  battery reporting and repeated suspend/resume cycles on the physical Deck.
  Ordinary system suspend is not part of Pocket Mode and is not assumed to
  preserve live audio.

### Portable applications

- **Customizable widget workspace.** Explore an optional desktop-style Guide
  environment composed from lightweight, owner-arranged widgets and icons. The
  initial ideas include categorized RSS panels for sorting news and other
  feeds; image widgets with adjustable placement and, later, bounded sizing or
  cropping; desktop-style application, document and collection icons; and
  interactable buttons that launch applications, open locations, control a
  permitted device or invoke a Guide Recipe. Layout editing must remain usable
  with the Deck controls, distinguish edit mode from ordinary activation, save
  atomically, and recover from malformed or missing widget data. Widgets must
  use shared storage, network and capability brokers rather than acquiring
  ambient access, and inactive widgets must not maintain frequent polling,
  redraw or background processes. The existing menu remains an available safe
  navigation path if the workspace fails or is disabled.

- **Desktop companions and playful utilities.** Support lightweight animated
  characters, novelty applications and other optional workspace toys inspired
  by older desktop companions, but without their surveillance, advertising or
  ambient system access. A companion may draw only inside its assigned visual
  layer, receive bounded interaction events and use explicitly granted actions
  such as speaking a local response, showing a reminder or reacting to a Guide
  Recipe event. Network, microphone, camera, location, personal data, arbitrary
  files, other applications and device control remain unavailable unless each
  narrow capability is separately explained and granted. Companions must have
  visible pause, mute, remove and uninstall controls; bounded CPU, memory and
  animation rates; no hidden persistence; and no work while disabled.

- **Owner-authored toys and microgames.** Define a simple, inspectable format
  for creating small game-like programs without requiring a native Linux build
  environment. The initial runtime should offer bounded scenes or screens,
  sprites or simple shapes, text, controller input, timers, collision and state,
  local sound, saved progress and deterministic update limits. It should share
  concepts with Guide Recipes where useful while keeping continuous game state
  distinct from event automation. Projects should be previewable, interruptible
  and packageable as Guide cartridges; run without network or personal-data
  access by default; and remain constrained by the supervisor, storage broker,
  audio ownership and global Power behavior. The authoring language, editor,
  graphics limits and relationship to a future general application runtime
  remain to be selected.

- **Side-scrolling pixel-game maker.** Build a small Deck-native authoring tool
  for creating and playing simple side-scrolling pixel-art games entirely with
  the handheld controls. A possible first scope includes a tile-based level
  editor, bounded sprite and animation editor, player start and goal placement,
  solid platforms, hazards, collectibles, simple enemies, signs or dialogue,
  sound assignment, play testing, saved projects and cartridge export. Prefer
  reusable behaviors and visual property editing over requiring code, while
  allowing later optional Recipe-like event logic. Projects should target the
  owner-authored microgame runtime rather than introduce a second incompatible
  execution system. Exact canvas, palette, tile, sprite, level, audio and logic
  limits remain TBD and should be derived from physical editing and playback
  tests on the Deck.

- **Native RPG Maker game playback.** Investigate running owner-supplied RPG
  Maker games locally through suitable maintained native or compatibility
  runtimes behind the Guide application lifecycle and input interface. Support
  is otherwise TBD: no RPG Maker generation, runtime, script system, asset or
  save compatibility, plug-in behavior, packaging convention, performance
  floor or legal redistribution assumption is adopted yet. Games and required
  proprietary assets are not included by GuideOS, and executable or scripted
  game content must not receive ambient network, storage or device authority.

- **Lightweight Reddit reader.** Provide a Deck-native interface for browsing
  and reading publicly available Reddit content without depending on Reddit's
  paid API. Evaluate public RSS feeds and ordinary public web retrieval first;
  a browser-backed presentation may be used where necessary. The application
  must identify itself appropriately, respect access controls and reasonable
  request rates, avoid bypassing authentication or anti-abuse mechanisms, and
  degrade clearly if Reddit changes or withdraws public access. Account login,
  voting, posting, messaging, mature-content handling, offline retention and
  the exact retrieval method remain unresolved.

- **JavaScript-capable web browser.** Provide ordinary modern web browsing
  through a maintained existing browser engine behind a custom Guide-native
  interface for navigation, tabs, history, downloads, permissions and status.
  Evaluate Chromium and lighter maintained alternatives, but do not assume a
  full Chromium process model will fit the current H700 and 1 GB memory target.
  The selected engine must integrate with Guide lifecycle, resource ceilings,
  input, Unicode text entry, audio, storage brokering, network policy and
  orderly cancellation. Site isolation, sandbox support, update cadence,
  certificate handling, private data, downloads, pop-ups and per-site device
  permissions require explicit security review before general use.

- **Native media playback — required before 0.4.0.** Play local video and audio files through lightweight
  Guide interfaces over suitable existing Debian software. Prefer adapting
  maintained native components where that reduces development cost without
  surrendering Guide control of lifecycle, focus, display, audio routing,
  cancellation or resource policy. The current implementation study recommends
  evolving the existing GStreamer/PipeWire service for Audio Player 1 and
  physically probing mpv's DRM and private IPC path for Video Player 1 while
  retaining the proven FFmpeg framebuffer fallback. The same media-session
  engine must play from External Storage 0, authenticated Node media tickets and
  resolved online sources. A controlled online-stream fixture is required before
  0.4.0; a complete YouTube adapter is later provider work. See
  `MEDIA_SERVICES_1.md` and `MEDIA_PLAYERS_1_PROPOSAL.md`.

- **Direct nearby-device connectivity.** Allow the Deck to communicate directly
  with nearby Wi-Fi and Bluetooth devices. The intended user functions,
  discovery behavior, permissions, trust model and supported device classes are
  still to be defined.

- **Notepad application.** Provide simple text entry, saving, listing,
  reopening and editing for notes containing up to 5,120 Unicode characters.
  A note name may contain up to 32 Unicode characters. Exact normalization,
  on-disk encoding, filename mapping, recovery and limit-counting behavior must
  be specified before implementation; the visible note name need not be used as
  an unrestricted filesystem path.

- **Voice-note application.** Record, name, save, list, replay and delete short
  audio notes using an attached Bluetooth device with a microphone. The first
  implementation should remain lightweight and use suitable existing Debian
  audio, Bluetooth and codec components behind a simple Guide interface.
  Recording limits, formats, microphone selection, interruption behavior and
  whether optional transcription belongs in a later version remain to be
  specified.

- **MIDI controller mode.** Allow the Deck to act as a MIDI controller for a
  connected device, exposing its buttons, sticks and other suitable controls as
  configurable musical actions. Supported USB and Bluetooth MIDI transports,
  default mappings, profiles, timing requirements and any MIDI-input behavior
  remain to be specified. This task does not by itself require the Deck to act
  as a synthesizer or digital audio workstation.

- **Music library and player.** Evaluate MPD as a lightweight playback and
  library backend behind a Guide-native browsing, queue and transport
  interface.

- **Audio conversion and sample tools.** Evaluate SoX for recording,
  conversion, trimming and simple effects shared by voice notes, media tools
  and the future music application.

- **SoundFont and MIDI synthesizer.** Evaluate FluidSynth as a local synthesis
  backend for MIDI playback, controller testing and later music tools.

- **Document reader.** Evaluate MuPDF for a lightweight Guide interface for
  PDF and other supported document formats, with practical small-screen zoom,
  navigation and resume behavior.

- **Calendar and reminders.** Evaluate Calcurse or its data model and command
  facilities as a basis for an offline personal calendar and reminder
  interface.

- **Task manager.** Evaluate Taskwarrior as a basis for an offline personal
  task list with a simpler Guide-native interface.

- **RSS and news reader.** Evaluate Newsboat or compatible feed-processing
  components for downloading, retaining and reading selected feeds offline.

- **IRC client.** Evaluate Irssi, WeeChat or their protocol components for a
  lightweight Guide-native IRC reader and messaging interface.

- **Personal file synchronization.** Evaluate Syncthing for owner-controlled
  synchronization between the Deck and trusted personal Nodes, subject to
  battery, metered-network, conflict and capability policies.

- **Download manager.** Evaluate aria2 for queued and resumable downloads
  governed by the Deck's network, storage, lifecycle and resource policies.

- **Offline dictionary and thesaurus.** Evaluate WordNet and `dict`-compatible
  data for local definitions, relationships and word lookup without a network
  connection.

- **Small personal databases.** Evaluate SQLite-backed Guide applications for
  user-defined collections, inventories and other structured personal records
  without exposing ordinary users to database administration.

These named Debian projects are candidate foundations rather than mandatory
dependencies. Their existing terminal interfaces need not be preserved, and
package availability alone does not establish acceptable performance,
security, accessibility or physical-device behavior.

## Long-term goals

- **First Node hardware prototype — far future, unprioritized.** Owner note,
  26 September 2026: scrap and repurpose the PS3 Fat already owned, together
  with the Raspberry Pi already on hand, to create the first Node prototype.
  Which PS3 parts to reuse, the Raspberry Pi model, the hardware arrangement
  and the Node's initial functions remain to be determined. This is a future
  project note, not current implementation or disassembly work.

- **Native music and beatmaking application.** Provide a simple, lightweight
  composition environment with a Deck-native interface, broadly comparable to
  a reduced pattern-based workstation. The intended functions include step or
  timeline sequencing, reusable and stackable patterns, multiple instrument
  tracks, project saving and loading, and basic editing of imported audio
  samples. The underlying Debian audio software, synthesis and sampling engines,
  plug-in boundary, project format, track and pattern limits, and division of
  processing between Deck and Node remain to be selected. This should remain
  compatible with the separate MIDI controller mode rather than duplicating its
  device-transport responsibilities.

## Governing references

- `README.md`
- `docs/DESIGN_ALIGNMENT_0.md`
- `MODERN_FOUNDATION_0.md`
- `IPC_ENVELOPE_0.md`
- `SUPERVISOR_CAPABILITY_FOUNDATION_0_PROPOSAL.md`
- `IPC_PRE_ARM64_REPORT_0.md`
- `docs/IPC_ARM64_IMAGE_VERIFICATION_0.md`
- `RESOURCE_CONTENTION_0.md`
- `LIVE_CAPABILITY_REGISTRY_0.md`
- `GUIDE_VIEW_1_DRAFT.md`
- `NETWORK_DEPLOYMENT_0.md`
- `TEXT_ENTRY_0.md`
- `MENU_POINTER_0.md`
- `UNICODE_RENDERING_0.md`
- `docs/AUDIO_BLUETOOTH_0.md`
- `docs/DIAGNOSTICS_0.md`
- `docs/DIAGNOSTIC_HARDWARE_COVERAGE.md`
- `EXTERNAL_STORAGE_0.md`
- `MEDIA_PLAYERS_1_PROPOSAL.md`
