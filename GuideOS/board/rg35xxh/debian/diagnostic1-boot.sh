#!/bin/sh
set -u
report=/data/guideos/diagnostics
mkdir -p "$report" /boot/diagnostics
say() { printf '%s\n' "$*"; printf '%s\n' "$*" > /dev/tty1 2>/dev/null || true; }
say 'GUIDEOS DEBIAN DIAGNOSTIC 1: USERSPACE REACHED'
say 'Press the game buttons and move both sticks during this test.'
say 'Graphics tests and automatic shutdown will follow.'
printf 'Debian diagnostic 1 started.\n' > /boot/diagnostics/userspace-reached.txt
dmesg > /boot/diagnostics/early-dmesg.txt
sync
sleep 20
mountpoint -q /sys/kernel/debug || mount -t debugfs debugfs /sys/kernel/debug
cat /sys/kernel/debug/devices_deferred > "$report/deferred-devices.txt" 2>&1 || true
date -u > "$report/date.txt"
uname -a > "$report/kernel.txt"
cat /proc/cmdline > "$report/cmdline.txt"
cat /proc/bus/input/devices > "$report/input.txt"
cat /proc/meminfo > "$report/memory.txt"
{
  for node in /sys/class/drm/*; do
    test -f "$node/status" || continue
    echo "$node"; cat "$node/status"
    cat "$node/modes" 2>/dev/null || true
  done
} > "$report/displays.txt"
ls -l /dev/fb* /dev/dri /dev/input /sys/class/bluetooth > "$report/device-nodes.txt" 2>&1 || true
aplay -l > "$report/audio.txt" 2>&1 || true
ip -brief link > "$report/network.txt" 2>&1 || true
iw dev > "$report/wifi.txt" 2>&1 || true
{
  for node in /sys/class/power_supply/*/uevent; do
    test -f "$node" && cat "$node"
  done
} > "$report/power.txt"
event_pid=
for node in /sys/class/input/event*; do
  case "$(cat "$node/device/name" 2>/dev/null)" in
    *[Jj]oypad*|*ROCKNIX*|*Anbernic*)
      say 'Recording game controls for 20 seconds: press buttons and move sticks.'
      timeout 20 evtest "/dev/input/${node##*/}" > "$report/game-events.txt" 2>&1 &
      event_pid=$!
      break;;
  esac
done
timeout 10 modetest -M sun4i-drm -c -p > "$report/drm-connectors.txt" 2>&1 || true
timeout 15 eglinfo.aarch64-linux-gnu -B -p gbm > "$report/egl.txt" 2>&1
printf '\nExit status: %s\n' "$?" >> "$report/egl.txt"
# DRM devices may enumerate in either order; use the display controller card.
for node in /sys/class/drm/card[0-9]; do
  driver=$(readlink -f "$node/device/driver" 2>/dev/null || true)
  case "$driver" in
    */sun4i-drm)
      say 'Testing a rotating cube for up to 15 seconds.'
      timeout 15 stdbuf -oL -eL kmscube -D "/dev/dri/${node##*/}" -c 360 > "$report/cube.txt" 2>&1
      printf '\nExit status: %s\n' "$?" >> "$report/cube.txt"
      break;;
  esac
done
test -z "$event_pid" || wait "$event_pid" || true
sleep 10
dmesg > "$report/dmesg.txt"
journalctl -b --no-pager > "$report/journal.txt"
systemctl --failed --no-pager > "$report/failed-units.txt"
cp "$report/"*.txt /boot/diagnostics/ || true
say 'DIAGNOSTICS SAVED. POWERING OFF.'
sync
systemctl poweroff
