# Diagnostic 3: usability and observation review

Reviewed 2026-09-22 against `board/rg35xxh/debian/controller-test.py`,
`CONTROLLER_DISCOVERY_TEST_0.md`, and `DEBIAN_DIAGNOSTIC_3.md`.
This is a source review of the built, unflashed guided test, not evidence of
physical operation. No runtime changes are included in this review.

## Priority 1: address before treating the guided run as trustworthy

1. **A mistaken press can mislabel controls and navigation.** `ButtonTrial.event`
   accepts the first unused key as the requested physical control (line 643).
   Pressing B at the A prompt therefore records B as A; later prompts can become
   ambiguous, and displayed A/B choices can respond to the wrong buttons.
   The software cannot infer physical intent from an event alone. Offer an
   explicit mapping review/correction step before using discovered controls for
   navigation. Keep a clearly explained automatic save/finish fallback when
   navigation cannot be trusted. During the first hardware run, record every
   accidental press and whether the subsequent labels still match the device.

2. **The retry offer cannot repair every problem it lists.** `run` builds its
   summary from all incomplete phases, but the final retry dispatch (lines
   618-623) only handles exercises and combinations. Failed button or axis
   discovery remains unresolved after the earlier fixed retry round. Add
   discovery retries before dependent exercises, or explicitly state which
   items are unavailable and need a new run. Show a revised result after retry;
   the current flow proceeds directly into optional outputs.

3. **Timing can measure reading speed and dexterity instead of hardware.**
   Welcome contains five lines but lasts four seconds; instructions normally
   expire after 12 seconds; the summary lasts five seconds. There is no normal
   pause or finish action during capture. Keep the visible bounded session and
   saved partial results, but give setup instructions enough reading time and
   use a separate, clearly labeled navigation mode for pause/retry/finish once
   navigation is established. Never consume tested controls as navigation
   during capture. Provide a plain-language warning before the session ends.
   Collect whether time expired while the user was still understanding or
   performing the step. Never interpret that as a failed control.

## Priority 2: make the next action and result understandable

- **Show press feedback immediately.** Discovery says “Press once, then release”
  throughout a held press. Change the visible state to “Pressed — let go” when
  the event arrives. This separates a missed press from a missing release.
  The controller drawing also always says “PRESS + RELEASE,” even during the
  hold exercise; make its text agree with the current instruction. The bottom
  bar is time remaining, not hold progress; label it or use a distinct hold
  indicator. Preserve words alongside color.
- **Clarify unfamiliar physical controls.** Use “Press the left stick down”
  rather than “LEFT CLICK”; use “Menu / function button” rather than an unexplained
  M. The implementation uses a top-edge shoulder row, not the requested rear
  view. Verify its positions against the actual RG35XX H before changing the
  drawing. Observe whether users search, rotate the device, or press the wrong
  shoulder/volume button. Keep raw event names and codes out of these screens.
- **Make stick and diagonal guidance concrete.** Stick discovery shows all four
  target dots while requesting only one direction; highlight only the requested
  direction. A D-pad diagonal currently uses “Hold UP; tap RIGHT; release both,”
  which can be hard to execute on one rocker. Explain “Keep Up held while you
  press and release Right, then let go,” with both directions visible. Distinguish
  a coordination difficulty from absent simultaneous input. Current combination
  prompts highlight only the first control.
- **Use local outcomes, not a discovery count everywhere.** Exercise screens
  still show “18 of 18 discovered”; this does not describe exercise progress.
  Label stages and their completed steps. The summary lists at most seven
  unresolved entries and can repeat the same control across phases; show the
  control plus the action needing review and allow all results to be inspected.
- **Separate an answer from silence.** Display/rumble/audio confirmation maps
  both B and timeout to “not confirmed” (lines 516, 542, 568). Preserve yes,
  explicitly no, skipped/no answer, and interrupted separately. Use question-
  specific labels (“A: Heard it; B: Didn't hear it”) instead of the shared
  “YES / RUN” and “NO / SKIP” footer. Offer replay before asking for a verdict.
- **Match headphone claims to the observed sequence.** The prompt requests
  insert then remove, but an initially inserted plug can complete with removal
  alone; the result can also be “complete” after both states were seen without
  ending unplugged. Record the initial state and actual sequence. Prompt the
  missing action explicitly. Keep switch detection separate from audible routing.

## Minimum useful subjective feedback for the first physical run

Use a short observer note or post-run form initially; do not lengthen every
control prompt with a questionnaire. Record the step/control and distinguish
what the user felt or heard from automatic event evidence.

| Question | Minimum useful answer |
| --- | --- |
| Could you read the text comfortably while holding the device normally? | Yes / difficult / no; identify the smallest or unclear text. |
| Which instruction, diagram, or button name made you hesitate or press the wrong thing? | Step/control and what the user thought it meant; “none” allowed. |
| Did any screen move on before you were ready? | Step; still reading / locating control / performing action / reviewing result. |
| Did any control feel stuck, unusually stiff, loose, inconsistent, or uncomfortable? | Physical control, sensation, and whether repeat attempts changed it. No electrical diagnosis. |
| Did the stick dot follow your movement and settle when you let go? | Left/right stick; smooth / jumped / lagged visibly / did not settle / unsure. Do not claim measured latency. |
| Could you tell what completed, what needed another try, and how to finish? | Yes / unsure / no; what was missing. |

For optional output checks, additionally capture: visible colors/motion and any
flicker or missing area; whether each rumble pulse was felt and comfortable;
whether each tone was audible, distorted, and perceived from the expected side;
and whether listening used speakers or headphones. “Unsure” must be possible.
Correct audio routing requires a separate audible check, not just jack events.

## Small physical acceptance pass

Run once without deliberate mistakes to establish ordinary completion time and
comfort. Then use a separate run to sample one accidental wrong press, one slow
response, a briefly held control at a transition, a missed stick direction, and
an unanswered optional question. Confirm saved results distinguish these cases
and that recovery is understandable. Do not request Start, Power, or Reset.
Do not expand this pass into charging, USB, storage, radio, or restart testing.

Physical validation remains pending. Fourteen reported software tests and
preview inspection are useful preparation, but do not answer the usability or
hardware questions above.
