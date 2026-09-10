# RG35XX H hardware audit

Status: physical bring-up in progress. Open boot-chain images have been built
and transferred successfully, but neither has yet produced a visible boot on
this Deck. A separate, known-good muOS card has booted successfully and is now
serving as a private hardware reference.

The Anbernic RG35XX H uses an Allwinner H700 system-on-chip, a 640 by 480
internal display, game controls, two microSD interfaces, a Realtek wireless
device, USB-C, mini-HDMI, audio hardware, and an AXP717 power-management chip.
The exact behavior depends on the production revision.

## Confirmed source support

| Area | Bring-up source | Current conclusion |
| --- | --- | --- |
| CPU and base board | Linux 7.1.2 plus H700 patches | ARM64 Cortex-A53 target; upstream contains the base RG35XX H device tree. |
| Internal display | H700 display and generic MIPI-panel patches | Required for a visible first boot; two panel descriptions are packaged. |
| Controls | Linux GPIO keys, ADC joystick, and H700 input patches | Directional, action, shoulder, menu, volume, and analog inputs are described. |
| Storage | Linux sunxi MMC plus H700 second-slot patch | Both slots are described; physical testing remains required. |
| Wireless | Linux `rtw88` SDIO driver and redistributable Linux firmware | RTL8821CS Wi-Fi and Bluetooth paths are configured; radio testing remains required. |
| Power | Linux AXP717 support and H700 device tree | Battery and input-power reporting are described; charging and shutdown need physical testing. |
| Boot | U-Boot 2026.01 and Trusted Firmware-A 2.12.0 | Separate LPDDR3 and LPDDR4 boot configurations are provided. |

## Hardware variants

Two independent differences must be handled:

1. Some units use LPDDR3 memory and others use LPDDR4. A bootloader trained for
   the wrong memory type may not start, so GuideOS produces separate image
   files rather than guessing at run time.
2. At least two internal panel revisions exist. Both device-tree files are on
   the Windows-readable boot partition. The original panel is selected by
   default; `README-PANEL.txt` explains how to select the revision-6 panel
   without rebuilding the image.

## Kernel decision

Linux 6.18.48 was downloaded, checksum-verified, and inspected because 6.18.y
is the intended long-term GuideOS kernel line. Its upstream RG35XX H files do
not yet provide the complete display and wireless description needed for a
useful first boot, and the current H700 series targets Linux 7.1.2.

`BRINGUP-0` therefore uses the exact Linux 7.1.2 release temporarily. Returning
to a maintained 6.18.y kernel requires a reviewed backport and physical tests;
it is not being represented as complete merely because a kernel can compile.

## Provenance and exclusions

The hardware patch set, alternate panel device tree, and memory-specific
U-Boot configurations come from the ROCKNIX `20260901` release at immutable
commit `1ebff24f36501fb6493beb2bf83bf2604536d9aa`. ROCKNIX is a hardware-support
reference, not the GuideOS distribution base. No ROCKNIX branding, interface,
emulator configuration, or noncommercial visual material is included.

Imported files retain their upstream licenses. Firmware is taken from the
Buildroot `linux-firmware` package with its original redistribution notices;
no firmware is copied from the factory card.

## Tests required on the physical Deck

- Boot with the correct memory image and reach the `BRINGUP-0` screen.
- Try the alternate panel description if the default screen is blank or wrong.
- Verify every button, both analog sticks, and volume controls with `evtest`.
- Verify both microSD slots without writing outside explicitly selected test data.
- Verify Wi-Fi association, Bluetooth discovery, audio, USB host/device mode,
  HDMI, battery reporting, charging, clean shutdown, and thermal behavior.

Passing a build is evidence about source consistency, not proof that these
physical functions work. Results will be recorded after the first controlled
boot.

## Bluetooth-audio preparation — 2026-09-06

The first Bluetooth target is deliberately narrow: one user-confirmed A2DP
earbud using the mandatory SBC codec. The reproducible DDR3, DDR4, and private
compatibility-root configurations now select BlueZ, BlueALSA, D-Bus, ALSA
plugins and utilities, and SBC. The Buildroot configuration step accepted the
complete dependency set; a physical audio result has not yet been claimed.

The known-working vendor kernel reports UART1 as `/dev/ttyS1` and includes
Bluetooth Classic, Bluetooth LE, RFCOMM, HIDP, H4, and H5 support. It does not
provide the newer in-kernel Realtek UART helper, so the private compatibility
path may require the RTL8821CS-specific Realtek H5 attachment program and the
matching firmware/configuration. That operation shares a combination radio
with the working Wi-Fi link and must not be guessed.

