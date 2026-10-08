# Diagnostic 3: actual-run control-flow audit

Run: `build/debian-diagnostic-3/hardware-tests/2026-09-22-012829/diagnostics/ed673d0c-8f98-4d96-87d6-3a8e3150c5d9/controller-summary.json`.

References below use **R01–R96** for one-based entries in that file's `results` array and **L** for its JSON line numbers. Code references are lines in `board/rg35xxh/debian/controller-test.py` as reviewed on 2026-09-22. Raw reports and runtime were not changed.

## Main finding

The missing final A mapping disabled the diagnostic's own navigation. It removed both pause checkpoints, prevented the recovery retry prompt from appearing, skipped all six experience questions, and skipped all optional output tests. This is a software dependency failure, not evidence that the user overlooked these screens or that A hardware failed.

### Exact causal sequence

1. **A originally completed discovery** with device 1/code 305 and two full taps: R01, L161. Seventeen controls were initially mapped; L1 was ambiguous in R09 and R19 (L393, L661).
2. **Mapping review initiated a complete redo.** R20–R36 (L668–L764) mark the 17 accepted mappings superseded. Code 681–687 enters this path only when the mapping-review choice returns False, archives the old mapping, clears it, and retests all buttons. This establishes which branch ran; it does not establish the user's intent beyond the interpreted button answer.
3. **A's replacement trial was ambiguous:** R37, L770, `Multiple different buttons pressed`, end 153.368 seconds. The redo branch has neither the first pass's automatic missed-control retry (677–680) nor a second mapping review. The remaining 17 controls complete, leaving A absent permanently for the rest of this run.
4. **Both stage gates disappear.** `stage_gate()` immediately returns if A or B is missing (552), before drawing or polling. Calls at 695 and 723 therefore offer no continue/pause screen.
5. **A exercise never executes.** The exercise list at 697 includes only labels present in the mapping. No A exercise result is written. L1+A is separately marked unavailable: R84, L1892.
6. **Recovery depends on the missing control.** The later retry branch at 707 could repair A at 710–711, but its `choice()` returns None before drawing because A is absent (518–520). The repair branch cannot be entered.
7. **Questions and outputs are not presented.** R90–R95 (L1955–L1995) all say `unanswered`, reason `navigation controls unavailable`, and are recorded between 464.447 and 464.970 seconds—only 0.523 seconds for all six nominal 15-second questions. R96 (L2003) records optional checks unavailable, reason `A/B navigation not discovered`; `outputs()` exits at 565–566 before its invitation or any output test.
8. **`session: finished` means flow exhausted, not all tests performed.** Code 731 assigns it unconditionally after `outputs()` returns. The saved elapsed time is 442.726 seconds, well below the 900-second session limit; this was not the global timeout.

## What the actual results support

