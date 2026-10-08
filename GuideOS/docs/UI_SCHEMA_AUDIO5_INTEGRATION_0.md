# 0.3.2 UI schema 1 and audio-path-5

Installed 2026-09-25 at 20:28 UTC. Full root readback matched the validated image;
boot and user-data regions were verified unchanged. Physical testing is pending.

Owner request: integrate the Future Planning handoff and the diagnostic correction,
then write the seed. This is the handoff's first migration slice: Home and System
Status. Wi-Fi, audio, keyboard and power screens retain their current layouts.

The shared renderer and Paper theme live in package/guide-ui. The shell retains
display ownership, navigation, pointer/context menus, global controls and the
28-pixel status bar. Header and facts geometry reserve that status bar. Text uses
the existing Pango/Unicode provider with the declared family, weight and size.
Drawn regions supply menu hit targets, with stable identities rechecked at
activation. Theme failures fall back to the existing built-in shell.

The Home frame is cached by menu contents and selection; pointer-only updates
reuse the shell's base frame. Caches hold only bounded screen/menu state, never
keyboard entries. The new immutable shell release retains the previous release
for rollback. Theme/provider installation uses the authorized root image update;
the network updater's shell-only scope has not been broadened.

Audio-path-5 separates S16 file playback, S32 file playback and internal sine
into independent player lifetimes. Each stage records its own snapshots and exit
status, then restores Normal before the next stage. This removes the earlier
diagnostic's mid-stream source switch. It does not establish a speaker repair.
See AUDIO_FORMAT_PROBE_0.md for the procedure and interpretation limits.

Validation: handoff SHA256SUMS verified; 284 tests passed in staged ARM userspace
(52 deployment, 135 input, 7 schema, 90 shell). Additional integration checks
cover the installed release, Pango availability, matching draw/hit geometry,
status entry before first render, stale-target rejection, Back/Home navigation
and theme-load failure. Actual staged screenshots were visually inspected.
Release smoke check, service validation and filesystem check passed.

Initial emulated timings were about 35 ms for changed Home content and 5 ms for
cached/pointer-only drawing; these are host/QEMU results, not Deck measurements.
The exact subsequent measurements and test logs are under build/debian-audio-5.

Recovery capture: private-recovery/audio5-return-20260925-161514 under E:/DGttG.
The rebase verified 21,215 original regular files outside the intended payload
unchanged, along with original symlinks. Kernel and codec remain unchanged.
The writer requires matching seed identity/layout and prewrite region hashes,
then verifies root readback and unchanged boot/data regions. installation.json
is the authoritative write outcome; physical acceptance remains pending.

Next physical checks: boot into the new Home design, open System Status and
return using pointer, D-pad and global Menu; confirm Wi-Fi/audio screens and the
diagnostic overlay remain usable. Reconnect Wi-Fi for the explicit three-stage
speaker probe and record which stages are audible. No automatic tone on boot.
