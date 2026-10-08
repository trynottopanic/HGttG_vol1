# Resident diagnostic overlay

Owner requirement: Start+Select pauses the screen-owning process and presents
transparent live diagnostics. Initial scope explicitly excludes boot animation.

The system-owned `guide-control.service` holds gamepad and volume input and
forwards ordinary events to the shell over a local socket. It recognizes the
chord outside the foreground process. Once both buttons are released, a new
chord can resume; B also resumes. Left/Right switches the two diagnostic pages.
Start, Power and Reset remain excluded from button exercises.

For this build the foreground owner is `guide-shell.service`. The control
service freezes its entire cgroup, confirms the kernel frozen state, captures
the framebuffer in RAM, and draws a half-opacity diagnostic panel. Resume
restores the captured frame, closes that display handle, thaws the shell and
resets forwarded input to prevent held gestures carrying into the interface.
Screenshots are not saved on the device. Audio, Wi-Fi and diagnostic collection
are separate services and continue; Power remains under systemd-logind.

The service uses ordinary scheduling with Nice=-5 and CPUWeight=1000, without
real-time scheduling or dedicated cores. It blocks waiting for input when idle,
checks device health every five seconds, and redraws an open overlay once per
second. Resource samples arrive every five seconds. MemoryHigh is 64 MiB and
MemoryMax is 96 MiB; these limits are not measurements of actual use.

An active deployment transaction defers opening the overlay. While open, a
shared deployment lock prevents a new activation from beginning. This avoids
freezing a health trial and provoking a false rollback. Pressing the chord
again cancels a deferred opening. Stop ordering puts control cleanup before
shell shutdown; ExecStopPost also thaws the foreground after a control crash.
Because systemd refuses its Thaw request when a stop job is already queued,
this host adapter uses the fixed foreground's kernel `cgroup.freeze` file for
both transitions and verifies `cgroup.events`. Mixing systemd Freeze with a
direct kernel thaw left systemd's cached freeze state inconsistent; the final
implementation avoids that combination. systemd still owns service start/stop
and resource limits. This is a narrowly scoped Linux-host adapter, not permission
for applications to alter other services. The virtual poweroff test deliberately
leaves the overlay open and requires clean shell cleanup.
See [systemd freezer implementation](https://github.com/systemd/systemd/blob/v257/src/core/unit.c)
and [kernel freezer interface](https://docs.kernel.org/admin-guide/cgroup-v2.html).

This is a concrete integration for the current shell, not a completed generic
application/display registry. Independent native graphics applications need
their own registered ownership and handoff before this overlay can cover them.
Diagnostic command acknowledgement latency may include time deliberately spent
paused; do not classify a long acknowledgement across a pause as CPU congestion.

## Acceptance

The disposable ARM guest checks actual systemd cgroup freezing, continued audio
progress, resumed navigation and automatic thaw after control-service failure.
Its display and input devices are fixtures. Physical acceptance must establish
the chord works on the gamepad, the original screen is visible underneath,
navigation is paused and then resumes, audio continues, and Power shuts down
cleanly with the overlay open. Also repeat a normal shutdown and second boot.
