# GuideOS system audit — 24 September 2026

Status: analysis completed 24 September 2026 after more than 30 minutes.
Started 14:08:41 UTC; the completion record below states the final review boundary.

## Findings that determine the next step

1. The seed contains the restored previous Debian shell software. Restoration was
   readback-verified on 23 September. The fresh capture adds a sixth saved shell
   run, recording navigation and a confirmed shutdown request without cleanup
   errors. No candidate has been installed during this audit. Visual quality and
   independent Power behavior still need physical acceptance.
2. The reported Wi-Fi build failure remains unresolved. Its captured root was
   byte-for-byte identical to the installed image and had mount count zero. Its
   bootloader region, kernel, board description and boot configuration match the
   preceding shell image. No new shell report or retained system journal locates
   the failure. This supports investigating startup before a successful writable
   root mount; it does not identify a defective component.
3. The same failed kernel/root combination boots on a full ARM virtual machine.
   NetworkManager starts, the actual discovery adapter correctly reports that the
   virtual machine has no Wi-Fi adapter, and orderly shutdown completes. This
   passes at 1,024 MB and 512 MB. It does not test H700 DDR initialization, the
   physical SD interface, the LCD, controls, battery, or wireless hardware.
4. A separate shell robustness bug was reproduced and corrected in source:
   inability to create either report directory prevented shell startup. Reporting
   now tolerates a failed destination, retries on later saves, and exposes the
   number of successful destinations. This is not established as the recent boot
   failure's cause. The fix is not installed on the seed.
5. The main architectural deficit remains integration. Tested policy, transfer,
   host-control and desktop components exist; a complete application Supervisor,
   live capability registry and shared Media Controller are not deployed on Debian.
6. A discovery output-handling issue was reproduced separately: the parent waits
   for child exit before reading its output, so a response larger than the pipe
   can block the child and be reported as a timeout. This remains a source issue
   for the next discovery revision, not an explanation of an early boot failure.

## What has evidence behind it

| Component | Evidence | Boundary still open |
| --- | --- | --- |
| Debian shell baseline | Six saved boot IDs record display-call completion, input navigation and shell-requested shutdown; the sixth was discovered in today's fresh capture. | Visual correctness, independent hardware Power under failure and service handoff still need physical confirmation. |
| Kernel and filesystem integration | Preserved failed image mounts root/boot/data and reaches systemd targets under full ARM system emulation. | RG35XX H startup and peripherals; a virtual board is not an H700 emulator. |
| Wi-Fi discovery source | Five adapter tests pass; full ARM guest returns the correct no-adapter response through live NetworkManager/D-Bus. | Actual wireless scans and appearance of the owner's network; association is outside this slice. |
| Shell reporting robustness | All 12 shell tests pass in WSL and Debian ARM64 userspace, including one/both report destinations failing, later recovery and a confirmed power request surviving report failure. | Display/input and shutdown dependencies are substituted in the fault test; this does not prove physical shutdown. |
| Resource decisions | Fifteen C test groups, including 2,224 allocation cases and deadline/checkpoint/priority edge cases, pass. | Measured device budgets, equal-tier scheduling, fluctuating capacity and production host integration. |
| Transfer provider | Five real HTTP tests, a recorded-session test and a combined real systemd/provider test pass. | Actual video decoding/playback, wireless interruption, measured link bottleneck and unrelated network traffic. |
| systemd host adapter | Four tests use real disposable user units and verify containment, controls and release. | Durable Supervisor restart recovery, privilege boundary and installation on the Deck. MemoryHigh is pressure control, not a hard memory guarantee. |
| Desktop Node | Full Windows suite passes 45 tests, including AT Field, media library, application-provider and Engine paths. | Physical Deck interoperability and actual remote capture/playback are not established by these tests. |
| Application ports and cartridges | Source, design and earlier prototype evidence exist. | Their presence in the repository does not establish Debian runtime integration. |

