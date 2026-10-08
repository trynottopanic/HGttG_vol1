# Cartridge Installer 0

Status: implemented, host-verified and ARM64 image-validated, 26 September 2026.
Written to Seed after fresh capture/rebase and full readback verification on
26 September 2026. Physical Deck boot acceptance remains pending.
The owner accepted the complete step 2 recommendation report and authorized this
build. This document distinguishes host, image and physical evidence.

## Ownership and installation path

The existing External Storage service remains the only card mount owner. Its
cartridge catalog examines at most 512 directory entries and 128 indexes, keeps
at most 128 KiB of index data and returns pages of 16 entries. Each selection is
bound to a provider epoch, insertion generation, card identity and index state.
The installer receives a read-only regular archive descriptor, never a card
mount path. Card insertion does not execute, install or launch anything.

The shell provides External Card → Cartridges and Home → Applications. Inspection
runs outside the display/input loop. The agreement states unsigned status,
requested permissions, optional denials, internal/private storage, memory and
update history. It has no reading deadline. Home does not cancel a transaction;
Installation status provides an explicit cancellation action until commit.
Opening an installed application is a separate owner action.

`guide-installer.service` is a socket-activated root publisher. It retains
NoNewPrivileges, a read-only system view and narrowly writable installation
locations. `guide-cartridge-parser.service` starts as the dedicated unprivileged
`guide-archive` account and receives one archive descriptor. Its CPU, memory,
process, descriptor and elapsed-time limits are enforced by systemd, rlimits and
seccomp. It cannot launch processes, create network connections or change its
credentials. Cartridge source is parsed for syntax and never imported there.

The parser is a separate process per owner request, not an automatic restart
loop. The publisher accepts fixed typed operations; packages cannot supply shell
commands, root destinations or post-install hooks.

## Profile and authority

`application-profile-v0.json` documents the bounded Python profile.
`guide_cartridge.py` is the shared verifier used by the Windows builder/verifier,
card-copy verification and the Deck parser. Legacy data cartridges retain their
existing tools; the shell labels their unsupported install actions explicitly.
The runtime currently supports one Python module, RGB/RGBA non-interlaced 64×64
PNG icons, and private storage, visual, action-input and text-input capabilities.
External Notepad document writes remain separate work.

The archive limit is 1 MiB, total expanded limit 2 MiB, file count 64, metadata
32 KiB, path length 128 UTF-8 bytes, depth eight and icon size 32 KiB. Actual ZIP
streams and PNG pixels are bounded. Duplicate JSON keys, ambiguous/traversing
paths, links, special files, unlisted/missing content, encryption, ZIP64,
multipart archives and unsupported compression are rejected. No extract-all is
used on an application cartridge.

The first runtime profile has a fixed 48 MiB memory-high/64 MiB memory-max and
128 KiB temporary footprint. A cartridge cannot request a smaller footprint and
silently receive the larger one. Private storage is bounded at 512 KiB. The
application worker retains the existing seccomp allow-list and mediated SDK.

Application identity is an ID plus semantic version and whole-archive hash.
Inventory and source hashes remain separate. The installation record also binds
the runtime, schema, footprint, permission agreement and activation generation.
Numeric aliases are allocated locally, collision-checked and retained with an
uninstalled application's saved data. The initial registry supports 128 IDs.

The authoritative record is
`/var/lib/guideos/applications/<id>/installation.json`. The numeric policy file is
a generated projection: both the C Supervisor and Python host reject a mismatch.
The canonical policy is the first JSON scalar so the C loader can compare its
complete escaped value without a second general-purpose JSON parser. A binding
hash covers the full package and agreement, not just executable source.

Immutable program releases live at
`/opt/guideos/applications/<id>/releases/<version>/`. Private storage uses the
logical `.../applications/<id>/private/` path; systemd manages its protected
DynamicUser backing directory. Recovery metadata is separate. Health instances
use a temporary runtime store and expose no foreground socket or owner documents.
Normal launches are denied during preparation/testing. Broker identities are
reclaimed after observed terminal state, including across different package IDs.

## Transactions and recovery

One transaction runs at a time. The service writes a durable internal archive,
re-verifies/extracts it unprivileged, checks the inventory again as publisher,
records activation intent, checkpoints/stops the old instance, publishes the
candidate and performs the isolated ready/checkpoint health test. Only a passing
candidate becomes normally launchable. Failure restores the prior activation.

