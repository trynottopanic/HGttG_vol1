#!/bin/sh
set -eu

reference_dir=/mnt/g/GuideOS-private/muos-reference
project_dir=/mnt/e/DGttG/HGttG_vol1/GuideOS
source_image=${reference_dir}/seed-node-link-base-rootfs.ext4
output_image=${reference_dir}/seed-node-link-next-rootfs.ext4
shell_binary=${reference_dir}/guide-hello-fb-node-link
client=${project_dir}/apps/node_link/guide_node_client.py
bridge=${project_dir}/apps/node_link/guide_node_bridge.py
commands=${project_dir}/build/node-link.debugfs

shell_hash=11f544eebe748681a1604cded4902a0ffe99d71d949f018cf2f0a9a28100678d
client_hash=2f050b7471a145f02b311de77f203b14ad3ff8affb47fa572b55e9d93a004dc4
bridge_hash=092b896f9a61156ab02944b976a5c25dc6207cfd47460fc0a8c4161cb7f6f638

test -f "${source_image}"
test "$(stat -c %s "${source_image}")" -eq 2147483648
test "$(sha256sum "${shell_binary}" | cut -d ' ' -f 1)" = "${shell_hash}"
test "$(sha256sum "${client}" | cut -d ' ' -f 1)" = "${client_hash}"
test "$(sha256sum "${bridge}" | cut -d ' ' -f 1)" = "${bridge_hash}"

cp "${source_image}" "${output_image}"
verify_dir=$(mktemp -d)
cleanup() {
    rm -rf "${verify_dir}"
}
trap cleanup EXIT INT TERM

# The captured live filesystem may contain a journal transaction from its last
# boot. Replay that transaction before making offline changes; otherwise a
# later check could correctly replay the old journal over our new directory
# entries.
set +e
e2fsck -fy "${output_image}"
precheck_status=$?
set -e
test "${precheck_status}" -eq 0 -o "${precheck_status}" -eq 1

while IFS= read -r operation; do
    test -n "${operation}" || continue
    debugfs -w -R "${operation}" "${output_image}"
done < "${commands}"
set +e
e2fsck -fy "${output_image}"
check_status=$?
set -e
test "${check_status}" -eq 0 -o "${check_status}" -eq 1
e2fsck -fn "${output_image}"

debugfs -R "dump /init ${verify_dir}/init" "${output_image}"
debugfs -R "dump /usr/sbin/guide-hello-fb ${verify_dir}/shell" "${output_image}"
debugfs -R "dump /usr/lib/guideos/node-link/guide_node_client.py ${verify_dir}/client" "${output_image}"
debugfs -R "dump /usr/lib/guideos/node-link/guide_node_bridge.py ${verify_dir}/bridge" "${output_image}"

test "$(sha256sum "${verify_dir}/init" | cut -d ' ' -f 1)" = "${shell_hash}"
test "$(sha256sum "${verify_dir}/shell" | cut -d ' ' -f 1)" = "${shell_hash}"
test "$(sha256sum "${verify_dir}/client" | cut -d ' ' -f 1)" = "${client_hash}"
test "$(sha256sum "${verify_dir}/bridge" | cut -d ' ' -f 1)" = "${bridge_hash}"

echo "BASE $(sha256sum "${source_image}")"
echo "ROOTFS $(sha256sum "${output_image}")"
echo "SHELL ${shell_hash}"
echo "CLIENT ${client_hash}"
echo "BRIDGE ${bridge_hash}"
