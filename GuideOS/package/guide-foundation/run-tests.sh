#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
common="-std=c11 -D_GNU_SOURCE -Wall -Wextra -Werror -I$root/include"
ipc="-I$root/../guide-ipc/include -I$root/../guide-ipc/generated"
cc $common -c "$root/src/guide_foundation.c" -o "$tmp/core.o"
cc $common -c "$root/src/guide_control_codec.c" -o "$tmp/codec.o"
cc $common $ipc -c "$root/../guide-ipc/src/guide_ipc_transport.c" -o "$tmp/ipc.o"
cc $common $ipc -c "$root/../guide-ipc/src/guide_ipc_envelope.c" -o "$tmp/envelope.o"
cc $common -c "$root/src/guide_systemd_adapter.c" -o "$tmp/systemd.o"
cc $common "$root/tests/test_core.c" "$tmp/core.o" -o "$tmp/test-core"
"$tmp/test-core"
cc $common -fsanitize=address,undefined -fno-omit-frame-pointer "$root/tests/test_core.c" "$root/src/guide_foundation.c" -o "$tmp/test-sanitized"
ASAN_OPTIONS=detect_leaks=1 "$tmp/test-sanitized"
cc $common "$root/tests/test_control_codec.c" "$tmp/codec.o" -o "$tmp/test-codec"
"$tmp/test-codec"
cc $common "$root/tests/test_systemd_adapter.c" "$tmp/systemd.o" -lsystemd -o "$tmp/test-systemd-adapter"
cc $common "$root/tests/probe_hold.c" -o "$tmp/probe-hold"
"$tmp/test-systemd-adapter" "$tmp/probe-hold"
cc $common $ipc "$root/src/guide-capability-broker0.c" "$tmp/core.o" "$tmp/codec.o" "$tmp/ipc.o" "$tmp/envelope.o" -o "$tmp/guide-capability-broker0"
cc $common $ipc "$root/src/guide-ipc-probe.c" "$tmp/codec.o" "$tmp/ipc.o" "$tmp/envelope.o" -o "$tmp/guide-ipc-probe"
cc $common $ipc "$root/src/guide-supervisor0.c" "$tmp/core.o" "$tmp/codec.o" "$tmp/ipc.o" "$tmp/envelope.o" "$tmp/systemd.o" -lsystemd -o "$tmp/guide-supervisor0"
mkdir -p "$tmp/units"
install -m644 "$root"/systemd/* "$tmp/units/"
sed -i 's#^ExecStart=/usr/libexec/guideos/.*#ExecStart=/bin/true#' "$tmp/units"/*.service
if [ -f "$tmp/units/guide-planegotchi-background.service" ]; then
    sed -i 's#^ExecStart=/usr/bin/python3 .*#ExecStart=/bin/true#' "$tmp/units/guide-planegotchi-background.service"
fi
systemd-analyze verify "$tmp/units"/*.socket "$tmp/units"/*.service
PYTHONDONTWRITEBYTECODE=1 python3 "$root/tests/test_application_runtime.py"
printf 'GUIDE_FOUNDATION_HOST_PASS\n'
