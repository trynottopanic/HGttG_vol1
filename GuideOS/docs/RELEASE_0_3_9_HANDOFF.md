# GuideOS 0.3.9 continuation handoff

Latest kernel: the TF2 initial-clock and resume-error correction is installed
and fully readback-verified. Root/data and bootloader are unchanged from the
latest returned capture. Physical cold-boot/reinsertion tests remain pending.
See [TF2_DRIVER_CANDIDATE_0_3_9.md](TF2_DRIVER_CANDIDATE_0_3_9.md).

Latest correction: physical 0.3.9 boot exposed a storage import-order failure.
See [RELEASE_0_3_9_STORAGE_STARTUP_RESULT.md](RELEASE_0_3_9_STORAGE_STARTUP_RESULT.md)
for the reproduced cause, two-file repair, fresh returned Seed, and evidence.
The correction is installed and fully readback-verified; boot/data are unchanged
from the latest returned capture. Physical storage startup is confirmed, and the
owner confirms card recognition and both Music and Video playback after one
reinsertion. Cold-boot
TF2 detection remains unreliable; do not report the controller fault as fixed.

Previous installation: **0.3.9 native Music/Video is installed on the Seed and fully readback
verified.** Boot/data hashes are unchanged; owner data and Notepad are preserved.
This image booted physically but its storage service failed. Start with
[RELEASE_0_3_9_MEDIA_RESULT.md](RELEASE_0_3_9_MEDIA_RESULT.md), whose top section
supersedes the historical candidate and installed-version statements below.
Root SHA256: `15278568DD3370D5EFFB8ECAF3F579B64978C35E97D27AF4182038807B1C28FB`.

## Continuation result, 27 September 2026

Read [RELEASE_0_3_9_STARTUP_RESULT.md](RELEASE_0_3_9_STARTUP_RESULT.md) before
following the original next-work list below. Cold-provider ordering, queued
health-job observation, failed-reinstall cleanup and uninstalled-record UI are
corrected and host-tested. The 0.3.9 root candidate is image-validated from the
exact successful Notepad capture, with owner-state preservation verified.
Root SHA256: `b8ffbd82a5a5e1ae19facc9f84f1f5951661bd1e3e966ed54ddaeb1796021044`.
Candidate: `build/release-0.3.9-startup/image/guide-0.3.9-root.ext4`.
**Not written; physical Seed remains 0.3.7.** TF2 diagnosis and physical acceptance
remain open; see [TF2_REINSERTION_INVESTIGATION_0_3_9.md](TF2_REINSERTION_INVESTIGATION_0_3_9.md).
The original handoff below remains historical context, including its pre-build
status statements. Do not repeat the corrected source work as still unimplemented.


Prepared 27 September 2026. This is the entry point for the next build conversation.
Read this before older release handoffs: many older documents describe superseded
candidates as pending or uninstalled.

## Version and deployment state

- Next development release: **0.3.9**, explicitly chosen by the owner. `VERSION`
  and the shell System Info label now say 0.3.9. No 0.3.8 release is implied.
- Installed and physically tested Seed: **0.3.7**, last written 26 September at
  23:21 EDT. No 0.3.9 image has been built or written by this handoff operation.
- Notepad remains **0.1.0-preview.1**; its application version is independent.
- Current workspace: `E:\DGttG\HGttG_vol1\GuideOS`. Windows PowerShell plus WSL
  Ubuntu. WSL path: `/mnt/e/DGttG/HGttG_vol1/GuideOS`.
- Read the [development guide](../../docs/DEVELOPMENT.md). The shared checkout contains substantial uncommitted and
  untracked work from multiple conversations. Do not reset, clean, replace or
  broadly commit it. No new branch/worktree or new chat was created for this handoff.

## Current physical evidence

The owner confirmed successful boot, cartridge installation and the first-note
test. Returned logs independently show a committed Notepad release, a successful
isolated health check, a normal application run and exit 0 with durable checkpoint.
Peak application memory on that run was 14 MiB.

The current captured private store has a checkpoint, but no named draft-index or
draft-N objects. Do not infer a separate named-save/reopen test from the first-note
report. No note contents were copied into the reports. Cartridge removal after
installation is proven by live host integration tests; physical cartridge removal
while using installed Notepad has not been separately reported as accepted.

The previous failed installation left an **uninstalled metadata record**, no
program release and no private objects. It was shown in Applications, misleadingly,
but had no Open action. The owner did not test launching it. They deleted retained
personal data and retried. That sequence does not prove deletion was necessary:
the install health check uses an isolated temporary store.

Primary evidence: `docs/NOTEPAD_PHYSICAL_RESULT_0.md`,
`build/notepad-physical-success-0/physical-result.json`, `before-records.json`,
`after-records.json`, `latest-services.log` and `latest-kernel.log`.

## Exact current recovery base

Most recent returned Seed capture (after successful Notepad installation):
`E:\DGttG\private-recovery\notepad-physical-success-return-20260926-233046\seed-used-region.img`

