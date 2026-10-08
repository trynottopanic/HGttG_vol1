#!/bin/sh
set -eu
project=${GUIDE_PROJECT_DIR:-/mnt/e/DGttG/HGttG_vol1/GuideOS}
root=${GUIDE_DEBIAN_ROOT:-/home/hacker/guideos-work/debian-shell-0/rootfs}
cross_root=${GUIDE_CROSS_ROOT:-/home/hacker/guideos-work/output-rg35xxh-ddr4/host}
headers=${GUIDE_GRAPHICS_HEADERS:-/home/hacker/guideos-work/guide-graphics-headers}
output=${GUIDE_UI_GPU_OUTPUT:-$project/build/gpu-ui/libguidegpu.so}
test -f "$headers/gbm.h"
mkdir -p "$(dirname "$output")"
"$cross_root/bin/aarch64-buildroot-linux-gnu-gcc" -std=c11 -O2 -fPIC -shared -Wall -Wextra -Werror \
    -I"$headers" -I"$cross_root/aarch64-buildroot-linux-gnu/sysroot/usr/include/libdrm" \
    "$project/package/guide-ui/gpu/guide_gpu.c" -o "$output" \
    -Wl,-z,relro,-z,now -L"$root/usr/lib/aarch64-linux-gnu" \
    -Wl,-rpath-link,"$root/usr/lib/aarch64-linux-gnu" \
    -l:libdrm.so.2 -l:libgbm.so.1 -l:libEGL.so.1 -l:libGLESv2.so.2 -lm
file "$output"
sha256sum "$output"
