#!/bin/sh
set -eu

tool=/home/hacker/guideos-work/output-rg35xxh-ddr4/host/bin/aarch64-buildroot-linux-gnu-gcc
source_dir=/mnt/e/DGttG/HGttG_vol1/GuideOS/package/guide-hello-fb/src
output=${GUIDE_SHELL_OUTPUT:-/mnt/e/DGttG/HGttG_vol1/GuideOS/build/guide-hello-fb-local-media}
developer_output=${GUIDE_DEVELOPER_OUTPUT:-/mnt/e/DGttG/HGttG_vol1/GuideOS/build/guide-devlink-control-aarch64}

test -x "${tool}"
"${tool}" -static -Wall -Wextra -Werror -O2 \
    -o "${output}" \
    "${source_dir}/guide-hello-fb.c" \
    "${source_dir}/cartridge.c" \
    "${source_dir}/installer.c" \
    "${source_dir}/wifi.c"
file "${output}"
sha256sum "${output}"

"${tool}" -static -Wall -Wextra -Werror -O2 \
    -o "${developer_output}" \
    "${source_dir}/developer_link_control.c"
file "${developer_output}"
sha256sum "${developer_output}"
