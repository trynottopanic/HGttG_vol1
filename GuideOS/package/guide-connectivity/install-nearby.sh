#!/bin/bash
# Image-only installer: no physical devices or owner network connections.
set -euo pipefail
root=$(realpath -- "${1:?Mounted Debian image root required}")
here=$(cd -- "$(dirname -- "$0")" && pwd)
test "$root" != / && test -f "$root/etc/debian_version"
mountpoint -q "$root"
test "$(chroot "$root" dpkg --print-architecture)" = arm64
chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get update
chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    nmap iputils-ping iputils-tracepath bind9-dnsutils python3-dbus python3-gi
install -Dm644 "$here/guide_nearby.py" "$root/usr/lib/guideos/connectivity/guide_nearby.py"
install -Dm644 "$here/guide-nearby.service" "$root/etc/systemd/system/guide-nearby.service"
mkdir -p "$root/etc/systemd/system/multi-user.target.wants"
ln -sf ../guide-nearby.service "$root/etc/systemd/system/multi-user.target.wants/guide-nearby.service"
# Native Debian packet tools remain available to the owner; the Guide UI uses
# selected presets, unprivileged children and cancellable operation limits.
chroot "$root" /usr/bin/nmap --version
chroot "$root" /usr/bin/ping -V
chroot "$root" /usr/bin/tracepath -V
chroot "$root" /usr/bin/dig -v
systemd-analyze --man=no --root="$root" verify guide-nearby.service
