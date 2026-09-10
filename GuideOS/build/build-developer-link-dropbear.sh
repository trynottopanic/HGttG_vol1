#!/bin/sh
set -eu

version=2026.93
expected=310a6087952897c182efbe16088fa0c4d07c467e850a22699472137278fabf09
work=/mnt/g/GuideOS-private/developer-link
archive=${work}/dropbear-${version}.tar.bz2
source=${work}/dropbear-${version}
toolchain=/home/hacker/guideos-work/output-rg35xxh-ddr4/host/bin/aarch64-buildroot-linux-gnu-

mkdir -p "${work}"
if [ ! -f "${archive}" ]; then
    curl --fail --location --proto '=https' --tlsv1.2 \
        --output "${archive}.partial" \
        "https://matt.ucc.asn.au/dropbear/releases/dropbear-${version}.tar.bz2"
    mv "${archive}.partial" "${archive}"
fi
echo "${expected}  ${archive}" | sha256sum -c -
rm -rf "${source}"
tar -xjf "${archive}" -C "${work}"
cat > "${source}/localoptions.h" <<'EOF'
#define DROPBEAR_SVR_PASSWORD_AUTH 0
#define DROPBEAR_SVR_PAM_AUTH 0
#define DROPBEAR_SVR_PUBKEY_AUTH 1
#define DROPBEAR_SVR_LOCALTCPFWD 0
#define DROPBEAR_SVR_REMOTETCPFWD 0
#define DROPBEAR_SVR_AGENTFWD 0
#define DROPBEAR_X11FWD 0
#define DROPBEAR_SVR_COMPRESSION 0
#define DROPBEAR_DO_MOTD 0
#define DROPBEAR_SMALL_CODE 1
EOF
cd "${source}"
CC="${toolchain}gcc" AR="${toolchain}ar" RANLIB="${toolchain}ranlib" \
    ./configure --host=aarch64-buildroot-linux-gnu --enable-static --disable-shared \
    --disable-zlib --enable-bundled-libtom --disable-harden --disable-wtmp \
    --disable-lastlog --disable-utmp --disable-utmpx --disable-pututline \
    --disable-pututxline
make clean
make -j2 MULTI=1 PROGRAMS="dropbear dropbearkey scp"
cp dropbearmulti "${work}/dropbearmulti"
"${toolchain}strip" "${work}/dropbearmulti"
file "${work}/dropbearmulti"
sha256sum "${work}/dropbearmulti"
