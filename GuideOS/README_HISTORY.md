# GuideOS

Current development version: **0.3.9**. Start continuation work with the
[0.3.9 handoff](docs/RELEASE_0_3_9_HANDOFF.md). The physical Seed remains 0.3.7,
with successful Notepad installation and first-note feedback recorded. Earlier
deployment and pending-work descriptions below are historical.

GuideOS is the provisional name of the HHG-owned Linux distribution for Decks.
This directory is the beginning of its reproducible source tree.

Current seed status (24 September 2026): the combined
[Wi-Fi and input revision](docs/WIFI3_INSTALLATION_2026-09-24.md),
`wifi3-20260924`, is installed with complete root readback verified and boot/data
unchanged. All 258 ARM64 tests and two virtual boots passed. The owner subsequently
reported that the tested seed works as intended; see the
[physical result](docs/WIFI3_PHYSICAL_RESULT_2026-09-24.md).
Component design notes retain their original local-development status; the
linked installation record establishes the current deployment state.

The proposed [network deployment framework](NETWORK_DEPLOYMENT_0.md) describes
small owner-authorized updates and diagnostic return with a 100 MB job ceiling,
local recovery and a one-time bootstrap. It is theoretical; remote deployment
has not been enabled on the seed.

The proposed [system update framework](SYSTEM_UPDATE_FRAMEWORK_0.md) places
paired Wi-Fi delivery and read-only cartridge import in front of one signed,
staged and reversible local update controller. Its first implementation boundary
is immutable Guide releases; Debian-package and boot-critical updates remain
deferred until their independent recovery models are proven.
The [Guide Signed Bundle 1 draft](SIGNED_BUNDLE_1_DRAFT.md) proposes the common
manifest, detached signature, trust scope and validation contract. Guide
releases and Runtime Packs use independently versioned profiles. The earlier
[combined package draft](SYSTEM_UPDATE_PACKAGE_1_DRAFT.md) is superseded design
history.
The adopted [Runtime Pack 0](RUNTIME_PACK_0.md) direction provides immutable,
versioned shared dependencies without replacing Debian system libraries; its
package schema and runtime broker remain to be implemented.

The next local input revision changes keyboard clicks to L3 case/R3 primary
selection and right-stick neighbors to highlight-while-held/select-on-release.
Menus use a 40%-opacity white dot and 30%-opacity context surfaces. Motion has
resting hysteresis, velocity smoothing, a 30 Hz drawing cap and one reusable menu
frame. It is tested locally; the seed still contains the preceding controls.

The preceding [Wi-Fi connections 2](WIFI_CONNECTIONS_2.md) physical test confirmed
discovery and signal display but failed connection: Guide cancelled all four
attempts after a roughly 302 ms D-Bus error. This revision includes the correction.
See the
[failure analysis](docs/WIFI2_CONNECTION_FAILURE_2026-09-24.md) and
[installation evidence](docs/WIFI2_INSTALLATION_2026-09-24.md).

The reusable [text-entry component](TEXT_ENTRY_0.md) retains the earlier
prototype's paper-and-ink keyboard appearance. The
[current ARM64 checks](build/keyboard-0/arm64-validation.json) record the tested
source snapshot and suite results.
The installed Wi-Fi correction passes 47 ARM64 connectivity tests and an actual
private D-Bus delayed-reply probe. The combined image's
[validation record](build/debian-wifi-3/validation.json) verifies installed source.

Experimental stick controls now extend text entry with left-stick navigation
and right-stick neighbor activation. The separate [menu pointer](MENU_POINTER_0.md)
uses a left-stick mouse cursor and a circular context menu with D-pad selection
or right-stick hold/release confirmation. Physical acceptance remains pending.

The installed input revision reduces the context radius to 84 pixels with
50% surface opacity, derives relevant actions dynamically, and supports expanded
menus with overflow pages. L1/R1 switch the keyboard between letters and
numbers/punctuation. An optional [Unicode rendering profile](UNICODE_RENDERING_0.md)
adds broad fonts, shaping and color emoji for the keyboard and Wi-Fi labels.
These changes await physical acceptance; international input methods are future work.

The preceding [Wi-Fi discovery 1](WIFI_DISCOVERY_1.md) physical run confirmed
discovery of nine networks, scrolling, rescan cancellation and orderly shutdown;
see the [physical result](docs/WIFI1_PHYSICAL_RESULT_2026-09-24.md). The
[system audit](docs/SYSTEM_AUDIT_2026-09-24.md) records the preceding investigation.

**GuideOS 0.3 “Liquid Snake”** was the minimal Debian RG35XX H
button baseline. Its physical run failed: see the
[failure audit](docs/LIQUID_SNAKE_FAILURE_AUDIT.md). The
[release notes](DEBIAN_DIAGNOSTIC_4.md) describe the tested image, not an accepted
working interface.

