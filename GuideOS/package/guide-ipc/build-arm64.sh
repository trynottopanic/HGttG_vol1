#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
out=${1:?output directory required}
cc=${GUIDE_ARM_CC:-aarch64-linux-gnu-gcc}
readelf=${GUIDE_ARM_READELF:-aarch64-linux-gnu-readelf}
strip=${GUIDE_ARM_STRIP:-aarch64-linux-gnu-strip}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
python3 "$root/tools/generate.py" --check
mkdir -p "$out"
common="-std=c11 -O2 -Wall -Wextra -Werror -fPIC"
$cc $common -D_GNU_SOURCE -I"$root/include" -c "$root/src/guide_ipc_envelope.c" -o "$tmp/envelope.o"
$cc $common -D_GNU_SOURCE -I"$root/include" -c "$root/src/guide_ipc_transport.c" -o "$tmp/transport.o"
$cc $common -I"$root/generated" -c "$root/generated/guide_ipc_interfaces.c" -o "$tmp/interfaces.o"
$cc -shared -Wl,-soname,libguide-ipc.so.0 -Wl,-z,relro,-z,now -o "$tmp/libguide-ipc.so.0.1.0" "$tmp/envelope.o" "$tmp/transport.o" "$tmp/interfaces.o"
$cc -std=c11 -D_GNU_SOURCE -O2 -Wall -Wextra -Werror -I"$root/include" "$root/tests/test_transport.c" -L"$tmp" -Wl,-rpath,/usr/lib/aarch64-linux-gnu -l:libguide-ipc.so.0.1.0 -o "$tmp/guide-ipc-selftest"
$readelf -h "$tmp/libguide-ipc.so.0.1.0" | grep -q 'Machine:.*AArch64'
$readelf -d "$tmp/libguide-ipc.so.0.1.0" | grep -q 'Shared library: \[libc.so.6\]'
$strip --strip-unneeded "$tmp/libguide-ipc.so.0.1.0"
$strip --strip-unneeded "$tmp/guide-ipc-selftest"
install -m755 "$tmp/libguide-ipc.so.0.1.0" "$out/libguide-ipc.so.0.1.0"
install -m755 "$tmp/guide-ipc-selftest" "$out/guide-ipc-selftest"
sha256sum "$out/libguide-ipc.so.0.1.0" "$out/guide-ipc-selftest" > "$out/SHA256SUMS"
