#!/bin/bash
set -euo pipefail
root=${1:?Mounted Debian root required}
here=$(cd -- "$(dirname -- "$0")" && pwd)
project=$(cd "$here/../../.." && pwd)
test "$root" != / && test -f "$root/etc/debian_version"
install -d "$root/usr/lib/guideos/diagnostics" "$root/etc/systemd/system" "$root/usr/lib/python3/dist-packages"
install -m644 "$here"/diagnostics_*.py "$root/usr/lib/guideos/diagnostics/"
install -m644 "$project/board/rg35xxh/debian/shell0/guide_telemetry.py" "$root/usr/lib/python3/dist-packages/guide_telemetry.py"
install -m644 "$here/guide-diagnostics.service" "$root/etc/systemd/system/"
cat > "$root/etc/tmpfiles.d/guide-diagnostics.conf" <<'EOF'
d /data/guideos/diagnostics 0750 root root -
EOF
chroot "$root" systemctl enable guide-diagnostics.service
