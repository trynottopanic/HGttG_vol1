# Diagnostic operator guide

## Current build: GuideOS 0.3 “Liquid Snake”

Internal build identifier: diagnostic 4, the untimed button baseline.

1. Boot the seed and wait for **RG35XX H / BUTTON CHECK**.
2. Press and release each of the 18 listed buttons in any order. Check that the
   highlighted name matches the physical button. Green **DETECTED** means a full
   press and release was observed. Stick clicks count; stick movement is not part
   of this baseline. **Keep Start, Power and Reset excluded.**
3. There is no time limit. To pause or finish, hold any included button for three
   seconds, then release it. The menu remains open until you choose an action.
4. Tap any included button to move the selection. Hold for two seconds, then
   release to choose. Resume is the default. Select either Save + finish option
   according to whether the tested labels matched or you saw a mismatch/are unsure.
5. Save + finish keeps partial results too, then shuts down safely. Reconnect the
   seed after shutdown. Reports are in `diagnostics/<boot-id>/results.html`.

If a control highlights the wrong name, retain that observation for the follow-up.
Missing input is reported without diagnosing the button as broken. No output,
analog-stick or timed exercise follows this check. See
[the implementation notes](../DEBIAN_DIAGNOSTIC_4.md) for evidence and limitations.

## Historical revision: diagnostic 3 guided sequence

The instructions below apply only to diagnostic 3, whose full run was archived
and audited. They do not describe the current button baseline.

## First run: follow the screen normally

1. Hold the device comfortably. Have headphones nearby only if you want to try
   their optional detection check. Note whether sound checks use the speakers
   or headphones.
2. At Welcome, press and release a game button such as A when ready. Welcome
   waits up to one minute. Leave every control untouched during the baseline.
3. Follow each highlighted physical label. Tap and release it, then tap and
   release the same control again to confirm. Digital prompts allow 20 seconds.
   “Left click” and “right click” mean pressing the corresponding stick down.
   Release controls between steps. Missed steps can be retried.
4. At Mapping Review, answer whether the highlights matched what you pressed.
   A accepts; B repeats digital discovery. If a displayed A/B action responds
   to a different physical button, record that explicitly: the earlier mapping
   may be wrong. Do not treat that run as proof of correct physical labels.
5. Move each named stick right and up when asked, returning it to center after
   each movement. Continue into the exercises: hold a control until told to
   release, then tap it again. Follow the paired-button prompts, trace the stick
   edge slowly, and try the requested stick click while moving.
6. At stage menus, A continues and B opens Pause. On Pause, A resumes and B
   saves and finishes the controller test. An unanswered stage menu finishes
   after 30 seconds; Pause lasts up to two minutes. The 15-minute session
   countdown keeps running. Finishing the controller test moves on to graphics;
   it is not a shutdown command. These menu actions do not apply during capture.
7. Read the summary and take a retry if useful. Answer the six experience
   questions about reading, instructions, timing, comfort, stick movement, and
   result clarity. A means yes, B means no; no answer is saved separately. Keep
   brief notes about any specific difficulty for later.
8. Optional checks cover colors and motion, available rumble, left/right tones,
   and headphone insertion/removal. Choose whether to run them. B stops a
   playing tone or rumble pulse. Adjust tone level with the discovered volume
   buttons at an audio question before playback. Follow the headphone prompt,
   including removing an already inserted plug before starting the sequence.
9. When graphics begins, no buttons are needed. Observe the display and allow
   the diagnostic to reach its normal completion before retrieving the reports.

Start, Power, and Reset are excluded throughout. Do not use them for navigation,
recovery, or edge-case testing in this procedure.

## What to report yourself

The software cannot feel a stiff button, hear distortion, or decide whether a
diagram was confusing. For each concern, note the screen/control, what you did,
what you saw/heard/felt, and whether a retry changed it. Useful observations are:

- Text that was hard to read; an unclear label or diagram; a screen that advanced
  too soon; uncertainty about pausing, finishing, or retrying.
- A sticky, loose, uncomfortable, or inconsistent control; a stick dot that
  jumped or failed to settle after release.
- Missing colors, flicker, or uneven motion; whether each rumble pulse was felt
  and comfortable; whether tones were audible, distorted, or heard on the
  expected side. Say “unsure” in your notes when appropriate.

## What the saved evidence means

Open the run's `results.html` for the readable report. Keep the complete run
folder, including raw logs and telemetry, when sharing results. Match your notes
to that run rather than combining different runs.

Software evidence includes observed input events, learned mappings, holds and
releases, stick ranges, combinations, saved answers, and detected interruptions.
“Complete” means the requested observable sequence occurred. “Not observed,”
“unavailable,” “skipped,” and “unanswered” need their context; none alone proves
broken hardware. Advertised support is different from observed operation, and
your output confirmations remain human observations.

This pass does not establish precise latency, electrical reliability, correct
headphone audio routing, charging, USB, storage-slot behavior, or radio operation.

## Optional second run: sample recovery

After retaining the normal run, optionally try one or two deliberate cases:
press the wrong control once and correct it on retry; allow a prompt to expire;
briefly keep a control held across a transition and then release it; miss a stick
direction and retry; or leave an optional question unanswered. You can also use
a stage menu to pause and resume or save a partial run.

Label every intentional case in your notes, including the affected step and
whether the next instruction made sense. Do not force a control, disconnect
internal hardware, interrupt storage writes, or test the excluded buttons.
