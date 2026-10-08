# GuideOS H700 Cedrus development integration

Selected by the owner as option 2: the downstream H700 Cedrus implementation
reported working with ROCKNIX by GreenOvercast. This is a development build,
not evidence of decoding on this physical Deck. No prebuilt ROCKNIX module is
installed: GuideOS rebuilds the driver and its dependencies for its own kernel.

## Sources and adaptation

The two kernel patches and device-tree resources are from
[GreenOvercast](https://github.com/Producdevity/GreenOvercast/tree/2e97ea66a7e917c3f158452877dd324aa852554c/vendor/rocknix-h700-cedrus),
commit `2e97ea66a7e917c3f158452877dd324aa852554c`.
The match uses an explicit H616 compatible and the existing H6 Cedrus variant;
it does not mislabel the device as an H6. The downstream SRAM workaround clears
bit 0 of the H616 system-control register and does not restore that bit on driver
removal, matching the tested reference. This is a board-specific workaround,
not a claim of mainline H700 support. Replacing it with upstream resource ownership
is a later integration change requiring physical regression checks.

`guide-h700-cedrus.dtsi` translates the reference's numeric clocks/reset/IRQ to
the kernel's named bindings. It describes the decoder at `0x01c0e000`, SPI 93,
AHB/module/RAM clocks and VE reset. GuideOS incorporates it into both H700-H
device trees at build time, avoiding a privileged runtime overlay service.

The FFmpeg request patch is from
[ROCKNIX](https://github.com/ROCKNIX/distribution/blob/e9e6b8531df13bc9058ca1771dab5f0c4fd5e98e/packages/multimedia/ffmpeg/patches/v4l2-request/0001-v4l2-request.patch),
commit `e9e6b8531df13bc9058ca1771dab5f0c4fd5e98e`. Its SHA256 is
`afd04c202c27081c355d8d34b58a52c4141de26433007e27ed6e0d2093d10d3c`.
The FFmpeg 9.0 portability patch is from the pinned GreenOvercast source.
`ffmpeg-guide-cedrus-only.patch` is GuideOS's additional discovery restriction:
only media devices whose kernel driver identifies as Cedrus are probed.

The private player uses FFmpeg 9.0, mpv 0.41.0 commit
`41f6a645068483470267271e1d09966ca3b9f413`, and static libudev-zero 1.0.3.
Source URLs, hashes, Debian development packages, and preserved licenses accompany
the build. Existing system FFmpeg/mpv libraries are not replaced. The cross compiler
uses the Debian target headers and libraries explicitly; a newer host libc must
never be copied into the Deck to satisfy accidental toolchain dependencies.

## Build and ownership

Run in the Ubuntu WSL build environment, in order:

```
python3 build/release-0.4.2.05/fetch-cedrus-sysroot.py
python3 build/release-0.4.2.05/prepare-cedrus-runtime.py
bash build/build-debian-cedrus.sh
bash build/build-debian-cedrus-runtime.sh
python3 build/release-0.4.2.05/finalize-cedrus-runtime.py
```

The kernel builder starts from the existing patched GuideOS Linux 7.2.7 tree in
an isolated directory. It preserves display, audio, power, Wi-Fi and card patches,
enables `CONFIG_VIDEO_SUNXI_CEDRUS=m`, builds a distinct kernel release, and rebuilds
the external ROCKNIX joypad module for that release. CMA remains at the baseline
32 MiB; memory reservation is not increased speculatively.
Clean builds also enable `CONFIG_EXFAT_FS=m`, `CONFIG_NLS_UTF8=m` and
`CONFIG_INPUT_UINPUT=m`: the deployed Storage service and Browser control owner
depend on them. The 0.4.2.05 source baseline omitted providers previously installed
as separate modules. [0.4.2.06](../../../../docs/BUILD_0_4_2_06.md) repairs this
with additive modules for the exact existing kernel; it leaves Image and DTBs intact.
The upstream H6 variant's 600 MHz module clock is retained; ROCKNIX's separate
648 MHz H6 performance patch is not imported. Its HEVC/AFBC patches are also
outside this H.264 copy-back slice.

The native media service remains the only owner of the player process, descriptor,
IPC reader and display/audio leases. There is no new system service, listener or
network permission. Its existing supplementary video group grants access to device
nodes created by udev. Udev's device modalias loads the matched Cedrus module.

`cedrus_runtime.py` checks the release, complete runtime hashes, executable
permissions and a usable media/video pair belonging to the same H616 Cedrus
platform device. Failed admission uses `/usr/bin/mpv --hwdec=no`. Successful
admission selects the private launcher with `--hwdec=v4l2request-copy`, restricted
to H.264, and mpv's three-failure software fallback. The launcher changes library
search paths only for the player. Copy-back preserves the established GPU/DRM
presentation and audio clock. Zero-copy, HEVC, VP9 and AV1 hardware support are
not promised by this implementation.

Readiness and status continue using observed IPC properties. Admission is not
proof of hardware use: only `hwdec-current` supplies the reported decoder path.
Checks occur once per open and add no per-frame status subprocess or IPC polling.

## Integration and acceptance

Build outputs are under `build/release-0.4.2.05/cedrus/`. The coherent addition
contains the new Image, both DTBs, matching modules (including joypad), private
runtime, integrity manifest and current media source. Full-image assembly must
stage all of these together. A UI-only Wi-Fi payload cannot deliver this change.
Retain the previous full kernel/root image for recovery; a UI rollback does not
undo kernel or system-runtime changes.

The previously verified 0.4.2.05 root image is an older baseline and does not contain
this integration. The owner subsequently authorized a fresh boot/root deployment;
its verified candidate and matching Seed readback are under
`build/release-0.4.2.05/deployment-candidate/`. Build scripts alone do not authorize
a Seed write. Physical boot and hardware decode are still pending.

After source, native-runtime and kernel verification, `stage-cedrus-addition.py`
and `archive-cedrus-addition.py` assemble and hash-check an offline addition. Its
archive assigns root ownership to system files. This is packaging input with
separate `root/` and `boot-assets/` trees, not a directly activatable UI release.

Physical acceptance requires a boot with this release; Cedrus probe and usable
media/video nodes as the service user; correct 640 x 480 H.264 frames with observed
`v4l2request-copy`; selected-route audio sync; pause/seek/A/B/stop and repeated
shell return; missing-driver/unsupported-profile/allocation-failure recovery;
and bounded memory, drops, CPU, temperature and power measurements. Exercise
larger/high-reference streams before recommending them with the 32 MiB CMA pool.
NDI source preparation can start with H.264 640 x 480 while that envelope is measured.

Stateless request API:
[Linux documentation](https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/dev-stateless-decoder.html).
