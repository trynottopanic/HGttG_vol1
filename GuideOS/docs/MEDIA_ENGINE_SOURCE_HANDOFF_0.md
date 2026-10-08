# Media Engine source handoff 0

Date: 26 September 2026.

Status: steps 1–4 source-staged and host-tested. Stop before step 5. This handoff
does not authorize image assembly, dependency installation, seed writing or a
claim of physical playback.

## Adopted result

- GStreamer owns audio-only sessions.
- One mpv process owns video and its associated audio clock.
- FFmpeg remains fallback/diagnostic evidence.
- Startup and recovery use bounded high-water buffering; smooth synchronized
  presentation is preferred over immediate start.

## Step 1 — provider grant validation

Foundation now defines `guide.broker.provider` 1.0 on the restricted
`/run/guideos/brokers/provider.sock`. The separate systemd socket is group-owned
by `guide-providers`; ordinary `guide-apps` cannot connect. A trusted provider
submits the kernel-authenticated peer PID/UID/GID, grant and capability code.
The capability broker resolves that peer through Supervisor and returns the
resolved instance identity and generation only when the grant matches.

Capability codes 6–8 cover media browse, source open and session control. The
cartridge verifier and language-neutral application profile recognize them with
an eight-capability manifest bound.

The Python `ProviderGrantValidator` verifies that Foundation's returned identity
matches the peer pinned by the provider. Library and session brokers use this
path when supplied, retaining the in-memory grant store only for host fixtures.

## Steps 2–3 — adapters

`buffer_policy.py` owns local, Node and online low/high-water thresholds and byte
ceilings. `gst_audio_adapter.py` and `mpv_video_adapter.py` translate the shared
Media Session engine contract. Media Session now acknowledges `BUFFERING` when
an engine cannot present yet and exposes a refresh transition to `PLAYING` only
after the adapter reaches high water.

`mpv_backend.py` constructs a no-config, software-decode-first supervised mpv
process. It inherits only the selected media descriptor, uses a private random
JSON-IPC socket, selects audio as the A/V clock, enables late-video dropping and
bounds graceful/terminate/kill shutdown. Its status adapter reports cache time,
dropped frames and A/V offset.

The existing GStreamer worker source now uses a 750 ms minimum threshold inside
a one-second/2 MiB non-leaky queue. This replaces its historical 250 ms queue in
source. Runtime GStreamer validation still belongs to the image/physical phase.

## Step 4 — source evidence

Passed in WSL/Linux:

- Media package: 22 tests.
- External Storage: 19 tests.
- Installer: 27 tests.
- IPC production preparation: 7 Python tests, C transport and generated registry.
- Foundation: core, sanitized core, codec, systemd adapter, nine Python tests,
  broker compilation and systemd unit verification.

Fixtures cover low/high-water startup, underrun/rebuffer, seek flushing,
one-clock mpv arguments, late-frame policy, bounded stop, session BUFFERING
acknowledgement and provider-returned peer identity binding.

The host lacks the GStreamer GI namespace, so the changed native audio worker was
syntax-reviewed but not executed in this environment. That is an explicit image
integration requirement, not a passed test.

## Step 5 handoff requirements

The build conversation should:

1. rebase onto the exact returned seed and preservation-audit it;
2. regenerate/build ARM64 IPC and Foundation artifacts after the provider
   interface change;
3. install the new provider socket and create `guide-providers`;
4. add the intended media provider service account to `guide-providers` without
   adding application accounts;
5. stage a pinned Debian arm64 mpv package and record its complete dependency and
   installed-footprint set;
6. run the media source installer and updated storage/audio packages;
7. run generated-registry checks, systemd verification and installed-layout
   tests in the candidate root;
8. exercise GStreamer prebuffering and mpv JSON IPC with controlled fixtures;
9. stop for owner approval before any seed write; and
10. treat image success separately from physical display, audible output,
    underrun and A/V synchronization acceptance.

The first physical mpv probe must remain software-decode-first. It must measure
DRM acquisition/restoration, startup buffer time, underruns, dropped frames,
maximum A/V offset, Power responsiveness, memory, CPU and temperature before
hardware decode or mpv acceptance.

## Image integration follow-up

The owner subsequently authorized image assembly and Seed installation in the
build chat. That later authorization supersedes the source-handoff stop above.
The resulting integration, engine evidence and remaining service/UI boundaries
are recorded in [Notepad and media image handoff 0](NOTEPAD_MEDIA_IMAGE_HANDOFF_0.md).
Physical playback remains unaccepted until tested on the Deck.
