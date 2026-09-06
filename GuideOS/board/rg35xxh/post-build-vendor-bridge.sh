#!/bin/sh
set -eu

# The temporary vendor bridge uses a single static GuideOS shell as PID 1 so
# boot, framebuffer, and control testing do not depend on the vendor kernel
# being able to start the newer Buildroot runtime loader. The normal Buildroot
# init system returns when the fully open boot path replaces this bridge.
rm -f "${TARGET_DIR}/init"
install -m 0755 "${TARGET_DIR}/usr/sbin/guide-hello-fb" "${TARGET_DIR}/init"
