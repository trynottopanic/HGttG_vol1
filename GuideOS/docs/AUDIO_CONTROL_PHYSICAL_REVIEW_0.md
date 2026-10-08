# GuideOS 0.3.2 physical review, 25 September 2026

Owner reports: menus and Start+Select overlay work; globe is delayed after a
blinking cursor/black screen; an unintended vertical bar appears beneath it;
Bluetooth discovery shows neither devices nor an empty-result explanation;
the internal-speaker test is silent. Owner confirms the earbud was in pairing
mode and only the internal speaker output could be selected.

## Preserved evidence

Read-only returned-seed capture:
`E:\DGttG\private-recovery\audio0-return-20260925-031258\seed-used-region.img`.
SHA-256: `396A3682291121661707722FA33FF9ED6B3DA7CC89E45625B3D68CA865F0CC93`.
The same private directory contains the complete journal, audio service journal,
saved ALSA state, audio-provider state, and copied diagnostic/lifecycle records.
No physical writes were made during this review.

The two relevant boots are `7fd5e7ccf15d4419b3214f0e5a610d7e` (main exercise)
and `ae6114df19a34055a5b5643c5ba19ac0` (short second boot). The device's wall clock
is stale; use boot IDs and monotonic times for this analysis.

## Findings and evidence limits

### Boot delay and vertical bar

First frame was logged at 14.705 and 14.504 seconds after Linux's monotonic
origin. Renderer initialization took 4.691 and 4.598 seconds respectively.
On the second boot DRM opened at 10.052, EGL configuration was logged at 13.969,
and first presentation at 14.504 seconds. Most of that renderer setup interval
precedes texture uploads. These times exclude unmeasured bootloader time.
Each animation then ran approximately eight seconds, with 482 presentations,
mean frame time near 16.67 ms and zero measured frames above 33.33 ms. The
separate initialization/playback deadlines now completed normally.

Source review identifies a concrete out-of-bounds mask-sampling defect. The
fragment shader samples silhouette coordinates outside [0,1], while texture
wrapping clamps to the edge. Asset row zero has opaque columns 34 through 45.
Consequently fragments below the globe reuse those edge pixels, producing a
vertical strip. Explicit silhouette bounds must preserve the allowed four-pixel
horizontal cloud extension and the separately rendered caption. Physical visual
acceptance will still be needed after correction.

### Silent internal speaker

Two six-second playback attempts reached playing, advanced beyond four seconds,
and finished without a recorded decoder error or worker timeout. The second
attempt used software volume 65%. Saved output is the Codec HiFi Speaker sink.
This establishes decoder progress, not audible output or correct physical routing.

Saved ALSA controls have Speaker, DAC Playback, and Line Out Playback switches
enabled, with no headphone detected. DAC Playback Volume is 45 (-20.88 dB), and
Line Out Playback Volume is 16 (-22.50 dB). Their combined nominal attenuation
is 43.38 dB, before the quiet sample and software volume. This is a strong lead
for near-inaudibility, not proof of the complete cause. We did not capture live
PipeWire route/port/mute state or measured analog output. Calibrate the board's
hardware gain with a conservative test volume; do not blindly set every mixer
control to maximum or infer silence from buffer statistics.

### Bluetooth discovery and missing feedback

BlueZ started and the HCI UART/H5 kernel support loaded. No successful discovery
or controller firmware initialization is established by the persisted evidence.
Six COMMAND_ERROR events were recorded, but they retain neither the command
action nor the underlying BlueZ error; they cannot all be attributed to scanning.
Daemon startup alone does not establish a usable radio.

There is a definite message-routing defect: audio_service stores command errors
in the general message, while the Bluetooth view displays bluetooth_message.
The view can therefore hide discovery failures. The scan completion text also
says only "Discovery finished", without distinguishing zero results. Fix these
paths and persist bounded adapter/power/discovery state plus standardized backend
error names. The exact radio failure remains unresolved; do not call this simply
an absent earbud, bad pairing mode, or proven missing driver.

### Accepted controls and remaining diagnostic work

Menus and overlay pass the owner's physical observation. The main boot records
two opens and closes, including closure during shutdown, followed by clean shell
cleanup. Both boots have no shell cleanup errors. Initial overlay opening took
321 ms, subsequent opening 114 ms; close took 13–21 ms. These are service-side
measurements, not physical input-to-photon measurements.

The collector produced 41 resource samples; observed sample execution time
averaged about 49 ms and peaked near 69 ms. These are elapsed costs, not CPU
utilization percentages. The process samples report four logical CPUs.

## Next implementation scope

1. Correct globe mask boundaries, instrument initialization stages, and address
   early console cursor presentation without hiding real boot failures.
2. Correct Bluetooth error/empty-result feedback and retain actionable controller
   diagnostics so the next failure identifies its operation and backend error.
3. Establish an explicit RG35XX H speaker gain/routing policy and capture live
   mixer and audio-route state during a conservative audible test.

Preserve the functioning menu/overlay behavior. Do not mark audio, Bluetooth or
the revised globe accepted until their physical checks pass.

Follow-up: AUDIO_RECOVERY_1.md records the implemented speaker gain/routing,
Bluetooth feedback and diagnostic changes, their virtual checks, and verified
seed installation. Audible output and earbud connectivity still require the next
physical test. The globe boundary correction has not yet been implemented.