Publication uses an owned temporary sibling in the destination release directory
and an atomic rename there. This is required because systemd bind mounts can
prevent a rename from the installer staging directory even when the device
numbers match. The verified archive is removed before this copy; source files
are retired after their destination copy is flushed. Actual combined staging
bytes are checked against 4 MiB. Capacity checks include duplication, metadata,
block rounding and a board-specific free-space reserve recorded in the image's
budget evidence.

File and directory flushes accompany publication and records. Journal intent
precedes activation changes. Recovery runs before the shell's installed catalog
and again on installer startup. Uncommitted candidates are rolled back without
launching an ordinary application. Malformed journals remain quarantined and
block subsequent installer starts until reviewed; cleanup does not guess paths.
The service retains 16 bounded completed transaction receipts. UI mutation
requests also carry the reviewed activation generation, preventing an old
confirmation from removing a newer installation.

Same version/same hash is already installed; same version/different content is
rejected. Downgrade requires an explicit decision. Data-schema migration is not
supported. Optional denials carry forward. At most two program releases are kept.
Uninstall preserves private data. Deleting retained private data is a separately
confirmed operation and never touches the external card or external documents.

The `.guide.sha256` file is build evidence. The runtime index's archive SHA-256
is sufficient; a present sidecar must agree. Format 1 remains unsigned.

## Evidence and remaining physical gate

The maintained reference source is `apps/runtime_reference/cartridge/`.
The build produces working 1.0.0 and 1.1.0 cartridges plus deliberately unhealthy
1.2.0 for rollback testing. They are not Notepad releases.

Evidence is collected under `build/cartridge-installer-0/`. The live fixture uses
real systemd units, Supervisor, grants, parser and publisher, with a synthetic
read-only card catalog. It covers install, card removal, launch/checkpoint,
update, unhealthy-candidate rollback, retained-release rollback, uninstall,
reinstall, private-data preservation and separate deletion. A separate live test
runs 36 distinct application identities to exceed the broker's cache size.
Failure tests inject abrupt interruption at journal/activation boundaries and
individual flush failures. ARM64 emulation verifies the candidate interpreter,
imports, profile and transaction logic; it does not establish handheld timing.

Physical acceptance still requires cold boot with the external card inserted,
controller navigation/readability, installation/removal/relaunch, reboot recovery,
failed-update rollback and measured handheld resources. A candidate built from
the saved installed baseline requires a fresh seed capture and preservation rebase
before writing. No physical acceptance is inferred from this build.

## Final build evidence

The final candidate is `build/cartridge-installer-0/guide-cartridge-installer-final-root.ext4`.
Its exact digest and acceptance state are in `candidate.json`; the complete
check summary is in `validation.json`. The earlier candidate is superseded.

- Host regression suites: 303 tests run, 302 pass and one existing skip.
- Foundation runtime: nine additional tests pass, plus C core, sanitizer, codec
  and systemd adapter checks.
- Actual installed ARM64 modules: 27 tests pass. The same 19 cartridge corpus
  cases produce the expected results on Windows and ARM64.
- Real systemd installation, update, rollback, removal/reinstall, isolated health
  and private-data preservation/deletion checks pass.
- Recovery tests cover 12 abrupt interruption points and 42 individual flush failures.
- Filesystem check passes; baseline inventory audit reports no removed files.

See the build [report](../build/cartridge-installer-0/BUILD_REPORT.md) for the exact
candidate and remaining physical gate.

## Seed installation — 26 September 2026

The owner explicitly authorized the root-partition write. The returned Seed was
captured, the validated payload rebased onto that capture, and 23,538 existing
files/links preserved. Full root readback matched
`03DE1FE186664F3A3B3B5C2E0CBDC46E1C873B66B7F21D27B2416763740F8262`.
Boot and data partition hashes remained unchanged. Evidence is in
`build/cartridge-installer-0/install/installation.json` and `seed-install.txt`.
Physical boot and cartridge-flow acceptance remain pending.

## Owner boot feedback and navigation correction

The owner reports that Seed booted successfully and the changes were confirmed.
Home grid navigation and power confirmation selection were reported defective.
Those are corrected in source and staged in `build/dpad-navigation-0/`, with four
actual Field geometry/button-routing regression tests; the correction is not yet
installed. This report establishes successful boot and observed changes, not a
separately completed cartridge installation/update/recovery acceptance sequence.
