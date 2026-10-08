# Project handbook

The Third Way is a personal computing project centered on the person using the
system. GuideOS provides the operating environment; HHGttG describes the wider
architecture and protocols. This handbook brings together the project overview,
current component status, terminology and prototype goals.

For specifications, use the [documentation index](README.md). For local setup
and contribution checks, use the [development guide](DEVELOPMENT.md). A
[plain-text edition](HANDBOOK.txt) contains the same handbook content.

## Devices and services

| Term | Meaning |
| --- | --- |
| Deck | A person's portable computer, responsible for its information, permissions and interface. |
| Node | A separate computer or service that offers specific capabilities to a Deck. |
| Interfacing Device | Hardware that adds input, output, storage, sensors or other capabilities. |
| Semiotic Engine | An optional service for interpretation and retrieval, with replaceable deterministic or model-based backends. |
| Guide Recipe and Guide Package | The proposed creation and exchange layers for readable instructions and inspectable packaged applications. |

Discovery, connection and permission are separate operations. Finding a nearby
device does not give either device access to the other. Optional computation
services remain subject to the same owner-controlled permissions as other tools.

The original [project definition](../HHG_Foundation/02_GUIDE_AND_PROTOTYPE_DEFINITION.txt)
and [design philosophy](../HHG_Foundation/03_DESIGN_PHILOSOPHY.txt) remain the
full foundations. Their plain-text format is readable without special software.

## Current status

The current Deck target is the Anbernic RG35XX H. The selected foundation is
minimal Debian ARM64, with systemd as PID 1 and Guide Supervisor above it.
Retained Buildroot recipes describe earlier work; they do not define the
current Debian system.

The latest documented local installation is **GuideOS 0.4.4.03**, with a verified
system-partition write and readback on 6 October 2026. The corresponding NDI
build record is **1.0.4**. These are local development records, not downloadable
GitHub releases. A verified write does not establish boot, radio, display or
complete feature acceptance. See the [release record](../GuideOS/docs/BUILD_0_4_4_03.md)
and [NDI implementation](../GuideOS/docs/NDI_GUIDEOS_1.md).

| Component | Available work and limitations |
| --- | --- |
| Deck interface | Controller and pointer navigation, shared text entry, settings, status and GPU composition source. |
| Media | Local native audio/video playback and Select-driven subtitle/audio options. Physical track-menu acceptance remains a Deck check. |
| Files and Notepad | Storage-provider browsing and Notepad text editing/internal-draft saves. External-document open/export remains pending. |
| Nearby | Wi-Fi survey, Bluetooth explorer, bounded signal watch and explicit network-tool jobs. Physical radio acceptance remains separate. |
| Windows Node interface | Pairing, selected media libraries, media preparation, diagnostics and signed update delivery. |
| Native Node video playback | The media provider exists; the native Deck NDI stream-source integration remains incomplete. |
| Semiotic Engine | Independent protocol/reference service and optional local model adapter. It is not required for core use. |
| Web browser | Active integration is paused; its source is retained for future work. |

This repository supplies source and documentation. It does not contain the
private base image or a fully pinned recipe for recreating the working Deck
image from scratch. Component builds and the initial Debian reference recipes
are available for inspection.

## Prototype scenarios

These scenarios describe intended acceptance behavior and retained desktop
experiments. They are not a claim of complete native Deck integration.

### Continue on Deck

Pause an authorized local video on a desktop Node, connect the Deck by USB,
transfer the file with its playback position, then disconnect and resume locally
near the same moment. The Deck verifies the transfer before publishing it.

- [Acceptance contract](../GuideOS/CONTINUE-ON-DECK-0.md)
- [Reference sender and receiver](../prototypes/continue_on_deck_0/README.md)

### Visiting Screen

With the network owner's consent, select a movie on the Deck and use a temporary
host to discover and control a compatible television. Media goes directly from
the Deck; access can be revoked afterward. The owner of the visited network
controls the destination and permission.

- [Windows reference experiment](../prototypes/visiting_screen_1/README.md)

### Message Chime

After a phone receives a message from an explicitly selected person, send one
local event and play a selected sound on the Deck. The event does not need to
include the message contents or depend on matching mobile providers.

- [Acceptance contract](../GuideOS/MESSAGE-CHIME-0.md)
- [Reference event-routing experiment](../prototypes/message_chime_0/README.md)

## Architecture reading order

1. [Modern foundation](../GuideOS/MODERN_FOUNDATION_0.md): portable system and board responsibilities.
2. [Application framework](../GuideOS/FUTURE_FRAMEWORK_0.md): application, service and job boundaries.
3. [Capability registry](../GuideOS/LIVE_CAPABILITY_REGISTRY_0.md): discovery, authorization and ownership.
4. [Guide View](../GuideOS/GUIDE_VIEW_1_DRAFT.md): semantic presentation and input.
5. [Design alignment](../GuideOS/docs/DESIGN_ALIGNMENT_0.md): reconciliation and unresolved integration.

## Source and documentation scope

Private owner state, credentials, disk images, deployment receipts and packaged
outputs stay outside the public repository. Planegotchi's implementation,
dedicated documents, tests and artwork also remain local. The public shell uses
a generic placeholder and handles the absent application.

Documentation uses UTF-8 Markdown and plain text. Reference artwork has text
catalogues or accompanying descriptions. Historical notes retain their dates
and evidence; see the [history guide](HISTORY.md) before treating an older
document's use of “current” as a statement about today's system.

## Licensing

Original software and functional build material use AGPL-3.0-or-later.
Original documentation and visual material use CC-BY-SA-4.0. File-specific and
third-party notices govern their own material. The [license policy](../LICENSE.md)
includes the canonical license texts. Project names do not imply endorsement
by Douglas Adams, his estate or associated rights holders.
