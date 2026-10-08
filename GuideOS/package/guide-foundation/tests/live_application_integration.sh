#!/bin/sh
set -eu
project=${1:?project root required}
work=/run/guide-foundation-integration
libexec=/usr/libexec/guideos
units=/run/systemd/system
exact_paths="/run/systemd/system/guide-cartridge-parser.socket /run/systemd/system/guide-cartridge-parser.service /usr/lib/guideos/installer /var/lib/guideos/installer /etc/guideos/installer-reserve-bytes /run/guideos-storage /run/systemd/system/guide-installer.socket /run/systemd/system/guide-installer.service /opt/guideos/applications /var/lib/private/guideos/applications /run/guideos/health /usr/libexec/guideos/guide-application-host /usr/lib/guideos/application-host /usr/lib/guideos/ipc /var/lib/guideos/applications /var/lib/guideos/apps/10001 /var/lib/private/guideos/apps/10001 $work /run/guideos $libexec/guide-supervisor0 $libexec/guide-capability-broker0 $libexec/guide-ipc-probe $units/guide-supervisor0.service $units/guide-supervisor0.socket $units/guide-capability-broker0.service $units/guide-capability-broker0.socket $units/guide-ipc-probe.service $units/guide-supervisor0.service.d"
cleanup() {
    if test "${created_archive_user:-0}" = 1; then systemctl stop guide-cartridge-parser.service guide-cartridge-parser.socket >/dev/null 2>&1 || true; userdel guide-archive; groupdel guide-archive 2>/dev/null || true; fi
    systemctl stop guide-cartridge-parser.service guide-cartridge-parser.socket guide-installer.service guide-installer.socket >/dev/null 2>&1 || true
    rm -f /run/systemd/system/guide-cartridge-parser.socket /run/systemd/system/guide-cartridge-parser.service /run/systemd/system/guide-installer.socket /run/systemd/system/guide-installer.service /etc/guideos/installer-reserve-bytes
    rm -rf /usr/lib/guideos/installer /var/lib/guideos/installer /run/guideos-storage

    systemctl stop 'guide-app-*.service' 'guide-health-*.service' >/dev/null 2>&1 || true
    rm -f /usr/libexec/guideos/guide-application-host
    rm -rf /opt/guideos/applications /var/lib/private/guideos/applications /usr/lib/guideos/application-host /usr/lib/guideos/ipc /var/lib/guideos/applications /var/lib/private/guideos/apps/10001
    rm -f /var/lib/guideos/apps/10001
    if test "${created_group:-0}" = 1; then groupdel guide-apps || true; fi
    systemctl stop guide-capability-broker0.service guide-capability-broker0.socket guide-supervisor0.service guide-supervisor0.socket >/dev/null 2>&1 || true
    rm -f "$libexec/guide-supervisor0" "$libexec/guide-capability-broker0" "$libexec/guide-ipc-probe"
    rm -f "$units/guide-supervisor0.service" "$units/guide-supervisor0.socket" "$units/guide-capability-broker0.service" "$units/guide-capability-broker0.socket" "$units/guide-ipc-probe.service" "$units/guide-supervisor0.service.d/test.conf"
    rmdir "$units/guide-supervisor0.service.d" 2>/dev/null || true
    systemctl daemon-reload >/dev/null 2>&1 || true
    rmdir /run/guideos/health /run/guideos/apps /run/guideos/installer /run/guideos/brokers /run/guideos/broker /run/guideos/supervisor /run/guideos 2>/dev/null || true
    if test -d "$work"; then find "$work" -type f -maxdepth 1 -delete; rmdir "$work" 2>/dev/null || true; fi
}
for path in $exact_paths; do
    if test -e "$path"; then printf 'PREFLIGHT_PRESENT %s\n' "$path" >&2; exit 2; fi
