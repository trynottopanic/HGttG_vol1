#!/bin/sh
# No session deadline: only an explicit successful Save + finish powers off.
set -u
boot_id=$(cat /proc/sys/kernel/random/boot_id)
report=/data/guideos/diagnostics/$boot_id
boot_report=/boot/diagnostics/$boot_id
say() { printf '%s\n' "$*"; printf '%s\n' "$*" > /dev/tty1 2>/dev/null || true; }
if ! mountpoint -q /data || ! mountpoint -q /boot; then
  say 'BUTTON CHECK CANNOT START: report storage is not mounted.'
  exit 1
fi
mkdir -p "$report" "$boot_report" || exit 1
save() {
  dmesg > "$report/dmesg.txt"
  journalctl -b --no-pager > "$report/journal.txt"
  cp "$report/"*.txt "$boot_report/" || return 1
  sync
}
printf '%s\n' "$boot_id" > "$report/boot-id.txt"
printf 'Debian diagnostic 4: untimed digital button baseline.\n' > "$report/userspace-reached.txt"
printf '%s\n' "$boot_id" > /boot/diagnostics/latest-boot.txt
date -u > "$report/date.txt"
uname -a > "$report/kernel.txt"
cat /proc/cmdline > "$report/cmdline.txt"
cat /proc/bus/input/devices > "$report/input.txt"
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS > "$report/storage.txt" 2>&1
say 'GUIDEOS BUTTON BASELINE: loading the untimed checklist.'
say 'Start, Power and Reset are excluded.'
save || say 'Warning: could not mirror initial boot notes.'
/usr/bin/python3 /usr/lib/guideos/button-baseline.py --report "$report" --mirror "$boot_report" > "$report/button-service.txt" 2>&1
status=$?
printf '\nButton check exit status: %s\n' "$status" >> "$report/button-service.txt"
if test "$status" != 0; then
  printf 'Button check interrupted or failed; inspect button-service.txt and partial results.\n' > "$report/completion.txt"
  save || true
  say 'BUTTON CHECK STOPPED. Partial reports retained; shutdown was not requested.'
  exit "$status"
fi
printf 'User chose Save + finish. Both report copies saved; requesting orderly shutdown.\n' > "$report/completion.txt"
if ! save; then
  say 'REPORT COPY FAILED. Device left on; inspect saved results before shutdown.'
  exit 1
fi
say 'BUTTON RESULTS SAVED. Shutting down safely.'
sync
systemctl poweroff
