#!/bin/sh
set -eu
root=${1:?root filesystem required}
reserve=${2:?measured board reserve bytes required}
source_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
chroot "$root" getent group guide-archive >/dev/null 2>&1 || chroot "$root" groupadd --system guide-archive
chroot "$root" getent passwd guide-archive >/dev/null 2>&1 || chroot "$root" useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin --gid guide-archive guide-archive
case "$reserve" in ''|*[!0-9]*) exit 2;; esac
test "$reserve" -gt 0
install -d -m755 "$root/usr/lib/guideos/installer" "$root/opt/guideos/applications" "$root/var/lib/guideos/applications" "$root/var/lib/guideos/installer" "$root/var/lib/private/guideos/applications" "$root/etc/guideos"
for name in guide_cartridge.py guide_install_wire.py guide_installer.py guide_install_worker.py guide_install_service.py guide_install_recovery.py; do
 install -m644 "$source_root/$name" "$root/usr/lib/guideos/installer/$name"
done
install -m644 "$source_root/application-profile-v0.json" "$root/usr/lib/guideos/installer/"
printf '%s\n' "$reserve" > "$root/etc/guideos/installer-reserve-bytes"
install -m644 "$source_root/systemd/guide-installer.socket" "$root/etc/systemd/system/"
install -m644 "$source_root/systemd/guide-installer.service" "$root/etc/systemd/system/"
install -m644 "$source_root/systemd/guide-installer-recovery.service" "$root/etc/systemd/system/"
install -m644 "$source_root/../../board/rg35xxh/debian/shell0/guide_installer_panel.py" "$root/usr/lib/guideos/shell0/"
install -m644 "$source_root/../guide-storage/cartridge_catalog.py" "$root/usr/lib/guideos/storage/"
install -m644 "$source_root/../guide-storage/storage_service.py" "$root/usr/lib/guideos/storage/"
install -m644 "$source_root/../guide-ui/guide_field_ui.py" "$root/usr/lib/guideos/ui/"
install -m644 "$source_root/systemd/guide-cartridge-parser.socket" "$root/etc/systemd/system/"
install -m644 "$source_root/systemd/guide-cartridge-parser.service" "$root/etc/systemd/system/"
systemctl --root="$root" enable guide-cartridge-parser.socket guide-installer.socket guide-installer-recovery.service
