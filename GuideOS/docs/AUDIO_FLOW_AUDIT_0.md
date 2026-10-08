# Audio flow audit — 25 September 2026

Status: investigation, not a diagnosed cause or a deployed repair. Owner requested
re-examination of the entire flow after ordinary playback and the direct ALSA
probe were both inaudible. No headphones are required for the next software
investigation. No Deck settings were changed during this audit.

## Actual flow and evidence

| Stage | Implementation | What is established | What remains unproved |
| --- | --- | --- | --- |
| UI request | AudioPanel sends an action/token to the local datagram socket | Commands reached the service and created playback | Token acknowledgement means dispatch, not audible success |
| Catalog/file | audio_core selects a file under /data/guideos/media | Returned test file matches packaged test.wav; it contains left-only, right-only, then stereo 440 Hz segments | Current remote protocol does not hash live media; comparison uses the returned card capture |
| Worker/decoder | Isolated process, GStreamer playbin, audio-filter queue, software volume | Controlled execution using the installed ARM libraries produced 288000 S16 samples exactly equal to the original WAV: peak 3276, RMS 1760.48 | This offline test replaces the output sink and does not validate the physical PipeWire graph |
| Buffer | Non-leaky queue, maximum 250 ms or 256 KiB, no buffer-count limit | Decoded content survives the actual filter arrangement in the controlled test | Maximum capacity is not a guaranteed prefill; empty-queue signals are not confirmed ALSA XRUNs |
| PipeWire sink | Explicit node.name target, no fallback/reconnect, sink unmuted at unity for onboard play | Physical PCM activity and virtual play/pause/output-loss behavior observed | No nonzero-sample measurement at the physical sink monitor; no complete live link/port snapshot |
| WirePlumber/UCM | Speaker profile sets DAC 58, line-out 27, switches on, Stereo route; soft mixer rule | Physical mixer values agree; installed audio Python files match reviewed sources | Complete applied UCM/port state is not exported |
| ALSA/kernel | H616 sun4i-codec driver and DMA playback | Physical PCM RUNNING and frame advancement at approximately 48 kHz | Advancing DMA does not establish analog conversion or signal amplitude |
| Internal codec graph | DAC Enable, Left/Right DAC, mixers, line-out selector and ramp controller | Reviewed source defines this path | Existing debug collection misses component-level widgets, clocks and registers |
| Board output | Speaker DAPM event controls PI5; board declares CLDO1 3.3 V speaker supply | Speaker widget On; PI5 changes low to high during direct playback; headphone path Off | GPIO state is not electrical power measurement; actual regulator state and full analog path remain unmeasured |
| Bluetooth branch | PipeWire/WirePlumber → BlueZ → controller → earbud | Earlier owner-confirmed audible playback | Current boot has zero controllers; this separate failure precedes A2DP transport, not merely discovery of earbuds |

## New verification

The exact installed ARM decoder libraries, playbin audio/soft-volume flags and
production queue limits were exercised with an appsink in a read-only mounted
copy of the installed root. All 288000 decoded samples matched the six-second,
24 kHz stereo source exactly. Each of the three file sections had the intended
channel activity. This rejects a silent packaged WAV or corruption by this decode
and filter arrangement. It does not certify every decoder or the entire worker
lifecycle. The returned card's media test file has SHA-256
`172689360daaccc318cf88f211c79951eacc68015e53c33ff638c6407f1d7849` and matches
that packaged file. Seven installed audio Python modules match their source.
Private evidence: `private-recovery/live-link/decoder-audit.json`,
`installed-audio-audit.json`, `audio-flow-inspect.json`, and the earlier active
PCM/direct-probe reports.

## Findings in the implementation and test design

1. **Incomplete low-level observation.** `deploy_board_diagnostics.py` searches
   `asoc/*/dapm/*`, collecting card widgets but not nested codec-component DAPM
   directories. The captures contain Speaker, Headphone, Line Out and bias level,
   not Left/Right DAC, mixer enables, digital DAC enable or ramp state. It also
   omits codec registers, regulator summary, clock summary and ALSA hardware
   parameters. “Speaker On” therefore covers only one part of the path.
