#!/bin/bash
set -euo pipefail
root=${1:?Mounted Debian root required}
here=$(cd -- "$(dirname -- "$0")" && pwd)
test "$root" != / && test -f "$root/etc/debian_version"
chroot "$root" getent group bluetooth >/dev/null || chroot "$root" groupadd --system bluetooth
chroot "$root" getent passwd guide-audio >/dev/null || chroot "$root" useradd --system --user-group --home-dir /var/lib/guideos-audio --shell /usr/sbin/nologin guide-audio
chroot "$root" usermod -a -G audio,bluetooth guide-audio
install -d "$root/usr/lib/guideos/audio" "$root/etc/systemd/system" "$root/etc/dbus-1/system.d" \
 "$root/etc/guideos/audio/wireplumber/wireplumber.conf.d" "$root/etc/systemd/system/guide-shell.service.d"
install -m644 "$here"/audio_*.py "$root/usr/lib/guideos/audio/"
install -m644 "$here"/*.service "$root/etc/systemd/system/"
install -d "$root/etc/pipewire/pipewire.conf.d" "$root/etc/pipewire/client.conf.d"
install -m644 "$here/guide-rt.conf" "$root/etc/pipewire/pipewire.conf.d/30-guide-rt.conf"
install -m644 "$here/guide-rt.conf" "$root/etc/pipewire/client.conf.d/30-guide-rt.conf"
install -m644 "$here/wireplumber.conf" "$root/etc/guideos/audio/wireplumber/wireplumber.conf.d/50-guide.conf"
cat > "$root/etc/dbus-1/system.d/guide-audio.conf" <<'EOF'
<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig><policy user="guide-audio"><allow send_destination="org.bluez"/></policy></busconfig>
EOF
cat > "$root/etc/systemd/system/guide-shell.service.d/25-audio.conf" <<'EOF'
[Unit]
Wants=guide-audio.service
[Service]
Environment=GUIDE_AUDIO=1
EOF
# Do not advertise or enable a radio merely because its software was installed.
install -d "$root/etc/bluetooth"
cat > "$root/etc/bluetooth/main.conf" <<'EOF'
[General]
DiscoverableTimeout=0
PairableTimeout=30
[Policy]
AutoEnable=false
EOF
# The media directory is created on the actual data filesystem at boot.
cat > "$root/etc/tmpfiles.d/guide-audio.conf" <<'EOF'
d /data/guideos/media 0755 root root -
C /data/guideos/media/Guide-audio-test.wav 0644 root root - /usr/share/guideos/audio/test.wav
EOF
install -d "$root/usr/share/guideos/audio"
python3 - "$root/usr/share/guideos/audio/test.wav" <<'PY'
import math,struct,sys,wave
with wave.open(sys.argv[1],'wb') as f:
 f.setparams((2,2,24000,0,'NONE','not compressed'))
 for n in range(6*24000):
  second=n/24000; section=int(second)//2
  envelope=min(1,(second%2)*20,max(0,(1.8-second%2)*20))
  sample=int(3276*math.sin(2*math.pi*440*second)*envelope)
  f.writeframesraw(struct.pack('<hh',sample if section!=1 else 0,sample if section!=0 else 0))
PY
chroot "$root" systemctl enable guide-audio.service bluetooth.service >/dev/null
chroot "$root" systemd-analyze verify --man=no guide-audio.service guide-audio-bus.service guide-pipewire.service guide-wireplumber.service guide-shell.service
