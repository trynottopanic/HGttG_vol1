# GuideOS Audio and Video Players 1 proposal

Status: engine and interface study, 25 September 2026. The owner adopted native
local and Node playback plus an online-provider-ready engine as pre-0.4.0 goals
on 26 September 2026, then selected the split GStreamer-audio/mpv-video direction
with smooth buffered playback preferred over instant start. `MEDIA_SERVICES_1.md`
and `MEDIA_ENGINE_ADAPTER_1.md` govern implementation. Physical playback remains
unverified.

## Purpose

This proposal turns the existing bounded media proofs into two recognizable
Guide applications:

- an audio player that can remain active after its page closes and can continue
  in Pocket Mode; and
- a video player that owns the display only for a supervised playback session
  and returns it predictably to Guide Shell.

Both applications use the common media library, external-storage broker, audio
route, supervisor and global Power behavior. They do not independently scan or
mount storage, pair Bluetooth devices, select unapproved network sources, own
Power, or leave detached decoder processes.

The intended implementation rule is to reuse maintained Debian-compatible
media engines while keeping GuideOS responsible for identity, access, input,
presentation, lifecycle, resource policy and recovery.

## Existing evidence and constraints

The repository already contains two different playback proofs:

1. `package/guide-audio` uses GStreamer for local audio decoding and PipeWire,
   WirePlumber and BlueZ for explicitly selected local or Bluetooth outputs. It
   has a bounded decoder worker, a 250 ms decoded queue, output-loss handling,
   persisted volume and systemd confinement. Physical speaker and earbud
   acceptance remains pending.
2. `apps/node_link/guide_node_bridge.py` invokes a bundled FFmpeg runtime for
   local and Node audio/video. Video is scaled and padded to 640 by 480 and sent
   directly to `/dev/fb0`; audio is sent to ALSA. This proved a direct video
   path, resume records, subtitle filters and bounded cleanup, but several
   transitions close and reopen FFmpeg. A framebuffer decoder can overwrite a
   Guide overlay unless playback acknowledges that it has released output.

The RG35XX H target has an H700 CPU, 1 GB of memory, a 640 by 480 display and a
developing Debian system. The shell, supervisor and Power path must remain more
responsive than playback. Hardware video decoding is not assumed until the
running kernel, V4L2 devices and decoder compatibility are physically probed.

## Backend assessment

### GStreamer

GStreamer is the recommended Audio Player 1 engine.

Reasons:

- it is already installed and integrated with the Deck's PipeWire route;
- its asynchronous state and bus messages fit supervised play, pause, seek,
  end-of-stream, buffering and error reporting;
- `playbin3` can discover formats, expose tags, select audio and subtitle
  streams, accept external subtitle files and prepare a following item;
- a bounded `queue` already exists in the Guide audio proof; and
- one engine can later support recording and other audio tools.

The audio application should use a persistent but idle service and one isolated
decoder worker only while a track is open. It should not add MPD merely to gain
a queue or music library.

GStreamer remains a viable video fallback, but direct Guide framebuffer output
would require either a tested DRM sink or a small appsink-to-framebuffer renderer.
That is more new display code than the first video application requires.

### mpv/libmpv

mpv is the first Video Player 1 candidate to probe.

Reasons:

- Debian supplies it for arm64;
- it already implements seeking, subtitle and audio-track selection, timing,
  resynchronization, software-decoding profiles and a DRM output mode;
- its JSON IPC or libmpv interface can report properties and accept commands
  without killing and reopening the decoder; and
- it is a maintained player rather than a Guide-specific playback engine.

The probe must not assume that mpv can acquire the current panel's DRM device
or coexist with the framebuffer shell. A supervised display handoff is required:
Guide Shell releases display presentation, the player acquires it, and the
player releases it before the shell redraws. If the current driver cannot
provide a reliable DRM session, GuideOS retains the proven FFmpeg framebuffer
path while the GStreamer renderer option is evaluated.

The command-line mpv process is preferable to embedding libmpv for the first
probe. A private inherited socket or file descriptor supplies JSON IPC; the
supervisor owns the complete process group. Embedding can be reconsidered only
if process IPC creates an observed limitation.

### FFmpeg

FFmpeg remains the Video Player 1 compatibility fallback and diagnostic oracle.
It already decodes the intended baseline and writes the actual framebuffer.
It is also useful for bounded metadata probing, thumbnails and Node-side media
preparation.

