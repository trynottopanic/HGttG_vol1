#!/bin/bash
# Assemble userspace only. Never opens or writes a physical storage device.
set -euo pipefail
project="${GUIDE_PROJECT_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)}"
work="${GUIDE_WORK_ROOT:-${HOME}/.cache/guideos}/debian-trixie-arm64-0"
root=$work/rootfs
artifacts="$project/build/debian-minimal"
test "$(id -u)" = 0
test ! -e "$root"
mkdir -p "$work" "$artifacts"
exec > >(tee "$artifacts/bootstrap.log") 2>&1
debootstrap --arch=arm64 --variant=minbase --force-check-gpg \
  --keyring=/usr/share/keyrings/debian-archive-keyring.gpg \
  --include=systemd-sysv,udev,dbus,ca-certificates,iproute2,kmod,e2fsprogs,iputils-ping \
  trixie "$root" https://deb.debian.org/debian
cat > "$root/etc/apt/sources.list" <<'EOF'
deb https://deb.debian.org/debian trixie main non-free-firmware
deb https://deb.debian.org/debian trixie-updates main non-free-firmware
deb https://security.debian.org/debian-security trixie-security main non-free-firmware
EOF
printf 'guide-deck\n' > "$root/etc/hostname"
printf '127.0.0.1 localhost\n127.0.1.1 guide-deck\n::1 localhost ip6-localhost\n' > "$root/etc/hosts"
mkdir -p "$root/usr/share/guideos" "$root/etc/systemd/journald.conf.d"
printf 'BOOTSTRAP ONLY: no board kernel, bootloader, remote login, or Guide runtime installed.\n' > "$root/usr/share/guideos/image-status"
printf '[Journal]\nStorage=volatile\nRuntimeMaxUse=8M\n' > "$root/etc/systemd/journald.conf.d/guide.conf"
# The image has no shared device identity and no enabled remote login service.
: > "$root/etc/machine-id"
chroot "$root" dpkg --audit
chroot "$root" dpkg --print-architecture | tee "$artifacts/architecture.txt"
chroot "$root" dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' > "$artifacts/packages.tsv"
cp "$root/etc/os-release" "$artifacts/os-release"
cp "$root/debootstrap/debootstrap.log" "$artifacts/debootstrap-detail.log" 2>/dev/null || true
chroot "$root" apt-get clean
du -sh "$root" | tee "$artifacts/rootfs-size.txt"
tar --numeric-owner --xattrs --acls -C "$root" -czf "$artifacts/guideos-debian-trixie-arm64-base.tar.gz" .
sha256sum "$artifacts/guideos-debian-trixie-arm64-base.tar.gz" > "$artifacts/SHA256SUMS"
printf 'USERSPACE_READY_NOT_BOOTABLE\n' | tee "$artifacts/status.txt"
