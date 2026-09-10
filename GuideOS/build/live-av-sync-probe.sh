#!/bin/sh
set -eu

DELAY_SECONDS="${1:-0.30}"
RUN_SECONDS="${2:-20}"
CONTROLLER_PID="${3:-}"
FFMPEG_PID="${4:-}"
audio_pid=""
video_pid=""

cleanup() {
    [ -n "$video_pid" ] && kill -KILL "$video_pid" 2>/dev/null || true
    [ -n "$audio_pid" ] && kill -KILL "$audio_pid" 2>/dev/null || true
    [ -n "$FFMPEG_PID" ] && kill -KILL "$FFMPEG_PID" 2>/dev/null || true
    [ -n "$CONTROLLER_PID" ] && kill -KILL "$CONTROLLER_PID" 2>/dev/null || true
}
trap cleanup EXIT HUP INT TERM

if [ -z "$CONTROLLER_PID" ] || [ -z "$FFMPEG_PID" ] ||
   [ ! -r "/proc/$FFMPEG_PID/cmdline" ]; then
    /usr/bin/python3 /usr/lib/guideos/node-link/guide_node_bridge.py play 3 \
        >/tmp/guide-sync-bootstrap.log 2>&1 &
    CONTROLLER_PID=$!
    count=0
    while [ "$count" -lt 50 ]; do
        FFMPEG_PID=$(ps -o pid,ppid,args | awk -v parent="$CONTROLLER_PID" \
            '$2 == parent && $0 ~ /ffmpeg/ { print $1; exit }')
        [ -n "${FFMPEG_PID:-}" ] && [ -r "/proc/$FFMPEG_PID/cmdline" ] && break
        count=$((count + 1))
        sleep 0.1
    done
fi

[ -n "$CONTROLLER_PID" ]
[ -n "$FFMPEG_PID" ]
[ -r "/proc/$FFMPEG_PID/cmdline" ]

cmdline=$(tr '\000' '\n' < "/proc/$FFMPEG_PID/cmdline")
source=$(printf '%s\n' "$cmdline" | sed -n '/^http:\/\//{p;q}')
audio=$(printf '%s\n' "$cmdline" | sed -n '/^bluealsa:/{p;q}')
[ -n "$source" ]
[ -n "$audio" ]

control="/run/guideos-media-control-$CONTROLLER_PID"
[ -f "$control" ]
printf 'stop\n' >> "$control"

count=0
while kill -0 "$CONTROLLER_PID" 2>/dev/null && [ "$count" -lt 30 ]; do
    count=$((count + 1))
    sleep 0.1
done
if kill -0 "$CONTROLLER_PID" 2>/dev/null; then
    echo "The original player did not stop." >&2
    exit 2
fi

RUNTIME=/usr/lib/guideos/media
LOADER="$RUNTIME/lib/ld-linux-aarch64.so.1"
FFMPEG="$RUNTIME/bin/ffmpeg"
export LD_LIBRARY_PATH="$RUNTIME/lib"
export ALSA_PLUGIN_DIR="$RUNTIME/alsa-lib"
export ALSA_CONFIG_PATH=/opt/guide/bluetooth/alsa-media.conf

"$LOADER" --library-path "$RUNTIME/lib" "$FFMPEG" \
    -nostdin -hide_banner -loglevel warning -threads 2 -readrate 1 \
    -i "$source" -map '0:a:0?' -vn -f alsa "$audio" \
    >/tmp/guide-sync-audio.log 2>&1 &
audio_pid=$!

sleep "$DELAY_SECONDS"

"$LOADER" --library-path "$RUNTIME/lib" "$FFMPEG" \
    -nostdin -hide_banner -loglevel warning -threads 2 -readrate 1 \
    -i "$source" -map 0:v:0 \
    -vf 'scale=640:480:force_original_aspect_ratio=decrease,pad=640:480:(ow-iw)/2:(oh-ih)/2' \
    -sws_flags fast_bilinear -filter_threads 2 -pix_fmt bgra \
    -an -f fbdev /dev/fb0 \
    >/tmp/guide-sync-video.log 2>&1 &
video_pid=$!

echo "SYNC_PROBE delay=$DELAY_SECONDS audio_pid=$audio_pid video_pid=$video_pid"
sleep "$RUN_SECONDS"
kill -KILL "$video_pid" "$audio_pid" 2>/dev/null || true
wait "$video_pid" 2>/dev/null || true
wait "$audio_pid" 2>/dev/null || true
video_pid=""
audio_pid=""
FFMPEG_PID=""
CONTROLLER_PID=""
echo "SYNC_PROBE_COMPLETE"
