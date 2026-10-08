#!/bin/bash
set -euo pipefail
root=${1:?Mounted candidate root required}
binary=${2:?Compiled renderer required}
here=$(cd -- "$(dirname -- "$0")" && pwd)

# Compatibility entry point for older image-build scripts. Dynamic boot-world
# installation is retired; every caller now receives the prebaked player.
exec "$here/install.sh" --root "$root" --binary "$binary"
