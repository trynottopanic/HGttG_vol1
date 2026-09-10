# GuideOS

GuideOS is the provisional name of the HHG-owned Linux distribution for Decks.
This directory is the beginning of its reproducible source tree.

Current status: **Stage 2 physical prototype bring-up.** The Deck now boots to
the GuideOS shell, accepts controls, shuts down safely, and recognizes a
read-only metadata payload in the external microSD slot.

`FUTURE_FRAMEWORK_0.md` records the forward architecture for structured Guide
Views, a richer Wikipedia reader, communications companions, remote application
streaming, Android providers, and the creator-facing Recipe path. It is a design
direction rather than a frozen protocol.

## Human-accessibility requirement

GuideOS treats making software as an ordinary use of the Deck. A person who is
comfortable using a computer, but has no computer-science training, must be
able to make, test, understand, and share a small Guide program with minimal
new vocabulary.

The friendly layer will be the Guide Recipe system: small programs expressed
as readable connections between events, conditions, information, devices, and
actions. Recipes must not require knowledge of Linux administration, process
management, networking internals, package managers, or traditional build
systems for common tasks.

This does not remove the exact technical layer. Every friendly concept must map
to inspectable files, capabilities, protocols, logs, and source code. GuideOS
documentation will explain the ordinary-language idea first, define necessary
technical terms at first use, show a working example, and then provide the full
technical reference.

Finished Recipes and more advanced programs will be exchangeable as provisional
`.guide` packages. These are inspectable ZIP containers using existing open
formats for metadata, portable behavior, and assets. A receiving Deck grants
its own permissions; authority and private information never travel merely
because the package does.

The first host-side Cartridge Workshop is available under `tools/cartridge`.
It builds, verifies, and safely copies Guide Cartridge Format 1 packages using
Windows PowerShell without administrator access. The current Deck prototype
does not import or run Format 1 packages yet.

Development of a native, reading-first Wikipedia application has begun under
`apps/wikipedia`. Its bounded MediaWiki client performs deliberate HTTPS
search/article requests and returns plain text rather than rendering remote
HTML or JavaScript. Controller interaction, article paging, visible failures,
and an atomic offline store are covered by host tests. The framebuffer view
still depends on the Wi-Fi platform feature and a shell application handoff.

The complementary Node-side Wikipedia library lives under `node/wikipedia`.
It can plan, resume, and verify Wikimedia's current English article dump,
stream its XML one page at a time, and produce conservative readable text
without asking a Deck to store or process the whole archive.

The first lightweight Windows Node shell lives under `node/desktop`. It builds
as one owner-facing program, supports local discovery and expiring pairing, and
reports narrowly named capabilities without exposing a remote command shell.
`DESKTOP_NODE_0.md` defines the encounter and protocol boundary.

The current prototype can share one owner-selected media folder. A paired Deck
receives a bounded catalogue with no Windows paths and requests a short-lived
ticket for one selected audio or video file; changed files are withheld until
the owner rescans. The Deck decodes the stream locally and retains stop and
pause controls while playback is active.

The Windows Node prepares demanding video in a private cache without modifying
the owner's original. A single bounded worker uses FFmpeg when available or
the locally installed VLC engine to produce a 640×360, 8-bit H.264, stereo AAC
MP4 derivative. Audio remains direct; video appears in the Deck catalogue only
after its compatible copy is complete. Stopping folder sharing cancels an
active preparation, and a source-file change invalidates the old derivative.

`LOCAL_MEDIA_PLAYER_0.md` extends the same bounded player to media stored on the
Deck or a read-only external cartridge. The unified Media browser preserves
folders, works without Wi-Fi, recognizes matching sidecar subtitles, rechecks
each local file before opening it, and privately remembers unfinished playback.

An authorized Developer Link session can run `guide-diagnostics` for a bounded,
redacted hardware and service snapshot. Human-readable and JSON forms correlate
the last player stage with display, input, storage, radio, audio, decoder,
resource, process, and recent-log evidence without exposing credentials or
private media paths.

Trusted-companion pairing is reciprocal and revocable. The Node owner arms one
trust request in the Windows interface, then the paired Deck owner accepts it
with `X`; both devices retain a random reconnect credential and stable local
identity. Trust restores the same scoped session after an ordinary restart—it
does not grant shell access or new capabilities. This first implementation
still uses clearly labelled, unencrypted development HTTP and is therefore
restricted to a trusted private LAN; persistent trust is not release-grade
until an authenticated encrypted transport replaces it.
The bounded Deck-side protocol client has begun under `apps/node_link`; it is
ready for a controller-facing screen but is not yet installed in the image.

