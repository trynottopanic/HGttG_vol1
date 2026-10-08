#!/bin/bash
set -euo pipefail
project="${GUIDE_PROJECT_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)}"
work="${GUIDE_WORK_ROOT:-${HOME}/.cache/guideos}/debian-h700-kernel"
reference="${GUIDE_WORK_ROOT:-${HOME}/.cache/guideos}/output-rg35xxh-ddr4"
export PATH="$reference/host/bin:/usr/bin:/bin"
export ARCH=arm64 CROSS_COMPILE=aarch64-buildroot-linux-gnu-
cd "$work/linux-7.2.7"
test -f .guide-patched
cp "$reference/build/linux-7.1.2/.config" .config
cp "$project/board/rg35xxh/dts/allwinner/"*.dts arch/arm64/boot/dts/allwinner/
scripts/config --set-str LOCALVERSION '-guide-debian0' --disable LOCALVERSION_AUTO
scripts/config --enable IKCONFIG --enable IKCONFIG_PROC --enable CGROUPS --enable MEMCG --enable CGROUP_PIDS
scripts/config --enable DEVTMPFS --enable DEVTMPFS_MOUNT --enable TMPFS --enable TMPFS_POSIX_ACL
scripts/config --enable SERIAL_EARLYCON --enable FRAMEBUFFER_CONSOLE --enable DRM_FBDEV_EMULATION
make olddefconfig
make -j6 Image modules allwinner/sun50i-h700-anbernic-rg35xx-h.dtb allwinner/sun50i-h700-anbernic-rg35xx-h-rev6-panel.dtb
mkdir -p "$project/build/debian-minimal/kernel"
cp arch/arm64/boot/Image .config "$project/build/debian-minimal/kernel/"
cp arch/arm64/boot/dts/allwinner/sun50i-h700-anbernic-rg35xx-h*.dtb "$project/build/debian-minimal/kernel/"
make -s kernelrelease > "$project/build/debian-minimal/kernel/release.txt"
