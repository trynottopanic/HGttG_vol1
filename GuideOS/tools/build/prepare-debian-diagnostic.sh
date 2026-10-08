#!/bin/bash
set -euo pipefail
project="${GUIDE_PROJECT_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)}"
work="${GUIDE_WORK_ROOT:-${HOME}/.cache/guideos}/debian-diagnostic-0"
root=$work/rootfs
test "$(id -u)" = 0
test ! -e "$root"
mkdir -p "$root"
tar -xzf "$project/build/debian-minimal/guideos-debian-trixie-arm64-base.tar.gz" -C "$root"
printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"
chmod 755 "$root/usr/sbin/policy-rc.d"
chroot "$root" apt-get update
chroot "$root" env DEBIAN_FRONTEND=noninteractive apt-get -y upgrade
chroot "$root" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  evtest alsa-utils iw wpasupplicant firmware-realtek
chroot "$root" apt-get clean
mkdir -p "$root/usr/lib/guideos" "$root/var/lib/guideos/diagnostics" "$root/data" "$root/boot"
install -m755 "$project/board/rg35xxh/debian/diagnostic-boot.sh" "$root/usr/lib/guideos/diagnostic-boot"
chmod 755 "$root/usr/lib/guideos/diagnostic-boot"
cat > "$root/etc/systemd/system/guide-diagnostic.service" <<'EOF'
[Unit]
Description=GuideOS Debian hardware diagnostic and bounded shutdown
After=multi-user.target
[Service]
Type=oneshot
ExecStart=/usr/lib/guideos/diagnostic-boot
TimeoutStartSec=120
[Install]
WantedBy=graphical.target
EOF
mkdir -p "$root/etc/systemd/system/graphical.target.wants"
ln -s ../guide-diagnostic.service "$root/etc/systemd/system/graphical.target.wants/guide-diagnostic.service"
ln -sf /usr/lib/systemd/system/graphical.target "$root/etc/systemd/system/default.target"
cat > "$root/etc/fstab" <<'EOF'
PARTUUID=47554944-02 / ext4 defaults,noatime 0 1
PARTUUID=47554944-01 /boot vfat defaults,noatime 0 2
PARTUUID=47554944-03 /data ext4 defaults,noatime 0 2
EOF
# No remote service or passwordless login is installed for this automatic test.
chroot "$root" dpkg --audit
chroot "$root" dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' > "$project/build/debian-minimal/diagnostic-packages.tsv"
echo DIAGNOSTIC_USERSPACE_READY
