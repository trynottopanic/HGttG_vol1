#!/bin/sh
set -eu

usage() {
    echo "usage: $0 --root ROOTFS --binary GUIDE_BOOT_ANIMATION" >&2
    exit 2
}

root=
binary=
while [ "$#" -gt 0 ]; do
    case "$1" in
        --root) root=${2-}; shift 2 ;;
        --binary) binary=${2-}; shift 2 ;;
        *) usage ;;
    esac
done

[ -n "$root" ] && [ -d "$root" ] || usage
[ -n "$binary" ] && [ -x "$binary" ] || usage

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
assets=$here/assets
animation=$assets/boot-eclipse-v1.rgb565a

test "$(wc -c < "$animation")" -eq 46080032
test "$(dd if="$animation" bs=1 count=8 2>/dev/null)" = GOSANIM1

install -d -m755 \
    "$root/usr/lib/guideos/boot-animation" \
    "$root/usr/share/guideos/boot-animation" \
    "$root/usr/share/doc/guideos-boot-animation" \
    "$root/etc/systemd/system" \
    "$root/etc/systemd/system/multi-user.target.wants"

install -m755 "$binary" \
    "$root/usr/lib/guideos/boot-animation/guide-boot-animation"
install -m644 "$here/guide_boot_console.py" \
    "$root/usr/lib/guideos/boot-animation/guide_boot_console.py"
install -m644 "$here/guide_boot_runner.py" \
    "$root/usr/lib/guideos/boot-animation/guide_boot_runner.py"
install -m644 "$animation" \
    "$root/usr/share/guideos/boot-animation/boot-eclipse-v1.rgb565a"

# Remove the superseded boot-only world generator, wrapper and layered globe
# assets. guide_home_world.py is intentionally retained for the shell fallback.
rm -f \
    "$root/usr/lib/guideos/boot-animation/guide_boot_dynamic.py" \
    "$root/usr/lib/guideos/boot-animation/guide_boot_world.py" \
    "$root/usr/lib/guideos/boot-animation/guide-boot-animation-fixed-backup" \
    "$root/etc/systemd/system/guide-boot-animation.service.d/40-dynamic.conf"
for legacy in terrain-fixed-v2.rgb565 clouds-fixed-v2.r8 roads-fixed-v2.r8 \
              lights-fixed-v2.r8 silhouette-standard-v3.r8 caption-dont-panic-v4.r8 \
              caption-world-words.r8 terrain-atlas-draft-v1.png \
              cloud-atlas-draft-v1.png world-vocabulary-v1.json; do
    rm -f "$root/usr/share/guideos/boot-animation/$legacy"
done
install -m644 "$here/README.md" \
    "$root/usr/share/doc/guideos-boot-animation/README.md"
install -m644 "$here/guide-boot-animation.service" \
    "$root/etc/systemd/system/guide-boot-animation.service"

ln -sfn /etc/systemd/system/guide-boot-animation.service \
    "$root/etc/systemd/system/multi-user.target.wants/guide-boot-animation.service"

dropin=$root/etc/systemd/system/guide-shell.service.d
install -d -m755 "$dropin"
install -m644 "$here/15-boot-animation.conf" "$dropin/15-boot-animation.conf"

echo GUIDE_BOOT_ANIMATION_INSTALLED
