# GuideOS Media Services 1

Status: adopted pre-0.4.0 service design, 26 September 2026. Engine choices
remain conditional on physical RG35XX H evidence. This document specifies the
service boundaries and acceptance target; it does not claim implementation.

Message-contract follow-up, 26 September 2026: `MEDIA_IPC_1.md` defines the
initial library/session operations, records, events and authority boundary. Its
generated C/Python registry and production-preparation tests pass. No media
service or physical playback behavior is established by that result.

## Required outcome before 0.4.0

GuideOS must provide native audio and video applications that can play suitable
media from External Storage 0 and from an authorized Node. The same playback
foundation must also accept resolved online streams through replaceable provider
adapters, so a later YouTube adapter does not require a separate player.

The pre-0.4.0 gate requires:

- local audio and video browsing and playback from `GUIDE/MEDIA/`;
- authenticated playback of selected media from a trusted Node;
- one controlled online-stream fixture proving that the engine is not limited
  to files or Node transport;
- audio continuation in Pocket Mode;
- supervised display, audio, network and decoder ownership;
- bounded buffering, cancellation, cleanup and resume state; and
- honest unsupported, unavailable, buffering and failed states.

YouTube discovery, accounts, recommendations and a production YouTube adapter
are not required for 0.4.0. Provider-specific extraction must remain outside the
media engine and comply with the provider's applicable interface and terms.

## Component ownership

```text
Guide Audio / Video views
            |
            v
guide-media-session        acknowledged playback state and controls
       |       |       |
       |       |       `-- guide-audio-route
       |       `---------- Guide Supervisor and resource admission
       `------------------ guide-media-library
                                  |
                +-----------------+------------------+
                |                 |                  |
       External Storage      Node Media         Online Provider
          provider            provider             adapter
                |                 |                  |
           read handle       media ticket      resolved stream
                +-----------------+------------------+
                                  |
                         supervised decoder
```

The shell owns global navigation, Power and the transition into or out of a
foreground video surface. The media session service owns player state but cannot
grant itself display, audio, storage or network authority. The Supervisor owns
the decoder process group and performs bounded stop and cleanup. Applications do
not mount storage, open arbitrary Node paths or invoke unrestricted URLs.

The initial implementation may colocate lightweight components, but their
identities, state and authority must remain distinct at the protocol boundary.

## Media Library service

`guide-media-library` is a system-owned catalog and selection service. It merges
three source classes without exposing physical paths:

1. `storage` — logical content beneath External Storage 0's `GUIDE/MEDIA/`;
2. `node` — media records advertised by an authorized Node session; and
3. `online` — records returned by a specifically enabled provider adapter.

Every visible record has an opaque `media_id`, a `source_id`, a source class, an
availability generation, bounded display metadata and a compatibility state.
Queue and resume records store these identities rather than filesystem paths or
expiring URLs.

Catalog operations are paginated and cancelable. Local metadata probing is lazy
tier 3 work. Playback is tier 1 and must pause or throttle indexing, artwork and
other background media work when the two contend. The index and thumbnails are
kept on internal storage; GuideOS does not write beside owner media.

Selecting an item produces a time-bounded **open offer**, not decoder authority:

- storage returns a contained read handle after grant and generation checks;
- Node returns a short-lived ticket scoped to one media object and session; or
- an online adapter returns a short-lived resolved stream description.

The media session revalidates the offer immediately before opening it. A stale
generation, revoked grant or changed file fails visibly instead of being treated
as an empty library or a decoder error.

## Media source description

All sources converge on a versioned description with bounded fields:

```text
source_class          storage | node | online
media_id              opaque stable library identity
open_generation       freshness and revocation generation
transport             inherited-fd | https
locator               private handle or short-lived URL; never shown in UI/logs
required_headers      bounded provider-supplied headers, if any
container_hint        optional, not trusted as proof
duration_hint         optional
seekability           yes | no | unknown
audio_tracks          bounded labels and stable per-open identifiers
subtitle_tracks       bounded labels and stable per-open identifiers
expires_at            required for tickets and resolved online streams
refresh_token_id      opaque provider refresh reference, never a credential
```

Secrets, Node addresses, owner file paths, HTTP headers and resolved URLs are
private session material. They must not appear in ordinary diagnostics, resume
records, cartridge state or application-visible logs.

The decoder receives only the selected handle or stream and the minimum headers
needed for that open operation. Redirects, protocols and destination addresses
are constrained by the owning provider rather than accepted from a cartridge.

## Media Session service

`guide-media-session` is the single acknowledged control boundary for audio and
video playback. Its public operations are semantic and engine-independent:

```text
open(media_id, source_generation)
play
pause
seek(relative_or_absolute_position)
select_audio(track_id)
select_subtitle(track_id_or_off)
set_output(output_id)
checkpoint
stop
watch(session_id, event_sequence)
```

Every mutating request carries the application instance, media-session identity,
request identity and relevant capability grant. A reply distinguishes accepted,
completed, rejected, stale, unsupported and failed. The UI never claims a seek,
pause, route change or stop until the corresponding state is acknowledged.

Common states are:

```text
closed -> resolving -> acquiring -> opening -> buffering -> playing
                                                 ^          |
                                                 |          v
                                              seeking <-> paused

