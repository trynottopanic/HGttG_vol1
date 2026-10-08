# Audio-path-8: measure the DMA source buffer

Current investigation checkpoint: [consolidated cause review and three leading
hypotheses](AUDIO_CAUSE_REVIEW_2026_09_25.md). No additional listening test is
requested until a discriminating measurement or working reference is prepared.

Status: installed and full readback verified on 2026-09-25 at 22:02 UTC.
Boot and user-data regions were unchanged. Physical isolated S16 measurement
completed at 22:15 UTC; the owner reported no audible tone.

Evidence: E:/DGttG/private-recovery/live-link/probe-result-20260925-181550.json.
The sampled 4096-byte kernel-buffer prefix matched the generated waveform:
3688 nonzero bytes and FNV-1a 4026200373 on both sides. Configuration was
48 kHz, stereo, 16-bit samples, 96000-byte buffer, DMA destination 0x05096020
and two-byte peripheral width. The player exited zero; restoration succeeded,
Normal source was restored and the buffer probe was disabled.

This establishes nonzero expected data at the sampled kernel-buffer boundary,
not delivery of that data to the converter. The active snapshots also retain
RUNNING PCM, Normal source and FIFO threshold 15. Audible playback remains
failed. Next investigation: actual DMA channel/descriptor configuration and
normal FIFO/converter delivery, including source address progression, request
selection and transfer width. The current aggregate reports driver intent,
not hardware descriptor readback; repeating the same tone adds little evidence.

The live Audio-Path operation at 2026-09-25 21:46 UTC confirmed the stored WAV
is nonzero: both channels peak 3276 and RMS 1760.485, at 24 kHz. Isolated raw
tone generation separately records its waveform hash and normalized peak.
Those earlier observations covered the source file, not the kernel buffer.
Before audio-path-8, the remote API exposed only counters/registers here.
Reading the transmit register as zero is not valid evidence of zero samples:
it is a write-only data port.

The added H616-only ALSA control arms one aggregate capture on the next playback
START. It is disabled by default, auto-disarms, and examines at most the first
4096 bytes of the ALSA runtime DMA buffer. It returns captured/bytes/nonzero-byte
count/FNV-1a checksum, sample width/channels/rate, buffer size, and the driver's
configured DMA destination and width. No raw audio, arbitrary addresses or
background capture are exposed. The short bounded capture runs under a spinlock;
result reads and arming use the same lock. Resumes do not recapture.

The existing isolated diagnostic computes the matching source prefix summary,
arms immediately before aplay, reads the aggregate afterward and records both
sides plus a match flag. An absent capture is unavailable, never success. The
finally path disarms and restores Normal even after failure; service recovery
forces both states before restarting application audio. The countdown and
single-tone behavior remain unchanged.

Interpretation: a matching checksum and counts provide evidence that the known
waveform reached the sampled kernel DMA-buffer prefix. They do not validate the
whole stream, physical bus delivery, or the converter input. Configured DMA
destination is driver configuration, not a hardware descriptor readback. A
mismatch needs examination of startup buffer placement/timing before declaring
sample corruption. Zero/nonzero evidence is useful independently of checksums.

Validation: ARM64 module compiled, checkpatch reported zero errors/warnings.
A C harness executes the actual capture helper over S16, S32 and silent waveforms
at three buffer sizes, checking the 4096-byte bound, disabled default, one-shot
behavior and all metadata against independently calculated Python summaries.
Diagnostic tests check fingerprint comparison, unavailable captures, arming
failure, cleanup and Normal restoration when disarming fails.

The prepared image passed 348 ARM userspace tests (52 connectivity, 63
deployment/diagnostic, 135 input, 7 UI schema and 91 shell), release smoke,
service validation, installed UI/overlay checks and filesystem validation.
The fresh-seed rebase preserved 21,264 original regular files outside the
three-file payload and checked the original symlinks. Capture and image hashes,
and the eventual write result, are recorded in build/debian-audio-8.

Artifacts are in build/debian-audio-8. Installing the module and paired probe
worker requires the seed; the live shell-only updater cannot deliver them.
The previous audio-path-7 module is the rollback baseline. The isolated S16
test preserved the same waveform, volume and output settings.
