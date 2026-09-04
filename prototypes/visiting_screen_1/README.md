# VISITING-SCREEN-1

This prototype tests a consent-based local handoff of one visitor-supplied
movie to a compatible television on another person's network.

It is a narrow experiment, not a finished GuideOS release. It runs on an
existing Windows computer and represents one future Third Way Node service.
It does not install or replace an operating system.

## Intended encounter

1. The store owner agrees to the test and starts `ThirdWayNode.exe` on a
   Windows computer connected to the same private network as the television.
2. Windows may ask whether to permit local-network access. The owner permits
   private-network access only.
3. The program opens an owner console and displays a short-lived visitor
   pairing address.
4. The visitor starts `ThirdWayDeck.exe`, chooses one locally owned or otherwise
   authorized movie, and enters the pairing address.
5. The owner searches for televisions, sees the offered filename, explicitly
   selects one discovered television, and requests playback.
6. The movie stays on the Deck. The host tells the television where to retrieve
   the Deck's temporary local stream; it never receives the full movie.
7. The owner presses **Stop and revoke**, or closes the host. The Deck then
   immediately closes the temporary stream and invalidates its unguessable URL.

## Success criteria

The test succeeds only if all of the following are observed:

- The owner knowingly runs the host and retains final playback control.
- The visitor can offer exactly one Deck-hosted movie through a time-limited
  pairing link.
- The host discovers and identifies the intended TV as a UPnP/DLNA media
  renderer.
- The TV accepts the playback request and retrieves the movie directly from the
  Deck, including byte-range requests used while seeking.
- The interface reports rejection or incompatibility instead of claiming
  playback when the TV does not accept the request.
- Revocation makes the Deck's movie URL unavailable without copying the movie
  onto the owner's host.
- No cloud account or internet upload is required.

Discovery does not guarantee success. The television must advertise a UPnP
AVTransport service and support the movie container, video codec, audio codec,
resolution, and bitrate. MP4 containing H.264 video and AAC audio is a useful
first test format, but individual televisions vary.

## Build the Windows programs and owner installer

Open PowerShell in this folder and run:

```powershell
.\build_node_installer.ps1
```

The script first runs the automated tests, creates `dist\ThirdWayNode.exe` and
the temporary desktop Deck stand-in `dist\ThirdWayDeck.exe`, and then packages
the owner program as `installer-dist\ThirdWayNode-Setup-0.1.0.exe`. Python,
PyInstaller, and Inno Setup are build-time tools; the store computer does not
need them. Give the owner the installer, not the loose development executable.
Use `FIELD-TEST-CHECKLIST.txt` during the first controlled visit.

Command dictionary:

- `build_node_installer.ps1`: tests the programs, packages them, and builds the
  ordinary Windows installer.
- `python -m unittest`: runs the safety and protocol parsing checks.
- `python -m PyInstaller`: bundles the Python program into one Windows `.exe`.
- `--onefile`: asks PyInstaller to produce one distributable executable.
- Inno Setup: wraps the Node in a per-user install with an ordinary uninstaller.

## Run from source

For development, run:

```powershell
python .\thirdway_host.py
python .\thirdway_deck.py
```

Optional controls:

```text
--port 8765     Change the local web-service port.
--max-gib 8     Change the maximum accepted movie size.
--no-browser    Print the owner address without opening it automatically.
```

## Security boundary

This is an early local-network prototype. It uses an unguessable owner token,
a short-lived visitor code, an unguessable media URL, private-network client
checks, explicit owner approval, bounded file size, and automatic temporary
storage cleanup. The owner console can be used only from the host computer.

The host receives the filename, size, media type, and unguessable temporary
Deck URLs, but not the full movie in the primary path. A browser-upload fallback
remains available for Decks that cannot run the Deck program.

The prototype does not yet encrypt traffic on the local network, authenticate
the TV, transcode incompatible video, prove that a reported device is the
physical screen the owner intended, or sandbox vulnerabilities in a TV's media
decoder. The short pairing code is not rate-limited in version 0.1.0. It must
be used only with informed permission on a network and display the owner
controls.
