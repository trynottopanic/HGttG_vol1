# Diagnostic controller edge review

Reviewed 2026-09-22, before flashing. Scope: `board/rg35xxh/debian/controller-test.py` and `test_controller.py`. Runtime files were not edited by this review. Line numbers refer to the original reviewed version and may move after fixes.

## Post-integration bounded recheck

The parent integrated fixes after the initial review. The original three regressions now pass: combination transitions are replayed, late competing-axis motion is rejected, and generation changes invalidate choices. The parent also added timed events, disconnected-state filtering, two-tap discovery confirmation, a longer session, and an ordered headphone insertion/removal check.

The separate edge suite now contains eight tests, all passing in the local synthetic harness: the original three plus batched kernel-time holds, delayed-processing short taps, duplicate edge handling, batched double-tap discovery, and rejection of a different second confirmation control. Runtime and base tests were not edited by this reviewer. The local test harness stubs `fcntl` only for import; parent Linux testing and on-device checks remain distinct.

No new P1 blocker was found in this bounded recheck. Residual limitations from the original report still apply where not fixed: the clock-ioctl fallback timestamps event consumption rather than occurrence; stick motion and headphone switch detection still use sampled final state; the headphone loop lacks a generation invalidation check; framebuffer partial-construction rollback remains absent. These should not be described as hardware-verified behavior. The findings below retain the original evidence as review history, rather than claiming that every listed defect remains present.

The existing 14 tests do not cover poll-batch boundaries, late axis contamination, output consent after event loss, framebuffer constructor failures, or output cleanup failure injection. No confirmed P1 hardware-damage defect was found. The following P2 correctness issues merit fixing before treating the diagnostic results as reliable evidence.

## P2: Valid combination taps disappear within a single poll

At original lines 450–456, `combination()` discards returned events and checks only the final key state. `Inputs.poll()` processes up to 128 events per device. Holding L1, then pressing and releasing A between two polls is valid but never sets `overlap`; the result becomes `not observed`. This is not limited to extremely quick users: framebuffer rendering or scheduling delays also batch events. `stick_click()` and stick coverage similarly sample final values, so intermediate click/axis states can be lost.

Reproduced using the existing mock session: L1 down at 0.8 seconds, A down at 0.901, A up at 0.909, L1 up at 1.3, with 50 ms polls. Result: `not observed`, `overlap=False`, `independent=False`. Added `test_combination_preserves_tap_inside_one_poll_batch` in `test_controller_edge.py`. Process transitions sequentially from a local trial state; preserve kernel report boundaries when correlating axes.

## P2: Axis discovery accepts later movement of another axis

At original lines 377–390, the multiple-axis check only runs while `chosen is None`. Once X is selected, a large Y movement is ignored for ambiguity. Returning X to center completes discovery even with Y held fully deflected. That undermines the stated one-axis discovery constraint and can retain a wrong physical mapping.

Reproduced: X=1800 at 0.8 seconds, Y=1800 at 1.0, X=0 at 1.5 (ranges -1800..1800). Discovery returns X as complete while Y remains 1800. Added `test_axis_rejects_second_axis_after_first_is_selected`. Continue checking all competing peaks through the entire trial and require an unambiguous return to neutral.

## P2: Output consent is accepted from a batch invalidated by event loss

Original `choice()` lines 483–498 lacks the generation checks used by button, combination and stick trials. A returned A press can authorize a rumble/audio output even when the same `poll()` increments generation because of SYN_DROPPED or a disconnect. `Inputs.poll()` can return events from before a later SYN_DROPPED marker in the same buffer; the normal button path catches this, but choices do not.

Reproduced with a mock poll that emits A-down and increments generation in that poll: `choice('RUMBLE', ...)` returns True. Added `test_choice_does_not_confirm_batch_with_event_loss`. Invalidate the prompt before consuming such a batch; require a fresh neutral/confirmation sequence or skip.

## P2: Hold duration measures processing time, not the recorded input time

`Inputs.poll()` records kernel timestamps in JSONL but returns only `(device, type, code, value)`. Original `button()` passes `time.monotonic()` while iterating the returned list. A genuine one-second hold queued behind slow rendering is collapsed to almost zero duration if press/release arrive in one read. Conversely, a short tap whose press is consumed immediately and release is consumed after a stall can satisfy the one-second hold requirement. Requesting CLOCK_MONOTONIC on the device does not fix this because trial logic never uses that timestamp.

