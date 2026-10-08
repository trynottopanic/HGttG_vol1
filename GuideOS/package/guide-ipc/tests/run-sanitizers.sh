#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d)
cleanup() { jobs -p 2>/dev/null | xargs -r kill 2>/dev/null || true; rm -rf -- "$tmp"; }
trap cleanup EXIT HUP INT TERM

cc -std=c11 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
  -Wall -Wextra -Werror -I"$root/include" \
  "$root/src/guide_ipc_envelope.c" "$root/tests/guide_ipc_spike.c" \
  $(pkg-config --cflags --libs libcbor) -o "$tmp/spike"

"$tmp/spike" server "$tmp/c.sock" >"$tmp/c.out" & pid=$!
while [ ! -S "$tmp/c.sock" ]; do sleep .02; done
PYTHONPATH="$root/python" python3 "$root/tests/guide_ipc_spike.py" client "$tmp/c.sock"
wait "$pid"
cat "$tmp/c.out"

PYTHONPATH="$root/python" python3 "$root/tests/guide_ipc_spike.py" server "$tmp/p.sock" >"$tmp/p.out" & pid=$!
while [ ! -S "$tmp/p.sock" ]; do sleep .02; done
"$tmp/spike" client "$tmp/p.sock"
wait "$pid"
cat "$tmp/p.out"
cc -std=c11 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
  -Wall -Wextra -Werror -I"$root/include" \
  "$root/src/guide_ipc_envelope.c" "$root/tests/mutation.c" -o "$tmp/mutation"
"$tmp/mutation"
printf '%s\n' GUIDE_IPC_SANITIZERS_PASS