Saved baseline boot IDs are `c5bbe2dc-206c-4785-9541-1543ccfe650c`,
`ecb334ff-dfb1-4606-8478-ba3a6a497d53`,
`69f121eb-1b86-48b5-bbcc-966e1d7e6d37`,
`0e0ec119-347e-4ba3-8171-1b7c58861ac9`, and
`7d60cdc8-8ae6-47c2-bdc8-96d3c010da65`. These are earlier shell runs, not proof
that the failed Wi-Fi revision booted. Their final reports show no cleanup errors;
they record a shutdown request, not a measurement of electrical power-off.

Today's capture adds `c58f9c06-f7cd-4bba-9d76-532945bb86e8`, absent from the
failed-build capture. The restored root mount count increased from five to six.
This run starts the shell at about 10 seconds, records both ordinary input
devices, visits Media Foundation and System Status, and ends after 15.37 seconds
of shell operation with confirmed shutdown and no cleanup errors. The image's
old clock prevents trustworthy wall-clock dating of that run.

Both saved report copies are byte-identical for all six runs. Across 122 matched
action/view event pairs, each run's median is about 29–31 ms; the largest pair is
41.2 ms. These timestamps exclude input waiting before it is read, physical
screen scanout, and report synchronization after the view event. They are useful
baseline instrumentation, not a measurement of end-to-end input latency.

## Fresh seed examination

A read-only sequential scan read all 62,239,277,056 bytes through the USB reader
without an error, in 989.18 seconds (58 chunks). This tests present readability
through this reader; it does not test writable capacity, retention, the Deck's
card interface or its power supply. The current used region was preserved
separately before inspection. No seed writes were made during the audit.

Raw root, boot and data hashes now differ from the earlier snapshots. New boot
records and filesystem state explain why byte identity cannot be assumed after
use. The bootloader and partition-table region is unchanged; the current root
passes read-only filesystem checks, as does the data partition. A dedicated FAT
consistency check was not run because that checker was unavailable; selected
boot files were read and compared. All files under `/usr`, the configuration
tree and package inventory match the restored backup. The kernel, selected board
description and boot configuration also match the preceding capture. Detailed comparison
results are saved in `build/system-audit-20260924/`.

Recovery identities (SHA-256):

- Previous root backup, verified at restoration:
  `5F258056BDA054AED7B97B89EBCE10ABED4F5E605B470F83D1DBC1E6FF245997`.
- Today's used-region capture:
  `CA3CAD7FCF78FBC0F91A2E25D5355301F77D9B41AEEA495E7D3818DAFDC98F0F`.
- Today's root partition after the additional run:
  `1B71B8D90EA1896981AF7D6027CB86E5DFD3EB97167C0095716BEAB9CFCA00C8`.

Do not use today's changed root hash as evidence that the earlier restoration
failed. The failed Wi-Fi candidate and the restored baseline are separate images.

## Recent failure: supported and unsupported explanations

| Candidate explanation | Evidence assessment |
| --- | --- |
| Incorrect or incomplete root write | Weakened: failed-card root exactly matched the candidate hash; read-only filesystem checks found it consistent. |
| Bootloader, partition-table, kernel or selected DTB accidentally replaced | Weakened: bootloader region, partition identity, kernel, selected DTB and configuration match the preceding image. |
| Root filesystem features unsupported by this kernel | Weakened: old/new feature sets match and the exact kernel mounts the failed filesystem in a full guest. |
| NetworkManager fundamentally cannot run on this ARM image | Weakened: full-system ARM boots run it successfully. The earlier user-mode QEMU abort is not reproduced there. Its exact emulator/platform cause is not established. |
| Shell/Wi-Fi logic crashed after normal startup | Not demonstrated: no new shell run or writable-root mount evidence from the failed card. A separate reporting-startup defect exists, but cannot be assigned as the cause. |
| Power, physical card contact, bootloader/media timing, board-specific early startup or display path | Still open. The USB read path and a virtual machine do not exercise these paths. No sufficiently specific operator observation or early serial capture exists. |

Do not identify one of the open possibilities as the cause without new evidence.
If the restored baseline also fails, adding Wi-Fi code cannot resolve that result.
If the baseline boots consistently and the candidate fails consistently, use
incremental changes and boot-stage evidence to isolate the difference.