2. **The direct probe is only a partial isolation.** It removes the application,
   decoder, buffering and PipeWire/WirePlumber from active playback. It shares
   the kernel, device tree, codec and analog path. It also inherits the line-out
   source selector and reversed-DAC settings instead of explicitly establishing
   every relevant mixer value. Earlier captured routing was Stereo, but that is
   not a substitute for capturing it during the probe. A successful aplay exit
   proves completion, not sound. Its known generated waveform still makes the
   common lower path the highest-value next investigation; hardware damage is
   not established.
3. **Premature playback reporting.** In `GstPlayer.tick`, ASYNC_DONE calls
   set_state(PLAYING), ignores its return and can immediately report playing.
   It should retain starting until the pipeline's PLAYING state change and
   handle immediate failure. This is a real status defect, but does not explain
   the observed direct ALSA silence.
4. **Queue telemetry overstates failure.** `underruns` counts GStreamer queue
   empty signals, including normal startup/drain events. It must be labeled
   queue-empty events, with hardware XRUNs recorded separately. The 250 ms queue
   limit does not promise a maintained 250 ms cushion.
5. **Provider control can stall.** Refresh runs synchronous pw-dump and BlueZ
   inventory calls in the same GLib callback as commands, worker polling and
   status publication. Each may take two seconds; onboard Play adds two wpctl
   calls. Processing up to eight commands in a callback can compound delays.
   This creates responsiveness/staleness risk, independent of constant silence.
6. **Existing virtual acceptance did not measure sound samples.** The guest uses
   a null audio sink and checks state, position, mute, pause and recovery. Those
   are useful lifecycle tests, not amplitude or hardware tests. Buffer unit tests
   also use a helper sink arrangement; the new decoder test exercises the actual
   audio-filter placement, but a physical output measurement is still missing.
7. **Diagnostic history loses useful context.** Process snapshots dominate the
   64 KiB report tail. Backend error reporting drops descriptive GStreamer
   diagnostics, while SYSTEM_ERROR includes warnings. Keep bounded actionable
   event history separate from resource samples and preserve useful backend
   detail in private reports.

## Kernel/board review

The local source includes the H616-specific FIFO register, playback-only quirk,
24.576 MHz clock request for 48 kHz, speaker pin control, headphone detection and
board speaker supply declaration. That is source evidence, not a readback of
active hardware registers. The extra card widget named `Line Out` is not the
same object as the codec endpoint `LINEOUT`; its Off state alone is not proof of
an interrupted route. The upstream correction explicitly retains LINEOUT as the
codec endpoint while using Speaker/Headphone board controls:
https://www.spinics.net/lists/devicetree/msg773416.html

PI1/PI2 labeled amux-a/amux-b belong to the joystick ADC multiplexer in this
board description. They must not be manipulated as the audio selector. No
specific kernel routing bug has been established by the source review.

Fresh service journals show RTKit and UPower unavailable. RTKit affects realtime
scheduling privileges and deserves configuration review, but it is not required
to reproduce the silence: direct aplay also failed audibly. UPower battery
reporting is not evidence that the speaker rail is unpowered. Do not fix these
warnings by assuming they are the root cause.

## Next investigation, without requiring headphones

1. Extend fixed read-only inspection to bounded recursive codec DAPM, codec
   regmap, relevant regulator/clock summaries, PCM hw_params, active PipeWire
   nodes/links/ports, and source identity/amplitude. Collect idle and active
   snapshots in one probe record, not unrelated captures minutes apart.
2. Make the direct probe establish and record the complete known mixer state,
   then emit left-only, right-only and stereo segments. Preserve and restore
   existing state exactly. Capture relevant internal DAC enables and ramp state
   while PCM runs; verify the sound-producing path rather than raising gain.
3. Add a signal-level PipeWire loopback test against the real service stack.
   Measure per-channel peak/RMS so a working state machine cannot pass with
   silent samples. This can run locally/virtually before another physical test.
