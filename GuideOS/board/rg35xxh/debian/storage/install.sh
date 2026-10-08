#!/bin/bash
set -euo pipefail
root=${1:?Mounted Debian root required}
modules=${2:?Directory containing exfat.ko and nls_utf8.ko required}
here=$(cd -- "$(dirname -- "$0")" && pwd)
project=$(cd "$here/../../../.." && pwd)
test "$root" != / && test -f "$root/etc/debian_version"
release=7.2.7-guide-debian2
for module in exfat nls_utf8; do
 test "$(modinfo -F vermagic "$modules/$module.ko" | cut -d' ' -f1)" = "$release"
 install -Dm644 "$modules/$module.ko" "$root/lib/modules/$release/extra/$module.ko"
done
depmod -b "$root" "$release"
install -Dm644 "$project/package/guide-storage/storage_service.py" "$root/usr/lib/guideos/storage/storage_service.py"
bash "$project/package/guide-media/install.sh" "$root"
install -Dm644 "$here/guide-storage.service" "$root/etc/systemd/system/guide-storage.service"
install -Dm644 "$here/guide-media-library.socket" "$root/etc/systemd/system/guide-media-library.socket"
install -d "$root/etc/systemd/system/guide-shell.service.d"
cat > "$root/etc/systemd/system/guide-shell.service.d/35-storage.conf" <<'EOF'
[Unit]
Wants=guide-storage.service
[Service]
Environment=GUIDE_STORAGE=1
EOF
chroot "$root" systemctl enable guide-storage.service
chroot "$root" systemctl enable guide-media-library.socket
chroot "$root" systemd-analyze verify --man=no guide-media-library.socket guide-storage.service guide-shell.service
