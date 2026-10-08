# Development guide

Start with the [handbook](HANDBOOK.md) and the contract for the component you
want to change. GuideOS is a personal experimental project; a focused check of
the affected behavior is usually more useful than running every historical test.

## Get the source

Clone the repository with Git or GitHub Desktop:

```sh
git clone https://github.com/trynottopanic/HGttG_vol1.git
cd HGttG_vol1
```

There is no single dependency installation or command that builds every
component. Python reference services generally use the standard library.
Host rendering checks also need Pillow and Linux platform modules. Native
providers document their C, systemd and display dependencies.

| Work area | Entry point |
| --- | --- |
| Windows Node interface | [NDI setup and builds](../GuideOS/node/desktop/README.md) |
| Initial Debian userspace and board recipes | [Reference build recipes](../GuideOS/tools/build/README.md) |
| Deck shell | [Shell source and historical Shell 0 notes](../GuideOS/board/rg35xxh/debian/shell0/README.md) |
| Native media providers | [Media source and initial development notes](../GuideOS/package/guide-media/README.md) |
| Optional interpretation service | [Semiotic Engine source](../GuideOS/semiotic_engine/README.md) |
| Desktop continuity experiments | [Prototype catalogue](../prototypes/README.md) |

## Documentation and source checks

From the repository root, these checks use Python's standard library:

```sh
python3 -B tools/repository/documentation.py --check
python3 -B tools/repository/publication.py --check
```

On Windows, use `python` if that is the installed interpreter name. The first
command checks UTF-8 documentation, entry-page links and the maintained text
edition/catalogue. The second checks the public source selection, file sizes and
common credential patterns. Neither builds an image or exercises hardware.

For Nearby/provider and public-shell changes on Linux:

```sh
python3 -B -m unittest discover -s GuideOS/package/guide-connectivity -p test_nearby.py
PYTHONPATH=GuideOS/board/rg35xxh/debian/shell0:GuideOS/package/guide-ui   python3 -B -m unittest test_public_source test_nearby_panel
```

Choose additional checks for the changed component. Record what was exercised
and any remaining limitation. Older fixtures can describe earlier interfaces;
investigate a mismatch before changing expectations.

## Design and source guidance

- Read the applicable feature contract and [design alignment](../GuideOS/docs/DESIGN_ALIGNMENT_0.md).
- Keep systemd as PID 1 and Guide Supervisor above it for the Debian implementation.
- Keep display ownership, global navigation, cancellation and power coordination in the system.
- Keep provider-owned device and storage operations behind their existing contracts.
- Treat discovery, permission and resource assignment separately.
- Preserve pause, checkpoint, exit and recovery behavior, including durable acknowledgements.
- Keep the hardware floor modest; use bounded work and caches with explicit cancellation.
- Preserve unrelated source changes, historical release identities and private owner data.

Intercommunication is part of the system's purpose. Earlier philosophical
material about a digital cyberspace does not impose universal anonymity,
absolute isolation or a new approval step on ordinary GuideOS implementation.
Apply the owner's explicit permissions and current component contracts.

Source checks, assembled images, card writes and physical behavior are different
evidence. A host rendering fixture cannot establish real display ownership or
shutdown behavior, and a card readback cannot establish boot or responsiveness.

## Maintain the documentation

Use Markdown (`.md`) for formatted prose or plain text (`.txt`) where formatting
adds little. Save both as UTF-8. Keep important explanations in text; use images
as supporting references with captions and provenance. Link to existing
contracts rather than keeping slightly different copies of their requirements.

The [handbook](HANDBOOK.md) is the shared project introduction and status entry.
Component READMEs hold setup/source guidance. The [catalogue](CATALOG.md) lists
the complete text documentation; the [history guide](HISTORY.md) distinguishes
dated evidence and older directions.

After editing a documentation file, refresh the catalogue and plain-text edition:

```sh
python3 -B tools/repository/documentation.py --write
```

Keep source requirements and dated evidence intact when consolidating documents.
Existing filenames can remain as short links to a combined document.

## Publication boundary

Keep build output in ignored directories. Do not add credentials, private
signing keys, saved owner databases, real device captures, disk images or
compiled cartridges. Public keys and clearly synthetic fixtures can be source.
Planegotchi-specific files and local automation instructions remain outside the
public tree. The public shell must work with the private application absent.

See [PUBLICATION.md](../PUBLICATION.md) for the source boundary and export history.
Preserve existing software, documentation and third-party license notices.
