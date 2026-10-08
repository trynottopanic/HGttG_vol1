# GuideOS 0.3 — Liquid Snake

**0.3 Liquid Snake** is the release name for the RG35XX H untimed button
baseline. Its internal build identifier remains **diagnostic 4** so existing
images, reports and verification records continue to identify the same build.

This revision replaces the guided diagnostic sequence with one untimed checklist.
It uses the already boot-tested Debian filesystem, 7.2.7-guide-debian2 kernel,
panel support and H700 input driver. There is no automatic transition into other
tests and no application or service deadline.

## Using the check

Press and release each included button in any order. The screen shows the expected
name while held, then marks a complete press/release cycle as **DETECTED**. Verify
that the name matches the physical button. Included controls are A/B/X/Y, four
D-pad directions, L1/R1/L2/R2, both stick clicks, Select, Menu and Volume +/−.
**Start, Power and Reset remain excluded.** Analog stick movement is outside this
baseline.

Hold any responding included button for three seconds to pause and open the menu.
Release it; tap any included button to change the selection. Hold for two seconds,
then release to choose. Resume is selected by default. Either Save + finish option
saves partial or complete results and requests an orderly shutdown. Select whether
the tested physical labels matched or there was a mismatch/uncertainty.

Menu gestures do not earn checklist credit. A button held at startup must first
be released; a fresh press/release is required. A stuck button does not lock out
navigation through other responding buttons. Lost input events or a disconnected
device pause the check and discard incomplete cycles, preserving prior completed
cycles. A disconnected device is marked unavailable. Reconnection requires a fresh
boot; live device rediscovery is not implemented in this baseline.

## What the result establishes

The expected Linux key codes come from the device-tree/joypad profile, not from
diagnostic 3's failed rediscovery. In particular, X/Y are expected at codes 307/308;
physical label confirmation is still required. An all-pass result requires all
18 included codes to complete a fresh press/release on an available device, plus
the user's label confirmation. Unobserved events do not establish faulty hardware.
This is not a debounce, endurance, analog-axis, or output test.

Each boot gets a separate folder under `diagnostics/<boot-id>/` on the boot
partition, mirrored from `/data/guideos/diagnostics/<boot-id>/`. Open `results.html`
for a readable report. `button-baseline.json` records counts, expected names and
codes, device identity, menu history, and user confirmation. `button-events.jsonl`
preserves raw events, including events excluded from scoring. `button-service.txt`
records application errors. Boot input inventory and kernel logs are also retained.

Summary files are replaced atomically and synchronized at checkpoints; raw
evidence is mirrored incrementally. Checkpoints are coalesced to at most once a
second during ordinary checking and made immediately for menu transitions and
finish. A failed report save is shown on screen and prevents successful finish.
Unplugging or using a hardware reset can still lose the most recent unsaved work.

## Validation and recovery

The original full seed backup remains in `E:\DGttG\private-recovery\`.
Diagnostic 3's complete 34-file report archive was rechecked against the connected
card before replacement; its audit and original evidence remain under
`build/debian-diagnostic-3/hardware-tests/2026-09-22-012829/`.

Eighteen synthetic behavior tests pass in the ARM64 Debian filesystem, including
arbitrary button order, exclusions, held/repeated/queued input, stuck keys, missing
devices, pause/resume, release-only menu confirmation, incomplete-report handling
and failed mirroring. A full application-loop regression verifies that the volume
buttons can finish a partial session while the gamepad remains in lost-event
recovery or disconnects during recovery. The two 640×480 previews were visually inspected. Final
image checks and card readback are recorded in `build/debian-diagnostic-4/`.
The first physical run exposed display artifacts, an ineffective test/navigation
flow, and a terminal-cleanup exception that prevented the intended shutdown.
See [the Liquid Snake failure audit](docs/LIQUID_SNAKE_FAILURE_AUDIT.md).

Build sequence: `prepare-debian-diagnostic4.sh`, then assembly and validation with
`GUIDE_DIAGNOSTIC_ID=4`, followed by `verify-diagnostic4-payload.sh`. The guarded
flash utility accepts `-DiagnosticId 4` and the exact assembled image SHA-256.

The corrected revision is installed on the identity-checked seed. Full card
readback matched SHA-256
`F7547A9463F0DD7A53A1CBC33B8250DFAB263AB419E5EA9F6FDB2AE874559E93`;
the cleared backup-GPT tail was also verified. The earlier candidate and its logs
are preserved separately. See `build/debian-diagnostic-4/flash-result.txt`,
`tests.log`, `validation.log`, and `payload-validation.log` for the final checks.
