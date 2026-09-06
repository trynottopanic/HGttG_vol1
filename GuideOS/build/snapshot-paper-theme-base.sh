#!/bin/sh
set -eu

source_image=/mnt/g/GuideOS-private/muos-reference/seed-devlink-wikipedia-rootfs.ext4
snapshot_image=/mnt/g/GuideOS-private/muos-reference/seed-paper-theme-base-snapshot.ext4

before=$(sha256sum "${source_image}" | cut -d ' ' -f 1)
cp "${source_image}" "${snapshot_image}"
after=$(sha256sum "${source_image}" | cut -d ' ' -f 1)
copied=$(sha256sum "${snapshot_image}" | cut -d ' ' -f 1)

test "${before}" = "${after}"
test "${before}" = "${copied}"
echo "${copied}  ${snapshot_image}"
