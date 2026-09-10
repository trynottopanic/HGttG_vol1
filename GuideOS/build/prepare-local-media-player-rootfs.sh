#!/bin/sh
set -eu

reference_dir=/mnt/g/GuideOS-private/muos-reference
project_dir=/mnt/e/DGttG/HGttG_vol1/GuideOS
source_image=${GUIDE_SOURCE_IMAGE:-${reference_dir}/seed-bluetooth-music-apps-live-rootfs.ext4}
output_image=${GUIDE_OUTPUT_IMAGE:-${reference_dir}/seed-local-media-player-next-rootfs.ext4}
shell_binary=${GUIDE_SHELL_BINARY:-${project_dir}/build/guide-hello-fb-local-media}
bridge=${project_dir}/apps/node_link/guide_node_bridge.py
client=${project_dir}/apps/node_link/guide_node_client.py
diagnostics=${project_dir}/apps/diagnostics/guide_diagnostics.py
dropbear=${reference_dir}/../developer-link/dropbearmulti
commands=$(mktemp)
verify_dir=$(mktemp -d)

cleanup() {
    rm -f "${commands}"
    rm -rf "${verify_dir}"
}
trap cleanup EXIT INT TERM

test -f "${source_image}"
test "$(stat -c %s "${source_image}")" -eq 2147483648
test -x "${shell_binary}"
test -f "${bridge}"
test -f "${client}"
test -f "${diagnostics}"
test -x "${dropbear}"

cp "${source_image}" "${output_image}"
set +e
e2fsck -fy "${output_image}"
precheck=$?
set -e
test "${precheck}" -eq 0 -o "${precheck}" -eq 1

printf 'rm /init\nwrite %s /init\nset_inode_field /init mode 0100755\n' \
       "${shell_binary}" >> "${commands}"
printf 'rm /usr/sbin/guide-hello-fb\nwrite %s /usr/sbin/guide-hello-fb\n' \
       "${shell_binary}" >> "${commands}"
printf 'set_inode_field /usr/sbin/guide-hello-fb mode 0100755\n' >> "${commands}"
printf 'rm /usr/lib/guideos/node-link/guide_node_bridge.py\n' >> "${commands}"
printf 'write %s /usr/lib/guideos/node-link/guide_node_bridge.py\n' \
       "${bridge}" >> "${commands}"
printf 'set_inode_field /usr/lib/guideos/node-link/guide_node_bridge.py mode 0100755\n' \
       >> "${commands}"
printf 'rm /usr/lib/guideos/node-link/guide_node_client.py\n' >> "${commands}"
printf 'write %s /usr/lib/guideos/node-link/guide_node_client.py\n' \
       "${client}" >> "${commands}"
printf 'set_inode_field /usr/lib/guideos/node-link/guide_node_client.py mode 0100644\n' \
       >> "${commands}"
printf 'rm /usr/sbin/guide-diagnostics\n' >> "${commands}"
printf 'write %s /usr/sbin/guide-diagnostics\n' "${diagnostics}" >> "${commands}"
printf 'set_inode_field /usr/sbin/guide-diagnostics mode 0100755\n' >> "${commands}"
for destination in /usr/sbin/dropbear /usr/bin/dropbearkey /usr/bin/scp; do
    printf 'rm %s\nwrite %s %s\nset_inode_field %s mode 0100755\n' \
           "${destination}" "${dropbear}" "${destination}" "${destination}" \
           >> "${commands}"
done

debugfs -w -f "${commands}" "${output_image}"
set +e
e2fsck -fy "${output_image}"
check=$?
set -e
test "${check}" -eq 0 -o "${check}" -eq 1
e2fsck -fn "${output_image}"

debugfs -R "dump /init ${verify_dir}/init" "${output_image}"
debugfs -R "dump /usr/sbin/guide-hello-fb ${verify_dir}/shell" "${output_image}"
debugfs -R "dump /usr/lib/guideos/node-link/guide_node_bridge.py ${verify_dir}/bridge" \
        "${output_image}"
debugfs -R "dump /usr/lib/guideos/node-link/guide_node_client.py ${verify_dir}/client" \
        "${output_image}"
debugfs -R "dump /usr/sbin/guide-diagnostics ${verify_dir}/diagnostics" "${output_image}"
debugfs -R "dump /usr/bin/scp ${verify_dir}/scp" "${output_image}"
test "$(sha256sum "${verify_dir}/init" | cut -d ' ' -f 1)" = \
     "$(sha256sum "${shell_binary}" | cut -d ' ' -f 1)"
test "$(sha256sum "${verify_dir}/shell" | cut -d ' ' -f 1)" = \
     "$(sha256sum "${shell_binary}" | cut -d ' ' -f 1)"
test "$(sha256sum "${verify_dir}/bridge" | cut -d ' ' -f 1)" = \
     "$(sha256sum "${bridge}" | cut -d ' ' -f 1)"
test "$(sha256sum "${verify_dir}/client" | cut -d ' ' -f 1)" = \
     "$(sha256sum "${client}" | cut -d ' ' -f 1)"
test "$(sha256sum "${verify_dir}/diagnostics" | cut -d ' ' -f 1)" = \
     "$(sha256sum "${diagnostics}" | cut -d ' ' -f 1)"
test "$(sha256sum "${verify_dir}/scp" | cut -d ' ' -f 1)" = \
     "$(sha256sum "${dropbear}" | cut -d ' ' -f 1)"

echo "BASE $(sha256sum "${source_image}")"
echo "ROOTFS $(sha256sum "${output_image}")"
echo "SHELL $(sha256sum "${shell_binary}" | cut -d ' ' -f 1)"
echo "BRIDGE $(sha256sum "${bridge}" | cut -d ' ' -f 1)"
echo "CLIENT $(sha256sum "${client}" | cut -d ' ' -f 1)"
echo "DIAGNOSTICS $(sha256sum "${diagnostics}" | cut -d ' ' -f 1)"
echo "DEVELOPER_LINK $(sha256sum "${dropbear}" | cut -d ' ' -f 1)"
