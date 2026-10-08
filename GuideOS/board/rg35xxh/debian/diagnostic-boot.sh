#!/bin/sh
set -u
report=/data/guideos/diagnostics
mkdir -p "$report"
say() { printf '%s\n' "$*"; printf '%s\n' "$*" > /dev/tty1 2>/dev/null || true; }
say 'GUIDEOS DEBIAN DIAGNOSTIC 0: USERSPACE REACHED'
say 'Collecting hardware status. Automatic power-off in about 60 seconds.'
mkdir -p /boot/diagnostics
printf 'Debian diagnostic service started.\n' > /boot/diagnostics/userspace-reached.txt
dmesg > /boot/diagnostics/early-dmesg.txt
sync
# Give asynchronously probed devices time to settle before the final inventory.
sleep 60
date -u > "$report/date.txt"
uname -a > "$report/kernel.txt"
cat /proc/cmdline > "$report/cmdline.txt"
cat /proc/bus/input/devices > "$report/input.txt"
cat /proc/meminfo > "$report/memory.txt"
find -L /sys/class/drm -maxdepth 2 -type f -name status -exec sh -c 'echo "$1"; cat "$1"' sh {} \; > "$report/displays.txt"
ls -l /dev/fb* /dev/dri /dev/input > "$report/device-nodes.txt" 2>&1 || true
aplay -l > "$report/audio.txt" 2>&1 || true
ip -brief link > "$report/network.txt" 2>&1 || true
find -L /sys/class/power_supply -maxdepth 2 -name uevent -exec cat {} \; > "$report/power.txt" 2>&1 || true
dmesg > "$report/dmesg.txt"
journalctl -b --no-pager > "$report/journal.txt"
systemctl --failed --no-pager > "$report/failed-units.txt"
mkdir -p /boot/diagnostics
cp "$report/"*.txt /boot/diagnostics/ || true
say 'DIAGNOSTICS SAVED. POWERING OFF.'
sync
systemctl poweroff
