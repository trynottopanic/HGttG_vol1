#!/bin/sh
set -eu

reference_dir=/mnt/g/GuideOS-private/muos-reference
project_dir=/mnt/e/DGttG/HGttG_vol1/GuideOS
source_image=${GUIDE_SOURCE_IMAGE:-${reference_dir}/seed-subtitle-modal-audio-1.2-next-rootfs.ext4}
output_image=${GUIDE_OUTPUT_IMAGE:-${reference_dir}/seed-doom-next-rootfs.ext4}
shell_binary=${project_dir}/build/guide-hello-fb-local-media
frontend=${project_dir}/build/guide-doom-aarch64
core=${project_dir}/build/prboom_libretro-aarch64.so
launcher=${project_dir}/apps/doom/guide-doom-launch
provenance=${project_dir}/apps/doom/UPSTREAM.txt
bridge=${project_dir}/apps/node_link/guide_node_bridge.py
client=${project_dir}/apps/node_link/guide_node_client.py
diagnostics=${project_dir}/apps/diagnostics/guide_diagnostics.py
dropbear=${reference_dir}/../developer-link/dropbearmulti
developer_control=${project_dir}/build/guide-devlink-control-aarch64
developer_key=${reference_dir}/../developer-link/desktop-key.pub
developer_license=${reference_dir}/../developer-link/dropbear-2026.93/LICENSE
developer_readme=${project_dir}/apps/developer_link/README.txt
developer_feature=${project_dir}/apps/developer_link/base-feature.json
font=${project_dir}/package/guide-hello-fb/src/assets/DejaVuSans.ttf
font_license=${project_dir}/package/guide-hello-fb/src/assets/DejaVu-Fonts-LICENSE.txt
upstream_dir=${GUIDE_DOOM_WORK_DIR:-/home/hacker/guideos-work/sources/libretro-prboom}
license=${upstream_dir}/COPYING
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
test -x "${frontend}"
test -f "${core}"
test -f "${launcher}"
test -f "${license}"
test -f "${bridge}"
test -f "${client}"
test -f "${diagnostics}"
test -x "${dropbear}"
test -x "${developer_control}"
test -f "${developer_key}"
test -f "${developer_license}"
test -f "${developer_readme}"
test -f "${developer_feature}"
test -f "${font}"
test -f "${font_license}"

cp "${source_image}" "${output_image}"
set +e
e2fsck -fy "${output_image}"
precheck=$?
set -e
test "${precheck}" -eq 0 -o "${precheck}" -eq 1

ensure_directory() {
    if ! debugfs -R "stat $1" "${output_image}" 2>/dev/null | grep -q '^Inode:'; then
        debugfs -w -R "mkdir $1" "${output_image}"
    fi
}

for directory in /root/.ssh /usr/share/licenses /usr/share/licenses/dropbear \
                 /usr/share/guideos /var/lib/guideos /var/lib/guideos/features \
                 /usr/share/guideos/fonts /usr/share/licenses/guideos \
                 /usr/lib/guideos/doom /usr/share/licenses/libretro-prboom \
                 /data/guide-games /data/guide-games/doom /data/guideos \
                 /data/guideos/doom; do
    ensure_directory "${directory}"
done

printf 'rm /init\nwrite %s /init\nset_inode_field /init mode 0100755\n' \
       "${shell_binary}" >> "${commands}"
printf 'rm /usr/sbin/guide-hello-fb\nwrite %s /usr/sbin/guide-hello-fb\n' \
       "${shell_binary}" >> "${commands}"
printf 'set_inode_field /usr/sbin/guide-hello-fb mode 0100755\n' >> "${commands}"
printf 'rm /usr/lib/guideos/node-link/guide_node_bridge.py\n' >> "${commands}"
printf 'write %s /usr/lib/guideos/node-link/guide_node_bridge.py\n' "${bridge}" >> "${commands}"
printf 'set_inode_field /usr/lib/guideos/node-link/guide_node_bridge.py mode 0100755\n' >> "${commands}"
printf 'rm /usr/lib/guideos/node-link/guide_node_client.py\n' >> "${commands}"
printf 'write %s /usr/lib/guideos/node-link/guide_node_client.py\n' "${client}" >> "${commands}"
printf 'set_inode_field /usr/lib/guideos/node-link/guide_node_client.py mode 0100644\n' >> "${commands}"
printf 'rm /usr/sbin/guide-diagnostics\nwrite %s /usr/sbin/guide-diagnostics\n' "${diagnostics}" >> "${commands}"
printf 'set_inode_field /usr/sbin/guide-diagnostics mode 0100755\n' >> "${commands}"
for destination in /usr/sbin/dropbear /usr/bin/dropbearkey /usr/bin/scp; do
    printf 'rm %s\nwrite %s %s\nset_inode_field %s mode 0100755\n' \
           "${destination}" "${dropbear}" "${destination}" "${destination}" >> "${commands}"
