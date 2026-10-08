# Working MuOS build versus Debian speaker playback

Status: analysis checkpoint, 25 September 2026. No new build installed or tone
played. The owner confirms speakers worked on the previous MuOS-derived build.

## Finding

The most likely fault location remains normal FIFO/DMA sample delivery in the
new kernel. The exact working binary exposes concrete differences: DMA burst
size, S16 memory-side transfer width, FIFO programming and request policy.
These are candidate incompatibilities, not a proven single-register fault.
Both S16 and S32 failure weakens an S16-only width or packing theory.

The earlier apparent twofold clock discrepancy is not sufficient evidence of a
physical clock error. The kernels account for PLL dividers differently. Do not
blindly double the codec clock. Ramp/line-out sequencing is a separate remaining
candidate. Our prior ramp patch followed related vendor source, not the exact
working MuOS binary.

## Reference and evidence quality

The September 21 full pre-Debian seed backup was opened read-only with journal
replay disabled. Its userspace has modules for Linux 4.9.170. The kernel identifies
itself as 4.9.170, build #274, dated 5 July 2024. It contains sunxi_internal_codec,
sunxi_aaudio and the vendor PCM/DMA implementation. Current GuideOS uses
7.2.7-guide-debian2, sun4i-codec, generic ALSA DMAengine PCM and sun6i-dma.

The analyzed 17,459,208-byte kernel and relevant sun50iw9 device tree were checked
byte-for-byte against the full backup, not merely assumed to be matching copies.
The entire 64 MiB boot partition also matches the earlier partition4.img.
Kernel SHA256: 5ff013ab1b575418d30eda5ea53b67fb549bf380edce0bfbde23cccd213ec759.
Device tree SHA256: 3668b321a1b40a7d8e70c052cb47ec09d8aba8a7aed2bcc2c949037b16d52187.

Kallsyms recovery allowed disassembly of the actual initialization, format,
prepare, trigger, clock, ramp and PCM routines. Recognizable register-update
calls and related symbol references agree in the inspected disassembly. This
is static binary analysis, not a new capture of the old system's active state.
The relevant tree is at backup offset 17,956,864; unrelated embedded Rockchip
trees were excluded. Runtime bootloader edits remain unmeasured.

Private evidence: E:/DGttG/private-recovery/muos-audio-comparison, including
identity.json, muos-1120000.dts, recovered muos-kernel.elf and the vendor codec,
PCM, platform, ramp and machine disassembly files. The analysis tool required
skipping optional release-date database logging; symbol recovery was unchanged.
The temporary read-only mount no longer existed after the interrupted WSL
session. No backup, seed or running Deck configuration was changed.

## Implementation differences

