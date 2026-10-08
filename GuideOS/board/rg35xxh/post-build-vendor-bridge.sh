#!/bin/sh
set -eu

# The compatibility bridge uses the small static Guide Supervisor as PID 1.
# The framebuffer interface is an ordinary supervised child and can surrender
# hardware ownership to foreground sessions without also surrendering init.
rm -f "${TARGET_DIR}/init"
install -m 0755 "${TARGET_DIR}/usr/sbin/guide-supervisor" "${TARGET_DIR}/init"
