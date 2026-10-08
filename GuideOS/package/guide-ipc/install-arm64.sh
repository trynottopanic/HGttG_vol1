#!/bin/sh
set -eu
root=${1:?mounted Debian root required}
build=${2:?ARM64 build directory required}
project=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test "$root" != / && test -f "$root/etc/debian_version"
sha256sum -c "$build/SHA256SUMS"
install -d "$root/usr/lib/aarch64-linux-gnu" "$root/usr/share/guideos/ipc"
install -m755 "$build/libguide-ipc.so.0.1.0" "$root/usr/lib/aarch64-linux-gnu/libguide-ipc.so.0.1.0"
ln -sfn libguide-ipc.so.0.1.0 "$root/usr/lib/aarch64-linux-gnu/libguide-ipc.so.0"
install -m644 "$project/schema/interfaces.json" "$root/usr/share/guideos/ipc/interfaces.json"
install -m644 "$project/schema/envelope0.cddl" "$root/usr/share/guideos/ipc/envelope0.cddl"
install -m644 "$project/generated/INTERFACES.md" "$root/usr/share/guideos/ipc/INTERFACES.md"
install -m644 "$project/generated/fixtures.json" "$root/usr/share/guideos/ipc/fixtures.json"
