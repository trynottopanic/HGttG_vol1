# GuideOS Local Media Player 0

The first local player lets a Deck open ordinary audio and video files without
requiring a Node or an internet connection. The existing **Media** screen now
combines three possible sources while preserving their folder structure:

- **This Deck** — files stored under `/data/guide-media`;
- **Cartridge** — recognized files on the external microSD card;
- owner-selected folders shared by a paired Node, when one is available.

The interface receives only display names, folders, sizes, and bounded source
indexes. Absolute local paths remain in a private runtime inventory. Immediately
before playback, GuideOS confirms that the selected file is still a regular file
under the same media root, has not become a symbolic link, and has not changed
since the scan. External storage remains mounted read-only with device files,
program execution, and elevated file permissions disabled.

## Initial formats

The browser recognizes common open or widely supported containers: MP4, MKV,
M4V, MOV, WebM, AVI, MPEG, MP3, M4A, AAC, FLAC, Ogg, Opus, and WAV. Recognition
does not promise that every codec variation can be decoded by this prototype.
A file the Deck cannot decode is left untouched and reported as needing Node
conversion or being damaged.

For predictable direct playback, use 8-bit H.264 video with `yuv420p` pixels at
640x480 or 640x360 and AAC stereo audio. A Node can prepare this form without
altering the owner's original.

Sidecar SRT, ASS, SSA, and WebVTT files are offered when their filename begins
with the video's complete base name. For example, `Film.mkv` can use
`Film.English.srt`. Sidecars receive the same containment and link checks as the
media file.

For Node-prepared video, embedded text subtitles are extracted once on the
trusted Node into small cached SRT sidecars. Selecting a track issues a separate,
short-lived, read-only ticket for that text file. The Deck never reopens or
decodes the complete network movie merely to discover subtitle packets, and
subtitle tickets are revoked with the same session as their parent media.

## Playback behavior

Playback uses the Deck's bundled FFmpeg runtime, direct framebuffer output, and
the established speaker/Bluetooth audio route. Local playback does not stop if
Wi-Fi disconnects. Existing controls remain available:

- **A** stops and returns to the browser;
- **B** pauses or resumes;
- **L2 / R2** seek backward or forward ten seconds;
- **L1 / R1** change audio tracks or video playback rate;
- **X** opens subtitle selection when a sidecar is available;
- the hardware volume buttons change the active audio route.

GuideOS records a small private resume position approximately every ten seconds
and when playback is paused, sought, or stopped. Reopening an unfinished local
file resumes from that point. Reaching the end removes the saved position.
The player also leaves a secret-free status record identifying its latest stage,
source class, audio route, position, and decoder return code for
`guide-diagnostics` to include after a failure.

## Navigation and power safety

Media playback is deliberately subordinate to the Deck interface:

- exactly one player may own the framebuffer and audio output at a time;
- the player runs at a lower scheduling priority than navigation and power input;
- its own process group and parent-death rule prevent a detached player from
  surviving the interface or maintenance session that launched it;
- pressing Power draws the shutdown confirmation immediately, then gives the
  player a bounded interval to save its resume point and exit;
- if graceful exit fails, the complete player process group is terminated
  without an unbounded wait;
- confirmed shutdown independently checks for a registered player and stops it
  before disconnecting radios, syncing storage, and requesting kernel power-off;
- owner data is synced before shutdown invokes optional radio or Developer Link
  helpers, and those helpers have hard deadlines rather than unlimited waits;
- a stale or foreign process identifier is never signalled unless its live
  command line identifies the Guide media controller.

These are platform rules, not RG35XX H conveniences. Future Guide player ports
and graphical interfaces must retain equivalent ownership, priority, bounded
cleanup, and emergency-shutdown behavior.

Video begins at real-time pacing rather than sending an unpaced five-second
burst to the clockless framebuffer. When a volume overlay temporarily holds a
video, the controller closes the decoder and discards queued PCM before reopening
at the recorded position; it never suspends video while buffered audio continues.
Pause, seek, track changes, and exit use the same discard-first transition, so an
old speaker or Bluetooth buffer cannot continue draining after the player closes.

Bluetooth devices can contain an additional private playout buffer which
BlueALSA cannot measure. The P20i tests established that starting its audio path
before video materially improves synchronization, but the final lead value is
still being calibrated. The next physical build holds video for 1.2 seconds,
an additional 200 milliseconds beyond the last tested setting. That
compensation belongs to a supervised, per-output profile; it must not be
implemented by launching detached test players.

Before drawing the subtitle selector, the shell now waits for a bounded
`paused` acknowledgement written only after the player has closed its decoder.
This prevents a queued video frame from painting over the modal menu and making
it appear to flash and disappear. A missing acknowledgement is logged and the
wait ends after 1.5 seconds so subtitle handling can never hold navigation or
Power indefinitely.

## Prototype limits

- The first browser shows at most 100 media records and stops filesystem work
  after inspecting 10,000 files.
- Embedded subtitle discovery and a visible duration/progress display remain
  follow-up work.
- Hardware video decoding remains disabled until the running vendor kernel is
  probed and the exact decoder interface is verified.
