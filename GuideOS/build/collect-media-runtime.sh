#!/bin/bash
set -euo pipefail

target=/home/hacker/guideos-work/output-rg35xxh-ddr4/target
readelf=/home/hacker/guideos-work/output-rg35xxh-ddr4/host/bin/aarch64-buildroot-linux-gnu-readelf
output=/mnt/g/GuideOS-private/muos-reference/media-runtime-0.1

if [ -e "${output}" ]; then
    echo "Refusing to replace existing runtime: ${output}" >&2
    exit 1
fi
mkdir -p "${output}/bin" "${output}/lib"
cp "${target}/usr/bin/ffmpeg" "${output}/bin/ffmpeg"

declare -a queue=("${output}/bin/ffmpeg")
declare -A copied=()
position=0
while [ "${position}" -lt "${#queue[@]}" ]; do
    current=${queue[${position}]}
    position=$((position + 1))
    while IFS= read -r needed; do
        [ -n "${needed}" ] || continue
        if [ -n "${copied[${needed}]:-}" ]; then
            continue
        fi
        source=$(find "${target}/lib" "${target}/usr/lib" \( -type f -o -type l \) \
            -name "${needed}" -print -quit)
        if [ -z "${source}" ]; then
            echo "Missing runtime dependency: ${needed}" >&2
            exit 1
        fi
        cp -L "${source}" "${output}/lib/${needed}"
        copied[${needed}]=1
        queue+=("${output}/lib/${needed}")
    done < <("${readelf}" -d "${current}" 2>/dev/null |
        sed -n 's/.*Shared library: \[\([^]]*\)\].*/\1/p')
done

cp -L "${target}/lib/ld-linux-aarch64.so.1" "${output}/lib/ld-linux-aarch64.so.1"
chmod 0755 "${output}/bin/ffmpeg" "${output}/lib/ld-linux-aarch64.so.1"
find "${output}/lib" -type f -exec chmod 0644 {} +
chmod 0755 "${output}/lib/ld-linux-aarch64.so.1"
du -sh "${output}"
find "${output}" -type f -print0 | sort -z | xargs -0 sha256sum
