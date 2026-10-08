# Codec mute and ramp investigation

Status: investigation complete; candidate correction identified, not deployed or
physically validated. 25 September 2026. Supplements AUDIO_FLOW_AUDIT_0.md.

## Finding

The current H616 codec implementation lacks the analog initialization used by
the vendor driver. This is the strongest explanation yet for onboard silence,
but sound restoration has not been demonstrated. It does not establish faulty
speakers or exclude a second downstream fault.

The captured playback register 0x310 is 0x0015e81b in all three segments. The
codec register map uses REGCACHE_NONE, so these values are not a software cache.

| Control | Captured | Vendor ramp-enabled setup |
| --- | --- | --- |
| Left and right analog channel unmute, bits 12/10 | 0 / 0 | 1 / 1 |
| Analog ramp enable, bit 8 | 0 | 1 |
| Reference selection, bit 9 | 0, ramp output | 0, ramp output |
| Digital ramp enable, 0x31c bit 0 | 1 | 1 during playback |
| Ramp step, 0x31c bits 6:4 | 0 | 1 |

The current mixer switches operate DAC-to-mixer connections and line-out
amplifier enables. They do not operate the separate mixer-to-line-out mute
bits. Consequently, all visible mixer switches can be On while these controls
remain cleared. ALSA completion and advancing sample counters cannot detect
this analog-path condition.

## Primary-source comparison

Allwinner's H616 manual, printed pages 565-567, documents separate analog
unmute controls and analog/digital ramp enables. It does not explain enough
internal automatic sequencing to infer that RDEN alone makes other controls
irrelevant.

The vendor sun50iw9 driver explicitly sets both analog unmute bits during
initialization. In ramp mode it selects the ramp reference, enables the analog
ramp and chooses step 1. Playback enables the digital ramp and waits 25 ms
before enabling line-out. Shutdown disables the external amplifier before
lowering the digital ramp. Its non-ramp mode instead selects VRA1 and disables
both ramp controls. Our captured state matches neither configuration.

Sources:
- [Allwinner H616 manual](https://linux-sunxi.org/images/2/24/H616_User_Manual_V1.0_cleaned.pdf)
- [Pinned vendor driver, initialization and power events](https://github.com/orangepi-xunlong/linux-orangepi/blob/0cd0547ea405b84b5b60fbc92978ac1bc2b68055/sound/soc/sunxi/sun50iw9-codec.c#L799)
- [Matching vendor register definitions](https://github.com/orangepi-xunlong/linux-orangepi/blob/0cd0547ea405b84b5b60fbc92978ac1bc2b68055/sound/soc/sunxi/sun50iw9-codec.h#L825)

Local Linux 7.2.7 sun4i-codec.c defines LMUTE, RMUTE and RAMPEN but never uses
them after those definitions. Its H616 ramp DAPM widget only controls RDEN,
with no event callback. Neither the platform probe nor H616 component supplies
an analog initialization callback. The reviewed ROCKNIX suspend/supply patch
also does not add that initialization.

This comparison uses the related vendor H616 implementation. The RG35XX H's
H700 uses the H616-compatible driver, but equivalent behavior on this physical
board must still be verified. Do not present vendor source as H700 bench proof.

## Proposed implementation and acceptance

Implement an H616-specific codec initialization path, preserving other SoCs.
Use masked updates to set LMUTE, RMUTE and RAMPEN, select the ramp reference,
and set the documented vendor ramp step. Keep digital ramp ownership with
DAPM, and review its settling and amplifier ordering rather than issuing raw
register writes from a shell, application, UCM recipe or the diagnostic gateway.
Check every update result and reapply settings after any reset/power-loss path.

For comparison only, keeping all other captured playback fields unchanged,
these settings predict 0x310 = 0x0015fd1b and 0x31c = 0x00000011 while active.
Those complete words must not be used as unconditional register writes.

Before deployment, build the driver and inspect the patch to ensure that gain,
FIFO state, sample counters and unrelated pins remain untouched. Preserve the
known boot image for rollback. The installed link currently cannot deploy
kernel changes; a kernel test build requires the established seed workflow.

Physical acceptance: collect registers during the same low-level left/right/
both test, obtain audible confirmation, then check normal application playback,
stop/start and cold boot. Listen for startup/shutdown pops. Later verify resume
if a codec power-loss/resume path is introduced. Fix GPIO report truncation so
PI5 is present in the next evidence set. No unchanged listening retest is useful.

## Evidence retained

Private research copies are under E:/DGttG/private-recovery/audio-ramp-research;
physical evidence is audio2-probe-result.json and audio2-inspect-after.json in
E:/DGttG/private-recovery/live-link. No device register, kernel or seed changes
were made during this investigation.

## Implemented candidate: audio-path-3

The H616-only patch is board/rg35xxh/debian/h616-analog-ramp.patch.
It sets the analog unmute/ramp fields at component probe and again before
DAPM ramp power-up, with checked masked updates. DAPM retains ownership of
RDEN. A 25 ms wait follows each digital ramp edge. Source sequencing places
speaker enable after the ramp's power-up event and speaker disable before
ramp power-down. Existing gains and the 700 ms speaker delay are unchanged.
This does not add system suspend support; a future reset/resume implementation
must preserve the same initialization contract.

The codec is a module. The new ARM64 module compiled successfully and matches
the installed module's kernel release/vermagic and dependency list. No full
kernel-image replacement is needed. The original installed module was extracted
from the verified audio-path-2 image for rollback. Build preparation now applies
the patch on future source preparations.

The bounded GPIO capture limit was increased from 2 KiB to 8 KiB, within the
existing 24 KiB total report limit. A regression test covers a speaker GPIO
beyond the previous cutoff; all 13 board diagnostic tests pass. Patch code-style
checks pass with submission metadata checks excluded. These checks do not
validate physical sound, analog settling, module load on the handheld or pops.

Candidate payload and hashes: build/debian-audio-3/candidate.json.
State: BUILT_NOT_INSTALLED. The reader reported zero media capacity at preparation
time. Deployment must use a fresh returned-card capture, preserving current
network/device state, and verify written contents before the physical test.

## Installation, 25 September 2026

Audio-path-3 is installed on the verified Transcend seed. Full root-partition
readback SHA256: A081184B8D854074F24929963679C3B0B4F837A120C5B6A90B730CADFECC1C1B.
Boot and data partitions match the fresh recovery capture. Exactly two regular
files changed; 21,215 other regular files and existing symlinks were verified
unchanged. All card handles closed. Installation record:
build/debian-audio-3/installation.json. Physical boot/audio acceptance pending.


## Physical result: audio-path-3 remains silent

The owner heard no sound during any segment of the left/right/both direct
speaker probe after the update. The probe completed with returncode 0 and
restored=true. All three active register captures match the proposed values:
0x310=0x0015fd1b, 0x314=0x00220d33, 0x31c=0x00000011. PI5 (gpio-261,
allwinner,pa) is high during each segment, and the expanded GPIO capture is
not truncated. The sample counter advances across all segments.

This confirms that the correction took effect but did NOT restore speaker
output. Missing analog initialization is not established as the root cause;
these controls being set is insufficient. Do not mark the audio defect closed
or repeat an unchanged listening test. Further isolation must cover actual
signal delivery to the DAC and the board's analog output/amplifier path.
Register enables alone do not establish electrical signal or amplifier power.

Evidence: audio3-path-before.json, audio3-probe-request.json,
audio3-probe-result.json, audio3-inspect-after.json under the private live-link
evidence directory. This result supersedes the earlier leading-cause inference.
