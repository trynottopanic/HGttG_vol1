# Minimal Debian bring-up 0

Current status, 22 September 2026: later diagnostics reached the display and
input tests. GuideOS 0.3 "Liquid Snake" failed its physical run; see
[the failure audit](docs/LIQUID_SNAKE_FAILURE_AUDIT.md) and
[design alignment](docs/DESIGN_ALIGNMENT_0.md). `ROCKNIX_ALIGNMENT_1.md` and
the initial assembly notes below are historical records, not current acceptance.

Selected direction: Debian 13 (trixie), ARM64, no desktop. Initial work assembles
userspace separately from the board boot chain. That initial userspace archive
was not an installable or physically validated image. The seed must not receive it
as though it were a full disk image.

## Driver inventory

The initial survey identified code for the following hardware functions. Later
diagnostic records supply the actual acceptance evidence for each function;
support listed here alone does not establish a working device or complete port.

| Function | Existing support | Integration/acceptance work |
| --- | --- | --- |
| CPU and board | Mainline sunxi/H700 support and RG35XX H device tree | Match boot firmware, memory training, clocks and regulators. |
| LCD/backlight | sun4i DRM plus H700 display, panel and PWM patches | Select standard or revision-6 panel; verify modes and backlight. |
| GPU | Panfrost kernel driver, with compatible Mesa userspace to be added | Verify rendering separately from merely displaying a console. |
| Buttons/sticks | GPIO keys, ADC joystick; ROCKNIX also supplies joypad integration | Confirm every button/axis and choose one coherent input path. |
| Both card slots | sunxi MMC plus board wiring/regulator descriptions | Confirm both devices, removable media and error handling. |
| Speaker/headphones | ALSA sun4i codec/I2S drivers and board routing | Confirm mixer routes, volume, jack behavior and shutdown silence. |
| Wi-Fi | rtw88 RTL8821CS SDIO driver | Supply matching redistributable firmware; test association and coexistence. |
| Bluetooth | Realtek UART/H5 support | Match firmware, UART and rfkill setup; test audio with Wi-Fi active. |
| Battery/charging | AXP717 support in AXP20x driver family | Validate readings, charger behavior, thermal conditions and power-off. |
| USB/HDMI | sunxi USB/DRM support plus board patches | Verify host/device roles and HDMI separately; HDMI audio not assumed. |

Driver modules must be built for the selected kernel. Do not copy Linux 4.9
modules into a modern kernel. Firmware files are a separate dependency and retain
their own licensing requirements. A Debian ARM64 userspace can be paired with a
custom maintained board kernel; Debian's generic installer is not proof of board
boot support.

## Pinned reference inspection

ROCKNIX distribution commit inspected:
`0b991b0ee6ebfac467e9101d7e6b444ef923829b`.
Selected upstream configuration files are saved under
`build/debian-minimal/hardware-reference/` with their original notices.
This is a reference inventory, not a complete locked hardware build.

Its generic kernel recipe currently selects Linux 7.1.2; it should not be
mistaken for proof of a complete H700 backport to our preferred 6.18 LTS line.
Audit shared and device-specific patches, bootloader recipes and initialization
together before choosing the production kernel. Existing local patches already
overlap this support and should not be applied twice.

The current ROCKNIX installation guide lists both:
- `sun50i-h700-anbernic-rg35xx-h.dtb`
- `sun50i-h700-anbernic-rg35xx-h-rev6-panel.dtb`

First physical milestone is a minimal diagnostic boot with identifiable progress
through bootloader, kernel and userspace. Previous blank-screen tests did not
isolate the failing stage. Do not add the old Guide interface to hide or complicate
this test. Establish an owner-accessible console/control route before deployment;
the initial rootfs intentionally has no enabled remote login or default password.

## Userspace assembly

`build/bootstrap-debian-minimal.sh` uses signed Debian repository metadata and
debootstrap minbase, with systemd, udev, D-Bus, certificates and basic system tools.
ARM64 programs execute under user-mode emulation in the build environment for
package configuration and audit. This is not kernel emulation or a boot test.

Working filesystem: `/home/hacker/guideos-work/debian-trixie-arm64-0/rootfs`
in the Ubuntu WSL build environment. Output archive, package versions, checksums
and logs: `build/debian-minimal/`. The script never opens physical disks and
refuses to overwrite an existing rootfs. Package versions are recorded, but the
mirror is moving; this first build is not a snapshot-pinned reproducible release.

Subsequent image integration must add the board kernel/modules/firmware, boot
configuration, storage mounts, network setup, diagnostics and an owner-approved
access method. Apply trixie-updates and security updates and capture final package
versions before physical deployment. Keep machine identity unique per device.

## First diagnostic image (2026-09-21)

The diagnostic candidate uses Linux **7.2.7** with the existing H700 patch set.
The kernel.org release list checked on this date marks 7.1 EOL; 7.2.7 is the
maintained stable line. This supersedes 7.1.2 for this experiment. Selection of
a production LTS kernel remains separate from proving this board boots Debian.
Patch 0003 needed a context refresh for 7.2; its board-specific register change
is retained in `board/rg35xxh/debian/linux-7.2/`.

