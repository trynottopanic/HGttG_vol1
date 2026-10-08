# GuideOS Media Engine Adapter 1

Status: adopted engine and buffering direction, 26 September 2026. This is the
implementation contract for the first adapters; measured thresholds remain
provisional until physical Deck acceptance.

## Adopted split

- Audio-only sessions use GStreamer and the existing PipeWire/WirePlumber route.
- Video sessions use one supervised mpv process for both video and its associated
  audio through private JSON IPC.
- FFmpeg remains a compatibility fallback and diagnostic oracle. It is not the
  preferred interactive session controller.
- Audio and video belonging to one video item must never be divided between the
  GStreamer audio adapter and mpv. mpv owns their common playback clock.

The adapters implement the common Media Session contract. Applications do not
receive engine-specific commands, process identifiers, paths or sockets.

## Playback preference

Stable synchronized playback takes precedence over instant start. Opening,
resuming and seeking may remain visibly in `BUFFERING` until the applicable
high-water threshold is satisfied. The interface must distinguish buffering
from a frozen application.

Initial policy values:

| Source and session | Start high water | Rebuffer low water | Resume high water |
| --- | ---: | ---: | ---: |
| Local audio | 750 ms | 250 ms | 750 ms |
| Local video | 2,000 ms | 750 ms | 2,000 ms |
| Node audio/video | 5,000 ms | 2,000 ms | 5,000 ms |
| Online audio/video | 8,000 ms | 3,000 ms | 8,000 ms |

These are adapter policy, not wire-protocol constants. Every buffer is bounded
by media time and bytes. Byte ceilings are derived from measured bitrate with a
fixed defensive maximum so malformed metadata cannot allocate memory without
bound. Repeated underruns may select the next larger bounded policy for that
session; they cannot grow a queue indefinitely.

## Required engine behavior

Each adapter must provide:

- acknowledged open, pause, play, seek and stop;
- position and duration from presented media time, not bytes read ahead;
- buffered duration and whether the high-water threshold has been reached;
- underrun count and reason;
- decoder failure, source loss and output loss as distinct failures;
- audio and subtitle track selection where applicable;
- bounded shutdown followed by supervisor-enforced process cleanup; and
- a diagnostic snapshot that contains no source path, URL, credential or private
  engine socket.

Seeking flushes data belonging to the old timeline, re-establishes the engine
clock, fills to the appropriate high-water threshold, and only then resumes.
Checkpoint position is the last acknowledged presented position.

## Audio adapter

The GStreamer adapter evolves the existing isolated decoder worker. It uses an
explicit non-leaky queue, GStreamer buffering messages and the selected
PipeWire clock. The present 250 ms queue is retained only as historical evidence;
the adapter begins with the local-audio policy above. Output replacement pauses,
rebuilds the bounded output path, restores position while muted, fills the queue,
then resumes explicitly. Earbud loss never falls back to speakers.

## Video adapter

The first mpv adapter is an external supervised process, not embedded libmpv.
It receives an already-authorized source descriptor, a private inherited JSON
IPC endpoint and the selected output/display leases. mpv owns audio/video sync;
audio is normally the master clock. Irrecoverably late video frames are dropped
within measured bounds instead of being presented in a catch-up burst. Audio is
not silently skipped to conceal sustained overload.

The adapter starts with conservative software decode and cache settings. mpv's
reported cache duration, underruns, dropped frames, A/V synchronization offset
and playback time are translated into Media Session state/events. Hardware
decode is a later independent probe with software fallback.

## Recovery rules

1. Buffer below low water: acknowledge `BUFFERING` and stop presentation.
2. Buffer reaches resume high water: resume from one established clock.
3. Repeated underrun: increase only to the next bounded policy and record it.
4. Excessively late video: drop late video frames; never accelerate a queued
   burst merely to display every decoded frame.
5. A/V offset outside the measured acceptance bound: attempt one engine-level
   resynchronization, then pause and report failure rather than drifting.
6. Decoder or IPC timeout: checkpoint the last presented position, terminate the
   whole supervised worker, release leases and report the responsible boundary.

## Acceptance evidence

Host fixtures must cover startup buffering, underrun/rebuffer, seek flushing,
late-frame dropping, stalled IPC, corrupt status, output loss and bounded stop.
Physical Deck acceptance must record startup delay, underruns, dropped frames,
maximum A/V offset, CPU, memory, temperature and Power responsiveness for local,
Node and controlled online fixtures. Smooth playback is not inferred from
successful decode or queue allocation alone.
