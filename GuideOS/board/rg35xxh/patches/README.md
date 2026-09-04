# Imported H700 hardware support

The patches in this directory are third-party hardware-enablement material.
They are not relicensed under GuideOS's default AGPL license.

They originated in the ROCKNIX `20260901` release, commit
`1ebff24f36501fb6493beb2bf83bf2604536d9aa`, and retain the notices and licenses
recorded in their patch headers and upstream projects. Minimal context and
overlap adjustments adapt the series to the exact official Linux 7.1.2 source;
GuideOS-specific compatibility additions identify themselves in their headers.
The imported `0153-enable-rgb-leds.patch` is deliberately omitted: despite its
filename it only labels the existing LED node and adds an otherwise unused
UART5 alias and pin group. None is required by the RG35XX H bring-up image, and
its old device-tree context does not apply cleanly to Linux 7.1.2.
The imported `0204-dts-Enable-hdmi-sound.patch` is also omitted from the first
image. It adds vendor-specific HDMI audio nodes, conflicts with the current
display tail of the device tree, and is unrelated to the built-in audio needed
by `CONTINUE-ON-DECK-0`. HDMI audio can return as a separately tested feature.

- `linux/` modifies Linux and is treated as GPL-2.0-only kernel material,
  except where an individual added source file states a compatible dual
  license.
- `uboot/` modifies U-Boot and retains its upstream GPL licensing.
- `arm-trusted-firmware/` modifies Trusted Firmware-A and retains its upstream
  BSD-3-Clause licensing.
- `gcc/` contains a GuideOS compatibility patch for building GCC 13 against
  current Linux kernel headers.

The DDR4 prototype configuration has produced a complete RG35XX H image with
the local media-handoff runtime. Physical boot, display, controls, audio, and
USB gadget behavior still require validation on the target handheld.
Unrelated ROCKNIX interface, branding, emulator, and distribution material is
intentionally excluded.
