# RG35XX H hardware audit

Status: `build.090326` pre-flash integration checkpoint. No complete image has
yet been produced or represented as bootable.

The Anbernic RG35XX H uses an Allwinner H700 system-on-chip, a 640 by 480
internal display, game controls, two microSD interfaces, a Realtek wireless
device, USB-C, mini-HDMI, audio hardware, and an AXP717 power-management chip.
The exact behavior depends on the production revision.

## Confirmed source support

| Area | Bring-up source | Current conclusion |
| --- | --- | --- |
| CPU and base board | Linux 7.1.2 plus H700 patches | ARM64 Cortex-A53 target; upstream contains the base RG35XX H device tree. |
| Internal display | H700 display and generic MIPI-panel patches | Required for a visible first boot; two panel descriptions are packaged. |
| Controls | Linux GPIO keys, ADC joystick, and H700 input patches | Directional, action, shoulder, menu, volume, and analog inputs are described. |
| Storage | Linux sunxi MMC plus H700 second-slot patch | Both slots are described; physical testing remains required. |
| Wireless | Linux `rtw88` SDIO driver and redistributable Linux firmware | RTL8821CS Wi-Fi and Bluetooth paths are configured; radio testing remains required. |
| Power | Linux AXP717 support and H700 device tree | Battery and input-power reporting are described; charging and shutdown need physical testing. |
| Boot | U-Boot 2026.01 and Trusted Firmware-A 2.12.0 | Separate LPDDR3 and LPDDR4 boot configurations are provided. |

## Hardware variants

Two independent differences must be handled:

1. Some units use LPDDR3 memory and others use LPDDR4. A bootloader trained for
   the wrong memory type may not start, so GuideOS produces separate image
   files rather than guessing at run time.
2. At least two internal panel revisions exist. Both device-tree files are on
   the Windows-readable boot partition. The original panel is selected by
   default; `README-PANEL.txt` explains how to select the revision-6 panel
   without rebuilding the image.

## Kernel decision

Linux 6.18.48 was downloaded, checksum-verified, and inspected because 6.18.y
is the intended long-term GuideOS kernel line. Its upstream RG35XX H files do
not yet provide the complete display and wireless description needed for a
useful first boot, and the current H700 series targets Linux 7.1.2.

`BRINGUP-0` therefore uses the exact Linux 7.1.2 release temporarily. Returning
to a maintained 6.18.y kernel requires a reviewed backport and physical tests;
it is not being represented as complete merely because a kernel can compile.

## Provenance and exclusions

The hardware patch set, alternate panel device tree, and memory-specific
U-Boot configurations come from the ROCKNIX `20260901` release at immutable
commit `1ebff24f36501fb6493beb2bf83bf2604536d9aa`. ROCKNIX is a hardware-support
reference, not the GuideOS distribution base. No ROCKNIX branding, interface,
emulator configuration, or noncommercial visual material is included.

Imported files retain their upstream licenses. Firmware is taken from the
Buildroot `linux-firmware` package with its original redistribution notices;
no firmware is copied from the factory card.

## Tests required on the physical Deck

- Boot with the correct memory image and reach the `BRINGUP-0` screen.
- Try the alternate panel description if the default screen is blank or wrong.
- Verify every button, both analog sticks, and volume controls with `evtest`.
- Verify both microSD slots without writing outside explicitly selected test data.
- Verify Wi-Fi association, Bluetooth discovery, audio, USB host/device mode,
  HDMI, battery reporting, charging, clean shutdown, and thermal behavior.

Passing a build is evidence about source consistency, not proof that these
physical functions work. Results will be recorded after the first controlled
boot.

## Checkpoint note

The `build.090326` checkpoint contains the reproducible Buildroot definitions,
hardware audit, and the in-progress Linux 7.1.2 compatibility series. The host
compiler toolchain built successfully. Patch validation reached the H700
storage changes; final series validation, kernel compilation, image assembly,
and image inspection remain work for the next checkpoint.
