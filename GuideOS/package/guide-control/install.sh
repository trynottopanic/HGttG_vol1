#!/bin/bash
set -euo pipefail
root=${1:?Mounted Debian root required}
here=$(cd -- "$(dirname -- "$0")" && pwd)
project=$(cd "$here/../.." && pwd)
test "$root" != / && test -f "$root/etc/debian_version"
install -d "$root/usr/lib/guideos/control/platform" "$root/etc/systemd/system/guide-shell.service.d"
install -m644 "$here"/control_*.py "$root/usr/lib/guideos/control/"
install -m644 "$project/board/rg35xxh/debian/shell0/guide_platform_rg35xxh.py" "$root/usr/lib/guideos/control/platform/"
install -m644 "$project/board/rg35xxh/debian/shell0/guide_status_bar.py" "$root/usr/lib/guideos/control/platform/"
install -m644 "$here/guide-control.service" "$root/etc/systemd/system/"
python3 "$project/package/guide-resources/stage.py" "$root"
cat > "$root/etc/systemd/system/guide-shell.service.d/30-control.conf" <<'EOF'
[Unit]
Wants=guide-control.service
[Service]
Environment=GUIDE_CONTROL_SOCKET=/run/guideos-control/input.sock
EOF
chroot "$root" systemctl enable guide-control.service
