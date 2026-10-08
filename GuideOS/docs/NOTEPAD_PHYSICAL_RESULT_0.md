# Notepad installation and first note: physical result

26 September 2026. The owner confirmed cartridge installation and the first-note
test succeeded after the Supervisor handshake fix. This confirms those observed
paths; it does not establish that every fresh-boot installation is reliable.

## Evidence

The returned Seed was captured read-only; it was not rewritten or cleaned.
Capture and extracts: `build/notepad-physical-success-0/`.
Capture SHA256: `D35855FB5D1F20079D29E2A86FFA74EAE09383C59A51A49A9B526CF37D2FF5E4`.

Current Notepad installation is `committed`, code 10000, with its release present.
The successful health check exited 0 with a durable checkpoint at 80.365 s.
The owner launch ran from approximately 84.722 to 152.821 s and ended with
`GUIDE_APPLICATION_EXIT 0 CHECKPOINT durable`. Peak application memory was 14 MiB.
There is an application-private checkpoint object. No named draft-index/draft-N
objects are present in this capture, so a separate named-draft save/reopen test
is not inferred from the checkpoint or the owner's first-note report. Note text
was not printed or copied into the diagnostic report.

## Misleading application entry

The prior returned Seed already proves the failed attempt left an `uninstalled`
record, no release directory and no private objects. It was not a successfully
installed or launchable program. The catalog deliberately retains identity and
agreement metadata for reinstall continuity; the UI includes these records in
Applications. Its status suffix and generic detail title are insufficiently clear.
The detail view supplies Delete retained private data instead of Open for that
state. The owner did not test launching the earlier entry; do not claim otherwise.

Follow-up: make the uninstalled state prominent before the name, distinguish
metadata-only records from retained owner data, and offer no unnecessary data
removal action when there is no private store. Preserve stable identity and
retained drafts; do not erase records or data merely to clean up the display.

## Another first-attempt startup failure

The latest boot also contains a failed health check before the successful install:

- 50.994 s: first health unit starts.
- 51.706 s: capability broker activation starts.
- 51.898 s: application host exits 72, checkpoint none, as the broker starts.
- 52.359 s: installer reports ValueError and rolls back.
- 79.554 s: second health unit starts; it exits successfully at 80.365 s.

The adapter handshake fault no longer appears. The runtime's broker call allows
only 200 ms; the cold-start timing is consistent with that deadline being consumed
by service startup. The typed exit does not retain the exact exception, so this
is a well-supported diagnosis to reproduce, not yet a confirmed repaired cause.
The health store is isolated temporary storage and does not read the owner's
private objects. Therefore successful installation after Delete data does not
establish that deletion was necessary or that retained data was corrupt.

Follow-up: order required provider startup before the bounded application health
check and add a cold-service activation regression. Do not require destructive
private-data deletion as a workaround. This result does not change the separate
external-slot controller clock-timeout issue.
