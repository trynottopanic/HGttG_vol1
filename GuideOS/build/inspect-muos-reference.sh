#!/usr/bin/env bash
set -euo pipefail

base=/mnt/g/GuideOS-private/muos-reference
analysis="$base/analysis"
unpacked="$analysis/android-boot"
mkdir -p "$unpacked"

(
    cd "$unpacked"
    abootimg -x "$base/partition4.img" bootimg.cfg zImage initrd.img stage2.img >/dev/null
)

{
    echo '=== FILE TYPES ==='
    file "$base"/partition*.img "$unpacked"/*
    echo
    echo '=== ANDROID BOOT HEADER ==='
    abootimg -i "$base/partition4.img"
    echo
    echo '=== FDT MAGIC OFFSETS ==='
    for candidate in "$base/partition3.img" "$base/partition4.img" "$unpacked/zImage" "$unpacked/initrd.img"; do
        echo "$candidate"
        grep -aob $'\xd0\x0d\xfe\xed' "$candidate" || true
    done
    echo
    echo '=== PARTITION 2 HEADER ==='
    xxd -l 512 "$base/partition2.img"
    echo
    echo '=== PARTITION 2 RELEVANT STRINGS ==='
    strings -a -n 5 "$base/partition2.img" |
        grep -Ei 'boot|dtb|sunxi|sun50|h700|rg35|anbernic|panel|kernel' |
        head -300 || true
    echo
    echo '=== PARTITION 3 RELEVANT STRINGS ==='
    strings -a -n 5 "$base/partition3.img" |
        grep -Ei 'boot|dtb|sunxi|sun50|h700|rg35|anbernic|panel|kernel|resource' |
        head -500 || true
    echo
    echo '=== PRE-PARTITION BOOT SIGNATURES ==='
    grep -aob 'eGON.BT0' "$base/muos-boot-prefix-163577856.img" || true
    grep -aob 'sunxi-package' "$base/muos-boot-prefix-163577856.img" || true
} > "$analysis/inspection.txt"

sha256sum "$unpacked"/* > "$analysis/android-boot-sha256.txt"
echo "$analysis/inspection.txt"
