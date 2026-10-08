# 0.3.9 media integration continuation

Latest: physical boot confirmed 0.3.9 but exposed a storage startup import error.
The returned journal confirms the cause. See
[the storage startup repair](RELEASE_0_3_9_STORAGE_STARTUP_RESULT.md) for the
fresh returned Seed and corrected image. The correction is installed and fully
readback-verified; boot/data are unchanged. The owner now confirms card recognition
and media playback after one reinsertion. Reliable cold-boot TF2 detection remains
open. The owner explicitly confirmed both Music and Video playback on the Deck.


## Latest state: installed and readback verified

The final native-player candidate was written to the verified Seed root partition.
Full root readback passed; boot and data hashes are unchanged. Root SHA256:
`15278568DD3370D5EFFB8ECAF3F579B64978C35E97D27AF4182038807B1C28FB`.
Active immutable release:
`971dd342b7de44c874c23cb70d18e5ce98526be421f7676c6ffd2ddce02e5e1b`.
The exact-base audit preserves 28,442 existing entries with 66 allowed changes or
additions; existing owner state and committed Notepad are unchanged.

Evidence: `build/release-0.3.9-media/install-final/installation.json`,
`seed-install.txt`, `final-audit.json`, and `image-v7/preservation.json`.
Final installed-only MP3/MP4, owner-exit, output-change, source-removal and checkpoint
fixtures pass in `installed-native-final.log`; all 25 audio tests pass there too.
No source overlays were used for that final fixture. Presentation sinks remain
null, so physical display/sound acceptance is still pending.

The owner has been asked to boot with both cards inserted and confirm that
Media > Music on card and Video on card list the existing files. A pauses/resumes
fullscreen video; Left/Right seek 10 seconds; B/Menu stop video and return control.
Select an available Audio output before playback. Music may continue on Home.
Do not infer successful boot or physical playback from readback verification.
TF2 clock-timeout correction remains unresolved and is not part of this image.

The following sections retain the chronology of source work and superseded images.

27 September 2026. Source and image evidence only. No Seed write was performed;
physical Seed remains 0.3.7. The owner approved writing after established checks.

## Base and package

Fresh read-only capture under E:/DGttG:
`private-recovery/release-0.3.9-media-return-20260927-002855/seed-used-region.img`.
3,490,709,504 bytes; SHA256:
`D35855FB5D1F20079D29E2A86FFA74EAE09383C59A51A49A9B526CF37D2FF5E4`.
It matches the successful installed-Notepad capture. The owner confirms MP3/MP4
fixtures are on the external card.

Future Planning package:
`build/handoffs/guideos-0.3.9-media-library-socket/START_HERE.md`.
All 26 integrity-bound files verified. This supplies library integration and
source engines/contracts, not deployed Media Session or Music/Video screens.

## Corrections and evidence

Startup/retry/uninstalled-record corrections remain included. Both policy loaders
and native-host acquire/revoke admit declared capabilities 6-8 and reject unknown
9. Library WATCH now has bounded persistent connections, change/resnapshot events,
owner-death, deadline and grant-revocation cleanup.

A real systemd-supervised fixture acquired browse/open grants, listed/described
an opaque item, received its descriptor, and verified wrong-capability and revoked
grant denial. Synthetic media only; not sandbox SDK or physical playback proof.

Provider validation returns authoritative owner identity to the session broker.
Closed sessions reuse bounded capacity; failed construction releases admission;
failed stop closes/releases exactly once. Closed controls are rejected and source
generation invalidation stops matching sessions. Resume waits for high water.
mpv distinguishes unavailable metadata from failure and rejects corrupt status.
Output selection requires a trusted route resolver instead of acknowledging a
no-op; track selection rejects unsupported opaque mappings.

Passed: 38 media tests; 30 storage tests; Foundation C/sanitizer/codec/systemd
checks plus 10 runtime tests; 31 installer tests. Evidence directory:
`build/release-0.3.9-media/`. Latest media log: `media-tests-session.log`.

## Latest image

`build/release-0.3.9-media/image-v2/guide-0.3.9-root.ext4`
SHA256: `afbbeab89aa6286696346a2256ebe27c8c599089f9dbd3b8b209cce37a7b1b21`.

Passed exact-base extraction, installed ARM64 Foundation, Python syntax and
systemd verification, actual installed GStreamer buffer/drain and mpv JSON IPC
pause/seek/bounded-stop tests, owner/Notepad preservation audit and filesystem
check. Synthetic/null-output engine tests do not establish sound or display.
47 allowed changed/added entries; owner state unchanged. The preceding `image/`
candidate predates session fixes; use image-v2 evidence for current modules.

Candidate metadata intentionally says `playbackReady=false`, `writeReady=false`.
This is incomplete functional integration, not missing owner permission.

## Remaining release work

- Deploy the session endpoint with authorized source access, resource admission,
  supervised decoders, subscriptions and owner/source-loss cleanup.
