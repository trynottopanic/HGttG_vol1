# Wi-Fi discovery 1: returned-card result

Owner report: tests performed fine; Bluetooth out-of-order messages were visible
before the interface and before shutoff. The seed was captured and inspected
read-only. No device settings or card contents were changed during this review.

## Confirmed run

Build `wifi1-20260924`, kernel `7.2.7-guide-debian2`, boot ID
`dbe8e86f-4d67-443d-b4a7-88f20419612e`.
The recorded shell source hash matches the installed release manifest.
Both saved shell-report copies are byte-identical. The persistent journal
contains 806 entries, including startup and orderly shutdown through the
poweroff target, filesystem synchronization and journald termination.

| Observation | Evidence |
| --- | --- |
| Shell startup | Both ordinary input devices found; first frame-call completion at 11.909 seconds from boot. |
| Fresh Wi-Fi discovery | Nine networks, `ready` result, 3.569 seconds after scan request. |
| Results interaction | Up/down scrolling recorded. |
| Rescan and cancellation | Second scan started at 26.734 seconds and B cancelled it at 27.344 seconds by leaving the page. |
| Exit and saved reports | Confirmed Power Off; no cleanup or report-destination errors. |
| System shutdown | Shell and NetworkManager stopped successfully; poweroff target reached at 33.044 seconds. |

Together with the owner's report, this supplies a successful physical discovery
run. It does not establish network association, IP connectivity, Bluetooth
operation, repeated-boot reliability or independent Power behavior under a fault.
The captured run does not separately demonstrate Menu cancellation or completion
of a second scan. Network names are intentionally absent from Guide's report.

The board clock reported April 2026 during a September test. Use boot identity
and monotonic times above; do not infer actual test dates from that clock.

## Bluetooth finding

Exact message: `Bluetooth: hci0: Out-of-order packet arrived`.
Five instances occur between 8.140 and 9.792 seconds from boot, with sequence
pairs `(0 != 1)` through `(4 != 5)`. Firmware/configuration loading continues,
and the driver prints firmware version `0x75b8f098` at 10.524 seconds.
There is no further out-of-order warning in this boot's retained journal,
including shutdown. Firmware progress alone does not prove Bluetooth works.

The compiled kernel's `drivers/bluetooth/hci_h5.c`, lines 487–493, emits this
message when a reliable H5 serial packet's sequence differs from the next
expected value. It requests an acknowledgment and resets the receive assembly
for that packet. The board description identifies the Realtek RTL8821CS Bluetooth
interface on UART1. These are internal controller/host transport messages.
The observed one-behind sequences are consistent with repeated older packets;
the underlying reason for those repetitions has not been isolated.

The same five warnings and firmware version are present in the 22 September
diagnostic capture. This behavior predates Wi-Fi discovery 1 and was not
introduced by its scan-output correction or NetworkManager package installation.
It did not prevent the successful Wi-Fi scan observed here.

The shell restores the previous terminal display mode when it releases the
framebuffer. Earlier console text becoming visible again at that point is the
likely explanation for seeing the warning before shutoff. This is an inference
from the timing and cleanup code, not a recording of the physical screen.

Track this as a separate Bluetooth initialization issue. Do not label Bluetooth
healthy, suppress the error as the repair, or change its driver/power controls
without a targeted Bluetooth test. A quieter startup/shutdown presentation can
be addressed independently while retaining journal evidence.

Other messages include ALSA rule/use-case warnings, board regulator/DMA warnings,
clock-related timer warnings, and an NM dispatcher activation declined while
D-Bus was shutting down. NetworkManager subsequently exits successfully. They
are not evidence of a Bluetooth shutdown failure, and this scan test does not
establish acceptance of the unrelated hardware paths.

## Evidence

Private capture and full journals are retained outside the public source tree.
`build/debian-wifi-1/capture-return.json` identifies the captured image; its SHA-256
is `6DFAF1016C339C32F4F8362FA9BA2E6B8119FABA325C69953151C042658267C8`.
`build/inspect-wifi1-return.sh` reads the capture with read-only loop devices and
disabled ext4 journal replay. Earlier diagnostic evidence is under
`build/debian-diagnostic-4/hardware-tests/2026-09-22-022635/`.
