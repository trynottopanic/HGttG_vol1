#!/bin/sh
set -eu

project=${GUIDE_PROJECT_DIR:-/mnt/e/DGttG/HGttG_vol1/GuideOS}
root=${GUIDE_DEBIAN_ROOT:-/home/hacker/guideos-work/debian-shell-0/rootfs}
source=$project/apps/boot_animation
output=${GUIDE_BOOT_ANIMATION_OUTPUT:-$project/build/guide-boot-animation-aarch64}
cross_root=${GUIDE_CROSS_ROOT:-/home/hacker/guideos-work/output-rg35xxh-ddr4/host}
cross=$cross_root/bin/aarch64-buildroot-linux-gnu-gcc
sysroot=$cross_root/aarch64-buildroot-linux-gnu/sysroot
header_cache=${GUIDE_GRAPHICS_HEADERS:-/home/hacker/guideos-work/guide-graphics-headers}

test "$(id -u)" = 0
test -d "$root"
test -f "$source/guide-boot-animation.c"

if [ -x "$root/usr/bin/cc" ] && [ -x "$root/usr/bin/pkg-config" ]; then
    install -m644 "$source/guide-boot-animation.c" "$root/tmp/guide-boot-animation.c"
    chroot "$root" sh -lc '
        set -eu
        pkg-config --exists libdrm gbm egl glesv2
        cc -std=c11 -O2 -Wall -Wextra -Werror \
            $(pkg-config --cflags libdrm gbm egl glesv2) \
            /tmp/guide-boot-animation.c -o /tmp/guide-boot-animation \
            $(pkg-config --libs libdrm gbm egl glesv2) -lm
    '
    install -m755 "$root/tmp/guide-boot-animation" "$output"
else
    # The staged production root intentionally omits a compiler. Reuse the
    # established RG35XX H glibc toolchain without adding build packages to it.
    test -x "$cross"
    test -f "$sysroot/usr/include/xf86drm.h"
    # Mesa's Buildroot staging output contains the target libraries but this
    # older build omitted public Khronos/GBM headers. They are architecture-
    # independent API declarations, so cache only those host header families.
    install -d "$header_cache"
    install -m644 /usr/include/gbm.h "$header_cache/gbm.h"
    rm -rf "$header_cache/EGL" "$header_cache/GLES2" "$header_cache/KHR"
    cp -a /usr/include/EGL /usr/include/GLES2 /usr/include/KHR "$header_cache/"
    "$cross" -std=c11 -O2 -Wall -Wextra -Werror \
        -I"$header_cache" -I"$sysroot/usr/include/libdrm" \
        "$source/guide-boot-animation.c" -o "$output" \
        -L"$root/usr/lib/aarch64-linux-gnu" \
        -Wl,-rpath-link,"$root/usr/lib/aarch64-linux-gnu" \
        -l:libdrm.so.2 -l:libgbm.so.1 -l:libEGL.so.1 -l:libGLESv2.so.2 -lm
fi
file "$output"
sha256sum "$output"