| Item | Evidence | Classification |
|---|---|---|
| Final A mapping | R37, L770; initial success R01, L161 | Discovery attempt inconclusive; initial event response remains credible. Not a dead-button finding. |
| A hold/release exercise | No row; code 697 | Not executed because mapping was absent. |
| L1 initial ambiguity | R09/R19; later R45 L980 and R68 L1489 complete | Recovered by redo; not an outstanding failed control. |
| B and X initial exercise ambiguity | R61/R62 L1330/L1337; R78/R79 L1795/L1824 complete | Recovered on retry. |
| Other 17 digital controls | Final discovery R38–R54; final exercise R63–R79 including retries | Credible observations of mapped event sequences and hold/release/tap completion. Physical labels still depend on correct user mapping. |
| UP+RIGHT | R80, L1861: `not observed`, overlap=True, independent=True | Executed but completion predicate not met. Overlap and a one-button-held state were observed; not evidence that the diagonal cannot register. Raw events are needed to explain the missing final completion. |
| DOWN+LEFT; LEFT+UP | R82/R83, L1876/L1884: overlap=False, independent=False | Executed, inconclusive. No recognized required overlap within these trials; user timing/instruction, mapping, and hardware remain distinguishable hypotheses. |
| RIGHT+DOWN; R1+B | R81/R85, L1869/L1898 | Recognized combination sequence completed. |
| L1+A | R84, L1892 | Not executed: missing A dependency. |
| Left stick axes | Initial right-axis ambiguity R55 L1270 recovered by R56/R57 | Mapping recovered; initial ambiguous attempt is not a persistent failure. |
| Left stick sweep | R86, L1905 | Credible coverage observation: all eight sectors, roughly full normalized extents, returned center [0, 0.005]. It is not precision calibration. |
| Left stick click with movement | R87, L1937 | Executed, inconclusive. Separate click exercise passed R72; this row does not establish a defective click switch. |
| Right stick horizontal discovery | R58/R59, L1303/L1310: `Axis already mapped` | Mapping collision/inconclusive discovery, not a finding that horizontal hardware is dead. |
| Right stick vertical discovery | R60, L1317 | Credible observed mapping to code 4, sign -1. |
| Right stick sweep and click+movement | R88/R89, L1943/L1949 | Not executed: only one of two required stick axes exists. Code 440–442 and 498–500 return unavailable before the exercise. |
| Experience questions | R90–R95, L1955–L1995 | Not presented, not merely ignored. There are no usable subjective answers. |
| Display colors/motion, rumble, stereo audio, headphone sequence | R96, L2003; code 565–566 | Not executed by this controller workflow. The ordinary UI being visible is not completion of the dedicated display test. Any later graphics benchmark is a separate test. |

## Pause/suspend finding

There is **no global pause command during a physical trial**. Pause exists only in `stage_gate()` after complete discovery and after all exercises. Even with intact A/B mappings it is a bounded 120-second prompt, followed by save/finish if not resumed; the session countdown continues (553–562). It is not indefinite suspend/resume. In this actual run the missing A mapping bypassed both gates entirely. MENU is tested as a physical input; it is not reserved as a pause command. Start, Power, and Reset remain excluded and should not be used as a workaround.

## Isolated software dependencies and remaining evidence gaps

1. **Navigation must survive failed discovery.** Provide a clearly identified independent navigation/recovery route, without silently restoring a mapping the user rejected. Test missing A, missing B, and both missing across stage gates, recovery, observations, and output consent.
2. **Make redo transactional and retryable.** Keep the archived mapping as evidence, expose missing controls after redo, and provide targeted retries before continuing. Do not silently discard a navigation prerequisite without offering recovery.
3. **Provide real trial pause/resume.** Freeze both per-trial and session deadlines during a pause; require a neutral restart and invalidate partial physical gestures. Preserve excluded controls. A pause input must be distinct from the control being measured.
4. **Report dependencies explicitly.** Emit blocked/not-executed rows for missing A exercise, absent navigation screens, and each output test; distinguish partial coverage from `finished`. Record trial start, end, transition evidence, and skip cause consistently so a user need not remember which screen misbehaved.
5. **Unresolved evidence remains limited to specific checks:** A confirmation/exercise, right-stick horizontal discovery and dependent exercises, three incomplete directional combinations, left click+movement, subjective questions, and optional output checks. Preserve the successful observations above rather than calling the entire physical test a failure. This list identifies missing evidence; it is not a decision to modify or rerun the diagnostic before the complete output review.

The report schema has no rows for the mapping-review answer, either stage gate, or the retry invitation. Their absence alone would not prove that a screen was skipped. Here, the final mapping, the code's early-return paths, and the immediate downstream unavailable/unanswered rows establish those skips. The absent A exercise row is a separate silent filtering behavior. Output checks have only one aggregate unavailable row, so individual display/rumble/audio/headphone labels are absent rather than individually recorded as skipped. No subjective complaint can be assigned to one of the three incomplete combinations or a stick step from this summary alone; the user's uncertainty should remain explicit.

Validation: a read-only synthetic invocation using this run's final mapping confirmed that `stage_gate()`, the retry `choice()`, and `outputs()` perform **zero screen draws and zero input polls** before returning/skipping. This audit does not attribute ambiguous physical inputs to a particular user action or component; raw-event reconstruction is separate.
