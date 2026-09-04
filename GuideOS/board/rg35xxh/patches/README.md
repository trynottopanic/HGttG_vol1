# Imported H700 hardware support

The patches in this directory are third-party hardware-enablement material.
They are not relicensed under GuideOS's default AGPL license.

They originated in the ROCKNIX `20260901` release, commit
`1ebff24f36501fb6493beb2bf83bf2604536d9aa`, and retain the notices and licenses
recorded in their patch headers and upstream projects. Minimal context and
overlap adjustments adapt the series to the exact official Linux 7.1.2 source;
GuideOS-specific compatibility additions identify themselves in their headers.

- `linux/` modifies Linux and is treated as GPL-2.0-only kernel material,
  except where an individual added source file states a compatible dual
  license.
- `uboot/` modifies U-Boot and retains its upstream GPL licensing.
- `arm-trusted-firmware/` modifies Trusted Firmware-A and retains its upstream
  BSD-3-Clause licensing.

At `build.090326`, sequential applicability validation has progressed through
the H700 storage changes but is not yet complete. A complete image has not yet
been produced. Unrelated ROCKNIX interface, branding, emulator, and
distribution material is intentionally excluded.
