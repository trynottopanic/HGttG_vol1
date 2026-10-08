# Debian Guide Shell integration slice 0

Predecessor status: seven saved baseline runs now record navigation and confirmed
shutdown without cleanup errors. [Shell 1](DEBIAN_SHELL_1.md) superseded this root
on 24 September with verified readback; visual and hardware acceptance remain open.

The subsequent [Wi-Fi discovery 0](WIFI_DISCOVERY_0.md) revision added a fourth
home choice and an asynchronous nearby-network scanner. Its write was verified,
but the owner reported that it did not boot. It was preserved for investigation
and replaced by the previous root on 23 September. See the
[system audit](docs/SYSTEM_AUDIT_2026-09-24.md) for current evidence. Reporting
robustness changes made during that audit were subsequently installed in Shell 1,
along with persistent boot evidence and the baseline menu profile.

## Purpose

This slice establishes the system boundary required before implementing the
shared Media Controller. It is deliberately smaller than a daily-use shell. The
question is whether one supervised system interface can own the RG35XX H display
and ordinary controls, release them predictably, preserve an independent Power
path and report its true lifecycle outcome.

## Ownership

The image masks `getty@tty1.service`, preserving the serial console while
preventing the login console from resetting the same terminal used by the Guide
Shell. `guide-shell.service` owns tty1, fb0, the H700 gamepad and volume buttons.
It conflicts with the earlier diagnostic service. The shell never opens the
dedicated Power input. systemd-logind retains that input and requests orderly
poweroff independently of shell health.

This is the first host integration slice, not the completed Guide Supervisor.
The shell currently runs as a system service because framebuffer and evdev access
have not yet been moved behind unprivileged brokers. `NoNewPrivileges` prevents
later privilege gain but is not a sandbox from its initial device authority.

## Interface and lifecycle

The shell exposes Media Foundation, System Status and Power Off. Media Foundation
states that the player is not installed. Power Off has a separate confirmation;
Menu returns home and B returns from a secondary view. Kernel repeat events and
releases never replay navigation. No test observation or ordinary long press is
overloaded as a shell command.

The framebuffer adapter uses a single contiguous copy when the physical layout
permits and performs idempotent, non-throwing cleanup. Each boot writes a bounded
semantic report to both persistent data and readable boot storage. Cleanup is
performed before the final outcome is saved. A cleanup error is evidence, not a
reason to suppress an already confirmed power request.

## Physical acceptance

1. Boot five times without mixed console text, stale frames or startup races.
2. Navigate every view and return using the documented controls.
3. Stop/restart the shell over the serial recovery route and confirm clean
   ownership recovery without a competing getty.
4. Use the physical Power key while the shell is responsive and after stopping
   it; both must request orderly shutdown.
5. Use the shell Power confirmation and verify saved final status and cleanup.
6. Inspect the service journal and both copies of `guide-shell.json`.

This does not validate animation smoothness or tear-free video. The Media
Controller should follow only after this ownership and lifecycle boundary passes.

## Installation result

The guarded writer matched Disk 4 to the backed-up Transcend seed by model,
serial number, capacity, USB bus and non-system status. It also required the
verified full-card recovery image and exact shell-image checksum before clearing
the previous layout. The complete 3,490,709,504-byte written region was read back
and matched SHA-256
`0A02C32268571C0D540E3D030FF47A30CE56F9022CC8ECD41E2C5F4FB91B9C47`.
The old backup-GPT tail was verified clear. See
`build/debian-shell-0/flash-result2.txt`. This proves the write, not the boot or
the shell's physical behavior.
