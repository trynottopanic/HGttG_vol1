# Speaker silence: consolidated cause review

Follow-up: [exact MuOS working-build comparison](MUOS_AUDIO_COMPARISON_0.md)
records concrete transfer and ramp differences, and qualifies the apparent
clock-rate mismatch. Use its revised priorities for the next investigation.

Status: investigation checkpoint, 25 September 2026. Owner requested a broad
review and the three most likely causes before another physical test. No new
tone, configuration change or installation was performed for this review.
The read-only live Inspect request failed with no route to host; conclusions
use retained physical captures, the exact local kernel tree, installed-payload
records, diagnostic source, the vendor source and primary documentation.

This covers the plausible failure classes across the implemented path. It is
not an exhaustive electrical fault diagnosis. Rankings are qualitative working
hypotheses, not established defects or numerical probabilities. The evidence
separates the normal playback path from the internal oscillator much more
strongly than it separates the three remaining hypotheses from one another.

## Evidence that changes the priorities

- The isolated internal codec sine was heard. This establishes an audible
  downstream path under that test's conditions, not that both channels and all
  analog states are independently healthy.
- Isolated S16 and S32 file playback were both reported silent. These bypass
  the Guide application, GStreamer, PipeWire, WirePlumber and network media.
- Audio-path-8 S16 was silent even though the first 4096 bytes of the actual
  kernel runtime buffer matched the generated waveform: 3688 nonzero bytes,
  FNV-1a 4026200373. This verifies a prefix at START, not the entire transfer.
- In that run, between snapshots about one second apart, ALSA hw_ptr advanced
  47936 frames and the codec input counter advanced 95888 samples. This is
  approximately the expected stereo 48 kHz relationship. Independent snapshots
  are not cycle-synchronous. Counter movement supports FIFO input activity,
  not correct received sample values or successful analog conversion.
- Source was Normal (0x28=0), DAC enabled, DAP disabled, analog controls
  0x310=0x0015fd1b, mixer 0x314=0x00220d33 and ramp 0x31c=0x11. The analog
  words match the earlier audible internal-source capture.
- Mute/ramp initialization and the FIFO threshold correction reached hardware
  but did not restore sound. Do not re-promote either as the diagnosed cause.
- Restorations succeeded. Audio-path-8 is an observation revision, not a fix.

## Three leading hypotheses

### 1. H700 normal digital playback requires configuration the driver is missing

Scope: FIFO sample interpretation and the digital path between the FIFO and
the internal test-source insertion point. The oscillator bypasses normal FIFO
samples; that difference fits all the confirmed audible/silent results.
H616-compatible operation on H700 may have an undocumented requirement or a
driver integration regression. A missing normal-path enable, reset sequence or
sample interpretation condition is more plausible than another application fix.

Against: the documented S16/S32 settings, source selection, DAC enable, DAP
bypass and clock rate look consistent. No specific wrong bit has been found.
The vendor uses FIFO mode 11 for S16 whereas this driver uses 01, but the
manual says these are equivalent. That difference alone is not a fix rationale.
S32 also failed, reducing the likelihood of an S16-only packing defect.

Best discriminator: compare the same board running a known-working OS using
the same direct waveform and capture its active codec, clock and DMA state.
Use an already available known-working card, or a spare; preserve this seed.
If no such reference is available, a reviewed, bounded CPU-fed FIFO diagnostic
could separate the normal codec path from DMA, but this is not implemented
and requires careful timing, exclusive ownership and automatic restoration.
Do not replace normal playback with an unreviewed userspace register loop.

### 2. DMA transfers the wrong data despite a correct CPU-visible buffer

Scope: actual descriptor source address, source advancement, destination,
request routing, transfer width/packing or DMA visibility of sample memory.
Our current probe reads the CPU-visible buffer and codec driver's intended
destination/width; it does not inspect the running DMA descriptor or bus data.
Thus a matching prefix cannot close this boundary.

Against: FIFO input and PCM counters advance at compatible rates. The local
tree uses request 6, TXDATA 0x05096020, a linear memory source and fixed I/O
destination in cyclic descriptors. Generic ALSA configuration propagates the
codec width; the DMA driver supports both tested widths. Buffer allocation
uses the managed DMA path and the DMA device, lowering the priority of a
simple missing manual cache flush. No concrete descriptor defect was found.
Totally wrong request routing or a completely stalled engine is less likely
than a subtler payload/address/packing problem.

Best discriminator: one bounded, owner-requested capture of actual active DMA
configuration, descriptor addresses and source progression correlated with the
ALSA DMA buffer and codec counter. Report address comparisons/aggregates where
possible; no permanent high-rate logger or unrestricted remote register API.
This requires additional instrumentation; the current gateway cannot do it.

### 3. Normal playback startup leaves the codec in a different effective state

Scope: FIFO flush, clock/reset, DRQ, DAC/ramp and amplifier sequencing, including
an underrun or internal state that is not represented by the later register
snapshot. The internal test has a material confound: its PCM writer errors and
closes, while the internal tone remains audible. Audible internal playback
therefore does not establish complete state equivalence with RUNNING PCM.

Against: the ramp delay and 700 ms speaker startup delay are already present;
four-second file tests and earlier six-second channel tests were silent
throughout. Snapshots show enabled paths. An ordinary short settling delay is
unlikely to explain the whole failure. This is the weakest of the three.

Best discriminator: capture a bounded timestamped startup/stop transition
trace, including driver trigger, FIFO flush, DRQ, DAC/ramp and amplifier events.
Compare with a working reference before changing delays. A controlled primed
start is a later experiment, only if the trace indicates a relevant ordering
problem. Sticky underrun status alone is not evidence of sustained starvation.

