# GuideOS 0.3.7 handoff

Continuation entry point: [GuideOS 0.3.9 handoff](RELEASE_0_3_9_HANDOFF.md).
This document is historical deployment evidence; the new handoff distinguishes
the installed 0.3.7 Seed from the 0.3.9 development version.

Latest write, 26 September 2026 at 23:21 EDT: the Supervisor handshake and stale
mount cleanup fixes are installed and fully readback-verified. Boot/data unchanged.
The external controller clock fault remains unresolved. See
[physical follow-up and write record](CARD_INSTALL_PHYSICAL_FOLLOWUP_0.md).


## Current follow-up: Notepad and media integration, 26 September 2026

The freshly returned Seed was captured, updated, preservation-audited, written
and fully readback-verified at 22:48 EDT. Boot and data partitions are unchanged.
See [the current image handoff](NOTEPAD_MEDIA_IMAGE_HANDOFF_0.md) and
[Notepad internal-draft preview](NOTEPAD_INTERNAL_DRAFT_0.md). The image includes
application/editor support, Home/power D-pad fixes, pointer improvements, the
single Wi-Fi icon, trigger paging, and Future Planning's media engine handoff.
Notepad is delivered as a cartridge and has not been silently preinstalled.
Physical boot and cartridge acceptance remain pending. Earlier stage/status
notes below are historical and do not describe this newly written image.


Step 1 follow-up, 26 September 2026: the [installed application host](APPLICATION_HOST_0.md) is implemented and host-verified, with staged ARM64 binaries and runtime dependency. The earlier probe-only readiness assessment below is historical. No seed write or physical acceptance is claimed. Cartridge catalog/installer work remains step 2.

Notepad documentation integration, 26 September 2026: see the
[cartridge installation readiness review](NOTEPAD_INSTALLATION_INTEGRATION_0.md).
Visual requirements and the save core exist; the general application host, Deck
installer and Notepad executable remain incomplete. This review writes no seed.

Pending source update: 4x4 stars and the exact three world-selection words above
the globe. Both captions now use 16-pixel bold OCR text with 11-pixel letter advance. The card startup retry fix also
remains pending. Neither is on the seed. See [dynamic globe](DYNAMIC_GLOBE_0.md)
and build/boot-words-bold for validation artifacts.


Physical follow-up, 26 September 2026: the owner confirmed text is readable at the new size and the landmasses changed and look substantially better. Stars remain invisible. External storage was not initially recognized but was recognized after removal/reinsertion. Source fixes and a new renderer are being validated; they are not on the card. See [follow-up](CARD_STAR_FOLLOWUP_0.md).

## Latest installation: readability and boot preparation correction

Written and fully readback-verified on 26 September 2026. The visible release
remains 0.3.7. Main text is 24 px, headings 28 px and secondary/control text 20 px;
the status bar retains its accepted size. Saved boot logs showed generation
fallback at the former three-second limit. Preparation now allows ten seconds,
with bounded outer deadlines and explicit timeout reporting. The native starfield
renderer is unchanged; physical generation and star visibility need verification.

The fresh-state image passed 415 regression tests and 14 boot tests, exact payload
and UI integration checks. 23530 files/links outside the update
were preserved, including current settings and the boot counter. Boot and data
partitions are verified unchanged. Physical readability and dynamic boot are pending.

Root SHA256: `353952426007CD096E2926BD93DDBB21D490CE5D1D01EDF6572E208219E134D1`.
Active shell: `06e3a53be156a7b67bf66a53439b021f71c8a8c37781790cf7ce88783646c175`.
Records: `build/readable-type/install/installation.json`, `final-audit.json`,
`prewrite.json` and `returned-boot.log`.
See [readability correction](READABILITY_CORRECTION_0.md).


Owner verification, 26 September 2026: the written build boots and recognizes the external card. The animation still visibly uses the old landmass with no observed stars; dynamic boot acceptance failed. Field text is too small except the status strip. The connected Deck reports the expected active shell c0a260703aa22378fc5db547c979a76e2f5f61f8ec69939e3a548d3cf21eac20. See [readability correction](READABILITY_CORRECTION_0.md).