The 512 MB guest also completed startup, discovery and shutdown with its clock
set to January 1970, reproducing the approximate age of timestamps seen in the
earlier root. Those old timestamps alone are therefore insufficient to explain
the reported failure. The virtual harness directly loads the kernel and bypasses
the physical bootloader; its success does not validate that stage.

An additional allocator audit exercised 1,000,000 deterministic wide-integer
plans under AddressSanitizer and UndefinedBehaviorSanitizer: 752,420 admitted
plans and 247,580 shortfalls. Conservation, admitted floors and ceilings, critical
allocation, and zero allocation on shortfall passed without instrumentation
findings. This supplements the existing tests; it does not establish real-time
scheduling performance or measured device capacity.

## Logging and release-validation gaps

The image explicitly sets journald to volatile storage with an 8 MB runtime
limit. Shell reports survive on data/boot, but only after shell startup. This
leaves a gap between kernel startup and a functioning shell. Persistence cannot
recover logs from code that never runs or from a root that never mounts.

For the next bring-up revision, prepare a small bounded persistent journal and
stage markers identifying root mounted, services started and shell ready.
Retain serial output; if failure precedes writable storage, a physical early-log
route or a visible boot-stage observation may be necessary. These are proposed
next-build changes, not installed settings.

Source reports now include the shell source SHA-256 and kernel release. Previously
the same report-version label covered different builds, making old reports easy
to misattribute. A complete release manifest should also bind boot files, root
image, package versions, board variant, source state and known acceptance gaps.

Image consistency, source tests and byte readback establish different facts.
They do not replace a physical boot. The newly added virtual-boot harness tests
kernel/userspace integration; physical display/input acceptance remains separate.

The dense-response probe produced a valid 64-network, 14,142-byte JSON result
through a deliberately reduced 4,096-byte pipe. The shell reported timeout
because it did not drain the pipe while the child was running. The test uses a
shortened deadline and does not establish the Deck's actual pipe capacity or
scan density. The repair should drain output asynchronously with a bounded
buffer while preserving responsive cancellation, then test a real child with
output larger than its pipe. This audit records the reproduction; it does not
silently replace the installed discovery implementation.

## Optimization review

Measured staged-image storage is approximately 757 MiB under `/usr` and 198 MiB
under `/var`. Significant contributors are 274 MiB of architecture libraries,
235 MiB of kernel modules, 63 MiB of locale resources, 90 MiB of package lists,
and 96 MiB of package download cache. These are disk measurements, not RAM use.

Priorities:

1. **Release cache cleanup:** package lists and download cache offer roughly
   186 MiB of potential savings without redesigning the OS. Preserve package
   manifests and recovery artifacts; keep build caches outside release images.
   Cleaning lists changes offline package-query convenience and requires a later
   metadata refresh for package work. No files were deleted from the seed.
2. **Reporting writes:** the current shell writes and syncs two report copies on
   each view update. Coalesce noncritical navigation history; immediately commit
   startup, failure, checkpoint and final cleanup outcomes. Measure target-card
   latency before selecting an interval. Do not weaken application save semantics.
3. **Board profiles:** select needed modules and firmware per board after hardware
   validation. Avoid stripping 235 MiB of modules indiscriminately and then losing
   portability or recovery devices. Locale selection is another optional profile
   choice, not a reason to remove multilingual support globally.
4. **Build I/O:** assemble ext4 images on WSL's Linux filesystem, then copy the
   finished artifact to Windows storage. This reduces cross-filesystem metadata
   traffic without changing the device filesystem.
5. **Runtime measurement:** the virtual guest reports about 27 MiB in the
   NetworkManager service cgroup. In the 512 MB guest, roughly 385 MiB was available
   at the probe. These measurements exclude a physical graphics/input stack,
   active Wi-Fi, media playback and apps, so they are not a Pi or Deck RAM budget.

Keep Debian and ext4 for the next controlled comparison. The evidence does not
justify another distribution, filesystem or kernel change as a boot-failure fix.
The card layout uses only a small part of its capacity: 128 MiB boot, 2 GiB root
and 1 GiB data. Expanding data later is useful, but should be a separate backed-up
storage operation after stable boot, not combined with another functional change.

APT timers are enabled, but no active periodic-upgrade configuration or installed
unattended-upgrades package was found in the reviewed package/configuration
inventory. This is not evidence of forced updates. Encode owner-controlled update
defaults explicitly in a future base profile to prevent drift as packages change.