The preceding [Debian Guide Shell integration slice 0](DEBIAN_SHELL_0.md)
has seven saved runs recording navigation and shell-requested
shutdown; this does not establish every visual or power acceptance criterion.
It removes the diagnostic from the boot path, gives one
service ownership of tty1/display/ordinary controls, and retains the Power key
as a system-owned shutdown path. Do not describe it as working hardware until
the documented physical acceptance run succeeds.

The [design alignment record](docs/DESIGN_ALIGNMENT_0.md) connects existing
requirements, current evidence and the shared contracts still needed for the
rework. Minimal Debian is the selected foundation; older prototype feature
descriptions below do not establish that those features are in the Debian image.

The accepted Debian architecture retains systemd as PID 1, with Guide Supervisor
coordinating applications and Guide policy above it. See the
[supervision boundary](MODERN_FOUNDATION_0.md#accepted-supervision-boundary).

The earlier Stage 2 prototype booted to the GuideOS shell, accepted controls,
shut down safely, and recognized a read-only metadata payload in the external
microSD slot.

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

## Earlier prototype components and development history

This section records existing source and earlier implementation work. Revalidate
each component when integrating it into the new foundation.

The first host-side Cartridge Workshop is available under `tools/cartridge`.
It builds, verifies, and safely copies Guide Cartridge Format 1 packages using
Windows PowerShell without administrator access. The current Deck prototype
does not import or run Format 1 packages yet.

Development of a reading-first Wikipedia application has begun under
`apps/wikipedia`. Its bounded MediaWiki client performs deliberate HTTPS
search/article requests. The proven controller reader retains its plain-text
fallback; the next view reduces article HTML to a passive allow-list and uses
NetSurf as a lightweight framebuffer renderer. NetSurf only visits the local
Guide gateway, while GuideOS controls requests, links, images, and safety
limits. A clean shell/input handoff still needs device testing.

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

`MEDIA_SERVICES_1.md` adopts the pre-0.4.0 service boundary for native audio and
video from External Storage 0 and authorized Nodes, plus a provider-neutral
resolved-stream path for later online services. `MEDIA_PLAYERS_1_PROPOSAL.md`
retains the engine and interface study; physical evidence still determines the
first supported video backend and codec envelope.

`MEDIA_IPC_1.md` defines the first executable Envelope 0 message contract for
the media library and acknowledged media sessions. Generated C/Python metadata
and host preparation tests validate the registry shape. The first library and
session broker cores now have separate host evidence; players remain unimplemented.

The first [Media Library 1 implementation](docs/MEDIA_LIBRARY_1_IMPLEMENTATION.md)
adds a host-tested, read-only External Storage catalog, lifecycle adapter and
Envelope 0 broker core. It returns bounded opaque records and contained read
descriptors without exposing card paths. Production socket wiring and physical
playback remain open.

The [Media Session 1 implementation](docs/MEDIA_SESSION_1_IMPLEMENTATION.md)
adds a decoder-independent, owner-bound, revision-checked session state machine
and grant-enforced broker core. Real decoder/output adapters, installed services
and physical playback remain open.

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

New foundation work follows [Modern foundation 0](MODERN_FOUNDATION_0.md) and
the [Debian bring-up record](DEBIAN_BRINGUP_0.md). Exact diagnostic inputs and
results belong to their individual build records.

### Retained Buildroot implementation

The earlier implementation uses a Buildroot `br2-external` tree. Its integration
files are present:

- `external.desc`
- `Config.in`
- `external.mk`

The root filesystem overlay begins under `board/common/rootfs-overlay`.
The initial board layer provides separate LPDDR3 and LPDDR4 definitions, both
known panel descriptions, a Windows-readable boot partition, and a minimal
diagnostic userspace.

The earlier approved baseline was Buildroot 2025.02.17 from the 2025.02.x
long-term-support series. Linux 6.18.y was the intended stabilization line,
but `BRINGUP-0` temporarily pins Linux 7.1.2 because that is the exact release
targeted by the currently tested H700 display and wireless patch set. Release
builds will never follow a moving branch implicitly.

Buildroot requires a Linux build host. The current workshop is Ubuntu in WSL2,
with generated files isolated under `/home/hacker/guideos-work`. GuideOS does
not depend on one Ubuntu release; the exact tools used for a release belong in
its build record.

## Image policy

The intended system policy includes the following. The diagnostic development
image does not establish that the final storage and recovery design is complete:

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

## Earlier prototype stage sequence

This records the earlier Buildroot plan. For the rework, the modern-foundation
acceptance sequence and design alignment record govern dependencies: establish
shared supervision and capability contracts before integrating richer applications.

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