## Latest installation: Field Theme and dynamic globe

**Written and fully readback-verified, 26 September 2026. Physical boot pending.**
Field Theme 1 from Musings is integrated with the dynamic terrain/cloud/ocean/star
boot sequence, TF2 Guide recognition, volume HUD, outlined pointer and Wi-Fi status.
The visible release remains 0.3.7. The fresh-state image passed 415 regression
tests and 14 boot tests; 23483 existing files/links outside the payload were preserved.
Boot and data partitions are unchanged. Do not repeat the write automatically.

Root SHA256: `9C0785BD2808BED4FB0A9662FC1E30B6693966F075EE269C88033A606D0FD942`.
Active shell: `c0a260703aa22378fc5db547c979a76e2f5f61f8ec69939e3a548d3cf21eac20`.
Records: `build/field-theme-install/install/installation.json` and `seed-install.txt`.
See [Field Theme implementation and recovery](FIELD_THEME_IMPLEMENTATION_1.md).

## Previous working audio installation

Status: **0.3.7 with audio-output-v2 and System Status Audio test installed and
fully readback-verified**, 25 September 2026, 22:20 EDT. Boot and data partitions
are verified unchanged. The owner has since confirmed the onboard speakers work.

Latest record: build/system-audio-test/install/installation.json. All 377 tests
passed on the fresh-seed rebased image. The visible release remains 0.3.7; active
shell identity is 1d772d7e5d6dd99303510a1fe0b7a1de8d9619b9d98c3649d517a5b2ea6f8600.
Root SHA256: 92544A48CA33DB2B56B3C4295348759D609877301EDB526D9245B87720EFF9F1.
Recovery capture: private-recovery/system-audio-test-return-20260925-221145.
Fresh state was preserved, with the documented one-time volume cap at 20% and
original audio state retained in codec-gain-v2-state.json. 21,268 other regular
files and existing symlinks were verified preserved during rebase.

Owner confirmed the onboard speakers work after this installation on 25 September
2026. Prior boot and louder-note results below refer to the earlier 0.3.7 installation. Do not
repeat the write or automatically run another isolated louder-tone test. The
owner can use System Status -> Audio test for a five-second normal-path tone.
See [System audio test](SYSTEM_AUDIO_TEST_0.md) and
[Output correction](AUDIO_OUTPUT_CORRECTION_0.md) for the installed changes.

Earlier installation record (21:27 EDT):
build/release-0.3.7/install/installation.json. Keep all previous recovery files.

## Earlier staging: dynamic globe

[Dynamic globe prototype](DYNAMIC_GLOBE_0.md) now generates reproducible terrain,
clouds and settlement lights from the accepted atlas and per-boot word sequence.
The latest cumulative candidate is
`build/dynamic-globe-v3/guide-dynamic-globe-root.ext4`, including all interface and
external-card changes below. It passed 14 animation tests, native runtime checks
and actual GLES shader previews in ARM64 emulation. The cloud atlas is integrated and ocean textures now include subtle blue
variation and wave crests. Twelve faint, independently twinkling stars now surround
the globe; shader checks verify their count, brightness and otherwise black sky. Generation measured 1.2-1.3 seconds there; physical timing and two-boot shell handoff remain unverified.
The image comparison preserved 23,585 existing files and links, with only the
renderer replaced and its original retained. No physical installation occurred.
Rebase onto a fresh seed capture before writing; retain the working audio baseline.

## Earlier staging: interface changes

[Transient volume display](VOLUME_OVERLAY_0.md) adds a translucent left-side
`N/100` bar with a 650 ms hold and 450 ms fade after confirmed volume changes.
The pointer now retains its 11-pixel circle with a bold 2-pixel white outline
and a 75% transparent black center; the 135 input tests passed after that change.
The preceding interface candidate is build/volume-overlay/guide-volume-overlay-root.ext4;
415 cumulative regression tests passed. The latest addition is the
[Wi-Fi connection and strength indicator](WIFI_STATUS_INDICATOR_0.md), with
108 shell and 9 control tests rerun successfully.
It includes external-card recognition and has not been installed. Rebase onto a
fresh seed capture before writing. Envelope and broker work remains separate.

