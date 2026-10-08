# Audio-path-4: isolate FIFO delivery from codec output

Status: built and tested locally, not installed. Speakers remain silent on
physically tested audio-path-3. This is a diagnostic revision, not a claimed fix.

## Investigation

The captured FIFO mode is 01 for 16-bit data. The H616 manual specifies the
same packing for 01 and 11, so the vendor's use of 11 is not evidence that our
01 packing is wrong. TXDATA offset 0x20, sample width, stereo selection and
48 kHz clock selection agree with the reviewed driver/manual. FIFO occupancy
and counter movement do not establish that the actual samples are nonzero.
Reading TXDATA as zero is not proof that DMA wrote zeros to a transmit register.

DAC debug register 0x28 is zero: normal FIFO source, no forced-silence pattern,
no debug clock selection. DAP processing at 0xf0 is disabled. The captured
speaker supply is requested at 3.3 V, PI5 is high during playback, and the
headphone jack control reports absent. These are software observations, not
measurements of physical voltage or analog signal. Upstream RG35XX routing
also uses PI5, with a shared speaker/headphone analog multiplexer. There is no
new evidence justifying a GPIO or voltage change.

References:
- Allwinner H616 User Manual, FIFO mode and DAC debug register, printed pp. 549-552:
  https://linux-sunxi.org/images/2/24/H616_User_Manual_V1.0_cleaned.pdf
- Board routing: https://www.spinics.net/linux/fedora/linux-sound/msg19181.html

## Diagnostic change

H616-only ALSA control `DAC Diagnostic Source` exposes the documented four
source choices. It only changes bits 10:9 of register 0x28; the driver initializes
it to Normal on load. It does not change debug clocks or modulator mode.

The existing explicit, idle-only speaker-probe operation now runs ten seconds:
left/right/both file tones over the first six seconds, followed by zero-valued
PCM. At 6.8 seconds the worker selects the hardware sine, with DAC volume 48
instead of 58 to approximately match the earlier tone level. At 8.4 seconds it
captures the registers and mixer as segment `internal-sine`. Expected source
field: 0x28 bits 10:9 = 01. This source bypasses WAV decoding and FIFO sample
content; PCM still runs to keep the clock and power path active.

Normal source is explicitly restored before services restart, including via
ExecStopPost after an interrupted worker. Failed source restoration leaves the
recovery plan and does not restart normal playback. Full saved mixer restoration
still runs. Boot starts with Normal. The existing service timeout remains the
outer bound; there is no background or automatic tone generator.

The built module and updated worker must be installed together using the seed
workflow. No kernel/provider payload is sent through the shell-only updater.
The existing analog initialization is retained to avoid changing two independent
hardware conditions during this comparison.

## Interpretation and acceptance

- File tones silent but internal sine audible: prioritize sample delivery/FIFO
  content; the downstream path has demonstrated audible output in this setup.
- Both silent with internal source register confirmed: focus on codec output,
  reference/ramp behavior, mux/amplifier and board power. This does not prove
  hardware damage or exclude a clock/power issue shared by both paths.
- Source activation or restoration fails: diagnostic invalid; inspect saved
  failure evidence rather than infer a hardware result.

Verify the final source returns to Normal, digital ramp powers down, services
recover and no unexpected tone remains. Hardware response and audible level
remain unverified until the next physical run.

## Validation

ARM64 module compilation and patch code-style checks pass. Sixteen diagnostic
tests pass, including a full mocked sequence, zero PCM tail, source-selection
failure, cleanup ordering, and suppression of service restart when source reset
fails. These do not simulate an H700 codec or prove acoustic output.

Artifacts: build/debian-audio-4/candidate.json and h616-diagnostic-source.patch
in board/rg35xxh/debian. The installed audio-path-3 module is the rollback base.

## Installed 25 September 2026

Audio-path-4 installed and full root readback verified:
D059CA420D3ED15A5D88267B20920BC0ED180D416F7DAADF7797B2B4A96601F3.
Boot and data partitions unchanged from fresh capture; 21,217 other root files
verified unchanged. Recovery capture: private-recovery/audio4-return-20260925-155203.
Card handles closed. Physical test pending; supersedes built-not-installed status above.


## Physical result, 25 September 2026

The owner heard ONLY the final internal tone; the earlier file-driven tones
and normal application test were silent. In the final capture, register 0x28
is 0x00000200, confirming internal sine selection. Normal/file segments have
0x28=0. During those segments PCM is RUNNING and hardware/application pointers
advance. The same corrected analog controls are active throughout.

This demonstrates audible output through the codec and downstream board path
under internal-source conditions. It substantially redirects investigation to
normal sample delivery, FIFO/data format and the normal-source digital path.
It does not validate every amplifier channel, all analog behavior or the prior
mute/ramp correction as necessary.

Caveat: aplay returned 1 with pcm_write Input/output error, and PCM was already
closed in the internal-sine snapshot. DRQ was then disabled (0x10=0x01604f00).
The internally generated tone does not require FIFO content, so the audible
result is still useful; this is NOT a successful ten-second PCM test. The error
must be investigated, including whether switching away from FIFO removes DMA
requests. A later diagnostic should separate playback stages and record player
exit time instead of treating this error as a completed PCM sequence.

Restoration succeeded, 0x28 returned to 0, and fresh inspection confirms all
three normal audio services active with zero restarts. The immediate after
snapshot still had RDEN=1, so it does not demonstrate completed delayed DAPM
power-down. Do not label that snapshot a fully settled idle state.

Evidence: audio4-before.json, audio4-probe-request.json,
audio4-probe-result.json and audio4-inspect-after.json in the private live-link
directory. A Wi-Fi deep-power warning is present in this boot, but is not
established as related to the audio fault.
