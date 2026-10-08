#!/bin/sh
set -eu

project=${GUIDE_PROJECT_DIR:-/mnt/e/DGttG/HGttG_vol1/GuideOS}
root=${GUIDE_DEBIAN_ROOT:-/home/hacker/guideos-work/debian-shell-0/rootfs}
binary=${GUIDE_BOOT_ANIMATION_OUTPUT:-$project/build/guide-boot-animation-aarch64}
readelf=${GUIDE_READELF:-/home/hacker/guideos-work/output-rg35xxh-ddr4/host/bin/aarch64-buildroot-linux-gnu-readelf}
test "$(id -u)" = 0
test -x "$binary"
test -x "$readelf"
test -f "$root/etc/systemd/system/guide-shell.service"

"$project/apps/boot_animation/install.sh" --root "$root" --binary "$binary"

chroot "$root" systemd-analyze verify --man=no \
    guide-boot-animation.service guide-shell.service
"$readelf" -d "$binary" | grep NEEDED

echo GUIDE_BOOT_ANIMATION_STAGED_AND_VALID
