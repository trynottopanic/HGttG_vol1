#!/usr/bin/env bash
set -euo pipefail

analysis=/mnt/g/GuideOS-private/muos-reference/analysis
out="$analysis/initramfs"
rm -rf "$out"
mkdir -p "$out"
cd "$out"
gzip -dc ../android-boot/initrd.img | cpio -idmu --quiet

{
    file init
    echo '=== INIT ==='
    sed -n '1,320p' init
    echo '=== CONTENTS ==='
    find . -maxdepth 3 \( -type f -o -type l \) -print | sort
} > "$analysis/initramfs-inspection.txt"
