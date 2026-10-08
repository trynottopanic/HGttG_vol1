#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
out=${1:?output directory required}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
cc=${GUIDE_ARM_CC:-aarch64-linux-gnu-gcc}
strip=${GUIDE_ARM_STRIP:-aarch64-linux-gnu-strip}
common="-std=c11 -D_GNU_SOURCE -O2 -Wall -Wextra -Werror -I$root/include"
ipc="-I$root/../guide-ipc/include -I$root/../guide-ipc/generated"
mkdir -p "$out"
$cc $common -c "$root/src/guide_foundation.c" -o "$tmp/core.o"
$cc $common -c "$root/src/guide_control_codec.c" -o "$tmp/codec.o"
$cc $common $ipc -c "$root/../guide-ipc/src/guide_ipc_transport.c" -o "$tmp/ipc.o"
$cc $common $ipc -c "$root/../guide-ipc/src/guide_ipc_envelope.c" -o "$tmp/envelope.o"
$cc $common -c "$root/src/guide_systemd_adapter.c" -o "$tmp/systemd.o"
$cc $common "$root/tests/test_core.c" "$tmp/core.o" -o "$out/guide-foundation-selftest"
$cc $common $ipc "$root/src/guide-capability-broker0.c" "$tmp/core.o" "$tmp/codec.o" "$tmp/ipc.o" "$tmp/envelope.o" -o "$out/guide-capability-broker0"
$cc $common $ipc "$root/src/guide-ipc-probe.c" "$tmp/codec.o" "$tmp/ipc.o" "$tmp/envelope.o" -o "$out/guide-ipc-probe"
$cc $common $ipc "$root/src/guide-supervisor0.c" "$tmp/core.o" "$tmp/codec.o" "$tmp/ipc.o" "$tmp/envelope.o" "$tmp/systemd.o" -lsystemd -o "$out/guide-supervisor0"
$strip --strip-unneeded "$out/guide-foundation-selftest" "$out/guide-capability-broker0" "$out/guide-ipc-probe" "$out/guide-supervisor0"
sha256sum "$out"/guide-* > "$out/SHA256SUMS"
printf 'GUIDE_FOUNDATION_ARM64_BUILD_PASS\n'