| Area | Working MuOS-derived implementation | Current implementation | Significance |
| --- | --- | --- | --- |
| Application path | Direct ALSA vendor card; old helper enables LINEOUT, OutputL Mixer DACL, OutputR Mixer DACR and SPK | Applications use GStreamer/PipeWire; isolated tests directly use onboard hardware | Application/framework differences cannot explain the isolated failure. |
| DMA destination/request | 0x05096020, request 6 | Same reviewed destination and request | No evidence for changing either address or request. |
| DMA bursts | Platform initializes source and destination maxburst to 4 | Codec maxburst 8; DMA driver defaults source burst to 8 | Concrete difference affecting both tested formats; strongest narrow transfer candidate, but validity of either setting is not disproved. |
| S16 transfer width | PCM copies destination width into source width: 2 bytes on both sides | DMA driver defaults unspecified source width to 4 bytes; destination is 2 | Real difference; supported width conversion and S32 silence weaken it as the sole cause. |
| S32 transfer width | Physical sample width gives 4 bytes on both sides | Expected 4 bytes on both sides | Actual current DMA descriptors have not been captured. |
| S16 FIFO mode | Writes both mode bits to 11 | Writes bit 24; observed mode 01 | H616 manual describes these as equivalent, so this alone is not a demonstrated bug. |
| S32 FIFO mode | Clears both mode bits to 00 | Clears bit 24; observed mode 00 | No observed S32 mode mismatch. |
| FIFO prepare | Flushes FIFO, writes 0x0e to status register 0x14, resets counter 0x24 | Flushes, sets threshold 15, FIR and zero-on-underrun; no explicit status/counter reset | Clear difference; counter reset improves measurement, not inherently sound output. |
| FIFO request policy | Reviewed codec routines leave threshold/DRQ-clear count alone; documented reset threshold 64 | Explicit threshold 15 and DRQ-clear count 3 | Different policy. Old runtime/bootloader state is not captured. Previous threshold correction did not restore audio. |
| Processing | Exact binary disables DAP, initializes digital attenuation to zero; no HPF enable in that initialization | Captured DAP disabled, normal-test attenuation 5 | The earlier related vendor source enabled HPF but is not identical to this kernel. No basis to call HPF-off the cause. |
| Ramp/line-out | Tree selects ramp index 5; driver waits using a clock-dependent table before enabling line-out | Ramp index 1, fixed 25 ms wait; UCM enables line-out before playback | Concrete sequencing difference; second lead, despite an audible internal oscillator. |
| Speaker GPIO/delay | PI5 active high, configured delay 100 ms | Same pin/polarity, existing 700 ms delay | Wrong GPIO or simply too-short amplifier delay is poorly supported. |
| Supply | AVCC 1.8 V, amplifier CLDO1 | Captured AVCC 1.8 V and speaker supply requested at 3.3 V | No new evidence for a supply change; electrical voltage still unmeasured. |
| Gain | Initial line-out 31, digital attenuation zero; app can change it | Normal test line-out 27, attenuation 5 | Reduced level, but known samples and audible attenuated internal sine argue against total silence from gain alone. |
| TX hub | Tree contains tx-hub-en and driver exposes a setter | Ordinary current playback has hub off | The property does not prove the old running system enabled hub mode. Do not enable it solely to match a property name. |

## Clock discrepancy: important qualification

The vendor machine callback selects 24.576 MHz for the 48 kHz family and applies
the tree's codec pll-fs=4. The codec set_pll callback sets its module clock to
half the supplied output frequency, implying a software request of 49.152 MHz.
Its ramp routine recognizes 49.152 or 45.1584 MHz. Current GuideOS requests and
reports 24.576 MHz for our test.

However, the exact vendor PLL routines and current CCU source use matching
tuning values: raw N=39, P=4 and SDM pattern 0xc001eb85. Current table values
n=40/m=5 include field offsets. The vendor reports 98.304 MHz for that PLL
setting; the current clock model applies a fixed post-divider of two and
reports 49.152 MHz. Software rates are therefore not interchangeable physical
measurements. Actual parent mux/divider register comparisons are necessary.
The approximately correct sample-counter cadence also argues against an
unexamined rate-doubling change.

Primary context: [H616 audio PLL divider modeling](https://lists.infradead.org/pipermail/linux-arm-kernel/2024-October/972360.html).
The exact local CCU source and working binary supplied the comparison above.

## Revised next step

1. Prioritize an H700-only vendor transfer-profile comparison: burst 4, actual
   source/destination widths, full FIFO-mode programming and request policy.
   Capture actual DMA configuration in the same run. A profile comparison can
   localize the regression but cannot identify the necessary individual fix.
2. Keep exact working-build ramp/line-out sequencing as the alternative. Do not
   re-label the already-tested unmute bits as missing.
3. Resolve clock parent/divider equivalence before any rate change. The reported
   twofold rate difference alone is not enough.

Keep waveform, gain and output fixed in any later experiment and verify recovery.
If a vendor profile succeeds, isolate its necessary change before adopting it.
If it fails, obtain active state from the working build or defer speaker work;
do not continue issuing unchanged listening tests. This analysis does not claim
that a repair is ready or require another physical test now.

## Follow-up experiment

The owner selected a narrower first test: DMA bursts and transfer widths only.
[Audio-path-9 protocol](AUDIO_DMA_TRANSFER_TEST_0.md) records that implementation
and its acceptance checks. FIFO, clocks and ramp remain unchanged for this test.
The analysis above remains historical evidence, not a claim of a successful fix.
