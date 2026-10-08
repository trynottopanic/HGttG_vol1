#!/bin/sh
set -eu
project=${1:?project root required}
work=/run/guide-foundation-integration
libexec=/usr/libexec/guideos
units=/run/systemd/system
exact_paths="$work /run/guideos $libexec/guide-supervisor0 $libexec/guide-capability-broker0 $libexec/guide-ipc-probe $units/guide-supervisor0.service $units/guide-supervisor0.socket $units/guide-capability-broker0.service $units/guide-capability-broker0.socket $units/guide-ipc-probe.service $units/guide-supervisor0.service.d"
cleanup() {
    systemctl stop guide-capability-broker0.service guide-capability-broker0.socket guide-supervisor0.service guide-supervisor0.socket >/dev/null 2>&1 || true
    rm -f "$libexec/guide-supervisor0" "$libexec/guide-capability-broker0" "$libexec/guide-ipc-probe"
    rm -f "$units/guide-supervisor0.service" "$units/guide-supervisor0.socket" "$units/guide-capability-broker0.service" "$units/guide-capability-broker0.socket" "$units/guide-ipc-probe.service" "$units/guide-supervisor0.service.d/test.conf"
    rmdir "$units/guide-supervisor0.service.d" 2>/dev/null || true
    systemctl daemon-reload >/dev/null 2>&1 || true
    rmdir /run/guideos/brokers /run/guideos/broker /run/guideos/supervisor /run/guideos 2>/dev/null || true
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
identity=$(PYTHONPATH="$ipc/python:$ipc/generated" python3 "$root/tests/owner_client.py" "$ipc/python" launch)
instance=$(printf '%s\n' "$identity" | cut -d' ' -f1)
generation=$(printf '%s\n' "$identity" | cut -d' ' -f2)
case "$instance:$generation" in (*[!0-9a-f:]*|????????????????????????????????:0|????????????????????????????????:) exit 1;; esac
unit="guide-app-$instance-g$generation.service"
printf 'GUIDE_OWNER_LAUNCH_PASS %s %s\n' "$instance" "$generation"
for attempt in $(seq 1 100); do
    if journalctl -u "$unit" --since '-1 minute' --no-pager | grep -q GUIDE_GRANT_ACQUIRED; then break; fi
    test "$attempt" -lt 100 || { journalctl -u "$unit" -u guide-capability-broker0.service --since '-1 minute' --no-pager; exit 1; }
    sleep .05
done
systemctl restart guide-capability-broker0.service
for attempt in $(seq 1 200); do
    if journalctl -u 'guide-app-*.service' --since '-1 minute' --no-pager | grep -q GUIDE_IPC_PROBE_PASS; then break; fi
    test "$attempt" -lt 200 || { journalctl -u guide-supervisor0.service -u guide-capability-broker0.service -u "$unit" --since '-1 minute' --no-pager; exit 1; }
    sleep .05
done
pid_before=$(systemctl show -p MainPID --value "$unit")
invocation_before=$(systemctl show -p InvocationID --value "$unit")
test "$pid_before" -gt 0 && test ${#invocation_before} -eq 32
supervisor_pid=$(systemctl show -p MainPID --value guide-supervisor0.service)
broker_pid=$(systemctl show -p MainPID --value guide-capability-broker0.service)
for measured in "supervisor:$supervisor_pid" "broker:$broker_pid" "probe:$pid_before"; do
    name=${measured%%:*}; pid=${measured#*:}; rss=$(awk '/^VmRSS:/{print $2}' "/proc/$pid/status"); descriptors=$(find "/proc/$pid/fd" -mindepth 1 -maxdepth 1 | wc -l); printf 'GUIDE_METRIC %s rss_kib=%s descriptors=%s\n' "$name" "$rss" "$descriptors"
done
systemctl restart guide-supervisor0.service
test "$(systemctl show -p MainPID --value "$unit")" = "$pid_before"
test "$(systemctl show -p InvocationID --value "$unit")" = "$invocation_before"
PYTHONPATH="$ipc/python:$ipc/generated" python3 "$root/tests/owner_client.py" "$ipc/python" stop "$instance" "$generation"
for attempt in $(seq 1 100); do
    test "$(systemctl is-active "$unit" 2>/dev/null || true)" != active && break
    test "$attempt" -lt 100 || exit 1
    sleep .05
done
test ! -d "/sys/fs/cgroup/system.slice/$unit"
systemctl is-active guide-supervisor0.service guide-capability-broker0.service >/dev/null
identity=$(PYTHONPATH="$ipc/python:$ipc/generated" python3 "$root/tests/owner_client.py" "$ipc/python" launch)
instance=$(printf '%s\n' "$identity" | cut -d' ' -f1)
generation=$(printf '%s\n' "$identity" | cut -d' ' -f2)
case "$instance:$generation" in (*[!0-9a-f:]*|????????????????????????????????:0|????????????????????????????????:) exit 1;; esac
unit="guide-app-$instance-g$generation.service"
for attempt in $(seq 1 100); do
    journalctl -u "$unit" --since '-1 minute' --no-pager | grep -q GUIDE_GRANT_ACQUIRED && break
    test "$attempt" -lt 100 || exit 1
    sleep .05
done
systemctl restart guide-capability-broker0.service
for attempt in $(seq 1 200); do
    journalctl -u "$unit" --since '-1 minute' --no-pager | grep -q GUIDE_IPC_PROBE_PASS && break
    test "$attempt" -lt 200 || exit 1
    sleep .05
done
record="/run/guideos/supervisor/$instance.record"
test -f "$record" && grep -Eq '^invocation=[0-9a-f]{32}$' "$record"
sed -i 's/^invocation=.*/invocation=00000000000000000000000000000000/' "$record"
pid_before=$(systemctl show -p MainPID --value "$unit")
systemctl restart guide-supervisor0.service
test "$(systemctl show -p MainPID --value "$unit")" = "$pid_before"
test ! -e "$record"
PYTHONPATH="$ipc/python:$ipc/generated" python3 "$root/tests/owner_client.py" "$ipc/python" stop-denied "$instance" "$generation"
systemctl stop "$unit"
for attempt in $(seq 1 100); do
    test ! -d "/sys/fs/cgroup/system.slice/$unit" && break
    test "$attempt" -lt 100 || exit 1
    sleep .05
done
printf 'GUIDE_SUPERVISOR_RECONCILIATION_PASS\n'
printf 'GUIDE_BROKER_RESTART_INVALIDATION_PASS\n'
printf 'GUIDE_CGROUP_REAP_STOP_PASS\n'
printf 'GUIDE_STALE_INVOCATION_REJECTION_PASS\n'
printf 'GUIDE_LIVE_SYSTEMD_INTEGRATION_PASS\n'
