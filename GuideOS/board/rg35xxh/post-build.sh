#!/bin/sh
set -eu

board_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(CDPATH= cd -- "${board_dir}/../../.." && pwd)

install -d "${TARGET_DIR}/usr/lib/guide"
install -m 0644 \
    "${repo_dir}/prototypes/continue_on_deck_0/deck_receiver.py" \
    "${TARGET_DIR}/usr/lib/guide/deck_receiver.py"
install -m 0644 \
    "${repo_dir}/prototypes/continue_on_deck_0/deck_runtime.py" \
    "${TARGET_DIR}/usr/lib/guide/deck_runtime.py"
install -d "${TARGET_DIR}/data/guide-media"

install -d "${BINARIES_DIR}/extlinux"
install -m 0644 "${board_dir}/extlinux-standard.conf" \
    "${BINARIES_DIR}/extlinux/extlinux.conf"
install -m 0644 "${board_dir}/extlinux-standard.conf" \
    "${BINARIES_DIR}/extlinux/extlinux-standard.conf"
install -m 0644 "${board_dir}/extlinux-rev6.conf" \
    "${BINARIES_DIR}/extlinux/extlinux-rev6.conf"
install -m 0644 "${board_dir}/README-PANEL.txt" \
    "${BINARIES_DIR}/README-PANEL.txt"
