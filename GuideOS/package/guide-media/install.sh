#!/bin/sh
set -eu
root=${1:?root filesystem required}
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test "$root" != /
install -d -m755 "$root/usr/lib/guideos/media"
for name in media_source_channel.py media_player_service.py gst_descriptor_backend.py gst_descriptor_worker.py buffer_policy.py gst_audio_adapter.py mpv_backend.py mpv_video_adapter.py video_options.py cedrus_runtime.py \
            media_library.py media_library_broker.py media_session.py \
            media_session_broker.py provider_grants.py storage_media_host.py storage_media_runtime.py; do
    install -m644 "$here/$name" "$root/usr/lib/guideos/media/$name"
done

# Shared runtime imports required by the installed broker modules.
install -d -m755 "$root/usr/lib/guideos/ipc"
install -m644 "$here/../guide-ipc/python/guide_grants.py" "$root/usr/lib/guideos/ipc/"
install -m644 "$here/../guide-ipc/generated/guide_ipc_interfaces.py" "$root/usr/lib/guideos/ipc/"

install -d -m755 "$root/etc/systemd/system" "$root/etc/pipewire/client.conf.d" "$root/etc/pipewire/client-rt.conf.d" "$root/etc/systemd/system/guide-shell.service.d"
install -m644 "$here/guide-media-player.service" "$here/guide-media-player.socket" "$root/etc/systemd/system/"
for folder in client.conf.d client-rt.conf.d; do
    install -m644 "$here/80-guideos-video-route.conf" "$root/etc/pipewire/$folder/"
done
cat > "$root/etc/systemd/system/guide-shell.service.d/45-media-player.conf" <<'EOF'
[Unit]
Wants=guide-media-player.socket
[Service]
Environment=GUIDE_MEDIA_PLAYERS=1
EOF
ln -sf /etc/systemd/system/guide-media-player.socket "$root/etc/systemd/system/sockets.target.wants/guide-media-player.socket"
