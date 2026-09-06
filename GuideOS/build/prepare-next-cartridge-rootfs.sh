#!/bin/sh
set -eu

reference_dir=/mnt/g/GuideOS-private/muos-reference
project_dir=/mnt/e/DGttG/HGttG_vol1/GuideOS
source_image=${reference_dir}/seed-before-devlink-wikipedia-rootfs.ext4
output_image=${reference_dir}/seed-devlink-wikipedia-rootfs.ext4
shell_binary=${reference_dir}/guide-hello-fb-next
rose_asset=${project_dir}/package/guide-hello-fb/src/assets/guide-rose-seal-250.rgba
mount_dir=/mnt/guideos-next-root
source_hash=4a573f4ceabf8553281762070122112b99e4a4eb4b40b41bea9f2209f8fe4358
shell_hash=fa3bd0508dc9a490b81bafb32049f34588cf7bce44ba4b0e2e8460eb984155b0
rose_hash=ea8ef43320283004b4260eaaabf80748a3b8219cf77b29112b035617d89d7dd7

test -f "${source_image}"
test "$(stat -c %s "${source_image}")" -eq 2147483648
test "$(sha256sum "${source_image}" | cut -d ' ' -f 1)" = "${source_hash}"
test -x "${shell_binary}"
test "$(sha256sum "${shell_binary}" | cut -d ' ' -f 1)" = "${shell_hash}"
test -f "${rose_asset}"
test "$(sha256sum "${rose_asset}" | cut -d ' ' -f 1)" = "${rose_hash}"

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
install -D -m 0644 "${rose_asset}" \
    "${mount_dir}/usr/share/guideos/guide-rose-seal-250.rgba"

for required in \
    usr/bin/python3 \
    usr/bin/unzip \
    usr/sbin/iw \
    usr/sbin/wpa_supplicant \
    usr/sbin/wpa_passphrase \
    lib/modules/4.9.170/kernel/drivers/net/wireless/8821cs.ko \
    usr/share/guideos/guide-globe-emblem-256.rgba
do
    test -e "${mount_dir}/${required}"
done

test "$(sha256sum "${mount_dir}/init" | cut -d ' ' -f 1)" = "${shell_hash}"
test "$(sha256sum "${mount_dir}/usr/sbin/guide-hello-fb" | cut -d ' ' -f 1)" = "${shell_hash}"
test "$(sha256sum "${mount_dir}/usr/share/guideos/guide-rose-seal-250.rgba" | cut -d ' ' -f 1)" = "${rose_hash}"
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
echo "ROSE $(sha256sum "${rose_asset}")"