FFmpeg alone is not the preferred finished interactive controller. Its current
Guide invocation is a transcode-style process whose pause, stream changes and
some overlays require process replacement or output release. Extending that
control scheme would reproduce player behavior that mpv or GStreamer already
provides.

### MPD

MPD remains a possible future music-library provider, especially for remote
control, large persistent libraries or gapless queue management. It is not
recommended for Audio Player 1 because it would duplicate the current
GStreamer decoder, PipeWire route, state owner and system service before the
common lifecycle and capability contracts are complete. The Guide queue and
library schema should not depend on MPD so it can be introduced or omitted
later.

## Common Media Library service

The players should not enumerate paths themselves. A small system-owned media
library consumes logical collections from External Storage 0, internal storage
and approved Node providers. It returns paginated, opaque records:

```text
media_id
source_id
kind                audio or video
display_name
folder_display
size
modified
duration_status      unknown, probing, known or unavailable
duration
artwork_status
audio_track_count
subtitle_track_count
availability_generation
```

Opening a local item asks the storage broker for a contained read handle. The
handle is inherited by the decoder and addressed using an engine-supported
descriptor form. The decoder never receives the card's unrestricted mount
path. A Node item instead receives a bounded media ticket from its provider.

The internal library index stores metadata and small thumbnails. It does not
write metadata beside media files. Ordinary browsing does not cryptographically
hash large content. Cartridge verification and an owner-requested integrity
operation remain separate.

Metadata probing is lazy, cancelable and tier 3 background work. The selected
row and visible page are probed before unseen directories. Playback suspends or
throttles probing if the card or CPU cannot serve both without measurable delay.

## Audio Player 1

### Components

```text
Guide Audio View
       |
Guide media-session API
       |---------------- Media Library
       |---------------- Audio Route service
       `---------------- supervised decoder worker
                              |
                         GStreamer playbin3
                              |
                     bounded queue -> PipeWire
```

The present `guide-audio` service can evolve into the audio portion of a
`media-session` provider rather than being replaced. Its trusted-shell datagram
protocol should become a versioned request/reply interface with application and
session identity, command acknowledgement and an event subscription. The
private status file may remain diagnostic evidence but should not be the
finished synchronization mechanism.

### State model

```text
closed -> opening -> playing <-> paused -> stopped
                   |    |
                   |    `-> output-lost -> paused
                   `-> end-of-item -> advancing or stopped

any active state -> checkpointing -> stopping -> closed
any active state -> failed -> stopped or explicit retry
```

Opening, seeking and output changes are asynchronous. The interface remains
responsive and shows the latest acknowledged state rather than assuming a
command succeeded. No operation may wait indefinitely for a decoder or sink.

### Queue and library behavior

- Queue entries contain media identities, not paths.
- The next item may be prepared on GStreamer's `about-to-finish` signal, but
  gapless playback is claimed only after physical measurement with representative
  files and both speaker and Bluetooth routes.
- Removing the external card marks unavailable entries without destroying the
  queue. Playback stops cleanly if the active read handle fails.
- Shuffle stores a finite queue order so pause, reboot recovery and diagnostics
  do not produce an unknowable changing sequence.
- Repeat modes are Off, One and Queue.
- The first release needs a queue, folder browsing and recently played view;
  artist/album indexing depends on reliable tag measurements and is not required
  to begin.

### Pocket Mode

Audio is the first Pocket Mode continuation class. Entering Pocket Mode:

- turns off the backlight and stops interface rendering;
- retains the media session, selected audio worker, PipeWire/WirePlumber and the
  required local or Bluetooth output;
- retains only deliberate wake and hardware volume input;
- pauses library scanning, artwork work and unrelated application activity;
- retains Wi-Fi only when the active source actually requires it; and
- checkpoints position without writing on every status tick.

Earbud loss pauses. It does not fall back to the speaker. If the selected route
cannot be restored, wake presents the output decision and retained position.

### Proposed Audio controls

The first UI draft treats controls as semantic actions rather than permanently
assigning every physical key here:

- move focus among previous, pause/resume, next and queue rows;
- open the selected action;
- open Queue, Library or Output through a small context action;
- seek from a focused progress control in bounded steps;
- use physical volume globally; and
- enter Pocket Mode explicitly or after the accepted inactivity rule.

The existing prototype's A/B behavior remains authoritative until the shared
input mapping is reconciled. The visual draft is not approval to reverse A and B.

### Audio resource targets to measure

- idle service: effectively sleeping, no fixed 250 ms wake solely to rewrite an
  unchanged status file;
- active decoder: one worker and bounded queue;
- decoded queue: begin with the existing 250 ms or 256 KiB limit;
- interface redraw: event-driven, with a progress update no faster than twice
  per second on the visible page and none with the display off;
- library work: tier 3, preemptible by playback; and
- initial acceptance target: no audible underrun from ordinary navigation and
  prompt global Power response under concurrent indexing.

## Video Player 1

### Components

```text
Guide Video View / overlay
       |