## Other causes reviewed

| Failure class | Evidence and disposition |
| --- | --- |
| Silent/wrong source file | Stored WAV hash and nonzero amplitude verified; isolated raw generator is independent. Strongly reduced. |
| Decoder/filter corruption | Earlier exact ARM decoder test matched 288000 samples; isolated raw playback bypasses it. Cannot explain all failures. |
| Guide command dispatch or wrong application state | Direct aplay completes with active PCM; application status defects are separate. |
| PipeWire/WirePlumber routing, software mute or UCM | Services are stopped for the probe; explicit onboard hardware device and mixer settings are used. These may cause separate app faults but do not explain isolated silence. |
| Wrong output/card, HDMI or Bluetooth selection | Explicit hw:CARD=Codec,DEV=0; onboard codec registers and counters change. Strongly reduced. |
| Low volume | Known nonzero 12% peak waveform; normal DAC attenuation is lower than the audible internal test. Similar intended effective test levels. Exact acoustic equivalence is unmeasured, but simple gain is low priority. |
| Analog mute/ramp bits | Corrected values read back during silent playback and match the audible internal case. Simple missing unmute is no longer a leading cause. |
| Speaker GPIO, regulator, jack detection | PI5 high, speaker supply requested, headphone absent in captures; internal sine audible. Electrical voltage has not been measured, so intermittent/state-dependent hardware remains possible. |
| Stereo cancellation or channel swap | Raw route bits show Stereo, reversed mixer off. Earlier left-only and right-only segments also silent. DAPM's Mono Differential route text is not a hardware selector readback. |
| Wrong sample rate/clock | 24.576 MHz codec clock reported at 48 kHz; pointer and counter rates broadly agree. Missing physical waveform measurement remains a limit. Gross rate error is low priority. |
| Unsupported sample format/endian/sign | Both direct S16_LE and left-aligned S32_LE were accepted and silent; generator uses explicit little-endian packing. Only S16 has the new kernel-prefix measurement. |
| FIFO threshold | Fixed 79-to-15 mismatch confirmed in hardware; silence remained. This correction alone is not the solution. |
| CPU load, scheduling, queue size, RTKit | Direct test fails outside the application queue; recorded low CPU load and progressing PCM. Increasing buffering is unsupported as a silence fix. |
| Constant underruns | Sticky underrun flag exists but is not cleared/re-measured within a controlled interval; advancing counters cannot alone quantify starvation. Retain within sequencing/DMA investigation, not a diagnosis. |
| DAP/debug forced silence or audio hub diversion | Captured DAP and debug registers zero in normal playback; DPC hub bit clear. No observed forced-silence state. |
| Completely broken speaker/amplifier | Contradicted by audible internal sine, with the caveat that both speakers were not independently confirmed. |
| Stale build/failed installation | Root readback and payload manifest verified; live buffer control and capture demonstrate new instrumentation running. Exact active DMA descriptor/device-tree state still lacks full export. |
| Diagnostic itself creates the silence | Silence predates buffer instrumentation; isolated selection and countdown remove the earlier multi-tone identification ambiguity. Internal PCM error remains a known confound. |
| Suspend/resume, network or storage speed | Not required to reproduce this fresh-boot local-file failure. No evidence prioritizes them. |

## Stop point and next-test gate

Keep audio-path-8 and its recovery evidence. No speculative audio-path-9 build,
gain increase, broad driver replacement or additional identical tone is justified
by this review. Speaker playback remains unresolved; Bluetooth has separate
prior owner-confirmed working evidence, not a fresh certification today.

On resumption, prefer one known-working same-board reference capture. Otherwise
prepare the bounded DMA and transition evidence together, before asking for
another listening session. A new test must distinguish hypotheses, verify
restoration and provide more than another successful aplay exit. Further work
can be deferred without pretending the speaker feature is complete.

## Evidence and primary references

Private captures in E:/DGttG/private-recovery/live-link:
probe-result-20260925-171143.json (audible internal),
probe-result-20260925-171423.json (silent S16),
probe-result-20260925-171557.json (silent S32),
probe-result-20260925-174411.json (threshold correction),
probe-result-20260925-181550.json (buffer match, silent S16).
Owner listening responses are recorded separately in the conversation and
the linked investigation documents; player exit is not acoustic acceptance.

Reviewed local sources: build/debian-audio-8/sun4i-codec.after.c;
package/guide-deploy/audio_probe_sequence.py and deploy_board_diagnostics.py;
Linux 7.2.7 drivers/dma/sun6i-dma.c, sound/core/pcm_dmaengine.c,
sound/soc/soc-generic-dmaengine-pcm.c and sun50i-h616.dtsi;
private-recovery/audio-ramp-research vendor codec and manual copies.

- [Allwinner H616 manual](https://linux-sunxi.org/images/2/24/H616_User_Manual_V1.0_cleaned.pdf), audio chapter: source, FIFO, counter, debug and analog controls.
- [H616 codec implementation submission](https://lists.infradead.org/pipermail/linux-arm-kernel/2024-October/971312.html), register and route differences; not evidence of a specific current bug.
- [H616 route correction](https://www.spinics.net/lists/devicetree/msg773416.html), board/component ownership distinction.
- [Vendor initialization](https://github.com/orangepi-xunlong/linux-orangepi/blob/0cd0547ea405b84b5b60fbc92978ac1bc2b68055/sound/soc/sunxi/sun50iw9-codec.c), local pinned copy reviewed; not proof of H700 physical equivalence.
