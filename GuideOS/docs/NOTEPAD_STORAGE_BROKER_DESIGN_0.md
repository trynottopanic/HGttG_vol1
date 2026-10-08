# Notepad Storage Broker Design 0

Status: compilation handoff. This is a proposed interface design for the next
implementation slice. It is not in `interfaces.json`, is not enabled in the
current root candidate, and is not physical Deck evidence.

## Purpose and non-goals

This design makes the existing provider-private `NotepadStore` reachable only
through a capability-checked External Storage provider. It supplies the accepted
`documents.notepad` collection without giving an application an external-card
path, a mount operation, directory handle, general card-write privilege, or
permission to complete a recovered transaction automatically.

It serves Notepad 0.1 only. There is no delete, rename, directory management,
arbitrary collection access, general document editor API, or broad writable-card
interface in this slice.

## Responsible components

| Component | Responsibility | Must not do |
| --- | --- | --- |
| External Storage provider | Own the external slot, writable mount lifecycle, card identity, insertion generation, collection root FD, write serialization, transaction recovery and safe eject. | Expose mount paths or direct writable FDs. |
| Capability broker | Authenticate peer through Supervisor, issue/revoke scoped grants, validate operation and collection scope. | Determine card identity or implement filesystem writes. |
| Supervisor | Resolves an authenticated process to its live application instance/generation and coordinates stop/checkpoint deadlines. | Authorize itself on behalf of an application. |
| Notepad | Requests list/open/status or a bounded transaction; displays typed outcomes; retains its private recovery checkpoint until confirmed save. | Mount/eject/scan a card or infer success from a local write attempt. |

The provider serializes mutations per physical card. Reads may run concurrently
only while the card generation and grant are valid.

## Capability and grant shape

Proposed provider capability: `storage.documents.collection`, interface major 1.
The concrete scope is exactly `documents.notepad`; a capability name is not a
wildcard over every document collection.

The broker has separate grants:

| Grant scope | Allowed operations | Lifetime |
| --- | --- | --- |
| `documents.notepad.read` | `STATUS`, `LIST`, `OPEN` | live instance, current card generation and provider revision |
| `documents.notepad.write` | `CREATE`, `COMMIT`, `REPLACE` | same bindings, plus one bounded transaction at a time |

Every grant record binds application instance ID, launch generation, interface
version, provider ID, card identity, insertion generation, collection, operations,
expiry, and revocation revision. Removal, reinsertion, safe eject, provider
restart, application exit, or Supervisor reconciliation failure revokes it.

## Proposed Envelope interface

Proposed family: `guide.storage.documents`, major 1, minor 0, endpoint
`/run/guideos/brokers/storage-documents.sock`. It uses the common Envelope 0
header, CBOR profile, authenticated connection context, and outcome codes. The
final compiler must add it to `package/guide-ipc/schema/interfaces.json` only
with matching generated validators/constants/fixtures.

All names are NFC UTF-8 base names, 1--32 code points, supplied without `.txt`.
All content is UTF-8 text normalized to LF, up to 5,120 code points and 20,480
bytes. The provider adds `.txt`; it does not accept caller paths. Status/digest
values are opaque 32-byte SHA-256 bytes, not paths.

| Operation | Grant | Arguments | Result | Outcome notes |
| --- | --- | --- | --- | --- |
| `STATUS` (1) | read | grant ID | provider/card/generation/collection writable state | `UNAVAILABLE`, `REVOKED` |
| `LIST` (2) | read | grant ID, after-name optional | bounded up to 64 `(name, state)` entries and continuation | `RESOURCE_EXHAUSTED` if collection cannot be safely indexed |
| `OPEN` (3) | read | grant ID, base name | normalized name, state digest, one `SCM_RIGHTS` read-only regular-file FD | `NOT_FOUND`, `STALE`, `INVALID_ARGUMENT` |
| `CREATE` (4) | write | grant ID, normalized base name, expected missing state, text, 16-byte retry token | transaction receipt and new state | `ALREADY_EXISTS`, `STALE`, `QUOTA_EXCEEDED`, `BUSY` |
| `COMMIT` (5) | write | grant ID, normalized base name, expected digest, text, 16-byte retry token | transaction receipt and new state | `CONFLICT`, `STALE`, `BUSY` |
| `REPLACE` (6) | write | grant ID, normalized base name, expected digest, text, explicit replace flag true, 16-byte retry token | transaction receipt and new state | `CONFLICT`, `STALE`, `DENIED` |

