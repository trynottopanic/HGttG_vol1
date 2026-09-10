#!/bin/sh
set -eu

reference_dir=/mnt/g/GuideOS-private/muos-reference
project_dir=/mnt/e/DGttG/HGttG_vol1/GuideOS
source_image=${GUIDE_SOURCE_IMAGE:-${reference_dir}/seed-media-trust-next-rootfs.ext4}
output_image=${GUIDE_OUTPUT_IMAGE:-${reference_dir}/seed-bluetooth-music-apps-next-rootfs.ext4}
shell_binary=${reference_dir}/guide-hello-fb-bluetooth-music-apps
bluetooth_stage=/home/hacker/guideos-work/bluetooth-deck-stage-0.1
media_runtime=${reference_dir}/media-runtime-0.1
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
test -x "${bluetooth_stage}/bin/rtk_hciattach"
test -f "${media_runtime}/alsa-lib/libasound_module_pcm_bluealsa.so"
test -f "${media_runtime}/lib/libdbus-1.so.3"

cp "${source_image}" "${output_image}"
set +e
e2fsck -fy "${output_image}"
precheck=$?
set -e
test "${precheck}" -eq 0 -o "${precheck}" -eq 1

mkdir_command() {
    printf 'mkdir %s\n' "$1" >> "${commands}"
}

write_file() {
    source=$1
    destination=$2
    mode=$3
    printf 'rm %s\n' "${destination}" >> "${commands}"
    printf 'write %s %s\n' "${source}" "${destination}" >> "${commands}"
    printf 'set_inode_field %s mode 0100%s\n' "${destination}" "${mode}" >> "${commands}"
}

mkdir_command /opt
mkdir_command /opt/guide
mkdir_command /opt/guide/bluetooth
mkdir_command /usr/lib/guideos/media/alsa-lib

write_file "${shell_binary}" /init 755
write_file "${shell_binary}" /usr/sbin/guide-hello-fb 755
write_file "${project_dir}/apps/node_link/guide_node_client.py" \
           /usr/lib/guideos/node-link/guide_node_client.py 644
write_file "${project_dir}/apps/node_link/guide_node_bridge.py" \
           /usr/lib/guideos/node-link/guide_node_bridge.py 755
write_file "${media_runtime}/alsa-lib/libasound_module_pcm_bluealsa.so" \
           /usr/lib/guideos/media/alsa-lib/libasound_module_pcm_bluealsa.so 755
write_file "${media_runtime}/lib/libdbus-1.so.3" \
           /usr/lib/guideos/media/lib/libdbus-1.so.3 755

# Recreate the isolated, physically verified Bluetooth runtime under /opt.
find "${bluetooth_stage}" -type d -printf '%P\n' | awk 'NF' |
while IFS= read -r relative; do
    mkdir_command "/opt/guide/bluetooth/${relative}"
done
find "${bluetooth_stage}" -type f -printf '%P\n' |
while IFS= read -r relative; do
    mode=$(stat -c %a "${bluetooth_stage}/${relative}")
    write_file "${bluetooth_stage}/${relative}" "/opt/guide/bluetooth/${relative}" "${mode}"
done
find "${bluetooth_stage}" -type l -printf '%P\n' |
while IFS= read -r relative; do
    target=$(readlink "${bluetooth_stage}/${relative}")
    printf 'rm %s\n' "/opt/guide/bluetooth/${relative}" >> "${commands}"
    printf 'symlink %s %s\n' "/opt/guide/bluetooth/${relative}" "${target}" >> "${commands}"
done

for name in guide-bluetooth-start guide-bluetooth-stop guide-bluetooth-status \
            guide-bluetooth-reconnect \
            guide-bluetooth-probe guide-audio-route; do
    write_file "${project_dir}/apps/bluetooth/${name}" "/opt/guide/bluetooth/${name}" 755
done
write_file "${project_dir}/apps/bluetooth/system-guide.conf" \
           /opt/guide/bluetooth/system-guide.conf 644
write_file "${project_dir}/apps/bluetooth/alsa-media.conf" \
           /opt/guide/bluetooth/alsa-media.conf 644

debugfs -w -f "${commands}" "${output_image}"
set +e
e2fsck -fy "${output_image}"
check=$?
set -e
test "${check}" -eq 0 -o "${check}" -eq 1
e2fsck -fn "${output_image}"

debugfs -R "dump /init ${verify_dir}/init" "${output_image}"
debugfs -R "dump /usr/lib/guideos/node-link/guide_node_bridge.py ${verify_dir}/bridge" "${output_image}"
debugfs -R "dump /opt/guide/bluetooth/guide-bluetooth-start ${verify_dir}/bluetooth-start" "${output_image}"
debugfs -R "dump /opt/guide/bluetooth/alsa-media.conf ${verify_dir}/alsa-media.conf" "${output_image}"
debugfs -R "dump /opt/guide/bluetooth/root/usr/libexec/bluetooth/bluetoothd ${verify_dir}/bluetoothd" "${output_image}"
debugfs -R "dump /usr/lib/guideos/media/alsa-lib/libasound_module_pcm_bluealsa.so ${verify_dir}/bluealsa-plugin" "${output_image}"

test "$(sha256sum "${verify_dir}/init" | cut -d ' ' -f 1)" = \
     "$(sha256sum "${shell_binary}" | cut -d ' ' -f 1)"
test "$(sha256sum "${verify_dir}/bridge" | cut -d ' ' -f 1)" = \
     "$(sha256sum "${project_dir}/apps/node_link/guide_node_bridge.py" | cut -d ' ' -f 1)"
test "$(sha256sum "${verify_dir}/bluetooth-start" | cut -d ' ' -f 1)" = \
     "$(sha256sum "${project_dir}/apps/bluetooth/guide-bluetooth-start" | cut -d ' ' -f 1)"
test "$(sha256sum "${verify_dir}/alsa-media.conf" | cut -d ' ' -f 1)" = \
     "$(sha256sum "${project_dir}/apps/bluetooth/alsa-media.conf" | cut -d ' ' -f 1)"
test -s "${verify_dir}/bluetoothd"
test "$(sha256sum "${verify_dir}/bluealsa-plugin" | cut -d ' ' -f 1)" = \
     "$(sha256sum "${media_runtime}/alsa-lib/libasound_module_pcm_bluealsa.so" | cut -d ' ' -f 1)"

echo "BASE $(sha256sum "${source_image}")"
echo "ROOTFS $(sha256sum "${output_image}")"
echo "SHELL $(sha256sum "${shell_binary}" | cut -d ' ' -f 1)"
echo "BLUETOOTH_FILES $(find "${bluetooth_stage}" -type f | wc -l)"
