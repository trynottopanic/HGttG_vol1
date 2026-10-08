# GuideOS External Storage 0

Status: initial structure and service direction accepted 25 September 2026.

External Storage 0 defines the first shared storage boundary for removable
memory used by the handheld Deck. The first physical target is a 256 GB microSD
card using exFAT. The service is intended to mount the card once, make its
contents quickly available to multiple applications, enforce access outside
those applications, and remain outside the bulk data path after granting an
open file handle.

This document records accepted structure and boundaries. Unspecified
subdirectories, application mappings, write capabilities, indexing schema and
user-interface details remain unresolved rather than being inferred here.

## Accepted top-level structure

The card has one canonical content root named `GUIDE`. Its accepted immediate
subdirectories are exactly:

```text
GUIDE/
|-- CARTRIDGES/
|-- APPLICATIONS/
|   |-- GAMES/
|   `-- BIOS/
|-- MEDIA/
|-- DOCUMENTS/
|-- GENERAL/
`-- MISC/
```

The names are uppercase canonical names. The storage service may recognize
case-insensitive equivalents when required by exFAT, but it must not create or
present case-only duplicates.

The first adopted lower-level assignments are `APPLICATIONS/GAMES/` for game
content and `APPLICATIONS/BIOS/` for owner-supplied application firmware. Other
lower-level structure remains unresolved. In particular, this revision does
not decide where music, video, images, books, projects, imports or exports
belong beneath their accepted roots.

## Root meanings

- `CARTRIDGES/` contains inspectable Guide cartridge packages and their bounded
  companion metadata.
- `APPLICATIONS/` contains external material used by applications, including
  game content under `GAMES/` and owner-supplied firmware under `BIOS/`. Its
  presence does not authorize executable content or permit applications to run
  from the card.
- `MEDIA/` contains media intended for suitable Guide media applications.
- `DOCUMENTS/` contains documents intended for reading, editing or reference.
- `GENERAL/` contains ordinary owner-managed data that has a known general use
  but does not belong to a more specific accepted root.
- `MISC/` is the owner's miscellaneous holding area. Its contents receive no
  implied type, trust or execution authority.

Directory placement is organizational metadata, not permission. A file under
`APPLICATIONS/` is not thereby executable, and a file under `CARTRIDGES/` is not
thereby verified or trusted.

## Service direction

One external-storage service owns detection, filesystem mounting, card
identity, indexing, access grants, coordinated writes, removal and safe eject.
Applications do not mount the card and do not receive its physical mount path.

For ordinary reads, the service checks the requested logical collection and
the application's grant, opens the contained regular file, and passes the open
file handle to the application. The application then reads directly through
the kernel. Media and emulation data do not pass through the service process.

The intended performance rule is:

> Mount once, index once, authorize once per open, then leave the data path.

Insertion, indexing and reconciliation must not require a complete scan before
previously indexed content becomes usable. Foreground interactive reads and
continuous playback take precedence over indexing, hashing, thumbnail work and
bulk transfers.

## Initial access boundary

The first implementation remains read-only and uses the equivalent of:

```text
ro,nodev,nosuid,noexec
```

Later mediated writes require explicit capabilities and a system-owned storage
transaction. Individual applications must not acquire unrestricted access to a
writable card mount. Reads must not update access times or create application
metadata beside owner content.

Application state, save data, permissions, search indexes, resume positions,
thumbnails and temporary work remain on trusted internal storage unless the
owner explicitly exports or backs them up.

## Prototype compatibility migration

The current emulation prototype directly scans `GUIDE/GAMES/` and
`GUIDE/BIOS/`. Those are earlier prototype paths and are not part of the
accepted External Storage 0 top level. Their adopted replacements are:

```text
GUIDE/APPLICATIONS/GAMES/
GUIDE/APPLICATIONS/BIOS/
```

The implementation must migrate to those locations through the shared storage
service before the old paths are removed.

The existing `GUIDE/CARTRIDGES/` convention already matches this structure.

## Unresolved work

- Define the substructure and content semantics beneath each accepted root.
- Define the lower-level system organization beneath `APPLICATIONS/GAMES/` and
  `APPLICATIONS/BIOS/`.
- Specify the distinction between a cartridge and application-related material.
- Define the card identity record without adding another top-level directory.
- Define logical collection names and application capabilities.
- Define the internal cached index and insertion-generation model.
- Define controlled writing, export, recovery and safe-eject behavior.
- Add native exFAT and UTF-8 support to the running kernel and card service.
- Consolidate existing cartridge, media and emulation mount logic under the
  external-storage service.
- Physically validate a full-size 256 GB exFAT partition, Unicode names, files
  larger than 4 GB, concurrent readers, removal and reinsertion.
