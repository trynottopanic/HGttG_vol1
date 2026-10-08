# GuideOS 0.3.2: boot 0.2.0, audio and diagnostic overlay

This test image combines the Discuss boot-animation handoff with local audio,
Bluetooth earbuds, a small playback buffer and resident diagnostics. Image and
virtual-service checks do not establish physical display or audio acceptance.

Installed 25 September 2026: Disk 4, Transcend USB reader, root partition only
(offset 135266304, length 2147483648 bytes). Full readback SHA-256:
`E719E36B31EA33BE78E6B029146B2156BA8A9DC7501282C2A03339B9F8DCF9E0`.
Boot and data partitions were verified unchanged. Recovery capture and final
installation evidence are recorded in `build/debian-audio-0/prewrite.json` and
`build/debian-audio-0/installation.json`. Hardware acceptance remains pending.

## Test on the Deck

1. Boot. Note roughly how long the screen stays blank before the globe appears.
   Look for a turning globe, moving clouds and the caption “Don't Panic.”
   Playback should last about eight seconds after its first frame, followed by
   the normal interface. Note artifacts, console interference or a stuck frame.
2. Navigate normally, including Wi-Fi and the keyboard. Check that buttons,
   sticks and volume controls still behave as before.
3. Press Start+Select together in the running interface. The diagnostic overlay
   should appear over the paused screen. Left/Right changes its page. Press
   Start+Select again, or B, to resume. Release both chord buttons between uses.
   Try opening it with a menu or keyboard already on screen; confirm the same
   screen and selection return. Boot animation is intentionally excluded.
4. Open Audio, select an available local output, and play `Guide-audio-test`
   under Music files. The quiet six-second tone tests left, right, then both
   channels. Check volume and pause/resume. If possible open diagnostics while
   the tone is playing: audio should continue while the screen is paused.
5. Put the earbud in pairing mode. In Bluetooth earbuds choose Find earbuds,
   select the device, then explicitly select it under Audio output. Play the
   sample. Note the earbud model and any failure message.
6. Disconnect the earbud during playback. Playback should pause without moving
   to the speaker. Reconnect it, choose its output and Resume; listen for whether
   audio actually advances. Do not rely solely on the displayed playing label.
7. Shut down using Power with diagnostics open. Boot again, check navigation,
   then perform a normal shutdown and reconnect the seed for log review.

Exact timings are optional; observations of blank screen, artifacts, frozen
input, sound gaps, unexpected speaker output or failed shutdown are useful.

## Evidence collected automatically

Five-second CPU and memory samples, process parent relationships, bounded error
summaries, audio queue/state events, boot frame statistics, and aggregate command
and navigation timing are retained under `/data/guideos/diagnostics`. The overlay
updates once per second but shows the age of its latest resource sample. Audio
statistics can lag the current state by a sample interval. Missing metrics do
not prove zero workload or zero latency.

Logs are capped at four files of 2 MiB each; ordinary keys and typed text are
not recorded by diagnostics. Boot and shell lifecycle evidence remain available
through the existing evidence paths.