Guide media-session API
       |---------------- Media Library
       |---------------- Audio Route service
       `---------------- Guide Supervisor
                              |
                    mpv process + private JSON IPC
                       or FFmpeg fallback
                              |
                    DRM or proven framebuffer output
```

Video is a foreground tier 1 application. It receives the display lease and an
audio lease as one supervised session. Navigation and Power remain system-owned
and can request a bounded checkpoint and stop even when the decoder is unhealthy.

### Engine probe order

1. Install the Debian arm64 mpv runtime in an isolated development image.
2. Inventory the actual DRM connector, mode and plane behavior without changing
   the production shell contract.
3. Play the known 640 by 480 H.264/AAC fixture using software decode and mpv's
   conservative DRM or software profile.
4. Verify private IPC for pause, resume, relative seek, position, duration,
   audio-track selection, subtitle selection and quit.
5. Test display release and shell restoration repeatedly, including decoder
   failure and Power during startup.
6. Test PipeWire output pinning and Bluetooth delay without automatic speaker
   fallback.
7. Compare CPU, memory, dropped frames, A/V error and power against the current
   FFmpeg framebuffer path.
8. Only then inspect V4L2 decoder devices and attempt hardware decoding as a
   separate experiment with a software fallback.

Failure to acquire DRM does not justify weakening shell ownership. It selects
the FFmpeg fallback or motivates the GStreamer framebuffer renderer.

### Video state and overlays

```text
browsing -> acquiring-display -> opening -> playing <-> paused
                                      |         |
                                      |         `-> overlay-visible
                                      `-> buffering or failed

playing/paused -> checkpointing -> releasing-display -> browsing
```

With mpv, the Guide can use IPC and a restrained player overlay. With direct
FFmpeg framebuffer output, Guide overlays must first obtain a positive paused
and output-released acknowledgement, as the subtitle selector already does.
The interface must never draw over an actively writing framebuffer and call the
result stable.

The overlay automatically clears after a short period of acknowledged playback.
It remains visible while paused. Subtitle, audio-track and output selection are
modal Guide views; playback state and buffer discard behavior are explicit.

### Video behavior

- Preserve source aspect ratio and letterbox or pillarbox rather than crop by
  default.
- Record resume position at bounded intervals and meaningful transitions, not
  every rendered frame.
- Offer external and embedded text subtitles when safely identified.
- Expose alternate audio tracks with bounded human labels.
- Seek asynchronously and show seeking until the engine acknowledges the new
  position.
- Do not enter Pocket Mode while video continues. A deliberate screen-off
  action may later offer "continue audio only", but that is a distinct mode and
  is not implied by Video Player 1.
- Local playback survives Wi-Fi loss. Node playback reports loss, retains the
  last durable position and offers retry or return.
- Files that exceed the tested decode envelope are left unchanged and reported
  as unsupported locally; a Node may prepare a compatible copy.

### Initial compatibility envelope

Keep the current predictable baseline:

- MP4 or MKV;
- 8-bit H.264;
- `yuv420p`;
- at or below 640 by 480 or 640 by 360 for the first acceptance set;
- AAC stereo; and
- SRT or WebVTT sidecars, followed by tested embedded text subtitles.

Other containers and codecs may work through the selected engine, but extension
recognition is not a compatibility promise. A fixture matrix must distinguish
container recognition, decode, seeking, duration, track selection, subtitles,
end-of-file and corrupt-input behavior.

## Interface drafts

The test drafts are stored at:

- `design/media-player-drafts/audio-player-concept-0.png`
- `design/media-player-drafts/video-player-concept-0.png`

They use Paper Theme 0's warm pale field, charcoal-olive ink, muted blue, rust
selection and mixed-case labels. They are visual direction studies, not pixel-
accurate implementation specifications. Generated typography, icons, spacing
and control assignments must be rebuilt using the Guide renderer and verified
at native 640 by 480 resolution.

The deterministic Schema 0 fixtures in the same directory now rebuild both
screens at native 640 by 480 resolution using shared design tokens and reusable
components. They remain local image evidence, not physical framebuffer
acceptance or working media controls.

### Audio screen arrangement

