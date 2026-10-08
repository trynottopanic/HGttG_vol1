# Boot handoff and browser startup follow-up

Owner observations: the terminal appears between the boot animation and Home; the r23 browser reports a startup timeout.

## Working-source changes

The boot service now notifies systemd when the native player presents its first frame, allowing Home initialization and first-frame composition during playback. A deferred shell framebuffer waits until the animation process has exited before opening the display. The boot console stays in graphics mode until Home writes its first frame and inherits the original terminal mode for cleanup. A ten-second failed-handoff recovery restores the console. The animation itself is unchanged.

Responsibility remains with the board boot/display adapters, with one display writer at a time. Acceptance requires a physical boot without terminal text between animation and Home, normal shutdown recovery, and a usable console when Home fails. Source checks cannot establish this behavior on the Deck.

The browser service claims its dedicated tty2 with `StandardInput=tty-force`, rather than waiting indefinitely for terminal ownership. Its VT switches have three-second command deadlines; service startup has a fifteen-second deadline. It retains its unprivileged account, PAM/logind integration, sandbox, process-group cleanup, and return to tty1. The shell still keeps the display lease until the service stops.

The full exporter now includes the pre-start command state, control PID, stop-post command state, and startup timeout in its service snapshot, to distinguish future service setup failures from compositor or WebKit failures.

## r23 capture evidence

Input: `E:/DGttG/private-recovery/live-link/full-capture-20260930-233356.zip`, boot `0c92c576-9168-4fb3-99c0-64a1be2e87e2`.

- The journal records uinput module insertion at 3.792 seconds and creation of `Guide Browser Controls` at 60.844 seconds. The earlier missing-driver failure is resolved in this boot.
- `guide-browser.service` begins starting at 60.911 seconds. Its control process is terminated at 86.051 seconds when the shell's 25-second startup deadline expires.
- The service has `MainPID=0`, no executed main command, and no compositor/browser processes. No Weston or WebKit startup is recorded. The failure occurs in service pre-start setup, before webpage loading.
- The installed pre-start command switches to tty2. Terminal ownership blocking is the leading inference, not a captured process stack. The previous exporter omitted `ControlPID` and `ExecStartPre` state.
- The supplied archive contains the current-boot journal and retained logs; full export succeeded.

The systemd execution contract says `StandardInput=tty` waits for an existing controlling process to release the terminal; `tty-force` claims it immediately. Source: https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml.

## Delivery status

These changes are included in the consolidated 0.4.2 system-root candidate; see `BUILD_0_4_2.md`. The systemd units, boot runner, console helper, and diagnostic exporter live outside the current signed shell/browser payload, so the ordinary shell-only Wi-Fi bundle cannot install all of them. The 0.4.2 installation receipt records the authorized Seed write and readback separately from physical browser/boot acceptance.
