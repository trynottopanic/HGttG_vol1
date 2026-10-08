# Application Streaming 0

Application Streaming 0 is the first reusable framework for viewing a program
running on a desktop Node from a Deck. Magic: The Gathering Arena is the first
target example; Discord and other applications use the same session protocol
rather than receiving special access to the Deck.

## Person-visible flow

1. The Node owner chooses a specific Windows `.exe` and identifies its window.
2. A paired Deck can see the application's name, but never its private path.
3. The Deck requests a temporary session.
4. The Node shows which Deck requested which application. Nothing launches
   until the person at the Node approves it.
5. After approval, the Node launches that exact executable without a shell and
   offers a short-lived 640×480 H.264/MPEG-TS view of that window.
6. Either device can close the session. Sessions also expire automatically.

## Present implementation boundary

The control plane, registration, local approval, application launch, session
ownership, expiry, close operation, and Windows FFmpeg capture command are
implemented. The Deck-side protocol can list, request, inspect, display, and
close these sessions. A person-facing Deck menu, a physical low-latency video
test, and a bounded input adapter are the next milestone.

Input is deliberately disabled in this build. A streamed session does not
grant keyboard, mouse, command, filesystem, clipboard, microphone, or general
desktop access. Later input adapters will translate a small, documented Deck
control vocabulary for each application class and will require their own
adversarial tests before activation.

## Why Arena runs on the Node

The RG35XX H cannot practically run the current Android or Windows Arena client
locally: its memory, graphics stack, architecture, and anti-tamper assumptions
do not match that software. Running the official client or an Android emulator
on a sufficiently capable Node and streaming its window lets the Deck remain a
small interface. The same division also makes Discord feasible later while
keeping account credentials and heavyweight processing on hardware selected by
the user.

## Expansion contract

Every provider uses the same capabilities: list applications, request a
session, read its state, receive its media description, submit only supported
input events, and close it. Future transports or codecs may be negotiated
behind that contract without changing what a Deck means or granting a provider
new authority.

## NDI streaming framework direction — 2 October 2026

Status: implementation proposal following the owner's request to start the
framework. This section does not change the implementation boundary above or
claim working streaming in the 0.4.2.05 image. No Deck or Seed installation is
part of this design work.

NDI is the existing GuideOS desktop interface. Reuse its paired Node identity,
shared-library catalog and background jobs. The Node provides the source and
encoding; the Deck owns playback, output selection, navigation and its display
lease. The transport remains a replaceable implementation behind the existing
Media Surface and Remote Application Surface contracts.

### Sources and playback modes

| Source | Surface and behavior | First transport evaluation |
| --- | --- | --- |
| Shared video file | Media Surface: finite duration, pause, seek and resume checkpoint | Existing authenticated media tickets and HTTP range delivery |
| Live video/audio source | Media Surface: live timing, reconnect and no fabricated duration or seek | Separate live adapter after finite playback works |
| Registered application or game | Remote Application Surface: approved capture, synchronized audio and declared controller input | Sunshine/Moonlight adapter evaluation |

Treat codec conversion as a Node-owned preparation job. Reuse an existing
compatible file or cached prepared copy when possible; defer on-demand conversion
until cancellation, encoder limits and seek behavior are demonstrated. Start at
640×480 output and 30 fps, preserving source aspect ratio. H.264 with stereo
audio is the initial compatibility target, subject to actual decoder evidence.

### Shared ownership and session contract

The provider must describe supported source kinds, transports, codecs, output
sizes, frame rates, seek/pause support and input profiles. The Deck negotiates
one supported combination; it must not infer support from an open network port
or a paired Node alone. Use opaque source identities; desktop paths stay on the
Node. Network endpoints and credentials stay inside the provider/decoder boundary,
not in labels, logs or arbitrary shell commands.

Each session has one owner and generation. Its observable states distinguish
requesting/approval, opening, buffering, playing, paused where supported,
reconnecting, closing, closed and failed. Late callbacks cannot revive a closed
or replaced session. Bound concurrent jobs, encoded/decoded queues, retries and
shutdown work. A transient link failure is visible and cancellable; reconnect
does not silently restart another application or grant additional access.

The shell grants and recovers the existing display lease. The audio provider
continues to own the selected output and volume. Passive playback preserves A
for pause/resume and B for returning to the launching screen. Interactive
sessions use their declared input profile, with a separate system-owned exit;
ordinary game buttons cannot simultaneously become player navigation controls.
Disconnect/exit releases all held inputs and stops capture/decoding. Home and
Power retain their system behavior.

### Existing integration gaps

`node/desktop/guide_ndi.py` and the current Node server already support pairing,
shared folders, prepared media, tickets and range delivery. The native Deck
player currently opens storage-owned descriptors through
`package/guide-media/media_source_channel.py`; it needs a Node-source adapter
rather than arbitrary URL access added to the storage provider. Preserve the
existing local source path and its authority checks.

The old application path in `apps/node_link/guide_node_bridge.py` invokes a
prototype FFmpeg framebuffer player with audio disabled. It must not become the
production streaming path. Reuse application registration/approval where
appropriate, then give a native adapter explicit display, audio and lifecycle
ownership.

The current Node-media policy starts after five seconds of buffered content.
That is a media-continuity policy, not an interactive latency policy. Games need
bounded short queues, late-frame dropping and loss recovery instead of accumulating
seconds of latency. Choose interactive queue/bitrate targets through measurements.
The Mali compositor does not establish hardware video-decoder availability.

### Implementation order and acceptance

1. Extend the native media source boundary with a paired Node adapter. Browse
   one existing shared video, obtain a scoped ticket and play through the native
   player. Demonstrate pause, range-backed seek, resume, selected audio output,
   cancellation and return to the launching screen.
2. Exercise ticket expiry, Node shutdown, source removal, interrupted Wi-Fi and
   stale generations. Verify bounded cleanup and immediate shell recovery. Treat
   current unencrypted HTTP as a controlled local prototype; define authenticated
   encrypted delivery before wider-network operation.
3. Evaluate a Sunshine host and a Moonlight-compatible ARM64 client at 640×480,
   30 fps. Verify the actual Debian/board decoder, audio synchronization, selected
   capture boundary and controller support. Default desktop/monitor capture is
   not proof of the selected-window contract; any broader capture needs an explicit
   design decision. Report decode time, drops, per-core load and end-to-end input
   latency before choosing production settings.
4. Add one latency-tolerant registered game with a small controller profile.
   Test held-button release, cancellation, emergency exit, host loss and repeated
   display handoffs. Add pointer/keyboard profiles and demanding games only after
   their specific behavior is defined and validated.

The existing [framework streaming direction](FUTURE_FRAMEWORK_0.md#game-and-application-streaming-path)
already calls for Sunshine/Moonlight evaluation. Upstream identifies Moonlight
Embedded as an embedded-Linux client for Sunshine; this does not prove RG35XX H
support: [Moonlight Embedded](https://github.com/moonlight-stream/moonlight-embedded).
Sunshine provides the host transport and encoding:
[official documentation](https://docs.lizardbyte.dev/projects/sunshine/latest/).
