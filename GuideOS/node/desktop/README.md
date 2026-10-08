# Windows Node interface

NDI connects a Windows computer with a paired GuideOS Deck. Its main window
provides Deck connection, selected media libraries, diagnostics and signed update
delivery. The current frontend is `guide_ndi.py`; the
[implementation record](../../docs/NDI_GUIDEOS_1.md) describes its behavior and
the documented 1.0.4 build.

## Run from source

Use Python 3 with Tkinter on Windows. From this directory:

```powershell
python guide_ndi.py
```

FFmpeg supplies automatic video preparation. HandBrakeCLI is an optional manual
preparation path. Neither program nor any owner configuration is bundled in this
source checkout. Check the component's profile and selected paths before
preparing media.

## Build NDI

Install PyInstaller in your development Python environment, then run:

```powershell
.\BUILD_NDI.ps1
```

The script reads the source version, packages the preparation preset and writes
the versioned executable under `GuideOS-NDI` beside the repository. It also
updates `GuideOS-NDI.exe` when that default program is not running. Build output
and receipts belong outside committed source.

`BUILD_WINDOWS.cmd` builds the earlier `guide_node_native_gui.py` interface as
`GuideNode.exe`. It is retained for that frontend and does not build current NDI.

## Connect a Deck

1. Start NDI and open Nodes on the Deck.
2. Select the computer and enter its displayed pairing code.
3. Choose whether to remember the computer on the Deck.
4. Select media folders in NDI to share their read-only catalogue.

Removing a media folder unshares it without deleting its contents. Preparation
writes a separate cache and preserves the original files. The provider converts
video to the Deck profile and retains supported alternate audio and text subtitle
tracks. Native Deck NDI stream-source integration remains incomplete; a prepared
file or successful Node connection does not establish native streaming playback.

## Services and permission

Diagnostics and signed update delivery also require WSL with the Ubuntu
distribution, an existing private developer transport profile and the installed
Deck developer link. A public source clone alone does not configure that
connection. Pairing and media services use the Node runtime directly.

- **AT Field** controls approachability through Closed, Familiar and Open modes;
  it does not replace media or application permissions.
- Diagnostics collect a bounded current-boot archive through the installed
  pinned developer connection.
- Signed update delivery stages a release; the Deck retains its installation
  and restart decision.
- Optional application sessions require approval for a named executable.
- The optional Semiotic Engine remains an independent, owner-enabled service.

See [AT Field](../../AT_FIELD_0.md),
[application streaming](../../APPLICATION_STREAMING_0.md) and the
[Semiotic Engine source](../../semiotic_engine/README.md) for their contracts.

Pairing, opaque media identifiers, selected-root checks and bounded requests
scope access to the services actually offered. The link uses local HTTP and is
intended for controlled private-network tests; authenticated transport remains
part of the wider protocol work.

## Source and checks

The HTTP/discovery service, media provider and connection state live beside the
frontend. Use the relevant component tests rather than rebuilding every program
to check a documentation change. The earlier frontend's full build command runs
its historical test set; some fixtures retain expectations from earlier pairing
directions.

Native interface changes follow the
[Windows UI performance standard](../../docs/WINDOWS_UI_PERFORMANCE_STANDARD.md).
The repository [development guide](../../../docs/DEVELOPMENT.md) covers common
source and documentation checks.
