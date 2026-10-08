#!/bin/bash
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
root=${1:?Pass the staged ARM64 Debian root}
cross_root=${GUIDE_CROSS_ROOT:-/home/hacker/guideos-work/output-rg35xxh-ddr4/host}
sysroot=$cross_root/aarch64-buildroot-linux-gnu/sysroot
headers=${GUIDE_GRAPHICS_HEADERS:-/home/hacker/guideos-work/guide-graphics-headers}
binary=$(mktemp "$root/tmp/guide-animation-test.XXXXXXXX")
trap 'rm -f "$binary"' EXIT
wrap=()
for name in eglChooseConfig eglGetConfigAttrib eglSwapBuffers gbm_surface_lock_front_buffer gbm_bo_get_user_data gbm_surface_release_buffer drmModePageFlip clock_gettime select drmHandleEvent; do
 wrap+=("-Wl,--wrap=$name")
done
"$cross_root/bin/aarch64-buildroot-linux-gnu-gcc" -std=c11 -O2 -Wall -Wextra -Werror \
 -I"$headers" -I"$sysroot/usr/include/libdrm" "$here/test_runtime.c" -o "$binary" "${wrap[@]}" \
 -L"$root/usr/lib/aarch64-linux-gnu" -Wl,-rpath-link,"$root/usr/lib/aarch64-linux-gnu" \
 -l:libdrm.so.2 -l:libgbm.so.1 -l:libEGL.so.1 -l:libGLESv2.so.2 -lm
timeout 5 chroot "$root" "/tmp/$(basename "$binary")"
