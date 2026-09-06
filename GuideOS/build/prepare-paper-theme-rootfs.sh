#!/bin/sh
set -eu

# Prepare a new root filesystem image; never modify the known-good source.
reference_dir=/mnt/g/GuideOS-private/muos-reference
project_dir=/mnt/e/DGttG/HGttG_vol1/GuideOS
source_image=${reference_dir}/seed-paper-theme-base-snapshot.ext4
output_image=${reference_dir}/seed-paper-theme-rootfs.ext4
shell_binary=${project_dir}/build/theme-update/guide-hello-fb
rose_asset=${project_dir}/build/theme-update/guide-rose-seal-250.rgba
mount_dir=/mnt/guideos-paper-theme

source_hash=7200481cbbb91ffd37878a21991012b953c31d3a16bff198949f38283606a9fa
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
echo "SHELL  $(sha256sum "${shell_binary}")"
echo "ROSE   $(sha256sum "${rose_asset}")"