done
trap cleanup EXIT HUP INT TERM
install -d -m755 "$work" "$libexec" "$units/guide-supervisor0.service.d"
install -d -m750 -o root -g daemon /run/guideos
install -d -m750 -o root -g daemon /run/guideos/supervisor
install -d -m750 -o daemon -g daemon /run/guideos/brokers
root="$project/GuideOS/package/guide-foundation"
ipc="$project/GuideOS/package/guide-ipc"
common="-std=c11 -D_GNU_SOURCE -O2 -Wall -Wextra -Werror -I$root/include -I$ipc/include -I$ipc/generated"
cc $common -c "$root/src/guide_foundation.c" -o "$work/core.o"
cc $common -c "$root/src/guide_control_codec.c" -o "$work/codec.o"
cc $common -c "$ipc/src/guide_ipc_transport.c" -o "$work/ipc.o"
cc $common -c "$ipc/src/guide_ipc_envelope.c" -o "$work/envelope.o"
cc $common -c "$root/src/guide_systemd_adapter.c" -o "$work/systemd.o"
cc $common "$root/src/guide-supervisor0.c" "$work/core.o" "$work/codec.o" "$work/ipc.o" "$work/envelope.o" "$work/systemd.o" -lsystemd -o "$work/guide-supervisor0"
cc $common "$root/src/guide-capability-broker0.c" "$work/core.o" "$work/codec.o" "$work/ipc.o" "$work/envelope.o" -o "$work/guide-capability-broker0"
cc $common "$root/src/guide-ipc-probe.c" "$work/codec.o" "$work/ipc.o" "$work/envelope.o" -o "$work/guide-ipc-probe"
install -m755 "$work/guide-supervisor0" "$libexec/guide-supervisor0"
install -m755 "$work/guide-capability-broker0" "$libexec/guide-capability-broker0"
install -m755 "$work/guide-ipc-probe" "$libexec/guide-ipc-probe"
install -m644 "$root/systemd/guide-supervisor0.service" "$units/guide-supervisor0.service"
install -m644 "$root/systemd/guide-supervisor0.socket" "$units/guide-supervisor0.socket"
install -m644 "$root/systemd/guide-capability-broker0.service" "$units/guide-capability-broker0.service"
install -m644 "$root/systemd/guide-capability-broker0.socket" "$units/guide-capability-broker0.socket"
install -m644 "$root/systemd/guide-ipc-probe.service" "$units/guide-ipc-probe.service"
sed -i 's/^User=guide-broker$/User=daemon/;s/^Group=guide-broker$/Group=daemon/' "$units/guide-capability-broker0.service"
sed -i 's/^SupplementaryGroups=guide-apps$/SupplementaryGroups=daemon/' "$units/guide-capability-broker0.service"
sed -i 's/^SocketUser=guide-broker$/SocketUser=daemon/;s/^SocketGroup=guide-apps$/SocketGroup=daemon/' "$units/guide-capability-broker0.socket"
sed -i 's/^SocketGroup=guide-broker$/SocketGroup=daemon/' "$units/guide-supervisor0.socket"
printf '[Service]\nEnvironment=GUIDE_PROBE_USER=daemon\nEnvironment=GUIDE_BROKER_USER=daemon\n' > "$units/guide-supervisor0.service.d/test.conf"
systemctl daemon-reload
systemctl start guide-supervisor0.socket guide-supervisor0.service guide-capability-broker0.socket
stat -c 'GUIDE_TEST_PATH %n %U:%G %a' /run/guideos /run/guideos/brokers /run/guideos/brokers/control.sock /run/guideos/brokers/health.sock /run/guideos/supervisor /run/guideos/supervisor/control.sock

created_group=0
if ! getent group guide-apps >/dev/null; then groupadd --system guide-apps; created_group=1; fi
chmod 755 /run/guideos /run/guideos/brokers
chgrp guide-apps /run/guideos/brokers/*.sock
install -d -m755 /usr/lib/guideos/application-host /usr/lib/guideos/ipc /var/lib/guideos/applications
install -m644 "$root/python/guide_application_runtime.py" /usr/lib/guideos/application-host/
install -m644 "$ipc/python/guide_ipc.py" /usr/lib/guideos/ipc/
install -m755 "$root/python/guide_application_host.py" /usr/libexec/guideos/guide-application-host
PYTHONPATH="$root/python:$ipc/python" python3 "$root/tests/live_application_client.py" "$root"
printf 'GUIDE_APPLICATION_LIVE_SYSTEMD_PASS\n'

installer="$project/GuideOS/package/guide-installer"
if getent passwd guide-archive >/dev/null || getent group guide-archive >/dev/null; then echo PREFLIGHT_ARCHIVE_ACCOUNT_PRESENT; exit 2; fi
groupadd --system guide-archive
useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin --gid guide-archive guide-archive
created_archive_user=1
install -d -m755 /usr/lib/guideos/installer /var/lib/guideos/installer /var/lib/private/guideos/applications /etc/guideos /run/guideos-storage
install -m644 "$installer"/*.py /usr/lib/guideos/installer/
printf '16777216\n' > /etc/guideos/installer-reserve-bytes
install -m644 "$installer/systemd/guide-cartridge-parser.socket" /run/systemd/system/
install -m644 "$installer/systemd/guide-cartridge-parser.service" /run/systemd/system/
install -m644 "$installer/systemd/guide-installer.socket" /run/systemd/system/
install -m644 "$installer/systemd/guide-installer.service" /run/systemd/system/
printf '\nEnvironment=GUIDE_INSTALLER_TEST_TRACE=1\n' >> /run/systemd/system/guide-installer.service
systemctl daemon-reload
systemctl start guide-cartridge-parser.socket guide-installer.socket
python3 "$installer/tests/live_installer_client.py" "$project/GuideOS" || { journalctl -u guide-installer.service -u guide-cartridge-parser.service --since "-2 minutes" --no-pager; exit 1; }
printf 'GUIDE_INSTALLER_LIVE_SYSTEMD_PASS\n'
