#!/bin/bash
set -euo pipefail
project="${GUIDE_PROJECT_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)}"
work="${GUIDE_WORK_ROOT:-${HOME}/.cache/guideos}/debian-h700-kernel"
cd "$work/linux-7.2.7"
mkdir -p .guide-patches
for p in "$project"/board/rg35xxh/patches/linux/*.patch; do
    name=$(basename "$p")
    test ! -e ".guide-patches/$name" || continue
    override="$project/board/rg35xxh/debian/linux-7.2/$name"
    if test -f "$override"; then p=$override; fi
    echo "APPLY $p"
    patch --batch --forward -p1 < "$p"
    sha256sum "$p" > ".guide-patches/$name"
done
# Later output patches overlap older patch context. Recognize the complete
# validated source before attempting to replay the earlier patch stack.
if cmp -s sound/soc/sunxi/sun4i-codec.c "$project/build/debian-audio-10/sun4i-codec.after.c"; then
    touch .guide-patched
    exit 0
fi
audio_patch="$project/board/rg35xxh/debian/h616-analog-ramp.patch"
diagnostic_patch="$project/board/rg35xxh/debian/h616-diagnostic-source.patch"
if ! patch --dry-run --silent -R -p1 < "$diagnostic_patch"; then
    if ! patch --dry-run --silent -R -p1 < "$audio_patch"; then
        patch --batch --forward -p1 < "$audio_patch"
    fi
    patch --batch --forward -p1 < "$diagnostic_patch"
fi
sha256sum "$audio_patch" > .guide-patches/h616-analog-ramp.patch
sha256sum "$diagnostic_patch" > .guide-patches/h616-diagnostic-source.patch
threshold_patch="$project/board/rg35xxh/debian/h616-fifo-threshold.patch"
if ! patch --dry-run --silent -R -p1 < "$threshold_patch"; then
    patch --batch --forward -p1 < "$threshold_patch"
fi
sha256sum "$threshold_patch" > .guide-patches/h616-fifo-threshold.patch
buffer_patch="$project/board/rg35xxh/debian/h616-buffer-evidence.patch"
if ! patch --dry-run --silent -R -p1 < "$buffer_patch"; then
    patch --batch --forward -p1 < "$buffer_patch"
fi
sha256sum "$buffer_patch" > .guide-patches/h616-buffer-evidence.patch
transfer_patch="$project/board/rg35xxh/debian/rg35xxh-dma-transfer.patch"
if ! patch --dry-run --silent -R -p1 < "$transfer_patch"; then
    patch --batch --forward -p1 < "$transfer_patch"
fi
sha256sum "$transfer_patch" > .guide-patches/rg35xxh-dma-transfer.patch
output_patch="$project/board/rg35xxh/debian/rg35xxh-audio-output.patch"
if ! patch --dry-run --silent -R -p1 < "$output_patch"; then
    patch --batch --forward -p1 < "$output_patch"
fi
sha256sum "$output_patch" > .guide-patches/rg35xxh-audio-output.patch
touch .guide-patched