## Architecture and planning

Keep the accepted division: systemd is PID 1; Guide Supervisor coordinates whole
applications and their workers; shared providers own display/input/media/network
functions. A logical responsibility does not require its own daemon.

The installation-time agreement should remain durable and versioned. Each launch
gets a new runtime identity and uses the existing agreement. Complete the restart
reconciliation path before claiming application recovery: the development host
adapter currently stores its instance records only in memory.

Connect availability, authorization and resource ownership with one small real
application/provider path. Priority tiers and cooperative transfer allowances are
already testable components. They are not a system-wide scheduler, a kernel
network shaper or proof of playback continuity. Keep AT Field as communication
policy, separate from joining a Wi-Fi network and resource permission.

Next three tasks, in order:

1. **Complete physical acceptance and failure visibility.** A new baseline boot
   report now exists; confirm the home screen is visually correct and repeat the
   ownership/Power checks. If it fails again, obtain a boot-stage observation
   before changing application code. Prepare bounded
   persistent logs and the source reporting fix for the next controlled revision.
2. **Finish discovery as a bounded hardware capability.** Test scan, rescan,
   cancellation, unavailable-radio behavior and repeat boots. NetworkManager may
   remain the future connection backend, but discovery alone does not require
   turning the entire connection/provisioning proposal into this task's scope.
   No password or automatic connection is needed for discovery acceptance.
3. **Integrate the first application lifecycle and transfer path.** Persist the
   installed agreement, attach workers/providers, observe actual containment and
   release, and test a saved-state recovery. Then add connection setup, measured
   LAN transfer and the video/download scenario with a real decoder. A headless
   Pi profile follows the same contract; virtual 512 MB boot is only preliminary
   userspace evidence.

For the next boot investigation, use a controlled sequence: the restored baseline;
then the reporting fix plus bounded boot evidence; then NetworkManager packages
with the original home screen; then the discovery page. Preserve and identify
each image and obtain a physical result before advancing. This is a proposed
isolation sequence, not four new builds installed during this audit. Keep the
kernel, bootloader, partition layout and normal controls constant for comparison.

Additional review targets are partial input/framebuffer initialization cleanup,
unusual framebuffer stride/channel layouts, and recovery after a provider exits
unexpectedly. Constructors can acquire resources before their caller receives
the object; these paths need explicit failure tests before live restart recovery
is claimed. They are source-review risks, not observed causes of this boot failure.

Future product decisions can wait until these foundations pass: how much storage
to retain for diagnostics; the simplest connection-setup interaction; and which
small application should first exercise the complete install/launch/save/recover
contract. None is needed to inspect the present seed or finish this audit.

## Changes and evidence locations

- Source-only reporting fault tolerance and source/kernel identification:
  `board/rg35xxh/debian/shell0/guide_shell.py` and `test_guide_shell.py`.
- Existing and added audit harnesses: `build/run-system-audit-tests.sh`,
  `build/prepare-audit-guest.sh`, `build/run-audit-guest.sh`, and
  `build/audit-seed-readability.ps1`.
- Test logs: `build/system-audit-20260924/`.
- Previous restoration record: `build/debian-network-0/seed-restore-previous.txt`.
- Failed capture and recovery images remain in private recovery storage outside
  the public source tree. No credentials were required or added during the audit.
- QEMU full-system tools were installed in WSL for isolated validation. Test guests
  use discarded writes and no network adapter. Host network settings were not changed.

## Completion record

The analysis ran from 14:08:41 UTC through at least 14:38:45 UTC on
24 September 2026: more than 30 minutes. The full sequential card read,
fresh-capture inspection, regression and fault probes, source correction,
architecture review and optimization plan are complete. Desktop export and
artifact verification follow this analysis boundary.

No seed writes were made during this audit. Temporary image mounts and test
guests were released. The restored baseline remains on the seed. The recent
Wi-Fi candidate's physical failure remains unresolved; the reproduced dense
scan output issue remains an explicit next-revision item. The reporting fix
is tested source only. Physical acceptance is the next owner-assisted step.
