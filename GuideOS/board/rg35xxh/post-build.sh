#!/bin/sh
set -eu

board_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

install -d "${BINARIES_DIR}/extlinux"
install -m 0644 "${board_dir}/extlinux-standard.conf" \
    "${BINARIES_DIR}/extlinux/extlinux.conf"
install -m 0644 "${board_dir}/extlinux-standard.conf" \
    "${BINARIES_DIR}/extlinux/extlinux-standard.conf"
install -m 0644 "${board_dir}/extlinux-rev6.conf" \
    "${BINARIES_DIR}/extlinux/extlinux-rev6.conf"
install -m 0644 "${board_dir}/README-PANEL.txt" \
    "${BINARIES_DIR}/README-PANEL.txt"
