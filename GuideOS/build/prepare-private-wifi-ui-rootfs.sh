#!/bin/sh
set -eu

reference_dir=/mnt/g/GuideOS-private/muos-reference
source_image=${reference_dir}/seed-post-wifi-ui-failure-rootfs.ext4
output_image=${reference_dir}/seed-wifi-ui-font-reconnect-shutdown-rootfs.ext4
shell_binary=${reference_dir}/guide-hello-fb-wifi-ui
mount_dir=/mnt/guideos-wifi-ui-root

test -f "${source_image}"
test "$(stat -c %s "${source_image}")" -eq 2147483648
test -x "${shell_binary}"

cp "${source_image}" "${output_image}"
mkdir -p "${mount_dir}"
mount -o loop,rw "${output_image}" "${mount_dir}"
cleanup() {
    if mountpoint -q "${mount_dir}"; then
        sync
        umount "${mount_dir}"
    fi
}
trap cleanup EXIT INT TERM

install -m 0755 "${shell_binary}" "${mount_dir}/init"
install -m 0755 "${shell_binary}" "${mount_dir}/usr/sbin/guide-hello-fb"

for required in \
    usr/sbin/iw \
    usr/sbin/wpa_supplicant \
    usr/sbin/wpa_passphrase \
    lib/modules/4.9.170/kernel/drivers/net/wireless/8821cs.ko \
    usr/share/guideos/guide-globe-emblem-256.rgba
do
    test -f "${mount_dir}/${required}"
done

sync
umount "${mount_dir}"
trap - EXIT INT TERM
set +e
e2fsck -fy "${output_image}"
check_status=$?
set -e
test "${check_status}" -eq 0 -o "${check_status}" -eq 1
e2fsck -fn "${output_image}"

echo "ROOTFS $(sha256sum "${output_image}")"
echo "SHELL $(sha256sum "${shell_binary}")"
