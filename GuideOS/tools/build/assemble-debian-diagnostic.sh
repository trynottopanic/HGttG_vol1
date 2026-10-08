#!/bin/bash
# All writes are to staging directories and image FILES, never a physical card.
set -euo pipefail
test "$(id -u)" = 0
project="${GUIDE_PROJECT_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)}"
id=${GUIDE_DIAGNOSTIC_ID:-0}
case "$id" in 0|1|2|3|4) ;; *) exit 2;; esac
work="${GUIDE_WORK_ROOT:-${HOME}/.cache/guideos}/debian-diagnostic-$id"
root=$work/rootfs
kernel="${GUIDE_WORK_ROOT:-${HOME}/.cache/guideos}/debian-h700-kernel/linux-7.2.7"
joypad="${GUIDE_WORK_ROOT:-${HOME}/.cache/guideos}/debian-h700-kernel/rocknix-joypad-d02ed13aae08113f6f9e0e9d699cb29bb3450fa2"
reference="${GUIDE_WORK_ROOT:-${HOME}/.cache/guideos}/output-rg35xxh-ddr4"
out=$project/build/debian-minimal
diagnostic=diagnostic-boot.sh
if test "$id" != 0; then
  out=$project/build/debian-diagnostic-$id
  diagnostic=diagnostic$id-boot.sh
  test -x "$root/usr/bin/kmscube"
fi
export PATH="$reference/host/bin:$reference/host/sbin:/usr/sbin:/usr/bin:/sbin:/bin"
export ARCH=arm64 CROSS_COMPILE=aarch64-buildroot-linux-gnu-
release=$(make -s -C "$kernel" kernelrelease)
test "$release" = "$(cat "$out/kernel/release.txt")"
test -f "$joypad/rocknix-singleadc-joypad.ko"
install -m755 "$project/board/rg35xxh/debian/$diagnostic" "$root/usr/lib/guideos/diagnostic-boot"
# This guard is only for package installation inside the build chroot.
rm -f "$root/usr/sbin/policy-rc.d"
make -C "$kernel" INSTALL_MOD_PATH="$root" INSTALL_MOD_STRIP=1 modules_install
install -D -m644 "$joypad/rocknix-singleadc-joypad.ko" "$root/lib/modules/$release/extra/rocknix-singleadc-joypad.ko"
"${CROSS_COMPILE}strip" --strip-debug "$root/lib/modules/$release/extra/rocknix-singleadc-joypad.ko"
depmod -b "$root" "$release"
mkdir -p "$root/etc/modules-load.d" "$root/usr/share/guideos/firmware-notices"
printf 'rocknix-singleadc-joypad\n' > "$root/etc/modules-load.d/guide-controls.conf"
cp -a "$project/build/debian-minimal/firmware/panels" "$root/lib/firmware/"
cat > "$root/usr/share/guideos/firmware-notices/panels.txt" <<'EOF'
Panel descriptions from ROCKNIX/distribution commit
0b991b0ee6ebfac467e9101d7e6b444ef923829b, projects/ROCKNIX/packages/linux-firmware/kernel-firmware/extra-firmware/panels/.
Private diagnostic image; redistribution review remains outstanding.
EOF
mkdir -p "$work/boot/extlinux" "$work/boot/allwinner"
cp "$out/kernel/Image" "$work/boot/"
cp "$out/kernel/"*.dtb "$work/boot/allwinner/"
for variant in standard rev6; do
  dtb=sun50i-h700-anbernic-rg35xx-h
  if test "$variant" = rev6; then dtb=$dtb-rev6-panel; fi
  cat > "$work/boot/extlinux/extlinux-$variant.conf" <<EOF
DEFAULT guide
TIMEOUT 10
LABEL guide
  LINUX /Image
  FDT /allwinner/$dtb.dtb
  APPEND root=PARTUUID=47554944-02 rootwait rootfstype=ext4 rw console=tty0 console=ttyS0,115200 earlycon loglevel=7 ignore_loglevel panic=0 systemd.show_status=yes
EOF
done
cp "$work/boot/extlinux/extlinux-standard.conf" "$work/boot/extlinux/extlinux.conf"
minutes=3
if test "$id" = 3; then minutes=20; fi
printf 'GuideOS Debian diagnostic %s\nDDR4 bootloader; standard panel selected.\nDiagnostic reports will appear in diagnostics/.\nAllow up to %s minutes for automatic power-off.\n' "$id" "$minutes" > "$work/boot/README.txt"
if test "$id" = 4; then
  cat > "$work/boot/README.txt" <<'EOF'
GuideOS Debian diagnostic 4 - RG35XX H button baseline
No time limit. Press and release each included button in any order.
Check that the highlighted name matches the physical button.
Start, Power and Reset are excluded. Analog stick motion is not tested.
Hold any included button for 3 seconds to pause and open the finish menu.
Release it. Tap any included button to move the selection.
Hold for 2 seconds, then release to select Resume or Save + finish.
Save + finish saves partial or complete results, then shuts down safely.
Reports: diagnostics/<boot-id>/results.html and button-baseline.json.
EOF
fi
test ! -e "$work/rootfs.ext4"
truncate -s 2G "$work/rootfs.ext4"
mkfs.ext4 -q -L GUIDE_ROOT -d "$root" "$work/rootfs.ext4"
truncate -s 1G "$work/data.ext4"
mkfs.ext4 -q -L GUIDE_DATA "$work/data.ext4"
truncate -s 128M "$work/boot.vfat"
mkfs.vfat -n GUIDE_BOOT "$work/boot.vfat"
mcopy -i "$work/boot.vfat" -s "$work/boot/"* ::/
image=$out/guideos-debian-diagnostic-ddr4.img
test ! -e "$image"
truncate -s 3329M "$image"
sfdisk "$image" <<'EOF'
label: dos
label-id: 0x47554944
unit: sectors

start=2048, size=262144, type=c, bootable
start=264192, size=4194304, type=83
start=4458496, size=2097152, type=83
EOF
dd if="$reference/images/u-boot-sunxi-with-spl.bin" of="$image" bs=1024 seek=8 conv=notrunc status=none
dd if="$work/boot.vfat" of="$image" bs=1M seek=1 conv=notrunc status=none
dd if="$work/rootfs.ext4" of="$image" bs=1M seek=129 conv=notrunc status=none
dd if="$work/data.ext4" of="$image" bs=1M seek=2177 conv=notrunc status=none
e2fsck -fn "$work/rootfs.ext4"
e2fsck -fn "$work/data.ext4"
fsck.vfat -n "$work/boot.vfat"
sfdisk --dump "$image" > "$out/diagnostic-partitions.txt"
{
  printf 'Kernel release: %s\n' "$release"
  printf 'Built UTC: '; date -u --iso-8601=seconds
  printf 'Physical boot validation: pending\n'
  sha256sum "$reference/images/u-boot-sunxi-with-spl.bin" "$out/kernel/Image" \
    "$out/kernel/"*.dtb "$project/build/debian-minimal/firmware/panels/"*.panel \
    "$root/lib/modules/$release/extra/rocknix-singleadc-joypad.ko"
  if test "$id" != 0; then sha256sum "$out/firmware/regulatory.db"*; fi
} > "$out/diagnostic-components.txt"
cp "$reference/build/uboot-2026.01/.config" "$out/uboot-diagnostic.config"
sha256sum "$image" > "$out/diagnostic-image.sha256"
echo DIAGNOSTIC_IMAGE_ASSEMBLED_NOT_PHYSICALLY_TESTED
