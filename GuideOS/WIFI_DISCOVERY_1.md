# Wi-Fi discovery 1

Build: `wifi1-20260924`. Installed on 24 September 2026 at 16:57:53 UTC with
complete root readback verified. Boot/data regions were verified unchanged.
The owner subsequently reported successful physical testing. Returned logs
confirm nine networks discovered, scrolling, rescan cancellation and orderly
shutdown. See the [physical result](docs/WIFI1_PHYSICAL_RESULT_2026-09-24.md)
for evidence limits and the separate pre-existing Bluetooth warning.

The owner explicitly skipped the intermediate Shell 1 physical test and asked
to continue until Wi-Fi needs testing. This revision builds on Shell 1, retaining
its reporting fault tolerance, persistent journal, ownership and Power policy.
The kernel and boot/data partitions stay unchanged. Physical acceptance of the
intermediate build is not claimed or used as a prerequisite.

Wi-Fi Discovery lists nearby networks and advertised security/signal. A rescans,
D-pad scrolls, and B/Menu cancel or leave. No password, connection profile,
automatic association or internet probe is added. Reading the results has no
countdown; each scan has a 15-second operation limit and remains retryable.

The parent drains the scan child's output while it runs, using nonblocking reads,
a bounded amount of work per frame and a 64 KiB response limit. This fixes the
dense-response deadlock found in the audit. Invalid responses and unsuccessful
children produce a retryable error; cancellation kills and reaps the owned child.

Scan start, result state/count and cancellation are included in the shell report
and Guide journal markers. Network names and credentials are not copied into
those Guide diagnostics.

Installation requires source/ARM64 tests, an isolated full-system boot with the
actual NetworkManager and discovery child, retained journal evidence, a recovery
copy, guarded target checks and complete root readback. The virtual no-radio
case cannot validate real radio discovery, controls or the Deck's display.

The first owner-assisted step is now the combined physical test: boot, confirm
`wifi1-20260924` in System Status, open Wi-Fi Discovery, look for `the wifi`,
rescan, and leave a scan with B or Menu. Use Power Off, then reconnect the card.
No association or working IP connection is expected from this discovery test.

## Software evidence

Twenty shell tests and five discovery-adapter tests pass in Debian ARM64
userspace. Real subprocess tests cover a 14 KiB response through a 4 KiB pipe,
bounded excessive output, cancellation, timeout, unsuccessful child exit and
malformed network rows. Existing reporting, navigation and Power tests also pass.

The installed package inventory matches the previous Wi-Fi candidate exactly;
installation used the existing local package cache. Persistent logging comes
from Shell 1. No kernel, bootloader or partition-layout change is included.

Two isolated 512 MB ARM boots started the actual NetworkManager and used the
shell's actual child manager to obtain four no-adapter responses in total.
Cancellation reaped a real discovery child. Both boots shut down and their
results remained in the persistent journal. These are no-radio integration
results, not hardware scan or physical display acceptance.

Candidate root SHA-256:
`A2CAFCDD7847AA7A8FDD96E2C5916F653A49DF4E51D4755D602BC32EF0870467`.

Build and installation evidence is kept under `build/debian-wifi-1/`. The fresh
prewrite capture preserves Shell 1, whose physical test was explicitly skipped.

The installer checked the recovery capture, exact prior root, disk identity and
partition offsets before writing only the root partition. Its readback matched
the candidate hash above; `installation.json` and `seed-install.txt` retain the
result. Physical boot, radio scans, display and controls remain to be observed.
