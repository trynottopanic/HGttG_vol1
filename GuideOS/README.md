# GuideOS

GuideOS is the Linux environment for a person-owned Deck. The present board
target is the Anbernic RG35XX H, using minimal Debian ARM64 with systemd below
Guide Supervisor. Hardware support stays in the board layer; application and
service contracts are intended to remain portable.

The [project handbook](../docs/HANDBOOK.md#current-status) holds the current
status and release limitations. [VERSION](VERSION) records this source snapshot's
version. The repository contains component source and reference recipes; it
does not supply a complete installable Deck image.

## Explore the source

| Directory | Purpose |
| --- | --- |
| [board/rg35xxh/](board/rg35xxh/) | Board patches, configuration and Debian shell/platform adapters |
| [package/](package/) | Connectivity, media, storage, lifecycle, IPC and system providers |
| [apps/](apps/) | Application source, including Notepad, media and boot animation |
| [node/desktop/](node/desktop/) | Windows Node/NDI interface and media preparation |
| [android/](android/) | Companion prototype source |
| [semiotic_engine/](semiotic_engine/) | Optional local interpretation service |
| [schema/](schema/) | Semantic presentation and interaction definitions |
| [tools/](tools/) | Cartridge tooling and reference build recipes |
| [design/](design/) | UI/boot concepts and generic reference assets |

## Main reading paths

- [Documentation index](../docs/README.md) and [complete catalogue](../docs/CATALOG.md)
- [Modern foundation](MODERN_FOUNDATION_0.md) and [design alignment](docs/DESIGN_ALIGNMENT_0.md)
- [Windows NDI setup](node/desktop/README.md)
- [Reference Debian recipes](tools/build/README.md)
- [Development guide](../docs/DEVELOPMENT.md)

## Public source scope

The public shell works without the private world application or its artwork.
Home uses a generic placeholder and handles the absent application. Local
images, credentials, owner data, packaged outputs and deployment receipts are
excluded; see the [publication boundary](../PUBLICATION.md).

Retained Buildroot material and [README_HISTORY.md](README_HISTORY.md) describe
earlier work. The [history guide](../docs/HISTORY.md) explains how to read dated
implementation, diagnostic and UI records.
