# Audio and Bluetooth integration 0

Status: initial implementation staged for GuideOS 0.3.2; physical speaker and
earbud tests pending. This is a bounded first Media Surface provider, not the
complete shared application or resource-grant implementation.

## Requirements and ownership

Owner request: begin integrating audio playback and Bluetooth earbud support.
`FUTURE_FRAMEWORK_0.md` keeps global input, volume, navigation and Power with
Guide Shell. `MODERN_FOUNDATION_0.md` puts process supervision under systemd,
with portable Guide contracts above it. `LIVE_CAPABILITY_REGISTRY_0.md` keeps
discovery distinct from permission and exercised capability.

The trusted-shell provider is `package/guide-audio`. GStreamer decodes local
files, PipeWire routes them to an explicitly selected output, WirePlumber
discovers local and Bluetooth endpoints, and BlueZ owns pairing and stored keys.
The provider runs as `guide-audio`, with no display or input ownership. Its local
socket is for the trusted shell, not a public cartridge capability API.

Missing Bluetooth hardware or pairing failure must not prevent local playback.
Audio remains optional for Guide installations, including headless Nodes.

## First user flow

- Audio replaces the Media Foundation placeholder when enabled in the image.
  Select Music files, Audio output or Bluetooth earbuds.
- Choose an output before playing. Changing output pauses; Resume is explicit.
  Global physical volume keys work outside the Audio page as well.
- Play, pause, resume, stop and volume use the provider. Back/Home leaves
  playback running. Power remains independent; systemd bounds service stop.
- Local files go in `/data/guideos/media`. WAV, FLAC, Ogg and MP3 extensions are
  listed; successful decoding is established separately. A quiet stereo WAV
  sample is installed at first boot. The shallow catalog is bounded to 128
  files from at most 512 directory entries.
- Find earbuds powers the adapter on request and scans for 20 seconds. Select
  a device to pair/connect. Connection has a 30-second deadline and cancellation.
  BlueZ retains pairings. Pairing does not silently change the selected output.
- This slice targets A2DP stereo with SBC. Microphones, calls, LE Audio and
  PIN/code-confirmation pairing are not implemented. The first pairing flow
  targets no-input/no-output earbuds.

## Provisional output-loss behavior

The owner was asked whether earbud loss should pause or use the speaker. Pending
that preference, the implementation pauses and requires explicit output choice
and Resume. Streams are pinned using PipeWire's `target.object`,
`node.dont-reconnect` and `node.dont-fallback`; preventing fallback does not rely
solely on a status poll noticing disconnection.

Discovery is user-triggered, not continuous radio scanning. Background queries
inspect the local audio graph and BlueZ object cache. Volume and selected output
persist. Playback does not auto-start at boot. Position is recorded on pause or
shutdown, but cross-boot resume is not implemented in this slice.

## Lifecycle and limits

Owner follow-up: add a small buffer to smooth playback. The decoder worker now
places a GStreamer queue before the selected PipeWire sink. Its limits are
250 ms of decoded audio or 256 KiB of payload, whichever is reached first;
whole buffers may cross a threshold by one buffer and allocator/thread overhead
is additional. No samples are dropped when full. There is no forced startup
prefill; decoding can run ahead of output to absorb brief stalls. End-of-file
drains queued samples, while Stop releases the pipeline and its queued data.
Pause retains the queue with the paused stream. Routing and disconnect policy
remain with the existing provider. This is an initial tuning choice, not a
universal hardware requirement or a solution to prolonged radio loss.