Reproduction recommendation: feed timestamped press/release events 1.2 seconds apart in one buffer, then feed a 0.1-second tap across a simulated 1.2-second rendering pause. Assert the first satisfies the hold and the second does not. Preserve timestamp provenance when falling back from the clock ioctl; do not subtract incompatible clocks. Existing pure recognizer tests only validate timestamps supplied by the test, not those supplied by the real poll path.

## P2: Disconnect retains held state and blocks unrelated controls

On read failure original lines 110–114 mark `connected=False` but retain `keys` and `axes`. `released()` and `down()` at lines 143–147 ignore connection state. A volume device disconnected while a key is down can therefore make every subsequent `neutral()` wait five seconds and fail, including otherwise healthy gamepad tests. There is also no reopen/rescan path, so reconnecting cannot satisfy the displayed suggestion without restarting the process.

Recommendation: mark mappings from the disconnected device unavailable, invalidate its state, and either reopen safely with new device identity/generation or clearly require a new session. Test disconnect while held, successful neutral on remaining live devices, and refusal to pass a trial based on stale disconnected values.

## P3: Additional lifecycle and reporting gaps

- **Framebuffer lifecycle:** original constructor lines 155–178 acquires framebuffer/mmap/TTY and changes VT state without rollback. A failure or termination during construction occurs before `fb=Framebuffer()` assigns the object, so main cannot call its close method. Original `close()` lines 195–199 stops cleanup if restoring KD mode raises; main then skips `inputs.close()` too. Process exit releases descriptors/grabs, but does not substitute for restoring console mode/active VT. Use explicit partial-construction cleanup, remember the prior active VT, and independently attempt every restoration. Fault-inject each ioctl/open/mmap step. Bounds validation should also check `xoff + width` against the row capacity; currently only vertical extent is checked.
- **Rumble cleanup:** original lines 538–540 erase the uploaded effect only if the stop write succeeds. A failing stop write skips erase. Nest independent cleanup attempts. The configured pulse is only 500 ms, which bounds normal hardware actuation; this is not evidence of indefinite vibration.
- **Audio evidence:** the player is reliably terminated/waited in a finally block, but a nonzero player exit can still be labeled `user-confirmed`; preserve failed execution distinctly from user perception. `controller-audio.txt` is written only to the primary report by this Python script; outer boot-script copying may cover it. `/run/guide-test-tone.wav` remains after checks, a minor transient-file cleanup issue.
- **Headphones:** original code records complete whenever both states were seen, including timeout while still plugged in; the prompt asks to insert then remove. Require the final unplugged state and preferably event order. Add generation checks to avoid interpreting stale switch state after loss/disconnection.
- **Timeout evidence:** `SessionExpired` saves the overall partial session but does not record which active trial was interrupted. Record current phase/label and an explicit interrupted outcome so an absent result is distinguishable from an unreached step. Worst-case retries exceed eight minutes by design; partial status must remain visibly separate from passing.
- **Mapping contamination:** `ButtonTrial.event()` ignores all events once `complete=True`. A complete tap followed by another button press in the same batch is accepted even though another control is now held. This could represent ordinary fast user input rather than defective hardware; at minimum require clean completion or record the contamination, and do not interpret the accepted discovery as proof of absence of ghost inputs.

## Excluded controls and limits of evidence

Start (315), Power (116), and Restart (408) are filtered from the recognizer and choice path, and ignored for neutral state. The device allowlist does not open the dedicated power-key input. The board patch uses BTN_START for Start, consistent with the exclusion. The existing exclusion test is good coverage of recognizer logic. This does not establish that hardware Reset is suppressible or that firmware/kernel power behavior is disabled; neither should be exercised as part of this diagnostic.

Synthetic reproductions were run on Windows Python with only `fcntl` stubbed for import; no hardware ioctls, card access, or Linux build operations were performed. Three standalone intended-behavior regression tests were added and run against the original reviewed runtime: all three failed their intended-behavior assertions, with zero test errors. Parent integration should run them on Linux after fixing the runtime. No full on-device validation is claimed.