`apps/bluetooth/guide-bluetooth-probe` is therefore the next live test. It
only reports the UART candidate, HCI and rfkill state, loaded modules, expected
firmware files, and bounded relevant kernel messages. It does not power-cycle
the radio, attach the UART, scan, pair, or modify storage. Its output will
determine the exact initialization package before any write-capable Bluetooth
test is attempted.

That read-only probe ran successfully over Developer Link. It confirmed Linux
4.9.170, `/dev/ttyS1`, the loaded `8821cs` Wi-Fi module, and a `sunxi-bt`
Bluetooth rfkill device at `/soc@03000000/bt`. The Bluetooth switch was soft
blocked, no `hci0` existed, and no RTL8821C/CS Bluetooth firmware or user-space
Bluetooth tools were present. Kernel messages independently confirmed H4, LL,
and H5 registration plus the Wi-Fi driver's RTL8821CS coexistence support.

This is a clean pre-initialization state, not a failed earbud test. The next
package must provide the correct Realtek firmware/configuration and UART
attachment program before BlueZ, BlueALSA, discovery, or pairing can be tested.
The Bluetooth power switch will remain untouched until that package is ready
so a failed partial initialization cannot strand the Wi-Fi Developer Link.

### Live Bluetooth bring-up — 2026-09-06

The first bounded live bring-up succeeded without interrupting Wi-Fi:

- `sunxi-bt` was enabled through its existing Bluetooth rfkill device.
- The Realtek H5 handshake completed over `/dev/ttyS1`.
- The controller identified itself as `RTL8821CS` with HCI revision `0x000c`.
- The checked 29-byte H5 configuration enabled UART flow control.
- Firmware loaded successfully and reported coexistence build
  `BTCOEX_20220309-5b5b`.
- The kernel created `hci0` and BlueZ 5.79 powered it on successfully.
- BlueALSA 4.3.1 registered an A2DP-source endpoint with the SBC codec.
- `wlan0` retained its address and the Developer Link remained usable.

The runtime is isolated at `/opt/guide/bluetooth` on the prototype. Pairing and
actual earbud playback remain physical acceptance tests; discovery has not yet
been started.

The bounded discovery test subsequently found `soundcore P20i`. The Deck
created and retained a BR/EDR bond, marked that device trusted, connected its
Audio Sink service, and exposed a BlueALSA A2DP-source PCM using SBC at 48 kHz,
16-bit stereo. A one-second 440 Hz PCM tone was transmitted at BlueALSA volume
25/127 while Wi-Fi remained connected. Human confirmation that the tone was
audible was received immediately afterward. This completes the first physical
end-to-end Bluetooth audio proof.

## Physical bring-up record — 2026-09-04

The LPDDR4 candidate was written to the 62,239,277,056-byte test microSD card
and the first 2,215,641,088 bytes were independently read back with SHA-256
`1f4166a488c96494075d412805f8fb6a47078f96ce80d144cd3d7dbd1fc56256`,
matching the source image. With the card in TF1/INT, the Deck's status LED
changed state in response to reset and returned to green, but the internal
display remained blank after a controlled wait. The same result occurred with
the standard panel description and the revision-6 panel description. This is
evidence that the image was transferred correctly, but it does not prove that
U-Boot completed DRAM initialization or that Linux started.

An independent LPDDR3 candidate was then built successfully. Its image is
2,215,641,088 bytes with SHA-256
`e397679ad14ca7dfe454f5f2e3adf2b78ecc81b7b576ccfa263f0c3fb60c61e4`.
The image contains the Allwinner `eGON.BT0`/SPL signature and both panel
descriptions, and its Windows-side copy matched the Linux build output. It was
subsequently flashed and produced the same green-LED/blank-display result as
the LPDDR4 image. A byte-level readback differed from the source only in the
backup-GPT relocation performed by the imaging program; the bootloader,
kernel, and root filesystem regions matched.

A separate 250 GB card successfully booted muOS on the same Deck with a full
battery indication. This control test confirms that the Deck, display, power
system, and card slot can boot a compatible image. A read-only capture was
made of only the pre-user-data boot region and is retained outside the public
repository. Inspection established that the working path uses Allwinner's
H700 DRAM bootstrap, a vendor U-Boot package, an Android-format `boot`
partition, Linux 4.9.170, and an initramfs which mounts partition 5 and hands
control to `/init`.

The original GuideOS root filesystem used glibc with a recorded minimum Linux
ABI of 6.12, so it cannot be paired with the known-working 4.9 kernel. A
temporary musl-based userspace configuration has therefore been added for a
private compatibility test. It contains no captured vendor binaries. Any
hybrid test image assembled from the user's reference card remains private
and non-distributable; the public GuideOS target remains a fully open boot
chain.

