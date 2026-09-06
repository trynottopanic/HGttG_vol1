#!/bin/sh
set -eu

reference_dir=/mnt/g/GuideOS-private/muos-reference
project_dir=/mnt/e/DGttG/HGttG_vol1/GuideOS
source_image=${reference_dir}/seed-media-trust-base-rootfs.ext4
output_image=${reference_dir}/seed-media-trust-next-rootfs.ext4
shell_binary=${reference_dir}/guide-hello-fb-media
runtime=${reference_dir}/media-runtime-0.1
client=${project_dir}/apps/node_link/guide_node_client.py
bridge=${project_dir}/apps/node_link/guide_node_bridge.py
commands=${project_dir}/build/media-trust.debugfs

shell_hash=f1b0842e19d63962f61c275d67e007449d37b4b2071379d0d127b6ec69a4ef4d
client_hash=933fc404830483fe44879cfa27d6aa70b963645d9b1d0bf6492b24fbb5ddebbe
bridge_hash=9ef7838911f66d7c09ac4ace7607b1cd8546514dbbcddb9772e495a88480a378
runtime_manifest_hash=11c0087178b299dba76885f6fe2759c04af08333c6ab6a80fef359d705037805

test -f "${source_image}"
test "$(stat -c %s "${source_image}")" -eq 2147483648
test "$(sha256sum "${shell_binary}" | cut -d ' ' -f 1)" = "${shell_hash}"
test "$(sha256sum "${client}" | cut -d ' ' -f 1)" = "${client_hash}"
test "$(sha256sum "${bridge}" | cut -d ' ' -f 1)" = "${bridge_hash}"
actual_runtime_hash=$(cd "${runtime}" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d ' ' -f 1)
test "${actual_runtime_hash}" = "${runtime_manifest_hash}"

cp "${source_image}" "${output_image}"
verify_dir=$(mktemp -d)
cleanup() { rm -rf "${verify_dir}"; }
trap cleanup EXIT INT TERM

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
debugfs -R "dump /usr/lib/guideos/media/bin/ffmpeg ${verify_dir}/ffmpeg" "${output_image}"
debugfs -R "dump /usr/lib/guideos/media/lib/ld-linux-aarch64.so.1 ${verify_dir}/loader" "${output_image}"

test "$(sha256sum "${verify_dir}/init" | cut -d ' ' -f 1)" = "${shell_hash}"
test "$(sha256sum "${verify_dir}/shell" | cut -d ' ' -f 1)" = "${shell_hash}"
test "$(sha256sum "${verify_dir}/client" | cut -d ' ' -f 1)" = "${client_hash}"
test "$(sha256sum "${verify_dir}/bridge" | cut -d ' ' -f 1)" = "${bridge_hash}"
test "$(sha256sum "${verify_dir}/ffmpeg" | cut -d ' ' -f 1)" = d5196459c84d0ef00c6f67ac75085ca6b4860fb287be00cecfa79fa475353303
test "$(sha256sum "${verify_dir}/loader" | cut -d ' ' -f 1)" = e6efcde33d80cde0a621428c3551dc45aab196b086d4eeb3caad2eaa45dce4ba

echo "BASE $(sha256sum "${source_image}")"
echo "ROOTFS $(sha256sum "${output_image}")"
echo "SHELL ${shell_hash}"
echo "CLIENT ${client_hash}"
echo "BRIDGE ${bridge_hash}"
echo "MEDIA-RUNTIME ${runtime_manifest_hash}"