- Complete real GStreamer descriptor backend, selected-output and display leases,
  track mappings and no-speaker-fallback behavior.
- Wire Music/Video browsing and playback controls, shell display restoration,
  Power responsiveness and visible buffering/failure states.
- Test the complete installed path, preservation-audit final image, verify exact
  target/card regions, root-only write, full readback and unchanged boot/data.
- Physical MP3/MP4 start/pause/seek/exit/output-loss/card-removal acceptance.

TF2 clock timeouts remain unresolved; no kernel repair is claimed. See
`TF2_REINSERTION_INVESTIGATION_0_3_9.md`.

## Actual adapter follow-up

The subsequent ARM64 adapter probe reproduced two failures missed by the earlier
raw-backend fixture: mpv's `set` command rejects a boolean pause value, and a
one-second clip never reaches the two-second buffer threshold. The adapter now
uses `set_property`, consumes verified demuxer end-of-input to drain a finite
remainder, and reports end-of-media so the session closes/releases resources.
Transient unavailable properties during open remain distinct from decoder failure.
The read-only image-v2 probe overlaid the changed source in temporary memory and
passed asserted start, pause, seek and short-clip end checks. This is source
execution against installed ARM64 dependencies, not a change to image-v2.
The image-v3 builder includes these source changes and runs that full fixture
before its preservation audit; consult candidate.json for final completion.

## Paused at owner request

The owner chose complete playback before writing, then explicitly stopped work
to reclaim processing power. Work is paused, not awaiting write permission.
The active image-v3 build was interrupted during root extraction, before mounting
or validation. Its partial root image is NOT usable; no candidate.json was sealed.
Preserve previous image-v2 evidence; source has the later tested adapter fixes.
On resume use a fresh image output directory (or explicitly account for the partial
image-v3 artifact); the builders refuse to overwrite existing images. No image
write was made to the Seed, and the external card was not modified.

Resume from this document and RELEASE_0_3_9_HANDOFF.md. Complete session/service,
source authorization, resource/output/display ownership and Music/Video UI before
writing. Do not repeat already-passing startup fixes or mistake null-output ARM64
engine fixtures for physical acceptance. The owner test media are on the card.

## Resumed native-player implementation

The owner resumed work and requested completion before writing. The new native
Music and Video views are in `guide_media_panel.py`, behind the existing Media
entry. A root-only shell control socket invokes `guide-media-player.service` as
`guide-audio`; decoder subprocesses are bounded by its systemd cgroup. This is a
system-owned native player path, not a claim that the public Media Session 1
endpoint or cartridge media SDK is complete. Their grant-bound source cores
remain separate. No application gains the shell's system-control authority.

External Storage retains mount ownership. Its private descriptor channel checks
the provider UID and exact systemd cgroup before opening an opaque item. It does
not publish card paths. A shared process-lifetime audio lease excludes the old
audio player/test from native playback. Selected-output loss and source-generation
loss stop playback; shell exit is observed by pidfd. The shell reserves display
before requesting video, suppresses framebuffer writes until release, and forces
a full redraw afterward. B/Menu and global Power recovery stop video. Audio can
continue while leaving the Media view. Left/right seek and A pause/resume control
fullscreen video. MP3 uses an isolated descriptor-only GStreamer worker. MP4 uses
one software-decoding mpv process for video and audio. The PipeWire stream policy
pins the selected target and disallows fallback/reconnection.

Host evidence: 42 media tests, 30 storage tests and 126 shell tests pass. Installed
ARM64 fixtures pass real MP3/MP4 start, pause, seek and stop over the native socket
with the actual systemd UID/cgroup checked by the source provider. Unauthorized
control callers are denied. Owner exit, output change, source removal and durable
checkpoint checks pass. All 25 audio regression tests pass inside the image.
The first installed fixture overlaid the corrected cold-start decoder handshake;
the final candidate must rerun with installed files only. Decoder initialization
has a separate 8-second deadline and reports buffering without blocking the UI;
normal worker operations remain bounded at one second.

Corrections found by integration: service boot-order cycle, cold GStreamer startup
exceeding a normal operation deadline, and a stale status reply releasing a queued
video display reservation. The image-v6 preservation audit also caught scratch
configuration directories created by mpv option probing; image-v7 moves that probe
inside temporary mounted scratch storage. Failed/partial candidates are not write
sources. Final image identity and write/readback evidence are recorded separately
when their gates pass.

The explicit native slice does not implement Node/online playback, subtitle/track
selection UI, or public cartridge Media Session activation. Those wider pre-0.4
contracts remain open. Physical display, speaker/earbud sound, synchronization,
Power response and TF2 behavior still require Deck evidence.

Route-policy references used during integration:
- https://raw.githubusercontent.com/mpv-player/mpv/v0.40.0/audio/out/ao_pipewire.c
- https://docs.pipewire.org/page_man_pipewire-props_7.html
- https://docs.pipewire.org/1.2/page_man_pipewire-client_conf_5.html