The private compatibility image was assembled as a 6 GiB image and written to
the 62,239,277,056-byte expendable seed card. A complete readback of the image
region produced SHA-256
`97467834afa6522238abeb6d3747b5b033019c323490cbf78f53ebd5c67bc821`,
matching the source. Physical boot testing is pending while the Deck is being
charged and its intermittent power behavior is investigated.

That image subsequently reached the visible muOS boot splash with a stable
green power LED, proving that the private hybrid path starts the working DRAM
bootstrap, bootloader, kernel, and display. It remained at the splash instead
of reaching GuideOS. Inspection found that the ext4 root image contained the
`orphan_file` feature, which Linux 4.9 predates. A corrected root image disables
`64bit`, `orphan_file`, and `metadata_csum_seed` and temporarily replaces the
normal init sequence with a minimal PID 1 that prints `HELLO WORLD`. The
corrected 2 GiB root partition was read back from the seed with SHA-256
`f60453207ace6787eb029a12ea41593c78c38eec0e892de286f8045284145397`,
matching its source. A second physical boot test is pending.

The corrected private compatibility image subsequently completed the handoff
to GuideOS. A statically linked AArch64 `/init` opened the vendor framebuffer,
cleared the retained boot splash, and displayed `HELLO WORLD`. This is the
first confirmed GuideOS userspace boot on the physical Deck. It proves the
temporary boot chain, legacy-compatible ext4 root, static PID 1, and direct
framebuffer output; it does not yet validate controls, networking, audio, or
safe shutdown.

The next physical test replaces the one-screen diagnostic with a static,
interactive shell. It presents the approved globe emblem and `HELLO WORLD`,
then opens a three-entry menu for display, input, and system-information tests.
The shell reads Linux evdev events directly and recognizes both keyboard-style
and gamepad-style D-pad/A/B codes. Exact event mappings remain provisional
until exercised on the Deck and recorded from its diagnostic log.

That interactive test passed on the physical Deck. The approved emblem and
`HELLO WORLD` rendered at 640x480x32, the timed transition reached the menu,
all three entries could be traversed, and the A/B actions opened and returned
from their test screens. The captured log identifies three input devices:
`axp2202-pek`, `muOS-Keys`, and `dierct-keys-polled` (the last name is reported
verbatim by the vendor kernel). D-pad vertical motion arrives as `EV_ABS`,
`ABS_HAT0Y` (code 17), with -1 for up and +1 for down. A and B arrive as
`EV_KEY` codes 304 (`BTN_SOUTH`) and 305 (`BTN_EAST`). These mappings are now
physically verified rather than inferred.

The post-test root capture required journal replay on the private copy before
the newest diagnostic files were visible. The card was not modified during
that recovery. This demonstrates that the minimal static shell still lacks a
coordinated sync/unmount/poweroff path; implementing and testing safe shutdown
is required before ordinary writable use.

Safe shutdown was then implemented and physically verified. A short press of
the Deck power control arrives as `EV_KEY` code 116 (`KEY_POWER`) and opens a
confirmation screen. B cancelled without leaving the active shell; a second
Power press followed by A flushed the log, synchronized storage, remounted the
root filesystem read-only, and invoked the kernel power-off path. The Deck
powered itself off. A subsequent read-only capture reported a clean ext4
filesystem with no `needs_recovery` feature, and the complete shutdown request
was present in the committed diagnostic log. This closes the first safe-power
milestone for the temporary static shell.

Payload Format 0 began physical testing of the external TF2 microSD slot. The
shell now offers a fourth `PAYLOADS` entry and scans only `/dev/mmcblk1p1` or a
partitionless `/dev/mmcblk1`. It attempts FAT32 and ext4 read-only mounts with
`nodev`, `nosuid`, and `noexec`, accepts only a bounded regular-file manifest
at `GUIDE/PAYLOAD.GDE`, and displays metadata without executing, installing,
copying, or modifying payload content. Leaving the screen and safe shutdown
both release the external mount. The implementation compiled and its seed
partition was read-back verified. The physical test then succeeded: with the
GuideOS seed in TF1/INT and the prepared FAT32 card in TF2/EXT, the Deck found
`GUIDE/PAYLOAD.GDE` and displayed the expected `HELLO CARD`, `DEMO`, and
summary metadata. This proves second-slot detection, bounded manifest reading,
and the read-only removable-card path on the target hardware.

