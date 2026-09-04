# CONTINUE-ON-DECK-0 reference receiver

This folder begins the first Node-to-Deck continuity test. `deck_receiver.py`
is the small service that will run on GuideOS: it describes the Deck, accepts
one pairing-code-authorized video transfer over the private USB link, verifies
the promised size and SHA-256 fingerprint, and publishes a JSON resume record
only after the video is complete. Pairing codes expire after ten minutes,
repeated incorrect guesses are locked out, and abandoned partial files are
removed when the receiver restarts.

`node_sender.py` is the matching desktop sender. It checks the Deck's identity,
free space, and declared formats; fingerprints the source video; sends the file
with progress; and prints that the cable is safe to remove only after the Deck
commits the verified handoff.

`node_player.py` adds the first human interface: it plays one local video in a
browser window and provides a **Continue on Deck** button. Pressing the button
pauses playback, captures the current position, and performs the verified
handoff. The page is reachable only from the Node itself through an unguessable
session address.

The code currently runs on ordinary computers for protocol testing. It is not
yet installed in the RG35XX H image. `deck_runtime.py` is the first deliberately
plain Deck interface: it shows a pairing code, receives and verifies the movie,
and asks `mpv` to continue it at the recorded position. A more polished Deck
screen remains future work; the plain interface is enough for the first physical
acceptance test once the operating-system image has been built and verified.

`build_windows.ps1` runs all handoff checks and packages the Node player as a
single `dist\ThirdWayNodePlayer.exe`. The Windows file is an unsigned
development build until the project establishes a signing process.

Run its focused tests from this folder with:

```powershell
python -m unittest -v test_deck_receiver.py
```

Command dictionary:

- `python`: runs the Python interpreter used for this early prototype.
- `-m unittest`: runs the built-in automated test system.
- `-v`: prints the name and result of each check.
