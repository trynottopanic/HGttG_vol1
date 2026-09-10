#!/bin/sh
set -eu

project_dir=/mnt/e/DGttG/HGttG_vol1/GuideOS
work_dir=${GUIDE_DOOM_WORK_DIR:-/home/hacker/guideos-work/sources/libretro-prboom}
toolchain=${GUIDE_TOOLCHAIN:-/home/hacker/guideos-work/output-rg35xxh-ddr4/host/bin/aarch64-buildroot-linux-gnu-}
output=${GUIDE_DOOM_OUTPUT:-${project_dir}/build/guide-doom-aarch64}
core_output=${GUIDE_DOOM_CORE_OUTPUT:-${project_dir}/build/prboom_libretro-aarch64.so}

test -f "${work_dir}/libretro/libretro-common/include/libretro.h"
test -f "${work_dir}/prboom_libretro.so"

"${toolchain}gcc" -std=c11 -O2 -Wall -Wextra -Werror \
    -I"${work_dir}/libretro/libretro-common/include" \
    "${project_dir}/apps/doom/guide_doom_frontend.c" \
    -o "${output}" -ldl -lasound
"${toolchain}strip" "${output}"
cp "${work_dir}/prboom_libretro.so" "${core_output}"
"${toolchain}strip" "${core_output}"

file "${output}" "${core_output}"
sha256sum "${output}" "${core_output}"
