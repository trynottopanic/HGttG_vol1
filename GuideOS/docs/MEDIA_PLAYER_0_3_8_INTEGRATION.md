# Media player integration 0.3.8

Status: implementation target. This document does not claim an installed image or Deck acceptance.

## Purpose

Make a file placed on a recognized external Guide card under `GUIDE/MEDIA` available to the Deck's Media screen without giving the shell, an application, or an audio/video backend a card mount path. The first physical fixtures are one owner-provided MP3 and one owner-provided MP4.

## Responsible components

| Component | Owns | Must not own |
| --- | --- | --- |
| External Storage service | card recognition, read-only mount, bounded catalog, file-descriptor validation and revocation on removal | display, input, output routing, persistent playback state |
| Media Library provider | opaque browse records and a revalidated read descriptor | a physical pathname in its public reply |
| Media Session provider | one bounded session, decoder lifecycle, buffering state, checkpoints and stop deadline | global navigation, arbitrary card access |
| Audio route provider | explicit speaker/Bluetooth output and volume | media catalog paths or decoder/display ownership |
| Deck shell | presentation, controls, focus, power interruption and visible error state | direct card access or a long-running decoder |

## First integrated behavior

1. Inserting a recognized card refreshes its storage generation and produces a read-only media snapshot. Removal immediately invalidates the source and stops any session using it.
2. The Media screen presents separate Music and Video rows from that snapshot. A record contains title, kind, size, and folder label only; it contains no filesystem path.
3. Selecting a record asks the Media Session provider to revalidate and open it. The provider obtains a close-on-exec descriptor from Storage, then gives only the decoder it starts the descriptor needed for the active session.
4. MP3 uses the existing bounded GStreamer/PipeWire audio route. MP4 uses mpv with a two-second local-video prebuffer, audio-clock synchronization and late-video frame dropping. Both have bounded stop/kill behavior.
5. Navigation and power stop or checkpoint the session before the shell changes display ownership. A card removal, output loss, decode failure or timeout produces a concise state in the shell and releases the decoder.

## Scope boundary for this version

- External-card audio and video are the target, not a temporary copy into the Deck's permanent media directory.
- The first UI is a compact catalog/player screen. Full metadata, playlists, streaming, subtitles beyond the existing mpv contract, and Node sources stay outside this acceptance slice.
- The current `guide-audio` panel remains responsible for pairing and output selection. Media playback must use its selected route rather than silently changing the system default.

## Evidence required before calling it complete

Source tests must cover catalog bounds, no-path public records, descriptor revalidation, card removal, denied or stale control, MP3 and MP4 dispatch, pause, resume, seek and bounded stop. Image checks must verify the service units, socket permissions, private state directories, required decoder packages and no writes to the external card. Physical Deck acceptance requires the owner's sample MP3 and MP4 from the external card: visible listing, audible MP3 through the selected output, visible MP4 with synchronized audio, pause/resume, seek, normal exit, card removal while idle, and normal power-off afterward.

## Current gap

`guide-media` already has the catalog/session/buffer contracts and host tests. The current Seed includes those modules and mpv but does not activate a Media Library endpoint, a Media Session provider, or a Deck player screen. Therefore the existing Media Foundation page must continue to report that a shared player is unavailable until this integration is installed and physically tested.