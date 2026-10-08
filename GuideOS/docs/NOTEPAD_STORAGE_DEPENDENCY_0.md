# Notepad Storage Dependency 0

## Status

Source-stage only. This does not add an application-facing storage interface,
enable writes in `storage_service.py`, produce a new Deck image, or establish
exFAT durability on physical hardware.

## Implemented bounded core

`package/guide-storage/notepad_store.py` is provider-private transaction code
for the single logical collection `documents.notepad`. It validates the accepted
Notepad filename and UTF-8 text limits, binds each save to the current card
identity and insertion generation, detects destination changes, requires an
explicit create or replace choice, writes a same-directory temporary object,
flushes it, then commits it only after revalidation.

An internal recovery record is retained after a post-setup interruption. Its
inspection helper never silently finishes the save: it only reports whether a
record describes a confirmed destination, a recoverable temporary object, a
different card, an invalid record, or an unresolved state.

## Ownership boundary

Only the future External Storage provider may construct `NotepadStore`. An
application must use a capability-checked broker request for the named logical
collection; it must never receive the storage mount path, a directory handle, or
general card-write authority.

## Evidence

`test_notepad_store.py` covers normalization, explicit replacement, stale-card
refusal, changed-destination refusal, recovery retention, recovery inspection,
and the accepted bounds. These tests run in Linux alongside the existing
read-only storage tests.

## Still required before Notepad can save external documents

1. Integrate the core into the External Storage service's writable lifecycle:
   safe mount policy, card identity/insertion generation, writer serialization,
   safe eject, and real recovery handling.
2. Add a versioned Envelope interface and broker grants with separated `list`,
   `open`, `create`, `commit`, and `replace` operations for
   `documents.notepad`.
3. Pass opened documents only as authorized regular-file handles; do not expose
   the mount path.
4. Validate target exFAT replacement, directory flush, interruption and removal
   behavior on the RG35XX H before claiming transaction durability.
