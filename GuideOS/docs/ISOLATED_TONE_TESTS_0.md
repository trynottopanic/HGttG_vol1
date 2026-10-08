# Isolated tone tests, audio-path-6

Installed: 0.3.2-tone-isolation-1, 2026-09-25 21:08 UTC. Full root readback
matched the validated image; boot and user-data regions were unchanged.
Physical listening and on-device countdown acceptance remain pending.

## First isolated physical result

2026-09-25 21:11 UTC: active release 994a50f57e3bda8297375e84c5083666e8eb74c4cbc5993956809f084fd0cf04
was confirmed before requesting Tone-Internal. The owner reported "I heard it."
The returned record contains exactly one stage, internal-sine, with a four-second
observation window. Internal-tone audibility is now confirmed without sequence
ambiguity. Countdown visibility has not separately been reported.

The PCM writer still exited with code 1; the probe therefore reports failed
transfer, independently of the confirmed audible oscillator. Normal source was
explicitly restored successfully, all restoration commands succeeded, and a
fresh health report showed audio available, stopped, non-stale and not busy;
the shell was ready. S16 and S32 audibility remain unconfirmed in isolation.
Evidence: private-recovery/live-link/probe-result-20260925-171143.json and
health-20260925-171144.json under E:/DGttG.

2026-09-25 21:14 UTC: the owner reported "No tone" for isolated file-s16.
The record contains only file-s16, return code 0, RUNNING PCM in both snapshots,
and advancing hardware pointers (34896 to 82928). Restoration succeeded; fresh
health showed audio stopped, available and non-stale. Thus successful S16
transfer is confirmed alongside physically silent output. Evidence:
private-recovery/live-link/probe-result-20260925-171423.json and
health-20260925-171424.json. A subsequent S32 request was refused by the idle
check; it did not start.

2026-09-25 21:15 UTC: a fresh idle reading permitted one S32 retry. The owner
reported "No tone". The record contains only file-s32, return code 0, RUNNING
PCM and advancing hardware pointers (35696 to 83680). Restoration succeeded;
fresh health showed stopped, available and non-stale audio. Evidence:
private-recovery/live-link/probe-result-20260925-171557.json and
health-20260925-171558.json. All three isolated listening outcomes are now known:
internal sine audible; normal S16 and S32 silent. This does not establish the
root cause, but switching the normal playback format alone is not a demonstrated
fix. Prioritize the normal sample-delivery and codec digital-source path.

Owner requirement: identify which audio path is audible without guessing the
position of a tone in a sequence. This diagnostic revision does not claim to
repair normal speaker playback.

The paired PC can request exactly one fixed stage through Guide-Link.ps1:
Tone-Internal, Tone-S16 or Tone-S32. Requests take no caller-provided commands,
paths or volume settings. The existing idle check, exclusive diagnostic lock,
mixer backup, service stop/restore and systemd timeout remain in force. A pending
request cannot be overwritten. The older Speaker-Probe operation still runs its
three stages and should not be used for single-tone listening confirmation.

The shell retains display/input ownership. A bounded root-written public status
file contains only a fixed stage name, phase, countdown and expiry. Existing
one-second status polling redraws on phase changes even when clock text is
unchanged. The banner displays a five-second countdown, LISTEN NOW, restoration,
and completion. It expires after completion and does not block global controls.
The initial acceptance is in the running shell, outside the separate diagnostic
overlay or boot animation. No tones run automatically at boot.

Each file stage contains four seconds of the same 440 Hz waveform at the previous
gain. The internal stage selects only the hardware sine source and feeds silent
PCM to activate the existing path. It retains a four-second observation window
even when that PCM writer exits early. An I/O error remains an error in the
record; it is never converted to playback success because a tone may be audible.
Normal source restoration occurs after the player has been reaped and before
audio services restart. The service's ExecStopPost retries restoration and clears
the queued request after interruption. Failed restoration remains reportable.

Probe results record the selected stage and audibility as unreported. The owner
reports heard/not heard/uncertain for that one named stage; this observation is
separate from transfer status. Reports stay available through Probe-Result.

Build evidence is in build/debian-audio-6: fresh capture identity, candidate file
hashes, immutable release identity, original-file preservation check, ARM tests,
rendered banner previews, filesystem check, and card readback result. Kernel,
codec module and the previous UI design remain unchanged. The previous shell
release and fresh returned-seed backup are retained.

Validation: 290 tests passed in staged ARM userspace (57 deployment/diagnostic,
135 input, 7 UI schema and 91 shell). Installed-release rendering verified all
banner phases and expiry, with countdown/listening/completion previews visually
inspected. Release smoke, service and filesystem checks passed. The rebase
verified 21,241 original regular files outside the payload unchanged. These
checks do not establish physical audibility or actual on-device display timing.

Physical acceptance: boot and connect Wi-Fi; leave Home visible. Request only
Tone-Internal first. Identify the countdown and LISTEN NOW banner, then report
whether that isolated tone was heard. Test S16 and S32 separately afterward,
with a separate report for each, and verify restoration after every run.