```text
The Guide / Audio                              Don't Panic.
------------------------------------------------------------
[art]  Track title
       Artist or source
       Selected output

elapsed  ---------------- progress ----------------  duration
             [previous] [pause/resume] [next]
------------------------------------------------------------
Queue row
Queue row
Queue row
------------------------------------------------------------
Back              Open              Queue              Home
```

The queue is useful immediately and avoids a second page for basic listening.
Artwork is optional; absent artwork becomes a stable Guide mark or neutral
placeholder rather than a failed-image icon.

### Video screen arrangement

```text
The Guide / Video          Item title                 battery
------------------------------------------------------------
|                                                          |
|                    video viewport                        |
|                                                          |
| pause  elapsed -------- progress -------- duration        |
------------------------------------------------------------
 audio track       subtitle track       selected output
------------------------------------------------------------
 Pause             Seek             Subtitles         Back
```

The viewport remains dominant. The information row is shown with the overlay,
not permanently burned over the film. The mockup's control labels are candidates
pending input-contract review.

## Packaging approach

Audio Player 1 should extend the current Debian audio package rather than ship a
second complete multimedia stack. Video Player 1 should be an optional package
whose declared footprint includes the chosen engine and overlapping libraries.
The engine version is pinned per image or signed update and included in
diagnostics.

Codec availability must follow Debian package licensing and the project's
distribution boundary. GuideOS does not include protected media, keys or
third-party streaming credentials.

Suggested system units are illustrative, not frozen API names:

```text
guide-media-library.service       system-owned index/provider
guide-media-session.service       audio session and route coordinator
guide-video@<instance>.service    transient supervised video process
```

The supervisor, rather than the UI, owns transient process lifetime. The UI may
crash and reconnect to an acknowledged audio session. A foreground video process
cannot remain hidden after losing its display lease.

## Verification plan

### Source and virtual checks

- Parser and state-machine tests for every request and acknowledgement.
- File-descriptor containment and stale-card-generation tests.
- Media fixture matrix for formats, tags, duration, seek and subtitles.
- Queue, repeat, shuffle and end-of-item transitions.
- Output removal with no unintended speaker fallback.
- Decoder hang, crash, malformed status and forced cleanup.
- Global Power during opening, seek, subtitle selection and output loss.
- UI snapshots for empty, loading, playing, paused, unavailable and error states.
- Static dependency and installed-footprint record for each engine candidate.

### Physical audio acceptance

- Speaker, headphone and at least one Bluetooth earbud.
- Pause/resume, seek, next item, queue continuation and route replacement.
- Navigation while playing and Pocket Mode with the display truly off.
- CPU, memory, current draw, wakeups, underruns and Bluetooth latency.
- External-card removal and reinsertion while queued and while playing.
- At least a two-hour mixed-format run and repeated orderly shutdown.

### Physical video acceptance

- Repeated display handoff and restoration without stale frames or console text.
- Baseline H.264/AAC at 24, 30 and, if practical, 60 frames per second.
- Long playback, seek storms, pause overlays, subtitle changes and track changes.
- Speaker and Bluetooth A/V synchronization measured separately.
- CPU, memory, dropped frames, temperature, current draw and Power responsiveness.
- Corrupt, truncated, unsupported and card-removed sources.
- Software decode first; hardware decode evidence reported separately.

## Recommended first implementation slice

1. Preserve and physically validate the staged GStreamer/PipeWire audio service.
2. Replace periodic unchanged status-file rewrites with event subscription or a
   lower-wakeup status mechanism before claiming Pocket Mode efficiency.
3. Add queue identity and metadata to the audio service without adding MPD.
4. Implement the Paper Theme audio view against a fixture provider, then the
   real acknowledged service.
5. Build an isolated mpv DRM/IPC probe; do not replace the FFmpeg fallback yet.
6. Implement the Paper Theme video overlay against recorded engine events.
7. Compare mpv and FFmpeg on the physical Deck and select the first engine from
   evidence.
8. Integrate External Storage 0 file handles after its read service exists.

The boot animation does not need another revision to enable this work. Media
architecture, player-state fixtures and native UI reconstruction are the more
direct next steps.

## Research references

- Debian `mpv` and `libmpv2` arm64 packages.
- Debian `mpd` arm64 package.
- Debian GStreamer 1.0 packages.
- GStreamer `playbin3`, playback component, buffering and seeking documentation.
- mpv manual sections for JSON IPC, DRM output and software playback profiles.
- FFmpeg device and playback documentation.
