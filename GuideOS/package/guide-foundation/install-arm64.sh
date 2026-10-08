#!/bin/sh
set -eu
root=${1:?root filesystem required}
artifacts=${2:?ARM64 artifact directory required}
source_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -d -m755 "$root/usr/libexec/guideos" "$root/usr/share/guideos/foundation" "$root/etc/systemd/system" "$root/usr/lib/tmpfiles.d" "$root/var/lib/guideos/supervisor"
install -m755 "$artifacts/guide-supervisor0" "$root/usr/libexec/guideos/guide-supervisor0"
install -m755 "$artifacts/guide-capability-broker0" "$root/usr/libexec/guideos/guide-capability-broker0"
install -m755 "$artifacts/guide-ipc-probe" "$root/usr/libexec/guideos/guide-ipc-probe"
install -m644 "$source_root/policy/guide-ipc-probe.json" "$root/usr/share/guideos/foundation/guide-ipc-probe.json"
install -m644 "$source_root/systemd/guide-supervisor0.service" "$root/etc/systemd/system/guide-supervisor0.service"
install -m644 "$source_root/systemd/guide-supervisor0.socket" "$root/etc/systemd/system/guide-supervisor0.socket"
install -m644 "$source_root/systemd/guide-capability-broker0.socket" "$root/etc/systemd/system/guide-capability-broker0.socket"
install -m644 "$source_root/systemd/guide-capability-broker0.service" "$root/etc/systemd/system/guide-capability-broker0.service"
install -m644 "$source_root/systemd/guide-capability-provider0.socket" "$root/etc/systemd/system/guide-capability-provider0.socket"
install -m644 "$source_root/systemd/guide-ipc-probe.service" "$root/etc/systemd/system/guide-ipc-probe.service"
install -m644 "$source_root/tmpfiles.d/guideos-foundation.conf" "$root/usr/lib/tmpfiles.d/guideos-foundation.conf"
chroot "$root" getent group guide-broker >/dev/null 2>&1 || chroot "$root" groupadd --system guide-broker
chroot "$root" getent group guide-apps >/dev/null 2>&1 || chroot "$root" groupadd --system guide-apps
chroot "$root" getent group guide-providers >/dev/null 2>&1 || chroot "$root" groupadd --system guide-providers
chroot "$root" getent passwd guide-broker >/dev/null 2>&1 || chroot "$root" useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin --gid guide-broker guide-broker
chroot "$root" getent passwd guide-probe >/dev/null 2>&1 || chroot "$root" useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin --gid guide-apps guide-probe
systemctl --root="$root" enable guide-supervisor0.service guide-supervisor0.socket guide-capability-broker0.socket guide-capability-provider0.socket

# Step 1 runtime. No application agreement is created by installing the host.
install -d -m755 "$root/usr/lib/guideos/application-host" "$root/usr/lib/guideos/ipc" "$root/var/lib/guideos/applications" "$root/var/lib/guideos/applications/releases"
install -m644 "$source_root/python/guide_application_runtime.py" "$root/usr/lib/guideos/application-host/"
install -m644 "$source_root/../guide-ipc/python/guide_ipc.py" "$root/usr/lib/guideos/ipc/"
install -m755 "$source_root/python/guide_application_host.py" "$root/usr/libexec/guideos/guide-application-host"
if ! chroot "$root" /usr/bin/python3 -I -c 'import cbor2' >/dev/null 2>&1; then
    dependencies=${3:?image lacks python3-cbor2; pass verified runtime-debs directory}
    package="$dependencies/python3-cbor2_5.6.5-1_arm64.deb"
    (cd "$dependencies" && sha256sum -c SHA256SUMS)
    test "$(dpkg-deb -f "$package" Architecture)" = arm64
    staged=$(mktemp "$root/tmp/guide-app-dependency.XXXXXXXX.deb")
    trap 'rm -f "$staged"' EXIT HUP INT TERM
    cp "$package" "$staged"
    chroot "$root" dpkg -i "/tmp/$(basename "$staged")"
    rm -f "$staged"
    trap - EXIT HUP INT TERM
fi
chroot "$root" /usr/bin/python3 -I -c 'import cbor2, ctypes; ctypes.CDLL("libseccomp.so.2")'
install -d -m755 "$root/usr/lib/guideos/shell0"
for name in guide_application_panel.py guide_shell.py guide_menu_input.py; do
    install -m644 "$source_root/../../board/rg35xxh/debian/shell0/$name" "$root/usr/lib/guideos/shell0/$name"
done