The additional queue is inside the existing worker memory limit. Its one
streaming thread uses GStreamer's blocking queue rather than a polling loop.
Physical latency and dropout improvement still require Deck measurements.
Reference: [GStreamer queue behavior](https://gstreamer.freedesktop.org/documentation/coreelements/queue.html).

The GUI sends bounded messages without waiting for decoding or pairing. Provider
status refreshes at 250 ms intervals; endpoint inventory every three seconds.
File opening has a ten-second deadline. Decoding runs in a separate worker;
an unresponsive worker is terminated after a twelve-second command or heartbeat
deadline, retaining the last reported position. Ordinary Resume continues the
paused stream rather than reopening it. Playback is audio-only and IP networking
is denied; arbitrary URLs are not accepted. Unexpected provider failures exit
so systemd can restart it instead of leaving a stale status loop.

Initial memory thresholds are test limits, not finalized installation footprint
contracts: PipeWire and WirePlumber each have 64 MiB high/128 MiB maximum limits;
the provider has 96/192 MiB. They are not reservations. Actual Deck CPU, memory,
power and underrun measurements remain required; simultaneous maxima would be
inappropriate for this hardware.

Debian packages add approximately 100 MB installed from approximately 23 MB of
downloads. This is a bootstrap change, outside the current shell/input-only
network update contract. The optional shell module fits the existing release
format without changing its minimum required file set, preserving older releases.

## Animation timers included

`guide_boot_runner.py` supervises up to 12 seconds of initialization and a
separate ten-second playback safety window. The renderer signals readiness only
after its first successful frame presentation and starts its eight-second timer
then. Termination gets two seconds of grace; systemd retains a 26-second outer
guard plus its stop timeout. Independent console cleanup remains in systemd;
the shell starts only after animation service completion. This separates timing
budgets; it does not claim faster initialization.

## Verification boundary

Evidence is in `build/debian-audio-0`. Virtual tests use real Debian services,
GStreamer and PipeWire with a software sink. Display and input are fixtures.
They cannot prove audible Deck output, speaker/jack routing, Bluetooth transport
stability or earbud compatibility.

The software checks cover 88 shell/input tests, twelve audio regression tests,
and seven animation lifecycle tests, plus native renderer checks. The virtual
acceptance covers explicit output selection, playback, volume control,
pause/resume, output removal, explicit replacement-output resume, Bluetooth
absence, and shutdown. A private-bus readiness check orders audio startup.
Output loss or explicit output replacement releases the isolated decoder worker
and its queue, retaining its last reported position. This avoids sending Resume
behind a stalled native teardown. A new worker handles explicit Resume on the
selected output. Physical testing must check this path with the actual earbud
before treating it as a finished interaction.
Position restoration starts the replacement stream muted, uses a non-flushing
seek while playing, then restores the requested volume. The queued PipeWire
path stalled with a flushing seek. The acceptance probe requires advancing
position after replacement, not merely a reported playing state. The isolated
worker still bounds any unexpected native stall.

Physical tests must cover the quiet left/right/both-channel sample, volume,
pause/resume, discovery and pairing with the actual earbud, explicit output
selection, disconnection without unintended speaker playback, navigation while
playing and normal shutdown. Earlier Bluetooth out-of-order packets remain a
tracked hardware concern until accessory testing establishes stability.

### First Deck test after an approved installation

1. Open Audio, choose an available local Audio output, then open Music files
   and play Guide-audio-test. Its six seconds cover left, right, then both.
2. Check volume keys and pause/resume; return Home while audio plays, then
   reopen Audio. Normal navigation and Power must continue working.
3. Put the earbud in pairing mode. Open Bluetooth earbuds, choose Find earbuds,
   then select the matching device. Record its exact model and any failure text.
4. Choose its entry under Audio output, then play the sample. Connection alone
   does not select it for playback.
5. Disconnect the earbud while playing. Confirm no unintended speaker output.
   Reconnect, explicitly choose the earbud output, and Resume. Record delay,
   audible glitches, and whether the menu stays responsive.
6. Shut down normally and return the seed for logs. Stereo channel checks are
   limited if only one earbud is present.

Sources: [WirePlumber Bluetooth setup](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html),
[BlueZ agent API](https://bluez.readthedocs.io/en/latest/agent-api/),
[PipeWire routing properties](https://docs.pipewire.org/page_man_pipewire-props_7.html).
