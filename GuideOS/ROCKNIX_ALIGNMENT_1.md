# ROCKNIX hardware integration audit — diagnostic 1

Physical-test update: the latest captured boot now registers the panel and
framebuffer, initializes Mali-G31/Panfrost EGL contexts, and enumerates the
gamepad and both radios with no deferred devices. Full acceptance remains open:
the cube and input-event tests had harness defects, and the imported panel
orientation call triggers DRM registration warnings. See
`build/debian-diagnostic-1/hardware-tests/2026-09-21-223428/RESULT.md`.
Earlier pending statements below describe the pre-test build record.

Reference: ROCKNIX/distribution commit
`0b991b0ee6ebfac467e9101d7e6b444ef923829b`.
The recursive source inventory was not truncated. Relevant H700, shared
mainline, 7.2 and default kernel patches were downloaded and verified against
their Git blob hashes. Inventory and checksums:
`build/debian-minimal/hardware-reference/patch-audit.json`.

## Identified configuration defects

| Dependency | First candidate | ROCKNIX / correction | Evidence |
| --- | --- | --- | --- |
| Panel command bus | SPI_GPIO disabled | SPI_GPIO=y | Board `/spi` has `compatible = "spi-gpio"`; its child is the panel. No panel could probe without its parent driver. |
| GPU power domain | SUN50I_H6_PRCM_PPU disabled | Enabled built-in | GPU references `prcm_ppu`; Kconfig explicitly requires this driver for the H616 GPU. First probe timed out. |
| Display IOMMU | SUN50I_IOMMU disabled | Enabled built-in | Missing board-specific driver present in ROCKNIX configuration. |
| Joystick ADC | SUN20I_GPADC disabled | Enabled built-in | Joypad's `io-channels` references `gpadc`; first probe returned EPROBE_DEFER. |
| Wi-Fi GPIO reset | RESET_GPIO=m | Disabled, matching ROCKNIX | Linux reset helper rejects GPIO references whose argument count is not two. Sunxi uses three cells. MMC pwrseq reported ENOENT; disabling this optional helper restores its direct GPIO fallback. |

These are configuration/integration errors in GuideOS's first kernel, not
evidence that drivers do not exist. Their hardware effects must be confirmed by
the second physical test. Debian remains the userspace base.

Both panel descriptions remain embedded. The signed Debian regulatory database
and its signature are also embedded because built-in cfg80211 requested them
before the first root filesystem mount. Kernel version is
`7.2.7-guide-debian1`; the already boot-tested LPDDR4 bootloader is retained.

## Patch comparison and scope

The main display, GPU OPP, PWM, panel selection and joypad board changes already
exist locally. Differences in patches 0002, 0010, 0127 and 0140 are context or
packaging differences in the added code. Regulator additions found in reference
0126 and 0152 are supplied by the local board-specific regulator patches and
RG35XX H device tree; the first boot already enumerated both cards.

Reference panel patch 0110 additionally communicates panel orientation to DRM.
That six-line change is now applied as `board/rg35xxh/debian/panel-orientation.patch`,
preserving its code from the pinned ROCKNIX patch and the source file's license.

Remaining H700 patches were inspected and retained as reference, not blindly
applied to a different kernel: 0153 concerns multicolor LED wiring; 0156 adds an
external RTC; 0157–0163 and 0210 concern wake, suspend, power/clock handling and
related peripheral behavior; 0204 adds HDMI audio while its related AHUB patch
is marked disabled. These remain a separate integration backlog. Suspend and
HDMI audio are not acceptance claims for this candidate.

Shared input-polldev restoration and ROCKNIX input-redirection patches are not
required by the locally ported joypad driver. The shared PWM compatibility
helper is not needed by the successfully linked H700 module. RTL8733BU, i915,
MSM and imon changes target other hardware; the initramfs/Rust build workarounds
do not address this configuration's boot dependencies. The asynchronous suspend
policy patch is outside this cold-boot test.

## Test and build procedure

Preserve the first candidate and reports. Prepare diagnostic 1 userspace with
`build/prepare-debian-diagnostic1.sh`, then run
`build/finalize-debian-diagnostic1.sh` as root in WSL. Build with
`build/build-debian-diagnostic1-kernel.sh`. Assemble and validate with
`GUIDE_DIAGNOSTIC_ID=1` using the existing assembly and validation scripts.
The guarded Windows flash script accepts `-DiagnosticId 1` and a required
expected image SHA-256. It only targets the previously backed-up seed.

Diagnostic 1 records DRM connectors, deferred probes, EGL driver/renderer data,
game input events and a bounded kmscube run. A software renderer such as llvmpipe
does not establish GPU acceleration. A successful Panfrost renderer and actual
display output are required before marking graphics operational. Presence of
input events does not by itself establish correct mappings for every control.

At publication of this audit, the corrections compile; physical acceptance of
diagnostic 1 is pending. The diagnostic shuts down automatically and keeps the
owner's original GuideOS state in the separate verified recovery image.

## Installation result

The 3,490,709,504-byte diagnostic 1 image passed independent partition/filesystem,
ARM64 image, module-version and checksum checks. The final assembly log contains
a shell EOF error caused by editing its script while it was running; the image
had already been written. `complete-diagnostic1-validation.sh` independently
checked the completed artifact and checksum, with success recorded in
`build/debian-diagnostic-1/validation.log`. The assembly script itself also passes
syntax validation. No success is inferred from that interrupted assembly command.

The image was then installed on the same identity-checked, backed-up seed.
Full raw-card readback matched SHA-256
`4BECEA7B5AC00FFF162E6D4241816E2626D57D93FDD4C769336849CD411EDA05`.
The cleared backup-GPT area also passed its separate check. Evidence:
`build/debian-diagnostic-1/flash-result.txt`.

Physical test: boot in the RG35XX H, press buttons and move sticks during the
first minute, watch for console text and a brief rotating cube, allow up to three
minutes for automatic shutdown, then return the card to the reader. These are
expected test stages, not a claim that display or GPU acceleration already works.
