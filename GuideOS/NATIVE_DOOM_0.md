# Native Doom runtime (prototype)

GuideOS runs Doom through a native, software-rendered engine. It is not a streamed
desktop application or an emulated game console. The small Guide frontend owns
only the display, audio, and controller while the game is running, then returns
those resources to the main Guide interface.

## Game data

The runtime does not contain the commercial Doom games. A user supplies a lawful
`.wad` data file in one of these locations:

- Deck storage: `/data/guide-games/doom/`
- Cartridge: `/media/guide-card/GUIDE/GAMES/DOOM/`

The open Freedoom data set is compatible and may be distributed separately under
its own licence. A cartridge can contain WAD data, but cannot supply executable
code to this runtime.

## Prototype controls

- D-pad or left stick: move and turn
- A: use/open
- X: fire
- L/R: strafe
- L2/R2: previous/next weapon
- Menu: game menu
- Power: leave the game and open GuideOS's safe-shutdown confirmation

The exact face-button mapping remains a physical-device test item because Linux
firmware revisions may label the same Anbernic controls differently.

Audio follows a connected trusted Bluetooth device when its strict BlueALSA
address is available, and otherwise falls back to the Deck speakers.

## Safety boundary

The launcher resolves the selected file to a real path, accepts only regular WAD
files below one GiB, and permits only fixed local or cartridge directories. It
does not follow a package-provided executable, shell command, library, or audio
device setting. GuideOS remains responsible for the power button and terminates
the game within a bounded interval before shutdown.

## Upstream components

- Engine: `libretro-prboom`, GPL-2.0, pinned and built outside this repository.
- Frontend: GuideOS native frontend, AGPL-3.0-or-later.

The final seed preparation must install the upstream engine licence and record
its exact source revision and binary checksum next to the runtime.
