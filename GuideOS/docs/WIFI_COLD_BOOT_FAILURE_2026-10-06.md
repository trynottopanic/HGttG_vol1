# Returned Seed: intermittent Wi-Fi initialization failure

The owner reported that the current Seed could not discover networks or connect.
They confirmed that the failed boot followed a full power-off. This is cold-boot
evidence, not a suspend/resume report.

## Evidence

The Transcend reader's model, serial, capacity and all three partition geometries
were verified on 6 October. Boot and root regions were captured through a
read-only physical-device handle. Inspection mounted only the captured root with
`loop,ro,noload`. The Seed was not mounted in Linux or written. Raw images,
journals and extracted configuration are retained privately under
`E:\DGttG\private-recovery\seed-wifi-20261006`.

The active installed release is `0.4.3.08`, release ID
`494bf3e76bfd2acb432254db9a86fd20bdb059fcf8357da9a8e59fd4939ee92a`.
The captured root SHA-256 is
`eed08629fd25612c95e169b60af92ce68f03d991cf0aacd095aa1931890837d0`.
The latest retained boot is `9753f7d7c2b14e4489ed0e324567bf1d`, running
`7.2.7-guide-cedrus0`, build #7 dated 2 October. Its journal contains 1,006
records; 566 kernel/network/provider records were extracted for investigation.

This is a log-access capture: the owner-data partition was not captured or
hashed. It must not substitute for the fresh full preservation capture required
by a later Seed deployment.

## Findings

| Seconds after boot, as recorded by the journal | Observation |
| --- | --- |
| 3.921 | The Wi-Fi controller enumerated an SDIO card. |
| 8.552 | `rtw88_8821cs` reported firmware version 24.11.0. This does not establish successful firmware download to the radio. |
| 8.876–9.032 | Repeated SDIO read/write timeouts (`-110`), controller data errors, reserved-page transfer failure, firmware download failure and chip setup failure. The driver probe failed. |
| 12.984–13.368 | NetworkManager reported Wi-Fi enabled by the hardware radio switch and saved state. |
| 13.555 onward | NetworkManager saw loopback; no Wi-Fi device appeared in this boot's retained events. |
| 58.099 and 60.214 | Guide's provider reported `unavailable` when discovery was requested. |

The driver failed before the user's network discovery attempts. The absence of
networks therefore has an established lower-level cause: radio initialization
did not complete. This run contains no completed association or password
rejection. It does not establish a permanently defective adapter.

Seven earlier retained boots with the same #7 kernel created a Wi-Fi interface
and did not record these radio/controller errors. Two further older retained
boots also show a Wi-Fi interface, but one no longer retains its kernel startup
messages. The comparison establishes an intermittent failure, not a universally
missing driver or an observed regression on every boot of the current kernel.
Those interface observations alone do not establish successful connection in
each older boot.

The regulatory database signature warning is also present in the latest boot.
The [earlier diagnostic audit](DIAGNOSTIC3_HARDWARE_AUDIT.md) recorded a similar
radio probe failure. Neither warning nor historical similarity establishes the
root cause of this returned boot. Startup timing, radio power/reset state and
SDIO transport remain hypotheses, not confirmed diagnoses.

## Release follow-through

The initial investigation left Wi-Fi repair and physical cold-boot acceptance
outstanding for `0.4.4.01`. The subsequently authorized recovery is described
below. The successful kernel baseline and failure evidence are preserved.
A UI timeout increase, password edit, service restart or unmeasured radio-clock
change would not establish a repair for this driver probe failure.

Acceptance must observe the driver completing initialization, a usable Wi-Fi
interface, fresh network discovery and a completed connection across repeated
cold boots. Any recovery must be bounded and must preserve working connections,
saved settings, Bluetooth and the Seed/TF2 controllers. No recovery candidate or
hardware repair was installed by the initial read-only investigation.

## Authorized recovery implementation

The owner subsequently authorized repair, a combined `0.4.4.01` build and a
Seed write. The board-specific startup provider waits for the initial probe to
finish, then permits at most two SDIO driver-bind retries only after the current
boot records the exact RTL8821CS timeout on `4021000.mmc`. A temporary driver link
during an unfinished probe is not treated as success. A usable or still-bound
radio is preserved; a changed target, different board/chip, old-boot error or
already-consumed boot marker prevents retries. The provider does not reset
controllers, change clocks, unload drivers, alter credentials or repeat recovery
continuously. NetworkManager starts after the bounded startup check.

Linux tests cover recovery, persistent failure, in-progress probe failure, target
identity and restart/working-radio preservation. The Wi-Fi page preserves a
specific missing-adapter result instead of attempting an impossible scan and
reporting a generic provider error. Repeated physical cold boots are still needed
to establish that re-probing repairs this intermittent hardware failure.

The recovery is included in the signed 0.4.4.01 image. Focused Linux tests passed
63 cases, including the initial-probe race; installed ARM64 recovery/media checks
also passed under emulation. The recovery was written to the Seed in 0.4.4.01.
The root write/readback and boot comparison completed; the owner stopped the
remaining full-data scan and directed lighter verification for this hobby project.
[Combined release record](BUILD_0_4_4_01.md) separates card completion and physical
acceptance. None of these checks proves the intermittent cold-boot failure has
been resolved on the actual radio.