Capture SHA256:
`D35855FB5D1F20079D29E2A86FFA74EAE09383C59A51A49A9B526CF37D2FF5E4`.
Bytes: 3,490,709,504. Metadata: `build/notepad-physical-success-0/capture-return.json`.
This capture contains installed Notepad and current owner state. **Do not rebase
onto the earlier failed-installation capture or an old candidate image.** The Seed
was last reported inserted in the PC; verify its presence and identity again.

Last written root hash (before the subsequent physical test changed runtime state):
`2211786B2D3E11A7A6C65B97D2E50826D366B9A18C3440D9840EE7ADD7546A0A`.
Write record: `build/card-install-followup-0/install/installation.json`.
That write changed exactly two files and preserved 24,551 others; root readback
passed and boot/data regions were unchanged. The last-written root hash is not
the hash of the root after the owner booted it.

The active immutable shell release in the returned 0.3.7 lineage is
`21894f4a9310ff577eb7ebe8ca5cde69f9e5f058487122a3513936d4c7842fab`.
Read the actual captured active record when packing the next release. Merely
copying shell source can be overridden by immutable activation; refresh the
release payload and active metadata consistently and set its version to 0.3.9.

## Next work, in order

### 1. Reproduce and correct cold-provider application startup

The first installation on the latest boot still failed once, although the later
attempt succeeded. Logs show first health unit start at 50.994 s, capability
broker activation at 51.706 s, application host exit 72/checkpoint none at 51.898 s
as the broker starts, then installer ValueError. The next health check succeeds
at 80.365 s with the broker already running.

The host Broker.call timeout is 200 ms. This is strong evidence of a cold-service
startup race, but the typed exit does not expose the exact exception. Reproduce
with the broker stopped and deliberately delayed startup. Likely correction:
ensure required providers are started/ordered before the bounded application
health check. Keep deadlines bounded, respect systemd ownership and avoid deadlock
with Supervisor peer-identity resolution. Do not weaken capability checks or
require private-data deletion. Cover first installation, retry without deletion,
ordinary launch, failure rollback and retained work.

Relevant source:
- `package/guide-foundation/python/guide_application_runtime.py`: Broker.call,
  request, worker/host startup, isolated health store.
- `package/guide-foundation/src/guide_systemd_adapter.c`: transient application
  unit properties and provider ordering.
- `package/guide-foundation/systemd/guide-capability-broker0.service` and sockets.
- `package/guide-installer/guide_installer.py`: install/restore/health_check.

### 2. Clarify uninstalled records in Applications

The catalog intentionally retains identity/agreement metadata for reinstall.
The suffix `/ removed` or `/ data retained` is easy to miss. Make “Not installed”
prominent, distinguish metadata-only records from actual retained owner data,
and do not offer unnecessary deletion when there is no private store. Preserve
stable identity, permissions and drafts. Only committed programs may offer Open.
Check the reinstall agreement too: an uninstalled record should not misleadingly
present itself as a currently installed update.

Relevant source: `package/guide-installer/guide_installer.py` catalog/restore,
`guide_install_service.py` preview, and
`board/rg35xxh/debian/shell0/guide_installer_panel.py`.

### 3. Correct external-slot reinsertion at the board/controller level

Physical sequence: absent at boot correctly reported; first insertion recognized;
removal followed by second insertion not recognized; reboot with card inserted works.
Captured kernel log: card enumerates at 53.532 s, removed at 76.924 s, then repeated
`sunxi-mmc 4022000.mmc: fatal err update clk timeout` from 139.156–143.720 s.
No successful second enumeration follows. This is below the shell mount layer.

Exact driver cause remains unresolved. Runtime power/clock restoration is a
candidate, not a demonstrated diagnosis. Do not indiscriminately reset MMC hosts:
TF2 is controller `4022000.mmc`; Seed is `4020000.mmc`, Wi-Fi is `4021000.mmc`.
Local kernel source:
`/home/hacker/guideos-work/debian-h700-kernel/linux-7.2.7/drivers/mmc/host/sunxi-mmc.c`.
It has runtime autosuspend and clock restoration paths. No driver correction or
power-policy workaround has been staged. Physical repeated-cycle acceptance is
required after an evidence-based correction.

Logs: `build/card-install-followup-0/kernel-previous.log`.
Design: `EXTERNAL_STORAGE_0.md`; single storage service remains the mount owner.

## Fixes already installed — do not redo or misdiagnose

- Supervisor sd-bus authentication now finishes at connection time using
  sd_bus_get_unique_name. Previously it waited idle with an unfinished handshake;
  D-Bus closed it at 30 s and install launch failed ENOTCONN. Fixed and confirmed
  absent from the latest physical failure. Source is in guide_systemd_adapter.c.
- Storage cleanup uses `/proc/self/mountinfo`, not stat-based ismount on a departed
  card. This fixes stale-mount cleanup, but **does not fix the controller timeout**.
- Application text is captured before Home/checkpoint; Done immediately followed
  by Home is preserved; cancelling changed keyboard text requires confirmation.
- Shared host preloads JSON/Unicode support before sandboxing Notepad.