The write operations are retryable mutations. Their record binds retry token,
operation, normalized request digest, grant/card binding, phase and terminal
result. The same token and identical request returns the prior outcome; changed
arguments return `CONFLICT`. One operation uses one inline document payload,
which remains inside Envelope 0's 32 KiB cap.

`OPEN` is the only operation that transfers a descriptor. The FD is read-only,
regular, close-on-exec and leased. The broker/provider may terminate a
noncompliant application after card removal or safe-eject release deadlines.
No writable external document FD is ever passed.

## Provider lifecycle and transaction states

The existing `storage_service.py` remains read-only until this is implemented as
a separate provider lifecycle. The compiler should not add write behavior behind
its current read-only probe flag. The old and new mount-owner lifecycles must
be mutually exclusive; keeping the old implementation for regression and rollback
does not authorize two live owners of the same slot. See the
[integration review](NOTEPAD_INSTALLATION_INTEGRATION_0.md) for generated codec,
transaction durability and recovery gaps that must be closed before deployment.

```text
ABSENT -> IDENTIFYING -> READ_ONLY_RECOGNIZED
      -> WRITABLE_READY -> EJECT_DRAINING -> UNMOUNTED
                         -> RECOVERY_PENDING -> WRITABLE_READY
      -> REMOVED / PROVIDER_FAILED
```

`WRITABLE_READY` requires exactly one recognized supported volume, a current
slot identity, a private provider mount, and successful provider self-check. It
does not mean any application has write permission.

For one mutation:

```text
RECEIVED -> VALIDATING -> RECORD_DURABLE -> TEMP_WRITTEN_AND_FLUSHED
         -> COMMITTING -> DIRECTORY_CONFIRMED -> COMPLETED
         -> RETAINED_FOR_RECOVERY
```

Cancellation is allowed before `COMMITTING`. Once commit begins it is bounded,
reports its actual terminal result, and safe eject waits for it or retains a
recovery record. At each entry to `VALIDATING`, `COMMITTING`, and pre-unmount,
the provider rechecks the physical card identity and insertion generation.

On restart or reinsertion, the provider asks the transaction core for bounded
recovery classification. It may clean an already-confirmed receipt only after
the same identity/generation checks. It must present owner/application recovery
choices for a temporary object or conflict; it must not auto-commit text.

## Required implementation order

1. Add a dedicated writable provider process/socket lifecycle; keep existing
   read-only recognition service intact as a regression control.
2. Move card identity and generation ownership into a shared provider state
   object; add an exclusive mutation queue and safe-eject drain protocol.
3. Compile the proposed interface into the Envelope schema and generated
   validators. Add broker grant issue/revoke verification bound to Supervisor
   connection context.
4. Adapt `NotepadStore` to receive only provider-owned directory descriptors and
   to return typed transaction results to the provider.
5. Add Notepad adapter code only after the above can return all typed outcomes.
   A denied or unavailable external feature leaves local/private Notepad usable.
6. Run integration and fault-injection tests, then an isolated physical card
   campaign. Do not place it in a seed image before the contract tests pass.

## Required tests and evidence

Source/integration tests must cover: separate read/write grants; rejected peer;
grant revocation after removal/reinsertion; stale generation before and during a
save; explicit create versus replacement; same-token retry; changed-token
conflict; bounded list; read-only descriptor transfer; no mount-path disclosure;
safe-eject drain; provider restart; and every recovery classification.

Physical RG35XX H evidence must record image hash, card identity, filesystem,
power/removal phase, reboot/reinsert result, save result and resulting document
digest. It must specifically test exFAT temporary write, flush, replacement,
directory update, removal and power interruption. Successful source or image
tests do not establish those facts.

## Compile handoff sources

- `NOTEPAD_CARTRIDGE_0.md`: accepted user behavior.
- `EXTERNAL_STORAGE_0.md`: service ownership boundary.
- `IPC_ENVELOPE_0.md`: framing, grants, descriptors and mutation lifecycle.
- `SUPERVISOR_CAPABILITY_FOUNDATION_0_PROPOSAL.md`: Supervisor/broker base.
- `package/guide-storage/notepad_store.py`: source-stage transaction core.
- `package/guide-storage/test_notepad_store.py`: transaction tests.
- `docs/NOTEPAD_STORAGE_DEPENDENCY_0.md`: current evidence and remaining work.
