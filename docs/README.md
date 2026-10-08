# Documentation

Start with the [project handbook](HANDBOOK.md), available as [plain text](HANDBOOK.txt).
Use the sections below for the main reading paths, or the
[complete catalogue](CATALOG.md) to find every retained text document.

## Project and development

- [Project handbook and current status](HANDBOOK.md)
- [Development and documentation maintenance](DEVELOPMENT.md)
- [Full project definition and philosophy](../HHG_Foundation/README.md)
- [GuideOS source map](../GuideOS/README.md)
- [Desktop prototype catalogue](../prototypes/README.md)
- [Publication boundary](../PUBLICATION.md) and [license policy](../LICENSE.md)

## Architecture and contracts

| Topic | Main references |
| --- | --- |
| Foundation | [Modern foundation](../GuideOS/MODERN_FOUNDATION_0.md) · [Design alignment](../GuideOS/docs/DESIGN_ALIGNMENT_0.md) |
| Applications and jobs | [Application framework](../GuideOS/FUTURE_FRAMEWORK_0.md) · [Application host](../GuideOS/docs/APPLICATION_HOST_0.md) |
| Capabilities and supervision | [Capability registry](../GuideOS/LIVE_CAPABILITY_REGISTRY_0.md) · [Supervisor foundation](../GuideOS/SUPERVISOR_CAPABILITY_FOUNDATION_0_PROPOSAL.md) |
| Presentation and controls | [Guide View](../GuideOS/GUIDE_VIEW_1_DRAFT.md) · [Menu/pointer](../GuideOS/MENU_POINTER_0.md) · [Text entry](../GuideOS/TEXT_ENTRY_0.md) |
| Local messages | [IPC envelope](../GuideOS/IPC_ENVELOPE_0.md) |
| Resources and lifecycle | [Contention](../GuideOS/RESOURCE_CONTENTION_0.md) · [Multicore guideline](../GuideOS/MULTICORE_OPERATION_GUIDELINE_0.md) |
| Packages and updates | [Cartridge format](../GuideOS/CARTRIDGE_FORMAT_1.md) · [System updates](../GuideOS/SYSTEM_UPDATE_FRAMEWORK_0.md) |
| Connection policy | [AT Field](../GuideOS/AT_FIELD_0.md) |
| Optional interpretation | [Semiotic protocol](../GuideOS/SEMIOTIC_ENGINE_PROTOCOL_0.md) · [Reference service](../GuideOS/semiotic_engine/README.md) |

Document titles containing “Draft” or “Proposal” retain their own status.
The alignment record explains accepted directions whose historical filenames
still contain those words.

## Components and features

| Component | Reading path |
| --- | --- |
| Native media | [Services](../GuideOS/MEDIA_SERVICES_1.md) · [Library](../GuideOS/docs/MEDIA_LIBRARY_1_IMPLEMENTATION.md) · [Session](../GuideOS/docs/MEDIA_SESSION_1_IMPLEMENTATION.md) |
| Video tracks | [Subtitle and audio options](../GuideOS/docs/VIDEO_OPTIONS_TRACKS_0.md) |
| Files and transfers | [Functional contract](../GuideOS/docs/FILE_BROWSER_CONTRACT_0.md) · [Combined UI direction](../GuideOS/docs/FILE_BROWSER_UI_0.md) · [Transfer provider](../GuideOS/TRANSFER_PROVIDER_0.md) |
| Storage | [External storage](../GuideOS/EXTERNAL_STORAGE_0.md) · [Card recognition](../GuideOS/docs/EXTERNAL_CARD_RECOGNITION_0.md) |
| Notepad | [UI implementation](../GuideOS/docs/NOTEPAD_UI_IMPLEMENTATION_2026_10_03.md) · [Storage broker](../GuideOS/docs/NOTEPAD_STORAGE_BROKER_DESIGN_0.md) |
| Nearby | [Wi-Fi, Bluetooth and network tools](../GuideOS/docs/NEARBY_AND_NETWORK_TOOLS_0.md) |
| Wi-Fi connections | [Connection controls](../GuideOS/WIFI_CONNECTIONS_2.md) · [Cold-boot investigation](../GuideOS/docs/WIFI_COLD_BOOT_FAILURE_2026-10-06.md) |
| Windows NDI | [Current implementation](../GuideOS/docs/NDI_GUIDEOS_1.md) · [Setup/source](../GuideOS/node/desktop/README.md) |
| Local search | [Quick Find](../GuideOS/docs/QUICK_FIND_0.md) |
| Renderer | [GPU compositor](../GuideOS/docs/GPU_UI_COMPOSITOR.md) |
| Installation | [Cartridge installer](../GuideOS/docs/CARTRIDGE_INSTALLER_0.md) |

## Build and reference material

- [Initial Debian reference recipes](../GuideOS/tools/build/README.md)
- [Debian bring-up history](../GuideOS/DEBIAN_BRINGUP_0.md)
- [Earlier Buildroot workshop](../GuideOS/BUILDING.md)
- [Hardware board notes](../GuideOS/board/rg35xxh/README.md)
- [UI draft text catalogue](../GuideOS/design/ui-theme-drafts/README.md)
- [Terrain reference text catalogue](../GuideOS/design/atlas/README.md)

## Historical evidence

The [history guide](HISTORY.md) groups release notes, diagnostics and earlier
design work. Dates and component-local status govern those records. Some older
notes refer to private build receipts that are not distributed here.

Every prose document is UTF-8 Markdown or plain text. Diagrams, screenshots and
reference artwork accompany those documents rather than replacing their text.