any open state -> checkpointing -> stopping -> closed
any open state -> reconnecting | unavailable | failed
```

Events are ordered within a session and carry a monotonically increasing
sequence. Reconnecting views request a current snapshot followed by later
events. Status files remain diagnostic evidence, not the synchronization API.

Only one session may own a given audio output, and only one foreground video
session may own the Deck display. An audio session may remain active after its
view closes. A video session losing the display lease must checkpoint and stop;
it cannot continue invisibly.

## Decoder and output adapters

The service contract does not expose a specific engine. The first implementation
direction remains:

- GStreamer `playbin3` for Audio Player 1, evolving the existing
  GStreamer/PipeWire service;
- an isolated mpv process with private IPC as the first Video Player 1 probe;
- the proven bundled FFmpeg framebuffer path as compatibility fallback and
  diagnostic oracle; and
- FFmpeg on a Node for explicit, bounded preparation or transcoding.

The physical probe selects the first video engine. No design text may promote
mpv, hardware decoding or a DRM path to supported status before display handoff,
codec, performance and cleanup evidence exists on the Deck.

The audio-route service owns speaker, wired and Bluetooth selection. Route loss
pauses playback and never silently falls back from private headphones to the
speaker. Video acquires display and audio as one admitted bundle; partial
acquisition cannot begin playback.

## Node Media provider

Node playback is a primary source class, not a special case inside the UI. A
paired and authorized Node exposes paginated media records with opaque identities
and compatibility metadata. Selecting one requests a short-lived, read-only
ticket for exactly that item and, when chosen, a subtitle track.

The Node may offer either:

- a direct byte-range stream of an already compatible object; or
- an explicitly identified prepared/transcoded representation suitable for the
  Deck's accepted decode envelope.

The owner’s original remains unchanged. A prepared representation records its
relationship to the selected item and reports whether seeking is available.
Transcoding is Node work with its own admission, progress, cancellation and
resource policy; the Deck must not report `buffering` when the Node is actually
still preparing media.

The Deck uses bounded HTTP buffering and range requests where supported. It does
not download the whole item before playback. The initial reconnection behavior
is:

1. retain the last durable position;
2. enter `reconnecting` with an explicit cause;
3. retry with bounded exponential backoff while the Node identity and grant
   remain valid;
4. request a fresh ticket, then seek to the retained position if supported; and
5. end as `unavailable` with Retry and Return actions when the retry budget is
   exhausted.

Revocation, unpairing or Node shutdown invalidates tickets and stops delivery.
Retries cannot silently create a new trust relationship. Public or hostile
networks require mutually authenticated encryption and pinned Node identity;
the existing unencrypted development link is not production acceptance.

## Online provider adapters

An online adapter performs service-specific discovery and resolution. It never
becomes the decoder and does not receive storage, display or audio authority.
The common engine sees only the normalized source description.

Adapters must declare:

- provider identity and protocol version;
- whether search, direct-open or authenticated access is implemented;
- domains and redirect policy;
- required network and credential capabilities;
- URL lifetime and refresh support;
- available variants, tracks and subtitles; and
- rate, retry and cancellation behavior.

Credentials remain in a protected provider or trusted Node, never in a media
description or cartridge. A provider refreshes an expiring locator through the
opaque refresh reference. The decoder cannot follow an arbitrary refresh URL.

The initial conformance test uses a controlled HTTP(S) fixture with seekable and
non-seekable variants. A YouTube adapter is later work and must be independently
maintainable or replaceable as its supported interfaces change.

## Buffering and resource policy

Playback is tier 1 foreground work. Node communication that directly sustains
active playback is admitted with that session; discovery and unrelated transfer
remain lower priority. Power and hardware-immediate work remain tier 0.

Buffers are bounded by bytes and media time. Initial sizes are measurements to
select, not frozen promises. The service reports at least:

- decoder input queue depth;
- estimated buffered media time when knowable;
- download or read throughput;
- dropped video frames and audio underruns;
- A/V offset;
- decoder and total session memory high-water marks; and
- reconnect and seek completion time.

If playback and download cannot both fit, active playback is preserved and the
download is paused according to `RESOURCE_CONTENTION_0.md`. The player may choose
a lower advertised Node or online variant only through an explicit quality
policy; it must not silently substitute unrelated content or claim uninterrupted
quality.

## Pocket Mode and persistence

Audio is an allowed Pocket Mode continuation class. The display, visible view,
artwork, indexing and unrelated work stop while the media session, selected
route and required source connection remain. Wi-Fi stays active only for a Node
or online source. Video does not continue with the screen off unless a later,
explicit **continue audio only** transition is designed.

Resume state is private internal data and contains media identity, source class,
durable position, selected tracks and a bounded timestamp. It contains no path,
ticket, URL or credential. Checkpoints occur at meaningful transitions and
bounded intervals rather than every progress update. Missing source, changed
generation and expired tickets remain distinguishable on restore.

## Capability and failure boundaries

The first vocabulary should be derived from the live capability registry and
kept narrow. Required distinctions include:

- browse a named media collection;
- read one selected local media object;
- use one authorized Node media object;
- ask one enabled online provider to resolve an item;
- acquire the selected audio route;
- acquire the foreground video display lease; and
- retain an admitted audio session in Pocket Mode.

Discovery or pairing grants none of these automatically. A media cartridge
cannot authorize its own network destination or output. The Semiotic Engine is
not in the deterministic playback, permission or recovery path.

Failures must identify the responsible boundary: source unavailable, grant
revoked, ticket expired, network interrupted, preparation pending, unsupported
format, decoder failure, output lost, display unavailable or resource admission
denied. `No media found` is never substituted for a provider or storage failure.

## Implementation sequence

1. **Contract complete:** define the versioned library and session messages over
   `IPC_ENVELOPE_0` and map them to Foundation 0 identities and grants. See
   `MEDIA_IPC_1.md`; the first library and session broker cores now enforce it in
   host tests, while production socket/service wiring remains.
2. **Core host slice complete:** adapt the local-media catalog to External
   Storage 0 logical records and contained read handles. Source and host tests
   pass; the storage service now has a same-namespace lifecycle seam, while
   production construction/socket activation and removal of legacy direct
   application traversal remain. See `docs/MEDIA_LIBRARY_1_IMPLEMENTATION.md`.
3. **Session core complete:** the decoder-independent acknowledged state machine
   and broker pass host tests. See `docs/MEDIA_SESSION_1_IMPLEMENTATION.md`.
4. **Engine direction adopted:** use GStreamer for audio-only sessions, mpv for
   complete video-plus-audio sessions, and retain FFmpeg as fallback evidence.
   Apply the high-water buffering and synchronization contract in
   `MEDIA_ENGINE_ADAPTER_1.md`.
5. Evolve `guide-audio` into the acknowledged audio session path and verify
   speaker, wired, Bluetooth and Pocket Mode behavior.
6. Build the mpv DRM/private-IPC probe and compare it with the existing FFmpeg
   path on the physical Deck before accepting the mpv video adapter.
7. Put existing Node listing and ticket behavior behind the Node Media provider;
   add bounded range streaming, interruption and revocation tests.
8. Implement the native Audio and Video views against recorded session fixtures,
   then the real services.
9. Add the controlled online-stream provider fixture and prove the same video
   session can play it without provider-specific player code.
10. Run image verification, then physical acceptance for local storage, Node and
   online-fixture playback before declaring the pre-0.4.0 gate complete.

## Acceptance evidence

Source tests and image inspection are necessary but not physical proof. The
pre-0.4.0 claim requires repeated hardware evidence for:

- external-card audio and video open, seek, pause, resume, end and removal;
- Node direct stream and prepared stream, including seek and subtitle ticket;
- interruption, bounded reconnect, revocation and Node shutdown;
- one controlled online stream using the same player service;
- display handoff and restoration without stale frames or console text;
- speaker, wired and Bluetooth routing without unintended fallback;
- Pocket Mode audio with measured wakeups and current draw;
- corrupt, truncated, unsupported and expired inputs;
- decoder crash/hang cleanup and immediate Power responsiveness; and
- CPU, memory, temperature, frame drop, underrun and A/V synchronization data.

Passing these tests establishes the service boundary and the measured baseline
formats. It does not establish universal codec support, production YouTube
support, hardware decoding or safe use over an untrusted network.
