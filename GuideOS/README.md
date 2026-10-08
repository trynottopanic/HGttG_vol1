# GuideOS

GuideOS is the provisional Linux environment for a person-owned Deck. The current
board target is the Anbernic RG35XX H; the selected foundation is minimal Debian
ARM64, with systemd below Guide Supervisor. The retained Buildroot material is
historical board/workshop source.

The latest locally installed revision is **0.4.4.03**, signed sequence 75. Its
system partition was written and fully read back on 6 October 2026. That confirms
the card write, not a subsequent boot or complete physical feature acceptance.
The working source contains ongoing development beyond that installed revision.

The public repository contains GuideOS and NDI source. It excludes Planegotchi's
implementation, dedicated documentation, tests and artwork, as well as owner
state, credentials, local images and build receipts. Home uses a generic world
placeholder and a visible unavailable response when that optional app is absent.
No private application is needed to import or navigate the public shell.

## Start here

- [Documentation index](docs/README.md)
- [Modern foundation](MODERN_FOUNDATION_0.md) and [design alignment](docs/DESIGN_ALIGNMENT_0.md)
- [Public-source checks and contribution notes](../CONTRIBUTING.md)
- [Publication boundary](../PUBLICATION.md)
- [Reference Debian build scripts](tools/build/README.md)

## Source map

| Directory | Purpose |
| --- | --- |
| `board/rg35xxh/` | Board patches, configuration and Debian shell/platform adapters |
| `package/` | Connectivity, media, storage, lifecycle, IPC and system providers |
| `apps/` | Application sources, including Notepad, media and boot animation |
| `node/desktop/` | Windows Node/NDI source and media preparation |
| `android/` | Companion prototype source |
| `semiotic_engine/` | Optional local interpretation service prototype |
| `schema/` | Semantic presentation and interaction definitions |
| `tools/` | Cartridge tooling and reference build recipes |
| `design/` | Generic GuideOS UI/boot design sources and original assets |
| `docs/` | Feature contracts, evidence summaries, proposals and dated history |

## Current feature work

The source includes the native media player and Select-driven subtitle/audio
track options; Settings / Nearby provides Wi-Fi survey, Bluetooth explorer,
bounded signal watch, Nmap, ping, DNS and route tools. NDI remains 1.0.4. Each
feature document states its implementation and physical evidence boundary.
The web browser integration is owner-paused; retained browser source does not
mean it is enabled in the installed system.

This checkout does not supply the private base image or a fully pinned recipe
for reproducing the installed 0.4.4.03 image. Component builds and the initial
Debian reference recipes are inspectable, but producing a public installable
release is separate work.

## History and licensing

[README_HISTORY.md](README_HISTORY.md) preserves the preceding overview and its
original claims. Dates and component-local evidence in older documents are
historical, not current installation status. Links to ignored build receipts or
private application material are retained provenance references.

Original software follows AGPL-3.0-or-later; original documentation and visual
material follow CC-BY-SA-4.0. Imported material retains its own license notices.
See the repository [license policy](../LICENSE.md).
