# Guided controller diagnostic 3

This revision implements `CONTROLLER_DISCOVERY_TEST_0.md` for the RG35XX H.
It keeps the hardware-tested `7.2.7-guide-debian2` kernel and drivers unchanged.
Python 3, Pillow, and a packaged DejaVu font provide the standalone framebuffer
test; they are diagnostic dependencies, not a proposed minimum GuideOS runtime.

## What the user sees

- A full-screen controller diagram highlights one control at a time. Shoulder
  buttons occupy a labeled top-edge row; volume buttons are shown to the side.
- Discovery asks for two confirming taps/releases of each of 18 controls. Physical labels
  are associated with observed device/code pairs, rather than assumed mappings.
  Start, Power, and Reset are excluded, including from navigation and combinations.
- Exercise asks for a one-second hold, release, and another tap. Selected D-pad
  diagonals and shoulder/face combinations check simultaneous reporting.
- Stick discovery learns axes and polarity. A live dot and targets guide a full
  outer-edge sweep, return to center, and click while moving. Coverage thresholds
  are diagnostic guidance; observed raw ranges are preserved for review.
- Missed/ambiguous steps get a retry. Mapping review can restart discovery;
  stage menus offer pause/resume or finish. A summary distinguishes unobserved steps
  from completed ones. Optional outputs use discovered A/B for yes/run or no/skip.
- Optional checks show colors/motion, offer two bounded rumble strengths, quiet
  left/right tones, and headphone insertion/removal. Audio tone level can be
  adjusted with discovered volume buttons at the audio prompt. Codec mixer routing
  is not reconfigured; inaudible output is reported as unconfirmed. Headphone
  detection does not establish correct audio routing.
- Six short questions separately record readability, instructions, pacing,
  comfort, perceived stick response, and clarity of results. Explicit negatives
  and unanswered questions remain distinct from measured hardware behavior.
- The guided session is bounded at fifteen minutes with an on-screen remaining-time
  counter. Partial results are saved if it expires. The outer service allows time
  for the subsequent cube test and orderly shutdown. Allow up to twenty minutes
  for the entire diagnostic, though normal completion should be much quicker.

## Evidence and implementation

`board/rg35xxh/debian/controller-test.py` reads evdev and renders to `/dev/fb0`.
It discovers event device paths by identity, grabs only the gamepad and volume
devices during testing, and leaves the dedicated power-key device alone. On exit
it releases those devices and restores the console display mode. Exclusion cannot
prevent a physical reset or hardware poweroff; these buttons should not be pressed.

Start, Power, and Restart key codes cannot satisfy discovery or navigation.
Duplicate mappings, multiple different button presses, lost-event notifications,
and disconnects invalidate affected trials. Stale held controls must be released
before another trial starts. The kernel remains responsible for button debounce;
this test records transitions without asserting an electrical diagnosis.

Every completed/unfinished trial checkpoints `controller-summary.json` and
`controller-events.jsonl` in the boot-ID report folders on both data and boot
partitions. The summary includes device capabilities, learned mappings, baseline,
raw observed axis ranges, outcomes, and timing. `controller-service.txt` records
application errors and exit status. The completed run also includes an offline
`results.html`, structured `results.json`, exposed power/temperature/memory/load
samples, storage inventory and Wi-Fi link state. `diagnostics/index.html` links
retained runs. No report claims unperformed radio, storage,
charging, power/reset, or long-term reliability tests.

## Validation

Twenty-five regression tests pass inside the ARM64 Debian filesystem, covering real
workflow methods and synthetic input sequences: mapping, exclusion, stale held
keys, duration/release/tap, duplicate/ambiguous input, axis polarity/centering,
simultaneous input including batched taps, kernel-timed holds, timeouts,
disconnects, lost-event recovery, report mirroring, conservative report findings
and escaped HTML content.
Framebuffer and force-feedback structure sizes/offsets were checked against the
ARM64 compiler's Linux headers. The rendered 640x480 button/stick previews were
visually inspected. These checks do not substitute for testing on the controller.

Build logs and previews: `build/debian-diagnostic-3/`.
Prepare with `build/prepare-debian-diagnostic3.sh`, validate/install application
files with `build/finalize-debian-diagnostic3.sh`, then assemble and validate using
`GUIDE_DIAGNOSTIC_ID=3`. The guarded flash script accepts `-DiagnosticId 3`.

Physical validation of the new guided interface remains pending.

## Installation

The reviewed package is installed on the identity-checked seed. Full raw-card
readback matched SHA-256
`FF6A9EB29C77FEB8F1F522A44A6FD93F1138CE5CCD1E7DC1CED367D1B028F9E5`.
The cleared backup-GPT tail also passed verification. Partition/filesystem checks
passed, and the installed application, report generator, sampler, boot script,
and service deadline were verified against the tested sources. Evidence is in
`build/debian-diagnostic-3/flash-result.txt`, `validation.log`, and
`payload-validation.log`. The earlier unflashed candidate and prior hardware
reports are preserved separately.

The coordinated usability, edge-case and coverage review is recorded in
`docs/DIAGNOSTIC_WORK_PLAN.md`; physical-run instructions are in
`docs/DIAGNOSTIC_OPERATOR_GUIDE.md`.
