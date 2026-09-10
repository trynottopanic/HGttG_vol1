# Windows UI Known-Good Baseline

Recorded September 6, 2026 on the first Guide Desktop Node development
computer after the user confirmed that window movement performed well.

## Environment

- Windows local session; DWM composition enabled
- 168 DPI / 175% scaling
- 120 Hz display movement budget

## Observed input and governed output

- incoming movement commands: 952.3 per second
- input oversubscription: 7.9 times the display budget
- governed position commits: 108.6 per second
- committed / suppressed positions: 834 / 6,482
- process CPU during drag: 0.0% of one CPU core
- paint messages: 3.6 per second
- physical-button release to modal-move end: 0.0 milliseconds
- movement processing interval, 95th percentile: 1.1 milliseconds

The incoming Windows positions were substantially stale, but the governor did
not replay them. It sampled current pointer state at the display budget and
terminated movement immediately on physical release. This is the behavioral
baseline future native Windows interfaces must preserve.

The original report labelled incoming-command staleness as window lag. The
diagnostic schema was corrected after this run to report source staleness and
governed output lag separately.
