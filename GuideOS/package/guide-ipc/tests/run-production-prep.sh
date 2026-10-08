#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
python3 "$root/tools/generate.py" --check
cc -std=c11 -D_GNU_SOURCE -Wall -Wextra -Werror -fPIC -I"$root/include" -c "$root/src/guide_ipc_envelope.c" -o "$tmp/envelope.o"
cc -std=c11 -D_GNU_SOURCE -Wall -Wextra -Werror -fPIC -I"$root/include" -c "$root/src/guide_ipc_transport.c" -o "$tmp/transport.o"
cc -std=c11 -Wall -Wextra -Werror -fPIC -I"$root/generated" -c "$root/generated/guide_ipc_interfaces.c" -o "$tmp/interfaces.o"
cc -shared -Wl,-z,relro,-z,now -o "$tmp/libguide-ipc.so" "$tmp/envelope.o" "$tmp/transport.o" "$tmp/interfaces.o"
cc -std=c11 -D_GNU_SOURCE -Wall -Wextra -Werror -I"$root/include" "$root/tests/test_transport.c" "$tmp/envelope.o" "$tmp/transport.o" -o "$tmp/test-transport"
"$tmp/test-transport"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v "$root/tests/test_production_prep.py"
size "$tmp/libguide-ipc.so"
echo GUIDE_IPC_PRODUCTION_PREP_PASS
