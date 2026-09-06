# Guide Desktop Node 0

This is the first small Windows Node shell. Double-clicking `GuideNode.exe`
opens one understandable control panel. A Deck on the same private Wi-Fi can
discover it, enter the code shown by the owner, and learn which carefully
limited services the Node offers.

The owner can designate one Media folder. Recognized music and video beneath
that folder become a read-only catalogue for paired Decks, with seeking-capable
byte-range streaming. Computer paths are never sent; each file receives an
opaque identifier valid only for the current Node run. Changed files are
refused until the owner rescans.

Videos are converted in a background cache to a conservative Deck format; the
owner's original is never modified. Compatible text subtitle tracks are kept
as selectable tracks. The Deck player uses a longer network buffer and exposes
pause, seek, forward scan, reverse preview, and subtitle-selection controls.

The Node deliberately cannot run arbitrary commands, browse outside the chosen
Media folder, modify shared files, or control Android. Those functions
must be added later as named capabilities with their own permission checks.
It can safely detect whether Android's command-line tools and virtual devices
already exist, but detection never starts an emulator or enables remote access.

## Current safety boundary

- The Node accepts private/local network addresses only.
- Pairing codes expire after ten minutes and lock after repeated failures.
- Paired sessions live only in memory, expire after eight hours, and are all
  revoked when the Node stops.
- Requests are small and bounded; authorization secrets are not logged.
- There is no remote shell or general-purpose file access.
- Reparse points, symbolic links, and unrecognized file types are excluded.

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

## Later Deck connection test

Run the Node, then run `guide_node_probe.py` on a second machine or the Deck.
The probe discovers the Node, asks for the displayed code, pairs, and prints the
Node's available services. The real Deck interface will replace this temporary
probe after the protocol has been verified.
