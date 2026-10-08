#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
package=$(dirname "$here")
export PYTHONPATH="$here:$package/guide-ipc/python:$package/guide-ipc/generated:$package/guide-supervisor/host"
python3 -m unittest -v "$here/test_media_library.py" "$here/test_media_session.py" "$here/test_engine_adapters.py" "$here/test_media_watch.py" "$here/test_native_player.py"