Android applications are being treated as an optional provider rather than a
requirement imposed on every Deck. `ANDROID_APPLICATION_PROVIDER_0.md` defines
Guide-native adaptation, future on-Deck execution, and the first practical
Node-hosted emulation route. The current Node can report installed Android
tools but cannot start or control them.

The first phone-side project lives under `android/guide-companion`.
`ANDROID_COMPANION_0.md` defines its first narrow capability: with explicit
notification access, it converts new Discord notification cards into bounded
Guide events. Build 0.1 keeps delivery closed until authenticated, revocable
Deck pairing is connected, so nothing captured can leave the phone yet.

The first hardware target is the Anbernic RG35XX H. The first functional
milestone is `CONTINUE-ON-DECK-0`: pause an authorized local video on a desktop
Node, connect the Deck by USB, transfer the video and its playback position,
disconnect, and resume locally on the Deck. `VISITING-SCREEN-1` follows after
that: the Deck joins an owner-approved local network and offers its video to a
compatible television through a temporary Node.

## Distribution boundary

GuideOS owns and defines:

- the root filesystem and service set;
- the Guide runtime, capability broker, interface, and protocol adapters;
- account, logging, update, recovery, and storage policy;
- reproducible image construction and dependency records.

The first RG35XX H image may temporarily reuse audited board-enablement work for
the bootloader, kernel patches, device tree, GPU, display, controls, audio,
power management, and wireless firmware. Every imported component must retain
its license and provenance. Hardware support is a replaceable layer, not the
definition of GuideOS.

## Build system

GuideOS uses a Buildroot `br2-external` tree. The three required integration
files are present:

- `external.desc`
- `Config.in`
- `external.mk`

The root filesystem overlay begins under `board/common/rootfs-overlay`.
The initial board layer provides separate LPDDR3 and LPDDR4 definitions, both
known panel descriptions, a Windows-readable boot partition, and a minimal
diagnostic userspace.

The approved build baseline is Buildroot 2025.02.17 from the 2025.02.x
long-term-support series. Linux 6.18.y remains the intended stabilization line,
but `BRINGUP-0` temporarily pins Linux 7.1.2 because that is the exact release
targeted by the currently tested H700 display and wireless patch set. Release
builds will never follow a moving branch implicitly.

Buildroot requires a Linux build host. The current workshop is Ubuntu in WSL2,
with generated files isolated under `/home/hacker/guideos-work`. GuideOS does
not depend on one Ubuntu release; the exact tools used for a release belong in
its build record.

## Image policy

The first image will use:

- a small read-only system filesystem where hardware support permits;
- a distinct writable data partition;
- no default remote password;
- development SSH enabled only with an explicitly installed public key;
- no cloud account or mandatory internet service;
- local Wi-Fi and receiver discovery;
- a temporary, read-only, single-file media share;
- visible failure states rather than automatic compatibility claims.

Disk 4 is the designated seed microSD card, currently observed through a
Transcend TS-RDF5 reader at 57.96 GiB. It must not be written until an image has
been built, inspected, hashed, and the physical target has been confirmed again.
The current recovery-image boundary and required safe-capture procedure are
recorded in `docs/ANBERNIC_FAILSAFE_STATUS.md`.

## Stages

1. Import and audit an RG35XX H hardware-support baseline.
2. Reproduce a minimal boot to display with working controls and clean shutdown.
3. Enable both microSD slots and persistent data separation.
4. Enable a bounded USB data link and atomic media import.
5. Add local playback and resume-state handling.
6. Run `CONTINUE-ON-DECK-0` and record transfer and resume accuracy.
7. Enable Wi-Fi with an explicit local configuration flow.
8. Add development SSH using public-key authentication.
9. Add the Guide supervisor and semantic input events.
10. Add receiver discovery and the bounded media-share service.
11. Run `VISITING-SCREEN-1` and record compatible and failed routes.

## Non-goals for the first image

- A new kernel written by the project.
- A local general-purpose Semiotic Engine.
- Live video transcoding on the handheld.
- Emulation-console features unrelated to the first Guide test.
- Dependence on one television vendor or casting platform.
