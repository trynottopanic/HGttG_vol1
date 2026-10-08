# GuideOS 0.3 “Liquid Snake” — physical-run failure audit

Audited boot: `40d0b767-26f0-43c6-b578-ac09008f9444`.
Evidence archive: `build/debian-diagnostic-4/hardware-tests/2026-09-22-022635/`.

All 15 exported files were copied from the identity-checked seed and verified by
SHA-256. The audit read every file, parsed all 1,388 raw input events, reviewed the
complete kernel log and journal, and examined the application and system units
from the verified image. The seed was not modified. This is an investigation,
not a new installation.

## 1. Screen ownership is not coordinated

**Confirmed configuration defect; leading explanation for the reported artifacts.**

The journal records `getty@tty1.service` starting alongside the diagnostic. The
diagnostic directly opens `/dev/tty1`, switches it to graphics mode and writes
pixels to `/dev/fb0`. Its service declares no conflict with the login console,
does not acquire an exclusive display session, and does not track terminal
ownership changes.

The image's getty unit has `Type=idle`, `TTYReset=yes`, `TTYVHangup=yes`, and
`TTYVTDisallocate=yes`. Its terminal is the same `/dev/tty1`. A console reset or
hangup can therefore invalidate the diagnostic's terminal handle and interfere
with its display. The observed exit error is consistent with this: the kernel's
hung-up terminal handler returns `EIO` for the graphics-mode ioctl used here.

This strongly supports a terminal-ownership/startup race. The logs do not record
the exact moment of hangup, terminal mode changes or screen pixels, so they do
not prove that this accounts for every visible artifact. Diagnostic 3 also had a
ten-second startup delay before its interface; revision 4 removed it. That may
have exposed the race. An arbitrary delay would not establish display ownership.

There is a second display weakness: `Framebuffer.show()` copies each row directly
into the displayed buffer, with no frame swap or refresh synchronization. That
permits tearing even without a console conflict. Actual tearing is not established
by the saved logs. No GPU reset, GPU fault or display-controller timeout was logged
during this capture; framebuffer geometry and frame timings were not captured.

Evidence: `journal.txt` login/diagnostic startup; archived
`runtime-config/getty@.service`, `guide-diagnostic.service`,
`controller-test.py` and `kernel-hung-up-tty.txt`.

## 2. The button test diverted activity into its own menu

**Confirmed by raw events and an offline replay of the installed program.**

At 23.160 seconds after boot, D-pad Left went down. The program opened its pause
menu at 26.217 seconds, before the release at 26.660 seconds. That hold therefore
earned no button-test credit. Subsequent taps changed menu selections.

The program resumed at 63.121 seconds. An A hold from 66.812 to 70.332 seconds
opened the menu again. It resumed at 86.737 seconds; another A hold from 90.888
to 94.404 seconds again opened the menu. At 105.440 seconds it interpreted a menu
selection as “finish, labels matched.”

The raw log contains **41 complete press/release cycles across seven expected
button codes**, while the scored checklist contains **zero**:

| Expected control | Raw complete cycles |
| --- | ---: |
| A | 15 |
| D-pad Up | 8 |
| D-pad Down | 6 |
| D-pad Left | 3 |
| D-pad Right | 2 |
| Left stick click | 4 |
| Right stick click | 3 |

Of 1,388 recorded events, 1,382 were logged in menu mode. All 82 key events pair
cleanly into the 41 cycles. There were no recorded lost-event markers, disconnects,
duplicate presses or unmatched releases. All four analog axes also produced
values spanning −1800 to +1800; this is raw activity, not a validated stick test.

The input policy explains the zero score. Every included button can become a
menu command, ordinary holds exit testing, and short presses of A, Up and Down
all advance the selection rather than having distinct select/up/down meanings.
That policy made normal exploration difficult to distinguish from navigation.
The logs show what commands were interpreted, not what the user intended.

An offline replay using the preserved implementation reproduced the same six
pause/resume/finish actions and all-zero checklist result. It used a simulated
50 ms polling interval, so transition times differ slightly from the device;
the action sequence and score agree. See `AUDIT.json` and `INPUT_TIMELINE.md`.

The other 11 included controls have no recorded press/release events in this run.
Their absence does not establish hardware failure. Physical label correspondence
also cannot be certified from this run's menu selection.

## 3. Cleanup failure prevented the promised shutdown

**Confirmed application failure.**

The application saved its report after the interpreted finish action, then called
`Framebuffer.close()`. Restoring the console mode failed:

```
fcntl.ioctl(self.tty, 0x4b3a, self.old_mode)
OSError: [Errno 5] Input/output error
```

That exception escaped cleanup and changed the program's exit status to 1. The
boot wrapper consequently entered its error branch instead of calling
`systemctl poweroff`. The stored completion note explicitly reports failure.
This proves that the program did not request its promised orderly shutdown;
the archive does not show what happened after the final log capture.

## 4. Final reporting and validation missed the failure boundary

**Confirmed reporting inconsistency and test-coverage gap.**

The JSON and HTML say “finished by user” and “labels matched,” while
`button-service.txt` and `completion.txt` record failure. The report is finalized
before terminal cleanup, and a cleanup exception does not revise it. The JSON
correctly leaves `complete=false`, but the readable report does not surface the
exit failure. “Labels matched” with zero scored buttons is not useful evidence
that the baseline succeeded.

The 18 software tests exercised scoring, navigation and simulated recovery. The
full-loop test replaced the framebuffer and display with test doubles; image
previews likewise never exercised the physical display. Neither checked real
getty coexistence, terminal hangup, refresh behavior or cleanup failure. Passing
them did not establish the physical interface contract.

The journal uses volatile storage and is exported before the wrapper exits. It
therefore lacks the subsequent service-failure/shutdown tail. Calendar timestamps
are unreliable: the RTC started in 1970 and systemd advanced to its packaged
epoch in April. This audit uses the boot ID and monotonic input times instead.

## Other findings, separate from these interface failures

- Audio state restoration reported a missing state file and missing UCM
  configuration. No audio functionality was tested in this baseline.
- Bluetooth logged five out-of-order initialization packets, then loaded its
  firmware. This does not establish a usable connection.
- Regulatory-database signature validation failed. Unlike the previous run,
  this run enumerated the SDIO device and logged the Wi-Fi firmware version;
  association was not tested. The previous SDIO failure must not be carried
  forward as if it occurred again.
- Standard APT maintenance timers started. The image's configuration listing
  does not establish that automatic package upgrades occurred, and none are
  recorded in this run. Update policy remains a separate integration question.

## Boundaries for the next decision

These findings identify failures in display ownership, interaction policy,
cleanup and result reporting. They do not establish that the board, GPU, Linux
kernel or all buttons are defective, nor that the entire OS must be replaced.

Before another physical test, the unresolved contracts are: who owns the screen
and how ownership is released; how observations remain separate from navigation;
and how final status survives cleanup errors. A future verification must exercise
those contracts on the real display and terminal path. No fix or reflash was
performed during this audit.
