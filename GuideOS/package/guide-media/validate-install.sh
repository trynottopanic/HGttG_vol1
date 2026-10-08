#!/bin/sh
set -eu
root=${1:?root filesystem required}
base="$root/usr/lib/guideos/media"
for name in buffer_policy.py gst_audio_adapter.py mpv_backend.py mpv_video_adapter.py video_options.py cedrus_runtime.py \
            media_library.py media_library_broker.py media_session.py \
            media_session_broker.py provider_grants.py storage_media_host.py storage_media_runtime.py; do
    test -r "$base/$name"
done
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$base:$root/usr/lib/guideos/ipc:$root/usr/lib/guideos/application-host" \
    python3 -m py_compile "$base"/*.py
printf '%s\n' GUIDE_MEDIA_SOURCE_INSTALL_PASS