Following that success, Cartridge Format 1 and host-side authoring tools were
added. They create inspectable `.guide` ZIP packages, inventory every content
file with SHA-256, reject unsafe paths and filesystem links, verify packages
independently, and copy them to mounted cards through a verify-copy-verify and
atomic-rename sequence. Format 1 remains a packaging contract only; execution,
installation, capability grants, and Deck-side import are deliberately not yet
enabled.

Cartridge Browser 0 has now been implemented and cross-compiled for the Deck.
It reads the card-copy tool's bounded `.gde` indexes, browses up to eight
packages, shows identity/version/capability/action information, labels Format
1 packages unsigned, and verifies the selected `.guide` archive's declared
size and SHA-256 before reporting success. The card remains read-only and
`noexec`; this revision cannot extract or install content. The same build adds
boot-time Wi-Fi diagnostics for the SDIO identity, network interfaces, loaded
modules, and kernel release needed to construct the kernel-compatible Wi-Fi
Installation Cartridge. Physical browser and diagnostic testing are pending.
The final legacy-compatible root filesystem has SHA-256
`62961f1402f031da145ef75434b5137fa17c510d32c9ed760a5cd783d7c2a6b5`;
the assembled private vendor-bridge image has SHA-256
`b620ff7ce1a42b6a880343ca55228948cf134361be94c9123aeb5a1fdc5a5d9b`.
Both values were recorded after the final cartridge size and installation-action
validation changes, and the 6 GiB assembled image passed byte-for-byte
verification before hashing.

The cartridge-browser root was then written to the exact previously designated
62,239,277,056-byte seed through the Transcend reader. Windows initially held
the card's sixth partition open; the guarded writer was updated to dismount
only drive letters belonging to the fully revalidated seed before opening the
physical device. No bytes were written during either denied attempt. The
elevated retry completed, and a full read-back of the 2 GiB root region matched
SHA-256 `62961f1402f031da145ef75434b5137fa17c510d32c9ed760a5cd783d7c2a6b5`.
Physical boot, Cartridge Browser 0 interaction, and Wi-Fi diagnostic capture
are now the next test.

That physical boot passed. The Deck reached the expected shell and opened the
Cartridge Browser while the older Payload Format 0 card was accidentally still
in TF2. The log proves `/dev/mmcblk1p1` mounted successfully as FAT with
`ro,nodev,nosuid,noexec` and was unmounted on exit. Because the old card has no
Cartridge Format 1 directory, the browser wording is being refined to report
**Ext storage loaded — no Guide cartridges on storage**, rather than implying
that no external card exists.

The same log records Linux 4.9.170, no loaded modules, no `wlan0`, and an empty
`/sys/bus/sdio/devices` directory. The radio has therefore not reached SDIO
enumeration in the temporary userspace. Driver packaging is gated on restoring
and observing the required vendor-kernel board/radio enablement; guessing a
module from the expected RTL8821CS chip alone would not be a valid installation
test.

The revised browser and the two prepared Format 1 cartridges then passed their
physical read-only test. The Deck distinguished loaded external storage from
missing or unrecognized cartridges, listed both the Wi-Fi and Wikipedia
packages, and verified their complete archives against their card indexes.

The next seed adds the first deliberately narrow persistent installer. It
offers installation only for the exact `guide.prototype.wifi` version 0.1.0
archive whose complete SHA-256 is pinned in the trusted Deck shell. The package
contains the 8821CS module built for the vendor kernel's exact 4.9.170 module
ABI, four networking utilities, and their two libnl libraries. Every extracted
file is independently hashed; pre-existing destinations are refused; failed
transactions remove everything they created; and the external card remains
mounted read-only with `nodev`, `nosuid`, and `noexec`. No network credential is
included or requested in this milestone.

A clean Buildroot output confirmed that the seed contains the installer and
required archive/hash/module-loading applets but does not preinstall the Wi-Fi
payload or Wikipedia application. Its 2 GiB root filesystem has SHA-256
`4db0a4a994799532bf314984052fee03219ceed46870341fc1fa685857e62295`.
That root was written to the exact previously designated 62,239,277,056-byte
seed while preserving the known-working boot partitions, then read back in
full with the same SHA-256. Physical installation and post-removal Wi-Fi driver
activation are the next tests.

The physical cartridge installation completed and displayed `INSTALLED RADIO
NEEDS RESTART`. This confirms that the trusted installer accepted the pinned
archive, verified and persistently copied its seven payload files, wrote its
installation record, and reached the driver-activation step without rolling
the transaction back. The kernel did not expose `wlan0` during that live boot.
A safe shutdown and cartridge-free reboot are required next to test automatic
driver loading and determine whether the radio needs additional board-level
enablement.

