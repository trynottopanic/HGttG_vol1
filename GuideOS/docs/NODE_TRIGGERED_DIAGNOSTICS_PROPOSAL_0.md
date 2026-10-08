# Node-triggered Deck diagnostics proposal 0

Status: Deck-side read-only health, report, inspect, audio-path, process, service, storage, and link data are available in candidate 0.4.1-home-v3-r17 over Guide-Link. The Desktop Node diagnostic catalog exists in source, but suite execution, progress/cancellation, and the rebuilt executable remain pending.

## Goal

Add a `Run Deck diagnostics` button to NDI. The owner selects a paired Deck, starts one run, and receives a useful report without opening a terminal or manually collecting separate outputs. Optimize for quick development iteration on the trusted local setup.

## First implementation

NDI should launch a local Guide-Link suite runner for the selected Deck. The runner can be a new `Guide-Link.ps1 -Action Suite` option that sequences the existing client operations; the initial read-only suite should not require a new Deck-side API.

The suite should:

1. Check `status` and collect `health` for device/build identity, sample freshness, system load, process CPU/RSS, audio state, and shell timing summaries.
2. Collect `report` for recent diagnostics, PCM status, and mixer state.
3. Collect `inspect` for the bounded boot, service, kernel, storage, link, Bluetooth, and probe summaries.
4. Collect `audio-path` for the current read-only audio routing snapshot.
5. Collect a final `health` snapshot so changes during the run are visible.

Use the selected Deck address with the existing Guide-Link profile and identity check. Keep the current deployment credentials where the helper already expects them. No need to build a second pairing system just for this button.

## NDI interaction

- Show the button for the selected paired Deck.
- Launch the runner in the background so NDI stays responsive.
- Show current step, duration, and a useful error if a step fails. Keep completed steps if a later one fails or the Deck disconnects.
- Save the report in the existing local private-recovery folder and provide an `Open report` action.
- Label each step `collected`, `passed`, `failed`, `unavailable`, `skipped`, `timed out`, `cancelled`, or `inconclusive`. Use `passed` only when a check has an explicit expected result; collecting a report is not itself a pass.

The shell timing summaries flush every thirty seconds and resource samples refresh every five seconds. Show their ages in the report so it is clear when data predates the current run.

## Add-on tests

Use a small test catalog so later checks can be added without redesigning the button. Each entry needs a stable ID, label, runner operation, prerequisites, timeout, result fields, and a simple `read-only`, `owner-observed`, or `state-changing` classification.

The one-button run can automatically execute available read-only checks. It can pause for a short owner response for tests such as audible playback, display behavior, file selection, or browser navigation. State-changing checks such as a speaker probe, Wi-Fi interruption, sustained playback/load, or card removal should show what they do and ask before that step. If prerequisites are not met, record `skipped` with the reason and continue where possible.

This keeps the common run fast while allowing the suite to grow to cover the current performance timings, process usage, service state, media controls, storage, Wi-Fi, and browser behavior.

## Report format

Save one versioned JSON bundle containing suite version, selected Deck identity, boot ID, GuideOS build, start/end time, and a result per step with status, duration, freshness, and bounded result data. Preserve partial output on error or cancellation. Keep measured data, inferred findings, and owner observations in separate fields.

Use the existing operation-level redaction and bounded reports. `Report` and `Inspect` can contain system identifiers and bounded journal text, so keep the saved bundle with the other local recovery reports. Avoid adding media content or unrelated desktop files.

## Acceptance

1. The NDI button runs the suite for the selected Deck without freezing the app.
2. Health, Report, Inspect, and Audio-Path results are saved together and remain understandable if a later step fails.
3. A Deck identity mismatch or missing Guide-Link setup reports a clear issue instead of collecting from a different target.
4. Read-only tests need no per-test prompts; owner-observed and state-changing tests pause only when needed.
5. The existing Watch and Report actions continue to work independently.

This is a local development convenience using Guide-Link as the Deck transport. It does not require an elaborate security subsystem or a new remote-command surface.