done
printf 'set_inode_field /root/.ssh mode 040700\n' >> "${commands}"
printf 'rm /root/.ssh/authorized_keys\nwrite %s /root/.ssh/authorized_keys\n' \
       "${developer_key}" >> "${commands}"
printf 'set_inode_field /root/.ssh/authorized_keys mode 0100600\n' >> "${commands}"
printf 'rm /usr/sbin/guide-devlink-control\nwrite %s /usr/sbin/guide-devlink-control\n' \
       "${developer_control}" >> "${commands}"
printf 'set_inode_field /usr/sbin/guide-devlink-control mode 0100755\n' >> "${commands}"
printf 'rm /usr/share/licenses/dropbear/LICENSE\nwrite %s /usr/share/licenses/dropbear/LICENSE\n' \
       "${developer_license}" >> "${commands}"
printf 'set_inode_field /usr/share/licenses/dropbear/LICENSE mode 0100644\n' >> "${commands}"
printf 'rm /usr/share/guideos/developer-link.txt\nwrite %s /usr/share/guideos/developer-link.txt\n' \
       "${developer_readme}" >> "${commands}"
printf 'set_inode_field /usr/share/guideos/developer-link.txt mode 0100644\n' >> "${commands}"
printf 'rm /var/lib/guideos/features/guide.prototype.developer-link.json\n' >> "${commands}"
printf 'write %s /var/lib/guideos/features/guide.prototype.developer-link.json\n' \
       "${developer_feature}" >> "${commands}"
printf 'set_inode_field /var/lib/guideos/features/guide.prototype.developer-link.json mode 0100644\n' >> "${commands}"
printf 'rm /usr/share/guideos/fonts/DejaVuSans.ttf\nwrite %s /usr/share/guideos/fonts/DejaVuSans.ttf\n' \
       "${font}" >> "${commands}"
printf 'set_inode_field /usr/share/guideos/fonts/DejaVuSans.ttf mode 0100644\n' >> "${commands}"
printf 'rm /usr/share/licenses/guideos/DejaVu-Fonts-LICENSE.txt\n' >> "${commands}"
printf 'write %s /usr/share/licenses/guideos/DejaVu-Fonts-LICENSE.txt\n' \
       "${font_license}" >> "${commands}"
printf 'set_inode_field /usr/share/licenses/guideos/DejaVu-Fonts-LICENSE.txt mode 0100644\n' >> "${commands}"
printf 'rm /usr/lib/guideos/doom/guide-doom\nwrite %s /usr/lib/guideos/doom/guide-doom\n' "${frontend}" >> "${commands}"
printf 'set_inode_field /usr/lib/guideos/doom/guide-doom mode 0100755\n' >> "${commands}"
printf 'rm /usr/lib/guideos/doom/prboom_libretro.so\nwrite %s /usr/lib/guideos/doom/prboom_libretro.so\n' "${core}" >> "${commands}"
printf 'set_inode_field /usr/lib/guideos/doom/prboom_libretro.so mode 0100644\n' >> "${commands}"
printf 'rm /usr/lib/guideos/doom/UPSTREAM.txt\nwrite %s /usr/lib/guideos/doom/UPSTREAM.txt\n' "${provenance}" >> "${commands}"
printf 'set_inode_field /usr/lib/guideos/doom/UPSTREAM.txt mode 0100644\n' >> "${commands}"
printf 'rm /usr/bin/guide-doom\nwrite %s /usr/bin/guide-doom\n' "${launcher}" >> "${commands}"
printf 'set_inode_field /usr/bin/guide-doom mode 0100755\n' >> "${commands}"
printf 'rm /usr/share/licenses/libretro-prboom/COPYING\nwrite %s /usr/share/licenses/libretro-prboom/COPYING\n' "${license}" >> "${commands}"
printf 'set_inode_field /usr/share/licenses/libretro-prboom/COPYING mode 0100644\n' >> "${commands}"

