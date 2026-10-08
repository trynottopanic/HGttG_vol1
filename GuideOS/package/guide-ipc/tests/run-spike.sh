#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d)
cleanup() {
    jobs -p 2>/dev/null | xargs -r kill 2>/dev/null || true
    rm -rf -- "$tmp"
}
trap cleanup EXIT HUP INT TERM

cc -std=c11 -O2 -Wall -Wextra -Werror \
  -I"$root/include" \
  "$root/src/guide_ipc_envelope.c" "$root/tests/guide_ipc_spike.c" \
  $(pkg-config --cflags --libs libcbor) -o "$tmp/guide-ipc-spike"

PYTHONPATH="$root/python" python3 "$root/tests/guide_ipc_spike.py" profile

wait_for_socket() {
    socket=$1
    count=0
    while [ ! -S "$socket" ]; do
        count=$((count + 1))
        [ "$count" -lt 100 ] || { echo "socket did not appear: $socket" >&2; return 1; }
        sleep 0.02
    done
}

socket="$tmp/c-server.sock"
"$tmp/guide-ipc-spike" server "$socket" >"$tmp/c-server.out" 2>"$tmp/c-server.err" &
pid=$!
wait_for_socket "$socket"
PYTHONPATH="$root/python" python3 "$root/tests/guide_ipc_spike.py" client "$socket"
wait "$pid"
cat "$tmp/c-server.out"

socket="$tmp/python-server.sock"
PYTHONPATH="$root/python" python3 "$root/tests/guide_ipc_spike.py" server "$socket" >"$tmp/python-server.out" 2>"$tmp/python-server.err" &
pid=$!
wait_for_socket "$socket"
"$tmp/guide-ipc-spike" client "$socket"
wait "$pid"
cat "$tmp/python-server.out"

for kind in magic duplicate length; do
    socket="$tmp/malformed-$kind.sock"
    "$tmp/guide-ipc-spike" server "$socket" >"$tmp/malformed-$kind.out" 2>"$tmp/malformed-$kind.err" &
    pid=$!
    wait_for_socket "$socket"
    PYTHONPATH="$root/python" python3 "$root/tests/guide_ipc_spike.py" malformed "$socket" "$kind"
    set +e
    wait "$pid"
    status=$?
    set -e
    [ "$status" -eq 3 ] || { echo "malformed $kind server exit $status, expected 3" >&2; exit 1; }
done

if command -v systemd-socket-activate >/dev/null 2>&1; then
    socket="$tmp/activated.sock"
    systemd-socket-activate --seqpacket -l "$socket" \
      "$tmp/guide-ipc-spike" server "$socket" >"$tmp/activated.out" 2>"$tmp/activated.err" &
    pid=$!
    wait_for_socket "$socket"
    PYTHONPATH="$root/python" python3 "$root/tests/guide_ipc_spike.py" client "$socket"
    wait "$pid"
    grep -q C_SERVER_PASS "$tmp/activated.out"
    echo SYSTEMD_ACTIVATION_PASS
else
    echo SYSTEMD_ACTIVATION_SKIPPED
fi

size "$tmp/guide-ipc-spike" | tail -n 1
printf '%s\n' GUIDE_IPC_SPIKE_PASS
