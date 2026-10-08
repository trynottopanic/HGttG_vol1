# Debian Guide Shell 1 — instrumented baseline

Build identifier: `shell1-20260924`. Status: installed on the seed on 24 September
2026 at 16:30:40 UTC, with complete root readback verified. Boot/data regions
were verified unchanged. Physical acceptance remains pending.

Subsequently superseded by [Wi-Fi discovery 1](WIFI_DISCOVERY_1.md). The owner
explicitly skipped this intermediate physical test and requested proceeding to
the Wi-Fi testing boundary. This release and its recovery copy remain preserved.

This controlled revision applies the reporting fix found in the 24 September
audit and adds retained startup evidence. It serves the existing display/input
ownership and truthful lifecycle-reporting contracts. It is not a new Supervisor
architecture or a return to timed diagnostic exercises.

The home screen contains Media Foundation, System Status and Power Off. Status
shows the build identifier and how many report destinations were saved. One or
both unwritable report destinations must not prevent interface startup or an
already confirmed shutdown request. Build/source/kernel identity accompanies
the reports. Wi-Fi discovery is explicitly disabled in this deployment profile.

The root is cloned from the newly captured seed baseline; kernel, bootloader,
boot configuration, package set, platform adapter and hardware Power policy are
retained. Installation writes only the root partition. Existing boot/data reports
are preserved. The complete used region is backed up before installation.

Persistent system logs use `/var/log/journal`, with a 16 MiB system budget,
4 MiB file limit, 64 MiB free-space reserve and seven-day retention. Journald
limits are rotation targets rather than a byte-exact quota. Normal journal sync
is requested every five seconds; abrupt power loss can still lose recent entries.
Stages mark local storage/journal readiness, shell launch, shell startup, first
frame-call completion, errors and cleanup. They do not prove visible frame quality
or capture failure before the kernel and writable storage can log.
The storage/journal marker is an ordering checkpoint after those startup jobs;
the retained journal and individual unit results establish whether persistence
actually worked. The marker alone is not a write-success acknowledgment.

Validation must include ARM64 shell tests, service ordering, filesystem checks,
an isolated full-system ARM boot, persistent-journal recovery after virtual
shutdown, and complete raw root readback after installation. Physical display,
controls and independent Power remain separate acceptance requirements.

On the Deck: open System Status and confirm `shell1-20260924`; navigate back;
visit Media Foundation; return and use Power Off with its separate confirmation.
After shutdown, reconnect the seed for reports. No Wi-Fi credentials are needed.

Evidence is kept under `build/debian-shell-1/`. The prior audit remains a dated
record; this document records the subsequent installation.

## Validation results

- All 14 shell tests passed in Debian ARM64 userspace, including the baseline
  menu mapping, unavailable report destinations, later reporting recovery and
  confirmed shutdown surviving report failure.
- Service ordering and root filesystem checks passed; the package inventory is
  unchanged from the captured baseline. The virtual guest uses the same kernel
  bytes as the seed.
- Two isolated 512 MB ARM virtual boots reached the validation service and shut
  down. Both boot IDs and both storage-ready markers were recovered from the
  on-disk journal afterward. The virtual board bypasses the hardware bootloader
  and does not validate the RG35XX H display, radio or controls.
- Readable startup markers and report identity are implemented. They report
  software milestones, not physical screen quality or electrical power-off.

Candidate root SHA-256:
`3A8D7D8377A4AB57ED64554DF06C660139D0E55CCB2A26583E4291C2D7728A9B`.

The raw seed root matched that hash after installation. The guarded installer
also verified the prewrite capture, disk identity, all three partition locations,
and unchanged boot/data hashes. See `build/debian-shell-1/installation.json` and
`seed-install.txt`. This is installation evidence, not a claim of physical boot.

Before installation, the fresh capture contained a seventh baseline run,
`7b785d4f-6c69-4d11-b592-ef4aec40361f`, ending with confirmed shutdown and no
cleanup errors. Its evidence is preserved separately from this revision's tests.