debugfs -w -f "${commands}" "${output_image}"
set +e
e2fsck -fy "${output_image}"
check=$?
set -e
test "${check}" -eq 0 -o "${check}" -eq 1
e2fsck -fn "${output_image}"

debugfs -R "dump /init ${verify_dir}/init" "${output_image}"
debugfs -R "dump /usr/bin/guide-doom ${verify_dir}/launcher" "${output_image}"
debugfs -R "dump /usr/lib/guideos/doom/guide-doom ${verify_dir}/frontend" "${output_image}"
debugfs -R "dump /usr/lib/guideos/doom/prboom_libretro.so ${verify_dir}/core" "${output_image}"
debugfs -R "dump /usr/lib/guideos/doom/UPSTREAM.txt ${verify_dir}/provenance" "${output_image}"
debugfs -R "dump /usr/share/licenses/libretro-prboom/COPYING ${verify_dir}/license" "${output_image}"
debugfs -R "dump /usr/lib/guideos/node-link/guide_node_bridge.py ${verify_dir}/bridge" "${output_image}"
debugfs -R "dump /usr/lib/guideos/node-link/guide_node_client.py ${verify_dir}/client" "${output_image}"
debugfs -R "dump /usr/sbin/guide-diagnostics ${verify_dir}/diagnostics" "${output_image}"
debugfs -R "dump /usr/bin/scp ${verify_dir}/scp" "${output_image}"
debugfs -R "dump /usr/sbin/guide-devlink-control ${verify_dir}/developer-control" "${output_image}"
debugfs -R "dump /root/.ssh/authorized_keys ${verify_dir}/developer-key" "${output_image}"
debugfs -R "dump /usr/share/licenses/dropbear/LICENSE ${verify_dir}/developer-license" "${output_image}"
debugfs -R "dump /usr/share/guideos/developer-link.txt ${verify_dir}/developer-readme" "${output_image}"
debugfs -R "dump /var/lib/guideos/features/guide.prototype.developer-link.json ${verify_dir}/developer-feature" "${output_image}"
debugfs -R "dump /usr/share/guideos/fonts/DejaVuSans.ttf ${verify_dir}/font" "${output_image}"
debugfs -R "dump /usr/share/licenses/guideos/DejaVu-Fonts-LICENSE.txt ${verify_dir}/font-license" "${output_image}"

for pair in "${verify_dir}/init:${shell_binary}" \
            "${verify_dir}/launcher:${launcher}" \
            "${verify_dir}/frontend:${frontend}" \
            "${verify_dir}/core:${core}" \
            "${verify_dir}/provenance:${provenance}" \
            "${verify_dir}/license:${license}" \
            "${verify_dir}/bridge:${bridge}" \
            "${verify_dir}/client:${client}" \
            "${verify_dir}/diagnostics:${diagnostics}" \
            "${verify_dir}/scp:${dropbear}" \
            "${verify_dir}/developer-control:${developer_control}" \
            "${verify_dir}/developer-key:${developer_key}" \
            "${verify_dir}/developer-license:${developer_license}" \
            "${verify_dir}/developer-readme:${developer_readme}" \
            "${verify_dir}/developer-feature:${developer_feature}" \
            "${verify_dir}/font:${font}" \
            "${verify_dir}/font-license:${font_license}"; do
    extracted=${pair%%:*}
    original=${pair#*:}
    test "$(sha256sum "${extracted}" | cut -d ' ' -f 1)" = \
         "$(sha256sum "${original}" | cut -d ' ' -f 1)"
done

echo "BASE $(sha256sum "${source_image}")"
echo "ROOTFS $(sha256sum "${output_image}")"
echo "SHELL $(sha256sum "${shell_binary}" | cut -d ' ' -f 1)"
echo "DOOM_FRONTEND $(sha256sum "${frontend}" | cut -d ' ' -f 1)"
echo "DOOM_CORE $(sha256sum "${core}" | cut -d ' ' -f 1)"
echo "DEVELOPER_LINK $(sha256sum "${developer_control}" | cut -d ' ' -f 1)"
echo "SUBTITLE_FONT $(sha256sum "${font}" | cut -d ' ' -f 1)"