## Included UI, Notepad and media baseline

UI: readable Field typography; dynamic globe/word captions/star changes from the
existing lineage; spatial Home D-pad and power-confirm selection; faster pointer
engagement/smoothing and changed-region framebuffer writes; single three-state
Wi-Fi bars icon; L2/R2 ten-icon Home pages with 200 ms horizontal slide. One page
remains stationary. Do not newly claim all these have physical acceptance.

Notepad: internal-only draft preview, shared keyboard, New/Edit/Read/Save/Save As,
explicit replacement/discard, recovery checkpoints, bounded Unicode/name/storage
limits. External document open/export and full document viewport remain unfinished.
Cartridge: `build/notepad-0/Notepad-cartridge.zip`, layout `GUIDE/CARTRIDGES/`.
Package SHA256: `51e9a2a2c094b3708ee5239964f4c5fad431c06f11b73ab1a4a3068bf637f672`.
A recovery copy is also in `/usr/share/guideos/cartridges/` on the image.

Future Planning supplied `docs/MEDIA_ENGINE_SOURCE_HANDOFF_0.md`. Its source-stage
stop was superseded by the owner's later image/write authorization. Restricted
provider validation socket, storage-owned media catalog lifecycle, GStreamer
buffering and pinned ARM64 mpv 0.40.0-3+deb13u1 are integrated. No finished video
player UI, deployed Media Session daemon/public library endpoint or full cartridge
media SDK exists yet. Controlled engine fixtures used null outputs; they do not
prove physical DRM, audio/video sync or playback acceptance. Coordinate from the
current handoff if that other chat supplies newer work; do not assume it did.

## Validation and build notes

- 29 storage tests passed after cleanup correction.
- Foundation C/sanitizer/codec/systemd tests and 9 runtime tests passed; ARM64 built.
- `build/run-notepad-idle-followup.sh` passes actual systemd installation after
  35 s idle, cartridge-absent save/relaunch, keyboard recovery and retained data.
  It does not simulate slow cold-broker activation; add that missing case.
- `build/card-install-followup-0/live-delayed-install.log` is NOT a successful full installer log: the
  corresponding older fixture stopped because reference cartridges were absent.
  The dedicated passing log is `build/card-install-followup-0/live-notepad-idle.log`.
- Notepad 11 tests, shared editor 4 tests, media 22 tests, ARM64 GStreamer/mpv
  checks and earlier UI suites are documented in the prior handoffs.
- Use `PYTHONDONTWRITEBYTECODE=1`. Storage tests need PYTHONPATH containing
  package/guide-installer and package/guide-ipc/python; use WSL for Unix behavior.
- `package/guide-foundation/build-arm64.sh OUTPUT` builds ARM64.
  `package/guide-foundation/run-tests.sh` and `package/guide-media/run-tests.sh`
  supply relevant tests. Rebuild missing reference cartridges with
  `tools/cartridge/build_reference.py` when using the full installer fixture.
- Live systemd fixtures alter temporary host units and clean them. Do not run
  them while candidate images are mounted; service namespaces can retain mounts.
- For mounted image work use explicit mkdtemp, finally unmount, then rmdir.
  Never recursively clean a directory which might still contain a mounted image.
- Windows files can expose mode 0777 in WSL; install explicit 0644/0755 permissions.
  Use explicit UTF-8 and `python -X utf8` on Windows. Shell scripts need LF endings.

## Seed write discipline

Current known reader: Disk 4, `TS-RDF5 SD  Transcend`, serial `00000000TS38`,
62,239,277,056 bytes, USB, neither boot nor system. Verify this every time; do not
assume drive number, identity or drive letters remain stable. Do not guess H:.

Partitions (offset, bytes): boot (1,048,576; 134,217,728), root
(135,266,304; 2,147,483,648), data (2,282,749,952; 1,073,741,824).
Capture the latest returned state, rebase exactly, audit all changes and preserve
owner data/credentials/counters/deploy records, validate image, compare current
card regions against the capture immediately before write, write only the intended
regions, flush and reopen for full readback, verify untouched regions. Preserve
Notepad's current installation/checkpoint. Do not rerun old write scripts unchanged:
they name old output folders/hashes and have one-shot installation records.

Useful recent examples: `build/prepare-card-install-followup.py`,
`build/install-card-install-followup-seed.ps1`,
`build/capture-notepad-physical-success.ps1`. These are historical executable
procedures, not automatic authorization to flash the next release. This handoff
request changed the development version and documents only.

## Starting instruction for the next conversation

Read this handoff, the [development guide](../../docs/DEVELOPMENT.md) and NOTEPAD_PHYSICAL_RESULT_0.md. Continue GuideOS
0.3.9 from the latest successful Notepad Seed capture. Start by reproducing and
fixing cold-provider startup and clarifying uninstalled application records;
then investigate the TF2 controller clock failure. Keep installed, staged and
physically accepted states distinct, preserve existing notes, and do not repeat
superseded diagnoses or treat deleting personal data as an installation requirement.
