# IPC Envelope 0 ARM64 image verification

Status: ARM64 image verified; not installed and not physically tested, 25 September 2026.

## Result

The Envelope 0 runtime package was cross-compiled for AArch64, installed into a
copy of the latest cumulative validated GuideOS root image, and exercised inside
that mounted ARM64 filesystem through QEMU user-mode emulation.

Result: `GUIDE_IPC_ARM64_IMAGE_VERIFIED`.

This verifies the runtime library package. It does not verify a live capability
broker, Supervisor reconciliation, boot ordering or physical Deck behavior. No
service was enabled because the systemd-era Supervisor authority path needed to
provision authenticated instances and grants is not yet present.

## Candidate identity

- Source image: `build/volume-overlay/guide-volume-overlay-root.ext4`
- Source SHA256: `F875DDC332F2151F364E496C221EF962616B337C3DD3D35C8A849B27103D5817`
- Candidate: `build/ipc-arm64/guide-ipc-arm64-root.ext4`
- Candidate SHA256: `307223B9B70E703D941D3C71348E5541F1EA30B9D17A30F300023E19DB32C41B`
- Installed library SHA256: `ECCB1DFB4AB4B1B746A3DDDF0ED785FB9759314D4BC30AC38C56AF7FFCDDE1B8`
- Installed library file size: 67,416 bytes
- Existing regular files verified preserved: 21,379
- Installed services: none
- Card writes: none

The source is a staging candidate, not the root currently installed on the Deck.
Consequently, this IPC image is also a staging candidate and must not be described
as an installed release.

## Installed payload

- `/usr/lib/aarch64-linux-gnu/libguide-ipc.so.0.1.0`
- `/usr/lib/aarch64-linux-gnu/libguide-ipc.so.0` -> versioned library
- `/usr/share/guideos/ipc/interfaces.json`
- `/usr/share/guideos/ipc/envelope0.cddl`
- `/usr/share/guideos/ipc/INTERFACES.md`
- `/usr/share/guideos/ipc/fixtures.json`

Headers, object files, cross-compilers, Python behavioral-oracle modules and the
self-test executable are not installed in the image.

## Verification performed

- deterministic generated-output check;
- strict ARM64 compilation with warnings treated as errors;
- AArch64 ELF and SONAME inspection;
- runtime dependency inspection: standard loader and `libc` only;
- immediate binding and RELRO link options;
- installed schema and fixtures byte-for-byte comparison with source;
- SONAME-link validation;
- ARM64 descriptor-transfer self-test inside the mounted image under QEMU;
- complete pre-existing regular-file and symlink preservation comparison;
- rejection of unexpected added files;
- read-only post-build image hash verification; and
- five-pass read-only `e2fsck` with no reported filesystem errors.

## Build-environment correction

The preserved Buildroot cross-toolchain wrapper still existed, but its sysroot no
longer contained standard C headers. The candidate therefore uses Ubuntu 24.04's
maintained `gcc-aarch64-linux-gnu` and ARM64 glibc development headers. Runtime
execution against the GuideOS image passed, which directly checks compatibility
with the image's loader and libc. QEMU user-static was used explicitly because WSL
did not register an ARM64 binfmt handler.

## Remaining boundary

Before enabling any application-facing broker or writing this candidate to a
card, GuideOS still needs:

1. the systemd-era Supervisor lifecycle/registry service;
2. boot and restart reconciliation of surviving application cgroups;
3. the trusted capability/grant broker implementation;
4. systemd socket and service units with hardening and ordering;
5. end-to-end acquire, use, revoke, reconnect and generation-invalidating tests;
6. descriptor-lease revocation tests involving process termination; and
7. physical RG35XX H resource, latency, restart and power testing.

The verified C transport library is suitable as the common IPC substrate for that
next implementation. ARM64 verification does not itself authorize enabling a
partially implemented security boundary.