## Earlier staging: external card recognition

[External card recognition 0](EXTERNAL_CARD_RECOGNITION_0.md) is implemented and
staged under build/external-storage. It adds Home -> EXTERNAL CARD, a single
read-only TF2 recognition provider, and matching exFAT/UTF-8 add-on modules.
395 ARM64 regression tests passed. The candidate has not been written to the
seed; rebase onto a fresh capture before installation so new owner state survives.
The installed working audio image above remains the baseline. No cartridge
installation or software-broker contract is implemented by this slice.

## Owner request and working rules

Integrate the work completed so far into the next seed update, call it 0.3.7,
include a purposefully louder test note, and prepare continuation in another
conversation. Standing authorization covers building, validating and writing
the identified seed. Do not request the same write permission again. No new
conversation was created or messaged. This file is the handoff entry point.

Read the [development guide](../../docs/DEVELOPMENT.md). Develop GuideOS from its documents; systemd is PID1 and Guide
supervision sits above it. Keep board-specific bring-up separate from portable
contracts. The owner wants direct technical communication, no unprompted joviality
or responsibility framing. Do not turn philosophical guidance into blanket
restrictions. Preserve current code, backups, credentials and unfinished work.

Workspace: E:/DGttG/HGttG_vol1/GuideOS. Windows PowerShell host, WSL Ubuntu root
for cross-building and ARM64 userspace checks. The workspace is heavily dirty;
do not reset, clean or commit unrelated work. Do not erase older recovery files.

## What is integrated

This release starts with the fully readback-verified audio-path-9 root image,
then installs three diagnostic-provider files and a new immutable shell/input
release. It also updates fallback shell/input copies and /etc/guideos-release.
The root VERSION and visible System Status identify 0.3.7.

| Area | Included state | Evidence and limits |
| --- | --- | --- |
| Foundation | Minimal Debian, kernel 7.2.7-guide-debian2, systemd PID1 | Board-specific RG35XX H target; broader portability remains architectural work. |
| Boot | Existing corrected globe animation, assets, console handling, timing/logging | Owner confirmed corrected appearance; preserve timing evidence separately from power-button-to-first-frame claims. |
| Input | Reusable grid keyboard, letter/symbol pages, Unicode rendering path, stick entry, menu cursor and dynamic context menu | Existing shared source matches installed baseline. Full international entry and future focus arbitration remain unfinished. |
| Shell/UI | Existing shared schema integration, status bar and controller-owned Home/navigation | New version label and louder-tone label only; do not claim every proposed Guide View surface is migrated. |
| Wi-Fi | Discovery, strength, connect/disconnect, saved credentials, reconnect policy and boot reconnect | Owner confirmed boot reconnect. Manual disconnect hold is retained. Switching between multiple networks remains physically untested. |
| Audio | Local playback, Bluetooth provider, bounded buffering and board mixer profile | Owner confirmed Bluetooth earlier and normal speakers now; low speaker volume remains open. |
| Time | Network time synchronization | Owner confirmed working. |
| Diagnostics | CPU/memory/process-tree and navigation/media telemetry, Start+Select overlay, PC link | Owner confirmed overlay; boot-animation interruption remains excluded. |
| Updates | Paired, pinned SSH link and transactional shell/input delivery below 100 MB | Provider/kernel/root updates still require seed. Do not smuggle those changes through shell delivery. |
| Recovery | Previous immutable UI release, root capture, persistent user state and readback checks | Preserve boot/data and all unchanged root files. No cleanup of recovery history in this release. |

Machine-readable audit: build/release-0.3.7/integration-audit.json. The source
comparison found only the intended new provider files and shell/version/label
changes differing from baseline. Missing render_previews.py and validate.py are
host-side UI tools; guide_deploy.py and guide_link.py are PC clients, not missing
Deck services. Wi-Fi sources match /usr/lib/guideos/connectivity.

Planning documents for Wikipedia, Notepad, media players, external storage,
Pocket Mode, broader lifecycle/resource enforcement and capability brokerage
are not evidence of completed Debian applications. Do not implement those
proposals just to claim that everything is integrated. Retain their status.