4. Correct premature state reporting and misleading queue telemetry separately,
   with tests that fail on the current behavior. Do not claim either fixes the
   speakers without physical evidence.
5. Choose a driver/device-tree correction only after a register, clock, power or
   routing mismatch is identified. The installed link cannot yet retrieve those
   missing states or replace provider/kernel code through its shell-only updater.

Conclusion: the application file and installed decoder/filter path have stronger
positive evidence now. The common kernel/codec/board path remains incompletely
observed, not proven defective. The next revision should close that evidence gap
and repair the identified status defects, rather than ask for another identical
listening test or declare the speakers faulty.

## Physical audio-path-2 capture, 25 September 2026

The owner confirmed no audible output during the six-second left/right/both
probe. The probe completed with aplay return code 0 and restored=true. A fresh
inspection confirms PipeWire, WirePlumber and guide-audio active, with zero
restarts, and the probe service inactive after successful completion.

All three active snapshots show DAC digital enable, both analog DAC enables,
both mixer enables and both line-out enables set. Codec clock is 24.576 MHz.
The sample counter advances from 0x0000f8c0 through 0x0003e6c0 to 0x0006d4c0.
This establishes hardware consumption of samples, not audible analog output.

Register 0x310 remains 0x0015e81b; 0x314 remains 0x00220d33; 0x31c is 1.
The mixer records Stereo (0,0), and source-select bits 6 and 5 are both zero.
DAPM text nevertheless names Mono Differential input paths. That text is not
sufficient evidence of an actual differential hardware selection; the control
and raw register agree on Stereo.

A new, unconfirmed lead is the analog mute/ramp state. Bits LMUTE (12), RMUTE
(10), RSWITCH (9) and RAMPEN (8) in 0x310 are all zero while RDEN in 0x31c is
one. Allwinner's H616 manual describes LMUTE/RMUTE zero as muted. The local
driver defines these bits but does not explicitly program them; it uses RDEN
as the DAPM ramp control. Establish how automatic ramp control affects these
fields on H700 before proposing a driver correction. This is a candidate
explanation, not a confirmed root cause and not evidence of damaged speakers.
Primary reference: https://linux-sunxi.org/images/2/24/H616_User_Manual_V1.0_cleaned.pdf

The GPIO collection is truncated at 2048 bytes before PI5 in this capture.
Therefore this revision does not freshly establish the physical speaker-enable
GPIO value, despite Speaker DAPM being On. Earlier captures are historical
evidence only. A follow-up collector should retain relevant GPIO lines within
the total budget rather than cutting off the desired pin.

Private evidence: audio2-path-before.json, audio2-probe-request.json,
audio2-probe-result.json and audio2-inspect-after.json in
E:/DGttG/private-recovery/live-link. No additional device changes were made
after this probe. Do not repeat the same unchanged listening test.

Follow-up: [mute/ramp investigation](AUDIO_MUTE_RAMP_INVESTIGATION_0.md) identifies missing analog initialization relative to the vendor driver; candidate correction remains physically unverified.

Physical audio-path-3 result: corrected mute/ramp registers confirmed, PI5 high, but the owner heard no sound. The correction did not resolve the fault. See AUDIO_MUTE_RAMP_INVESTIGATION_0.md for exact values and evidence.

Next isolation is prepared: [internal codec source comparison](AUDIO_CODEC_SOURCE_PROBE_0.md). Audio-path-4 is built, not installed, and is a diagnostic revision rather than a confirmed fix.

Audio-path-4 physical result: owner heard only the internal codec tone. Normal source remains silent. Internal source register confirmed; player reported I/O error and was closed by the final snapshot. Source restored and services recovered. Prioritize normal FIFO/sample delivery; see AUDIO_CODEC_SOURCE_PROBE_0.md for interpretation limits.

Next prepared revision: [audio-path-5 direct format comparison](AUDIO_FORMAT_PROBE_0.md), built and ARM-userspace-tested; physical acceptance pending.