Two integration dependencies were absent from the older modern-kernel build:
the panel description firmware requested by the built-in panel driver, and the
external ROCKNIX single-ADC joypad module required by the patched device tree.
Both are included in this candidate; panel descriptions are embedded in the
kernel so early display probing does not depend on mounting the root filesystem.
These are plausible contributors to earlier failures, not proven causes.
The diagnostic configuration also enables the AXP20x ADC and battery drivers.
Wi-Fi and Bluetooth UART drivers are modules, so probing can access Debian's
firmware files after the root filesystem is mounted.
The pinned external joypad source required adaptation from the removed
`input_polled_dev` API to `input_setup_polling`, normal input-device registration
and managed allocation. `board/rg35xxh/debian/joypad-linux72.patch` records this
change and removes its dependency on ROCKNIX's optional global remapping hook.
The adapted module compiles and passes kernel symbol resolution; actual button,
axis, open/close and suspend behavior must still be checked on hardware.

Build steps, in order:

1. `build/prepare-debian-kernel.sh` — fetch and patch isolated kernel sources.
2. `build/build-debian-kernel.sh` — build kernel, modules and both panel DTBs.
3. `build/finish-debian-kernel.sh` — embed panel descriptions and build joypad.
4. `build/prepare-debian-diagnostic.sh` — derive diagnostic Debian from base.
5. `build/assemble-debian-diagnostic.sh` — assemble and check an image file.

The rootfs and assembly steps require root inside WSL. Assembly writes only
staging files. The distinct Windows flashing script checks the physical card's
model, serial, capacity, USB bus and non-system status, the backup record and
image checksum before writing. It clears the old backup GPT and verifies the
entire written image by reading the card back. Flashing is not a boot test.

Initial layout uses an MBR, with the existing LPDDR4 U-Boot/SPL at 8 KiB:

| Partition | Offset | Size | Purpose |
| --- | --- | --- | --- |
| GUIDE_BOOT / FAT32 | 1 MiB | 128 MiB | Kernel, DTBs, extlinux configuration, reports |
| GUIDE_ROOT / ext4 | 129 MiB | 2 GiB | Minimal Debian and diagnostic service |
| GUIDE_DATA / ext4 | 2177 MiB | 1 GiB | Persistent diagnostic data |

Unused card capacity is deliberately left unallocated during bring-up. This
is not the final update/rollback partition layout. The bootloader's memory
variant and standard-versus-revision-6 panel still need physical confirmation.
Both panel configurations are present; `extlinux/extlinux.conf` selects standard.

The automatic diagnostic prints a userspace marker, records kernel/input/display/
audio/network/power information, waits 60 seconds, saves logs on both data and
boot partitions, then powers off. No default password or remote login is enabled.
The diagnostic does not test button operation, Wi-Fi association, Bluetooth audio,
GPU rendering or charging accuracy. Those follow a successful first boot.

### Build and installation result

The kernel and adapted joypad module built successfully. Debian's package audit,
the diagnostic service check, the final image partition-table check, and read-only
checks of both embedded ext4 filesystems passed. FAT validation also passed.
The module's version magic matches `7.2.7-guide-debian0` and ARM64.

The 3,490,709,504-byte image was installed on the guarded Transcend seed on
21 September 2026. Full card readback matched image SHA-256
`2d79860ba3e703f447f4749d62ebbdf777710d8f34fddd591438a03d56a5ac44`.
The old backup GPT was separately confirmed cleared. The flashing script's
stream options use explicit .NET enum types; string options had selected an
incorrect constructor overload during earlier unsuccessful attempts. The final
method clears the old layout after all guards and writes boot metadata last.

**Physical boot test remains pending.** Put the seed in the RG35XX H system-card
slot, power on and allow up to three minutes. A successful userspace boot records
diagnostics and powers off after roughly a minute. Return the card to the reader
after shutdown so `GUIDE_BOOT/diagnostics/` can be inspected. A blank screen alone
does not prove failure: the saved userspace marker and logs distinguish display
failure from an earlier boot failure. If it stays powered on after three minutes,
record the screen/LED behavior and power it off before removing the card.

## Sources

- https://github.com/torvalds/linux/blob/master/arch/arm64/boot/dts/allwinner/sun50i-h700-anbernic-rg35xx-h.dts
- https://rocknix.org/devices/anbernic/rg35xx-h/
- https://rocknix.org/configure/h700-installation/
- https://github.com/ROCKNIX/distribution/tree/0b991b0ee6ebfac467e9101d7e6b444ef923829b/projects/ROCKNIX/devices/H700
- https://manpages.debian.org/trixie/debootstrap/debootstrap.8.en.html
- https://www.kernel.org/
- Local history: `board/rg35xxh/HARDWARE_AUDIT.md`
