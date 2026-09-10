# Music Player 0

Music Player 0 is a small Deck interface over the media folder selected by the
owner of a trusted desktop Node. It does not scan the rest of the computer and
does not copy or modify the owner's source files.

## Controls

- **A** stops playback and returns to the library.
- **B** pauses or resumes playback.
- **L1 / R1** selects the previous or next audio track.
- **L2 / R2** moves ten seconds backward or forward within the track.
- The Deck's volume buttons change the active Bluetooth output or internal
  speaker and show the same visible percentage indicator.

When a track finishes, the next later audio item starts automatically. The end
of the audio list returns to the library rather than looping without consent.
Video controls retain their separate two-times and subtitle behaviors.

Each appended media command is consumed exactly once. Replaying an old pause,
seek, or rate command would repeatedly restart the decoder at the same point
and make the control appear ineffective.

Physical input testing established that the RG35XX H vendor driver reports
L1, R1, L2, and R2 as Linux key codes 308, 309, 314, and 315. GuideOS maps
those model-specific values while retaining the standard Linux shoulder codes
for future Deck hardware. Earlier builds listened only for the standard codes,
so shoulder commands never reached the player.

Pause now closes the decoder and remembers its approximate media position;
resume reopens it at that position. This avoids an audible queue continuing
after pause. Seek, rate, and subtitle changes also fully close the former
decoder and allow the audio device a short release interval before reopening.
This prevents rapid restarts from colliding with a still-busy internal or
Bluetooth ALSA output.

## Failure behavior

If Bluetooth is absent or disconnected, playback uses the internal speaker. If
the Node becomes unavailable, playback stops and the Deck returns to a readable
library state. The player accepts only the fixed media-control vocabulary; it
does not expose a shell or arbitrary FFmpeg arguments.
