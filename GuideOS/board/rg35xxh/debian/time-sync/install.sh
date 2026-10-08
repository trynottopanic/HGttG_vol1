#!/bin/bash
set -euo pipefail
root=${1:?Mounted Debian root required}
test "$root" != / && test -f "$root/etc/debian_version"
test -x "$root/usr/lib/systemd/systemd-timesyncd"
install -d "$root/etc/systemd/timesyncd.conf.d"
cat > "$root/etc/systemd/timesyncd.conf.d/50-guide.conf" <<'EOF'
[Time]
NTP=0.debian.pool.ntp.org 1.debian.pool.ntp.org 2.debian.pool.ntp.org 3.debian.pool.ntp.org
PollIntervalMinSec=32
PollIntervalMaxSec=2048
SaveIntervalSec=3600
EOF
# NetworkManager connectivity is sufficient; never gate the interface on NTP.
chroot "$root" systemctl enable systemd-timesyncd.service
test -f "$root/usr/share/zoneinfo/America/New_York"
ln -sfn /usr/share/zoneinfo/America/New_York "$root/etc/localtime"
printf 'America/New_York\n' > "$root/etc/timezone"
chroot "$root" systemd-analyze verify --man=no systemd-timesyncd.service
