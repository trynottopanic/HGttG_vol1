# Guide Desktop Node 0

This is the first small Windows Node shell. Double-clicking `GuideNode.exe`
opens one understandable control panel. A Deck on the same private Wi-Fi can
discover it, enter the code shown by the owner, and learn which carefully
limited services the Node offers.

The source control panels now include **AT Field**: Closed, Familiar or Open.
The preview explains the change; existing sessions stay connected. Familiar and
Closed hide the Node from broadcast discovery. Familiar permits trusted
reconnections and code-approved pairing; Closed declines new incoming connections
except named trusted-peer exceptions. Open preserves the previous discovery and
pairing behavior. The selection is remembered without changing media or application
permissions. See [AT Field](../../AT_FIELD_0.md) for behavior and implementation status.
The separate [AT Field build](../../build/node-at-field/dist/GuideNode-ATField.exe)
contains this change. It does not replace an existing installation. The native
launcher accepts `--config PATH` for a separate Node settings profile.

The owner can designate any number of Media folders. Recognized music and video
beneath them become a read-only catalogue for paired Decks, with seeking-capable
byte-range streaming. Each selected folder becomes a top-level shelf on the
Deck, and the directory structure beneath it is preserved for familiar browsing.
Absolute computer paths are never sent; each file receives an opaque identifier
valid only for the current Node run. Changed files are refused until the owner
rescans. Existing one-folder settings migrate automatically.

Videos are probed, converted, and validated in a background cache against a
conservative Deck profile; the owner's original is never modified. The normalizer
accepts common MP4, Matroska, WebM, AVI, QuickTime, MPEG, transport-stream, WMV,
3GP, Ogg Video, VOB, and FLV containers; selects real media streams rather than
cover art; repairs timestamps; scales varied resolutions and frame rates; and
converts video and audio to H.264/AAC. Compatible text subtitle tracks are kept
as selectable tracks. If damaged or unsupported subtitle data would invalidate
the entire movie, conversion retries without that data and reports the actual
file and encoder reason if both attempts fail. Video-only sources receive a
silent audio track because the current Deck playback path expects one.
On Windows, the Node tries AMD AMF, NVIDIA NVENC, and Intel Quick Sync against
normalized real input, then remembers the first working H.264 encoder. If none
works—or if a driver rejects the source—it falls back automatically to a bounded software
encode using half of the computer's logical processors at below-normal process
priority, keeping the control panel and other programs responsive.
The latest detailed local failure is retained as
`%LOCALAPPDATA%\GuideNode\media-cache\last-conversion-error.txt`; this diagnostic
path and its contents are never disclosed to a Deck.

The Node deliberately cannot run arbitrary commands, browse outside the chosen
Media folder, modify shared files, or control Android. Those functions
must be added later as named capabilities with their own permission checks.
It can safely detect whether Android's command-line tools and virtual devices
already exist, but detection never starts an emulator or enables remote access.

## Optional Semiotic Engine connector

The Semiotic Engine is a separate program. The Node does not contain its model
runtime and does not offer it merely because it is installed. The native Node
window provides a clear owner-controlled permission switch and remembers that
choice; the independent Engine must also be started separately. The Node reads
the local loopback connection record,
advertises `semiotic.text` only while the service answers compatibly, and keeps
the Engine credential hidden from Decks.

Paired Decks submit bounded text through `/guide/v1/semiotic/jobs`, inspect
their own jobs, and may request cancellation. Job identifiers are scoped to the
submitting Deck session; another Deck receives `not found`. The command-line
`--semiotic-engine` flag remains available as an explicit startup override for
testing, but ordinary use does not require it.

The owner may also register specific Windows applications for temporary
streaming sessions. A Deck sees only friendly names and every request must be
approved in the Node window before that exact executable launches. With FFmpeg
available, the Node can expose only the named application window as a
640×480 H.264/MPEG-TS stream. Remote input remains disabled until its bounded
adapter has been independently tested; an application session never becomes a
general desktop-control or command interface. See
`../../APPLICATION_STREAMING_0.md` for the full boundary.

## Paired Deck diagnostics

When the Deck is paired over Wi-Fi, **Run diagnostics** collects its retained
runtime event log and a full current-boot snapshot. The archive includes the
browser and compositor journal, browser launch arguments and display-device
handles, kernel/DRM state, Wi-Fi and network state, process and service status,
and audio/storage diagnostics. The Deck continuously retains bounded logs while
it runs, so capture can happen after a failed attempt. Archives are saved under
`E:\DGttG\private-recovery\live-link` on the development computer.

## Current safety boundary

- The Node accepts private/local network addresses only.
- Pairing codes expire after ten minutes and lock after repeated failures.
- Paired sessions live only in memory, expire after eight hours, and are all
  revoked when the Node stops.
- Requests are small and bounded; authorization secrets are not logged.
- There is no remote shell or general-purpose file access.
- Reparse points, symbolic links, duplicate physical files, and unrecognized
  file types are excluded.

This is still a development link. Its local HTTP traffic is not encrypted, so
it is suitable only for controlled tests on a trusted private network. A
production version requires authenticated encryption and persistent Node
identity before it is safe on hostile or public Wi-Fi.

## Build the Windows program

Double-click `BUILD_WINDOWS.cmd`, or run it from a Windows terminal. The built
program appears at `dist\GuideNode.exe`. Python and PyInstaller are needed only
on the development computer, not the computer that runs the resulting file.

Command dictionary:

- `python -m unittest`: checks pairing, authorization, and route boundaries.
- `python -m PyInstaller`: turns the Python program into one Windows program.
- `--onefile`: puts the program in one `.exe` file.
- `--windowed`: opens the control panel without a command window behind it.

## Windows responsiveness requirement

All native Windows interfaces in this project must follow
[`../../docs/WINDOWS_UI_PERFORMANCE_STANDARD.md`](../../docs/WINDOWS_UI_PERFORMANCE_STANDARD.md).
The shared `windows_ui_performance.py` movement governor prevents high-rate
pointer input from becoming a replay queue that continues after the user stops.
Its tests and the built-in movement report are required for future native UI
prototypes, rather than being optional debugging aids.

## Later Deck connection test

Run the Node, then run `guide_node_probe.py` on a second machine or the Deck.
The probe discovers the Node, asks for the displayed code, pairs, and prints the
Node's available services. The real Deck interface will replace this temporary
probe after the protocol has been verified.
