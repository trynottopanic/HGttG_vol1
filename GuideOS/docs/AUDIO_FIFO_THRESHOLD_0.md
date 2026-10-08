# Audio-path-7: correct the H616 FIFO threshold mask

Status: installed and readback verified on 2026-09-25 at 21:40 UTC;
audibility remains unverified. The image also includes boot-reconnect-1 Wi-Fi.

Physical result, 2026-09-25 21:44 UTC: the owner reported no audible sound for
isolated file-s16. Both active snapshots read FIFO control 0x01600f10, confirming
threshold 15 and Normal source (0x028 = 0). The player exited 0, restoration
succeeded, and fresh audio health was available, stopped and non-stale.
The mask correction took effect but did not resolve S16 silence. Do not treat
the threshold mismatch as the established root cause. Evidence:
E:/DGttG/private-recovery/live-link/probe-result-20260925-174411.json and
health-20260925-174412.json. S32 has not been retested with this correction.
This is a single-variable correction for the next physical test, not a confirmed
explanation of the silent normal playback path.

## Evidence and inference

The isolated internal oscillator was audible. Isolated S16 and S32 file tones
were silent despite RUNNING PCM and successful player exit. Comparing their
first register snapshots found only these differences:

| Register | Internal | S16 | S32 |
|---|---|---|---|
| 0x000 digital control | 8000f000 | 80005000 | 80005000 |
| 0x010 FIFO control | 01604f00 | 01604f10 | 00604f30 |
| 0x014 FIFO status | 00000804 | 00002004 | 00002c04 |
| 0x024 sample counter | 00000078 | 000110a8 | 000721a0 |
| 0x028 source | 00000200 | 00000000 | 00000000 |

The captured analog controls were identical. Differences in gain, source,
format, transfer enable and running counters are expected for these tests.
This strengthens the case for investigating normal sample delivery, but does
not prove correct sample contents or electrical equivalence of every condition.

The H616 manual defines TX_TRIG_LEVEL as bits 14:8, with reset value 0x40.
The existing prepare function updates only bits 13:8 while intending to select
15. Reset bit 14 survives, producing 0x4f (79), exactly as recorded in both
silent file tests. The manual describes a 64-level stereo FIFO. The mismatch
between intended and actual threshold is established; its effect on audibility
still requires testing. Underrun flags are sticky, so their presence alone does
not establish ongoing starvation.

Sources: [H616 manual, printed pp. 549-552](https://linux-sunxi.org/images/2/24/H616_User_Manual_V1.0_cleaned.pdf),
and [Linux codec driver](https://raw.githubusercontent.com/torvalds/linux/master/sound/soc/sunxi/sun4i-codec.c).
The reviewed local driver is build/debian-audio-4/sun4i-codec.after.c; physical
reports are the three isolated results named in ISOLATED_TONE_TESTS_0.md.

## Bounded correction and checks

Only H616-compatible devices use a seven-bit threshold mask. The target value
remains 15. Other SoCs preserve their prior behavior. No gain, source selection,
DMA width, waveform, routing, analog initialization or clocks are changed.
The patch is included in the canonical kernel preparation script.

The ARM64 module compiled successfully and checkpatch reported no errors or
warnings. Kernel version magic and dependencies match the installed module.
A C harness executes the actual old and corrected prepare functions: it
reproduces 79 from the captured value, verifies 15 after correction, and checks
512 combinations of device family, prior threshold and sample-rate branch.
Non-H616 results match the old function, and unrelated bits are preserved.

Artifacts: build/debian-audio-7/candidate.json, sun4i-codec.ko,
threshold-regression.c and threshold-regression.log. Fresh-seed capture, rebase
and guarded root-write scripts are prepared; they do not modify the running
Deck. The paired updater cannot replace kernel modules, so installation needs
the seed in its reader. Existing isolated-tone controls remain installed.

Next acceptance: confirm normal-playback FIFO thresholds read 15 (typical S16
0x01600f10 and S32 0x00600f30), then independently check both tones and ordinary
GuideOS playback. If still silent, retain the valid mask correction but do not
declare the root cause resolved; the next evidence gap is actual PCM-buffer
content at the kernel/DMA boundary versus data reaching the normal codec path.
