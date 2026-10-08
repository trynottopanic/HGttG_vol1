# RG35XX H audio output correction

Status: installed and fully readback-verified on the seed, 25 September 2026,
22:20 EDT, together with System Status Audio test. The version remains 0.3.7.
The owner subsequently confirmed the onboard speakers work.

The owner requested all three proposed corrections after the 0.3.7 louder note
remained quiet. No additional listening tests are part of this work. These are
combined corrections; the owner report does not isolate which correction was decisive.

## Requirements, ownership and acceptance

The board profile owns codec gain and routing; the codec owns analog sequencing.
Guide audio retains software volume and explicit playback. This follows
MODERN_FOUNDATION_0.md and AUDIO_BLUETOOTH_0.md. Systemd, Bluetooth selection,
global controls and the working DMA transfer settings remain intact.

1. Speaker gain is DAC 63/63 and line-out 31/31, removing 11.8 dB fixed
   attenuation. The installer backs up original state as codec-gain-v2-state.json,
   caps initial volume at 20%, preserves other fields and uses a one-time v2
   marker. Headphone gains remain 45/16. Diagnostic waveforms and reference gains
   remain unchanged. Displayed 100% is not a calibrated acoustic measurement.
2. RG35XX H uses ramp index 5. The exact MuOS table at virtual address
   0xffffff8008a4e080 gives 138 ms for the 44.1 kHz family and 126 ms for 48 kHz.
   Mainline module-clock accounting uses 22.5792/24.576 MHz where the vendor uses
   45.1584/49.152 MHz. No clocks, FIFO settings or DMA settings are changed.
   Unknown rates fail before enabling line-out; shutdown falls back to 138 ms.
   A mutex serializes control requests and ramp events. Line-out switch readback
   now represents requested state, with physical enables gated until settling.
   Shutdown ramps down before disabling line-out. Other boards retain old behavior.
   Physical timing equivalence remains unmeasured.
3. Both speaker and headphone activation explicitly clear reversed DAC routing
   and set both channels to Stereo. Diagnostics already showed correct routing;
   a routing defect is not proven. This clears stale state instead of changing
   the board to an unsupported differential connection. DAPM channel routes remain
   unchanged. Comma-separated enum names are supported by the upstream
   [ALSA control parser](https://github.com/alsa-project/alsa-lib/blob/master/src/control/ctlparse.c).

Software acceptance covers kernel compilation, actual callback sequencing,
clock families, shutdown, register errors, unchanged DMA and other-board fallback,
state migration and full image regression. Physical loudness, distortion, channel
separation and pop-free transitions remain pending. The owner stopped playback.

## Build and recovery

Patch: board/rg35xxh/debian/rg35xxh-audio-output.patch, after the DMA transfer patch.
Build: build/prepare-audio10-codec.py and build/build-audio10-codec.sh.
Image: build/prepare-audio10-candidate.py, then build/verify-audio10.sh.

The candidate copies the verified 0.3.7 installation image, changes only the
allowlisted audio payload and preserves 21,288 other regular files plus symlinks.
The staging image is not a fresh returned-seed image. Rebase this payload onto a
fresh seed capture before installation to preserve subsequent user state.
Provider/driver/UCM changes cannot use the shell/input-only network updater.
The installed build and all previous recovery images remain unchanged.

## Completed validation

All 368 ARM64 regression tests passed: audio 19, connectivity 52, deployment 64,
input 135, UI 7, shell 91. Active-release integrity, integrated UI rendering,
0.3.7 tone-overlay checks, service configuration and filesystem checks passed.
The kernel compiled with matching 7.2.7-guide-debian2 vermagic and dependencies;
checkpatch reported no errors or warnings. Actual callback tests passed for
ramp ordering, both clock families, restart/shutdown, invalid rates, failed
register writes, mute requests and unchanged behavior on other boards. The DMA
callback is byte-identical to audio-path-9. ALSA parsed the updated profile.
Migration tests verified initial volumes 0/10/100, original-state backup,
preservation of selected output and position, and preservation of a later
owner-adjusted volume on reinstall. Repeated kernel preparation succeeded.

Candidate record: build/debian-audio-10/candidate.json.
Image SHA256: 2FE32A9A1DC5E52F2F43E64AAC923E525E278ABD70E6AD659449FA8615F4296C.
Codec SHA256: 61F477926044BAFD8DACA4811E2C8AC9DEACE11F11013375EDD25B04A7FA7751.
No device commands, playback, seed writes or live gain changes were performed
for this implementation. A combined change cannot identify which hypothesis
contributes to any eventual physical improvement.

Latest installation: build/system-audio-test/install/installation.json. The final
fresh-seed image passed 377 tests; full root readback matched and boot/data were
unchanged. Earlier staging-only statements above describe preparation history.
