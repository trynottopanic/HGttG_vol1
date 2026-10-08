# Audio-path-5 format isolation

Status: installed and readback verified on 2026-09-25 with UI schema 1;
physical acceptance pending.
Continues AUDIO_CODEC_SOURCE_PROBE_0.md. Internal tone was physically audible on
path-4 while ordinary file playback was silent. No new root cause is claimed.

## Source review

The H616 device tree selects DMA request 6 and the codec driver uses TXDATA at
0x20. The DMA driver supports 16- and 32-bit peripheral accesses. The codec
selects two-byte access for S16 and four-byte access for S32; the current source
review does not justify changing either automatically. FIFO modes 01 and 11
have equivalent documented 16-bit packing. Test the two supported paths before
changing global playback policy or DMA wiring.

The path-4 player reported I/O error after switching to the internal source;
its final PCM was closed. Source switching may remove the normal FIFO request
stream, but that explanation is not established. Path-5 avoids switching a
running player's source, so a format-specific error can be interpreted without
that confound.

## Fixed test sequence

The existing explicit idle-only speaker-probe runs three independent stages:

1. Four seconds of stereo 440 Hz S16_LE, direct hw:CARD=Codec,DEV=0.
2. Four seconds of the same normalized waveform in S32_LE, same direct device.
3. A separate internal sine stage, with zero PCM and attenuated DAC gain.

A one-second interval follows each stage, in addition to hardware startup time.
There is no plughw conversion. S32 uses the exact S16 samples shifted left by
16 bits, so format changes do not silently change signal amplitude. File tones
have 50 ms fades. Both speakers carry the same signal during format comparison.

Each player is reaped before the source changes. Each stage records signal
identity/format/amplitude, two timed board snapshots when possible, player exit
observation, return code, bounded error output, and a timeout flag. A failed
file stage does not skip the other format. A mixer/source reset failure aborts
further stages. Recovery always forces Normal before restarting audio services.

The internal stage can fail as a PCM transfer while still yielding useful
analog evidence. Interpret its return code and source readback separately from
what the owner hears; do not report it as successful file playback.

The worker is bounded by a 60-second service timeout plus existing restoration.
Normal applications, gains, routing and the kernel module are unchanged. No
new background monitoring is introduced.

## Validation and deployment

21 focused tests passed. All 52 deployment tests passed under the installed
ARM userspace with QEMU. Tests cover exact sample equivalence, direct device
selection, early failure, timeouts, cleanup and restoring Normal before service
restart. Service validation passed; permission warnings arose from the Windows
source bind mount. Installed files will use mode 0644 on the Linux filesystem.
These checks do not establish physical S16/S32 behavior.

### First connected run, 2026-09-25 20:40 UTC

The Deck reported the intended UI schema 1 release and an idle local audio
output. Both file-s16 and file-s32 exited with code 0, with RUNNING PCM snapshots
and their requested formats. The internal-sine stage exited with code 1 and
`pcm_write:2178: write error: Input/output error`; its sampled PCM was closed
while the diagnostic-source register remained 0x200. Thus the internal-stage
transfer error also occurs without changing source under a running player.
The owner heard one tone and subsequently selected "Only the final tone".
The initial report explicitly could not identify the stage because the start
was unclear. Record final-tone identification as provisional, not a conclusive
format comparison. Neither successful file transfer nor an internal-source
setting establishes audible output. Further listening comparisons need isolated
stages with a clear start indication, rather than this ambiguous sequence.

Restoration returned success, explicitly selected Normal, and completed the
service-restoration commands. Overall probe state is failed because the internal
stage failed; the successful file-stage results remain independently available.
Evidence: E:/DGttG/private-recovery/live-link/probe-result-20260925-164141.json.

Payload: deploy_board_diagnostics.py, audio_probe_sequence.py, and the revised
service unit. The deployment manifest requires the existing audio-path-4 codec
hash. Canonical installer includes the new helper. Fresh-card rebase/install
scripts are prepared in build/ for audio5. Candidate hashes are in
build/debian-audio-5/candidate.json. The paired updater remains shell-only, so
this provider update uses the seed workflow.

Next acceptance: identify which of the first, second and third tones are
audible; correlate the first two with RUNNING PCM, format and FIFO register
settings and their own player results. Confirm source Normal and service
recovery afterward. If S32 works and S16 fails, investigate the width/packing
path before adopting a compatibility workaround.