## Speaker breakthrough: preserve this evidence

Exact working MuOS binary comparison: docs/MUOS_AUDIO_COMPARISON_0.md.
Implemented patch: board/rg35xxh/debian/rg35xxh-dma-transfer.patch.
Only anbernic,rg35xx-h gets playback source width equal to destination width
and source/destination burst lengths 4. Generic DMA code is unchanged. S16
uses two-byte widths; S32 uses four-byte widths. FIFO, clocks, ramp and gain
were deliberately unchanged from audio-path-8.

Owner confirmed S16 audible, then the ordinary interface test played two tones,
then S32 audible, then repeated S16 audible after service recovery. All were
quiet. Kernel logs confirmed the new transfer settings, captured buffers matched
and tests completed with return code zero and restored=true. See
AUDIO_DMA_TRANSFER_TEST_0.md and build/debian-audio-9/physical-result.json.

This establishes the combined transfer change works in those cases; it does not
prove which setting alone is necessary. Do not replace this with the internal
oscillator: that bypasses sample delivery. Do not double the codec clock from
software rate labels; vendor/mainline PLL accounting differs.

Confirmed codec SHA256:
A82C63D2084EB35F89F36B4BA2B754425C367728C4E2C410221CEA6EF1399E2E.
Last installed root SHA256:
A9A0124E49E8472171DDADE50D050D98E15BE0B8C99F57764BC12ECACF721105.

## Louder test added in 0.3.7

New fixed operation: Tone-S16-Higher. One four-second 440 Hz stereo S16 note,
five-second visible countdown, 50 ms fades. Wave amplitude is 24% versus the
previous 12%, approximately +6.02 dB. Hardware DAC 58 and line-out 27 remain
unchanged. It is explicit-only: the legacy multi-tone sequence does not include
it. It does not change saved volume. Existing mixer/service restoration and
one-shot kernel-buffer checks remain in force. The new UI labels it +6 dB.

No louder note has yet been played on the Deck. Current volume 100% does not
mean full hardware gain: the existing file peaks at 10%, isolated tone at 12%,
DAC gain is 58/63 and line-out 27/31. These attenuations are observations, not a
calibrated speaker-level measurement or a complete diagnosis of low volume.

## Completed installation procedure (reference only)

The owner returned the seed; the procedure below is complete. Keep these steps
for recovery/reference, not as an instruction to repeat the write.

1. Recheck the seed identity and three-partition layout. Expected reader:
   Transcend TS-RDF5 SD, serial 00000000TS38, USB, 62,239,277,056 bytes;
   historically PhysicalDrive4, but recheck before every raw operation.
2. Run build/capture-037-return.ps1 in an elevated hidden PowerShell process.
   It validates identity/layout, captures the used region read-only and records
   its hash under build/release-0.3.7/install/capture-return.json.
3. Run in WSL root: python3 /mnt/e/DGttG/HGttG_vol1/GuideOS/build/prepare-037.py --install.
   Requires passed staging validation, expected installed codec and unchanged
   validated payload. It rebases onto the fresh capture, retaining latest state.
4. Run in WSL root: bash /mnt/e/DGttG/HGttG_vol1/GuideOS/build/verify-037.sh install.
5. Only after PASS, invoke build/install-037-seed.ps1 -ExpectedImageHash with
   the exact install-validation.json hash. Use elevated hidden PowerShell.
   It verifies capture, candidate, card identity/layout and original regions;
   writes root only; closes/reopens and hashes readback; verifies boot/data unchanged.
6. Read installation.json and transcript before claiming installed. Update this
   handoff status with actual outcome. Do not overwrite existing capture/image/
   transcript records blindly on retry; investigate first.

Staging commands use prepare-037.py without --install and verify-037.sh without
arguments. The staging image is explicitly not a fresh returned-seed write image.
Both modes preserve every pre-existing regular file and symlink outside the
listed payload; integration.json records the list and count.

## After the owner boots and connects Wi-Fi

Last Deck address: 192.168.4.70. Use build/Guide-Link.ps1 -DeckAddress ADDRESS
-Action Health / Inspect / Audio-Path. The paired profile is stored privately in
WSL at /home/hacker/guideos-private/deploy0/profile.json. Never print credentials.
Reports go to E:/DGttG/private-recovery/live-link. SSH port 2222 is a constrained
protocol, not a root shell.

