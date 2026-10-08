# System Info audio test

Status: installed and fully readback-verified on the seed, 25 September 2026,
22:20 EDT. Physical boot and listening acceptance remain pending.

Owner request: a small Audio test option on the system information screen that
plays one five-second tone at regular volume when pressed.

The existing System Status screen exposes Audio test in its action row when the
audio provider is enabled. Controller A or pointer activation starts it; the
label changes to Stop test while active. D-pad navigation, Back and Menu remain
shell-owned. Both the shared-schema and fallback screen expose the action.

The trusted audio provider generates one five-second, 440 Hz stereo PCM waveform
at 48 kHz, with 50 ms fades and half-scale peak headroom. It uses the normal
GStreamer/PipeWire player and current software volume, including mute at zero.
There is no isolated codec probe, hardware-gain override or countdown. Global
volume keys continue to work. Completion releases the test worker and temporary
waveform. A bounded startup/completion deadline also releases failed workers.

The selected output is used. When no output has ever been selected, explicit
activation uses the available onboard output without saving a new selection.
A missing selected output causes a visible error instead of speaker fallback.
Playing music must be paused first. The test uses a separate bounded worker so
paused music, track identity, position and saved selection remain intact. It
does not automatically resume music. Output switching, disconnect or Stop ends
the test. Closing the screen does not extend its five-second duration.

Ownership follows AUDIO_BLUETOOTH_0.md and the existing systemd-managed audio
service. The shared UI describes action identities; the shell dispatches them.
The renderer gains no provider or hardware authority. This remains trusted-shell
IPC, not a new public cartridge permission API.

Build: build/prepare-system-audio-test.py, build/finalize-system-audio-test.py,
build/verify-system-audio-test.sh. The separate build/system-audio-test candidate
includes the preceding speaker gain/ramp/routing corrections. Its root is based
on the verified 0.3.7 image, not a fresh capture of subsequent handheld state.
The final shell bundle alone is insufficient: provider and UI-library updates
require the seed path. Rebase onto a fresh capture before physical installation.
No additional physical playback was performed during development.

## Validation

377 ARM64 tests passed: audio 25, connectivity 52, deployment 64, input 135,
UI 7 and shell 94. Tests cover exact waveform duration/stereo/fades/frequency,
current volume including zero, output choice, refused interruption, paused-track
preservation, repeat activation to stop, completion, timeout and errors.
Normal playbin decoded exactly five seconds at volume 0.37 into a silent fake
sink. This validates decoding and configured volume, not physical audibility.
Installed candidate UI navigation/hit regions, active-release integrity,
shared input/Unicode rendering, service configuration and filesystem checks pass.
Ready, playing and fallback screenshots were visually reviewed without clipping.

The candidate record is build/system-audio-test/candidate.json. Use the final
shell bundle identified there; earlier intermediate bundles are not delivery
candidates. Provider/UI-library changes must accompany it through the seed path.

Staging image SHA256: DAAC8B4CECF1386F56D0D33D045A9D15E095C10E5C93B5F5EF45453E45C2CC73.

## Seed installation

The fresh-capture rebased image passed all 377 tests and was written root-only.
Full readback matched 92544A48CA33DB2B56B3C4295348759D609877301EDB526D9245B87720EFF9F1.
Boot and data were verified unchanged. Record: build/system-audio-test/install/installation.json.
