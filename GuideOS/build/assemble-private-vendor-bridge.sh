#!/bin/sh
set -eu

# Private hardware-bring-up helper.  This must never be used to create a
# distributable GuideOS image: partitions 1-4 and the pre-partition bootstrap
# come from the user's own known-working muOS card.
reference_dir=/mnt/g/GuideOS-private/muos-reference
build_output=${GUIDE_BUILD_OUTPUT:-/home/hacker/guideos-work/output-rg35xxh-vendor-bridge}
rootfs=${build_output}/images/rootfs.ext4
output=${GUIDE_PRIVATE_IMAGE_OUTPUT:-${reference_dir}/GuideOS-RG35XXH-private-vendor-bridge.img}
prefix=${reference_dir}/muos-boot-prefix-163577856.img

test -f "${prefix}"
test -f "${rootfs}"
test "$(stat -c %s "${prefix}")" -eq 163577856
test "$(stat -c %s "${rootfs}")" -le 5368709120
for partition in 1 2 3 4; do
    test -f "${reference_dir}/partition${partition}.img"
done

truncate -s 6442450944 "${output}"
sgdisk --zap-all "${output}"
sgdisk --resize-table=8 "${output}"
sgdisk \
    --new=1:73728:90111 --typecode=1:EF00 --change-name=1:spare \
    --new=2:90112:155647 --typecode=2:EF00 --change-name=2:boot-resource \
    --new=3:155648:188415 --typecode=3:EF00 --change-name=3:env \
    --new=4:188416:319487 --typecode=4:EF00 --change-name=4:boot \
    --new=5:319488:10805247 --typecode=5:EF00 --change-name=5:rootfs \
    --new=6:10805248:0 --typecode=6:0700 --change-name=6:guide-data \
    "${output}"

# Reproduce the attributes used by the working layout.
for bit in 0 45 63; do sgdisk --attributes=1:set:${bit} "${output}"; done
for partition in 2 3 4; do
    for bit in 0 45 62 63; do
        sgdisk --attributes=${partition}:set:${bit} "${output}"
    done
done
for bit in 0 63; do sgdisk --attributes=5:set:${bit} "${output}"; done

# Preserve our new GPT in sectors 0-3, then restore the known-working H700
# bootstrap and its four boot partitions byte-for-byte.
dd if="${prefix}" of="${output}" bs=512 skip=4 seek=4 count=73724 conv=notrunc status=none
dd if="${reference_dir}/partition1.img" of="${output}" bs=512 seek=73728 conv=notrunc status=none
dd if="${reference_dir}/partition2.img" of="${output}" bs=512 seek=90112 conv=notrunc status=none
dd if="${reference_dir}/partition3.img" of="${output}" bs=512 seek=155648 conv=notrunc status=none
dd if="${reference_dir}/partition4.img" of="${output}" bs=512 seek=188416 conv=notrunc status=none
dd if="${rootfs}" of="${output}" bs=1048576 seek=156 conv=notrunc status=progress
sync

sgdisk --verify "${output}"
cmp --silent --bytes=163575808 --ignore-initial=2048:2048 "${prefix}" "${output}"
cmp --silent --bytes="$(stat -c %s "${rootfs}")" --ignore-initial=0:163577856 "${rootfs}" "${output}"

echo "Private vendor-bridge image assembled and verified:"
ls -lh "${output}"
sha256sum "${output}"
