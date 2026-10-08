#!/bin/sh
set -u
boot_id=$(cat /proc/sys/kernel/random/boot_id)
report=/data/guideos/diagnostics/$boot_id
boot_report=/boot/diagnostics/$boot_id
mkdir -p "$report" "$boot_report" || exit 1
say() { printf '%s\n' "$*"; printf '%s\n' "$*" > /dev/tty1 2>/dev/null || true; }
save() {
  dmesg > "$report/dmesg.txt"
  journalctl -b --no-pager > "$report/journal.txt"
  cp "$report/"*.txt "$boot_report/"
  sync
}
printf '%s\n' "$boot_id" > "$report/boot-id.txt"
printf 'Debian diagnostic 2 started.\n' > "$report/userspace-reached.txt"
printf '%s\n' "$boot_id" > /boot/diagnostics/latest-boot.txt
say 'GUIDEOS DEBIAN DIAGNOSTIC 2: USERSPACE REACHED'
say 'Controls test, then rotating cube, then automatic shutdown.'
save
sleep 10
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
printf 'No matching game controller found.\n' > "$report/game-events.txt"
for node in /sys/class/input/event*; do
  case "$(cat "$node/device/name" 2>/dev/null)" in
    *[Gg]amepad*|*[Jj]oypad*|*ROCKNIX*|*Anbernic*)
      say 'CONTROLS: press game buttons and move both sticks for 30 seconds.'
      timeout -k 3 30 stdbuf -oL -eL evtest "/dev/input/${node##*/}" > "$report/game-events.txt" 2>&1
      printf '\nExit status: %s (124 means timed capture finished)\n' "$?" >> "$report/game-events.txt"
      break;;
  esac
done
save
timeout -k 3 10 modetest -M sun4i-drm -c -p > "$report/drm-connectors.txt" 2>&1 || true
timeout -k 3 15 eglinfo.aarch64-linux-gnu -B -p gbm > "$report/egl.txt" 2>&1
printf '\nExit status: %s\n' "$?" >> "$report/egl.txt"
printf 'No display controller found.\n' > "$report/cube.txt"
# kmscube watches stdin with select(). /dev/null is immediately readable at EOF.
# Hold a private FIFO open for reading and writing, without supplying any input.
# Its descriptor stays idle until the bounded renderer exits; no helper process.
fifo=/run/guide-cube-$boot_id.fifo
cleanup() { exec 3>&-; rm -f "$fifo"; }
trap cleanup EXIT
for node in /sys/class/drm/card[0-9]*; do
  test -e "$node/device" || continue
  driver=$(readlink -f "$node/device/driver" 2>/dev/null || true)
  case "$driver" in
    */sun4i-drm)
      say 'GRAPHICS: rotating cube, 1800 frames (up to 40 seconds).'
      if mkfifo -m 600 "$fifo"; then
        exec 3<> "$fifo"
        started=$(cut -d ' ' -f 1 /proc/uptime)
        timeout -k 3 40 stdbuf -oL -eL kmscube -D "/dev/dri/${node##*/}" -c 1800 <&3 > "$report/cube.txt" 2>&1
        status=$?
        finished=$(cut -d ' ' -f 1 /proc/uptime)
        printf '\nExit status: %s (124 means time limit reached)\nUptime start: %s\nUptime end: %s\n' "$status" "$started" "$finished" >> "$report/cube.txt"
        cleanup
      else
        printf 'Failed to prepare idle renderer input.\n' > "$report/cube.txt"
      fi
      break;;
  esac
done
systemctl --failed --no-pager > "$report/failed-units.txt"
printf 'Diagnostic tests finished; requesting orderly poweroff.\n' > "$report/completion.txt"
save
say 'DIAGNOSTICS SAVED. POWERING OFF IN 10 SECONDS.'
sleep 10
sync
systemctl poweroff