The cartridge-free reboot passed the persistence and automatic-loading test.
The installation record remained present, the trusted shell revalidated all
installed payload hashes, and `/sbin/insmod` loaded `8821cs.ko` with exit status
0. `/proc/modules` then reported `8821cs` live. The external cartridge was not
needed for any of these steps.

The immediate startup snapshot still showed no entry under
`/sys/bus/sdio/devices` and no `wlan0` under `/sys/class/net`. The driver is
therefore installed and accepted by the running kernel, but the snapshot was
taken directly after `insmod` and does not prove that delayed enumeration never
occurred later in the boot. The live System Information screen must be checked
after a short wait before changing board-level power/reset initialization.

The live System Information check subsequently reported `WIFI INTERFACE
READY`. This proves the radio enumerated after the immediate startup snapshot
and Linux created `wlan0`. Wi-Fi Installation Cartridge 0.1.0 has therefore
passed its complete first milestone: trusted installation, persistent storage,
cartridge-free automatic driver loading, delayed hardware enumeration, and a
live wireless interface. Network discovery, credential entry, association, and
DHCP remain separate interface tests.

Basic dual-stick support is prepared for the next seed update. The shell now
recognizes the usual `ABS_X`/`ABS_Y` left-stick pair and either
`ABS_RX`/`ABS_RY` or `ABS_Z`/`ABS_RZ` for the right stick. It queries each
device's declared range and flat area, derives a conservative dead zone, and
requires recentering between menu steps. Both vertical axes navigate menus;
horizontal axes are recorded as left/right actions and can browse cartridges.
The Input Test now displays and logs all absolute-axis events, including
neutral movements which do not trigger an action.

The change cross-compiled cleanly with warnings treated as errors. A private
2 GiB root image was derived from the post-Wi-Fi-install capture so the
installed feature remains intact. Its filesystem is clean, both shell binary
locations match SHA-256
`1086c3314339050f7742177345ba52c69881fa9957ece72f500c09a8dd672395`,
and all seven installed Wi-Fi files retain their pinned hashes. The complete
prepared root image has SHA-256
`67dcae6eab3e0b97ea5552fd4250755c2e4019e59267f9ae924788ef0e14d010`.
Physical transfer and axis calibration testing are pending.

Before physical analog testing, the welcome text was changed from `HELLO
WORLD` to `DON'T PANIC`. The final shell cross-compiled cleanly; both `/init`
and `/usr/sbin/guide-hello-fb` in the private update image match SHA-256
`2d1769c78dc62f8c71aa04f915a4070e94a653c2f5e97e82e351b389d119a02e`.
The complete clean 2 GiB root image, still carrying the verified Wi-Fi
installation, has SHA-256
`b4682a2123b473fd5156611b48ded73d8ee722556a2c8001dae9b6acbe47b4c1`.

That final root image was written to the exact designated seed while preserving
the existing boot partitions. A complete read-back of the 2 GiB root region
matched SHA-256
`b4682a2123b473fd5156611b48ded73d8ee722556a2c8001dae9b6acbe47b4c1`.
The seed is ready for physical confirmation of the new greeting, both analog
sticks, and retained cartridge-free Wi-Fi initialization.

The first Deck-to-Node client is now integrated. The home menu includes
`Nodes`; its controller-driven flow requires working Wi-Fi, sends a bounded
local discovery request, lists at most eight validated Guide Nodes, and accepts
the six-digit code through a purpose-built numeric keypad. Candidate addresses
and session tokens never enter the framebuffer protocol or diagnostics log,
and session material lives only under `/run`. The link exposes status and named
capabilities rather than a remote command shell.

The updated shell passed host and ARM64 cross-compilation with warnings treated
as errors. Deck/Node protocol and bridge tests passed, and the complete update
was first assembled and verified on a disposable prior seed snapshot. The live
seed root was then preserved with SHA-256
`7042e6dc6b338c9133b6843b9313aaa3ed275104af9878b4cedd5528dd1a328d`.
After journal recovery, file injection, a clean `e2fsck`, and file-by-file hash
verification, the prepared 2 GiB root image had SHA-256
`3d0b1854083bcf05004837b446490056ed808483869bfd3ee77a8504159ae1fe`.
It was written only to the exact verified root offset of the designated seed
and read back in full with the same hash. Physical boot, Node discovery, and
pairing remain to be observed.

## Checkpoint note

The `build.090326` checkpoint contains the reproducible Buildroot definitions,
hardware audit, and the in-progress Linux 7.1.2 compatibility series. The host
compiler toolchain built successfully. Patch validation reached the H700
storage changes; final series validation, kernel compilation, image assembly,
and image inspection remain work for the next checkpoint.
