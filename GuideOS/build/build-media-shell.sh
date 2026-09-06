#!/bin/sh
set -eu

tool=/home/hacker/guideos-work/output-rg35xxh-ddr4/host/bin/aarch64-buildroot-linux-gnu-gcc
source_dir=/mnt/e/DGttG/HGttG_vol1/GuideOS/package/guide-hello-fb/src
output=/mnt/g/GuideOS-private/muos-reference/guide-hello-fb-media

test -x "${tool}"
"${tool}" -static -Wall -Wextra -Werror -O2 \
    -o "${output}" \
    "${source_dir}/guide-hello-fb.c" \
    "${source_dir}/cartridge.c" \
    "${source_dir}/installer.c" \
    "${source_dir}/wifi.c"
file "${output}"
sha256sum "${output}"