Confirm Health deployment version is 0.3.7, audio idle/local, Home visible.
Announce the louder single note before using -Action Tone-S16-Higher. Wait for
the countdown/note, fetch Probe-Result, Inspect and Health. Require the selected
higher test, normalized peak near .24, matching kernel-buffer evidence, correct
DMA settings, return code zero and restored=true. Ask the owner about audibility,
relative loudness and distortion. Do not infer those from software success.

Stop after the single requested higher-level comparison and evaluate. Do not
silently raise hardware gains to maximum or introduce continuous playback.
Remaining work: assess comfortable loudness/volume calibration, preserve working
transfer settings, then return to the accepted project priorities. Cold-boot
repeatability and broader lifecycle/resource/application conformance still need
separate evidence; this audio result does not finish the OS architecture.

## Staging validation result

All 349 ARM64 tests passed: connectivity 52, deployment/diagnostics 64, shared
input 135, UI schema 7, shell 91. Active-release import/render integrity,
integrated input/Unicode preview, louder countdown/playback/expiry overlay,
service configuration, SSH configuration and filesystem checks passed.

Staging root SHA256:
415D0D8F8986BCDCBC43631B77E3192FD19FBCB9CD1EB7C9FE432BCC5E5E4F29.
This is not the final fresh-capture installation hash. Shell release identity:
8c141813425a2e51a638adcdcd423c840df59055195526c86a27831c6a2a77c4.
The shell bundle is 167,488 bytes. Test logs and rendered overlay images are in
build/release-0.3.7/staging. No new physical behavior is claimed for 0.3.7 yet.

## Final-image preparation note

The final fresh-seed image passed all 349 tests and integration checks. It
preserves 21,251 existing regular files outside the payload. Final image SHA256:
0AD6AF8AE8FFB130AB97B66EF4408ABDF9D2D5B58CDF489A1084DF237B1A1ABB.
The returned-seed backup is private-recovery/037-return-20260925-211830;
capture SHA256 5331F32A9F4D49023C8D9FD2D73864A5815361A075DF42B07EB2CDB23F8F8443.

The first preparation attempt stopped before any card write because the ZIP
manifest timestamp changed its archive hash. Every archive member was verified
byte-identical. prepare-037.py now compares every member and then reuses the exact
validated staging archive, preserving its hash. The failed attempt image/archive
remain under install with attempt1 in their names; they are not installation
candidates and can be reviewed during later owner-requested cleanup.

## Physical continuation: 25 September 2026, 21:37 EDT

Supersedes the pending physical-test status above. Health confirmed active 0.3.7
and ready shell; owner confirmed Home visible and normal. One Tone-S16-Higher
was run. Owner reported: "I heard a note but it was still quite quiet. Enough
testing; theorize 3 most likely faults." Testing is stopped.

Completed probe-result-20260925-213732.json selected file-s16-higher, normalized
peak 0.239990234375, returncode 0, restored=true. Its 4096-byte kernel buffer
matched checksum 2052021913 and 3842 nonzero bytes. Inspection at 21:37:21 shows
fresh DMA widths 2/2 and bursts 4/4 at boot-relative 175.724111 seconds, and
healthy audio services with zero restarts. Health at 21:37:23 confirms idle local
audio, volume 100. Reports remain in private-recovery/live-link. No further
playback or gain changes were made. Relative loudness and distortion were not
specifically established. Cold-boot repeatability remains untested.

Output follow-up: owner requested all three proposed corrections. See
[AUDIO_OUTPUT_CORRECTION_0.md](AUDIO_OUTPUT_CORRECTION_0.md). These are staged
changes, not additional playback or a new installed release.

System Info follow-up: [SYSTEM_AUDIO_TEST_0.md](SYSTEM_AUDIO_TEST_0.md) records the
requested five-second normal-volume test option. The combined staging candidate
is build/system-audio-test; it includes the preceding output corrections and
requires a fresh-seed rebase before installation. The handheld remains unchanged.
