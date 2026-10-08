#!/bin/bash
set -euo pipefail
project="${GUIDE_PROJECT_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)}"
work="${GUIDE_WORK_ROOT:-${HOME}/.cache/guideos}/debian-h700-kernel"
reference="${GUIDE_WORK_ROOT:-${HOME}/.cache/guideos}/output-rg35xxh-ddr4"
export PATH="$reference/host/bin:/usr/bin:/bin"
export ARCH=arm64 CROSS_COMPILE=aarch64-buildroot-linux-gnu-
cd "$work/linux-7.2.7"
scripts/config --enable IIO --enable AXP20X_ADC --enable BATTERY_AXP20X
# Load radios from userspace, after Debian's firmware files are accessible.
scripts/config --module RTW88_8821CS --module BT_HCIUART
# Built-in display probing happens before the root filesystem is available.
# Include both small panel descriptions in the kernel itself.
scripts/config --set-str EXTRA_FIRMWARE 'panels/anbernic,rg35xx-plus-panel.panel panels/anbernic,rg35xx-plus-rev6-panel.panel'
scripts/config --set-str EXTRA_FIRMWARE_DIR "$project/build/debian-minimal/firmware"
make olddefconfig
for setting in CONFIG_AXP20X_ADC=y CONFIG_BATTERY_AXP20X=y CONFIG_RTW88_8821CS=m CONFIG_BT_HCIUART=m; do
  grep -qx "$setting" .config || { echo "Required setting missing: $setting" >&2; exit 1; }
done
make -j6 Image modules
printf '%s  %s\n' 89ade1769d6eb7b4f37265f26407a422cdbcf517487f80eb1c29964904ca138e "$work/joypad.tar.gz" | sha256sum -c -
joypad=$work/rocknix-joypad-d02ed13aae08113f6f9e0e9d699cb29bb3450fa2
if grep -q 'include <linux/input-polldev.h>' "$joypad/rocknix-singleadc-joypad.c"; then
  patch -d "$joypad" -p1 < "$project/board/rg35xxh/debian/joypad-linux72.patch"
else
  patch --dry-run -R -d "$joypad" -p1 < "$project/board/rg35xxh/debian/joypad-linux72.patch"
fi
make -j4 DEVICE=H700 M="$work/rocknix-joypad-d02ed13aae08113f6f9e0e9d699cb29bb3450fa2" modules
cp arch/arm64/boot/Image .config "$project/build/debian-minimal/kernel/"
sha256sum arch/arm64/boot/Image > "$project/build/debian-minimal/kernel/Image.sha256"
