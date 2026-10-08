# Live capability registry 0

Status: proposed architecture, 21 September 2026. This document does not implement
a registry or assert that the running device provides the capabilities below.
Names and records are provisional. Existing application behavior is evidence for
requirements, not evidence that a broker currently enforces them.

## Purpose and boundaries

The registry answers: what functions can this installation supply now, through
which providers, under what constraints, and what has changed?

The capability broker answers: may this application instance use a function,
for which purpose and objects, and for how long? The supervisor decides whether
the required providers can run within available resources. These are separate
responsibilities; they may initially share one lightweight implementation.

Discovery never grants access. An installed decoder is not proof that a file
will decode; a connected display is not proof that an application owns it;
writable storage is not proof that a checkpoint has been saved durably.

The owner controls standing policy and explicit exceptions. Neither applications
nor provider advertisements can grant themselves authority. Discovery responses
are filtered by caller: private device names, remote identities, and paths need
not be disclosed to every application.

## Initial vocabulary

Use a tree for browsing capability families. Use typed relationships to express
which providers and endpoints can actually work together. Do not make every
codec a child of every speaker, or treat a broad parent as a wildcard permission.

```text
output
  visual.surface          present pixels to a selected display
  audio.playback          send decoded audio to a selected audio endpoint
input
  actions                 receive semantic navigation/game actions
  text                    receive text entry
content
  selected.read           read owner-selected content and scoped companions
storage
  private                 read/write application-private persistent state
media
  decode                  turn specified encoded tracks into raw audio/video
  subtitles.render        present supported subtitle cues with video
communication
  local.channel           communicate between owned application components
network
  http.request            make policy-scoped HTTP(S) requests
companion
  discover                look for nearby Guide providers
  session                 use an owner-authorized companion session
  media.read              retrieve a selected companion media object
knowledge
  search                  search a specified knowledge source
  read                    retrieve an identified document
interpretation
  text.summarize          summarize explicitly supplied text
system
  diagnostics.read        obtain a bounded, redacted diagnostic snapshot
  connectivity.manage     configure owner-approved connections
  power.request           request a system power transition
```

This is an initial vocabulary, not a mandatory installation feature list.
No display, network connection, decoder, or model is required merely to implement
the registry. Keyboard, touch, controller and speech adapters may eventually
provide the same semantic input interface; existing apps must be adapted before
such substitutions work. Rich rendering and remote transcoding can be added as
providers later; their discovery must not imply that local applications already
support them.

Capabilities have major interface versions. Concrete formats, dimensions,
sample rates, source identities and limits are properties or constraints, not
unbounded numbers of new capability names. Unknown names or incompatible major
versions are unsupported, never silently treated as equivalent.

## Four records

### Capability definition

Contains the stable name and interface version, plain-language meaning,
property names and units, request constraints, permission scopes, and allowed
sharing modes. For example, visual dimensions are pixel integers; audio rates
are samples per second. Unknown values are explicitly unknown, not zero or
unlimited. Range semantics must distinguish continuous ranges from discrete modes.

### Provider offer

Contains an opaque offer ID; owning service/application instance; capability
and interface version; endpoint ID when applicable; properties; dependencies;
local/remote location; observation evidence; revision; and live status.

Statuses: unknown, starting, ready, degraded, unavailable, failed. Occupancy is
separate: a ready display may be exclusively leased. Permission is also separate:
a ready microphone or network service may be denied to this caller.

Evidence distinguishes configured, provider-declared, probed, and recently
exercised support. A filename extension or installed executable alone must not
be advertised as verified end-to-end playback support. Keep specific failures
scoped to the attempted input/mode unless evidence supports a broader failure.

The supervisor registers trusted local provider identities. Dynamic providers
report through authenticated, scoped registration channels; remote advertisements
are untrusted until validated by an authorized companion adapter. Applications
cannot publish fictitious system-device offers.

### Application requirement

Contains application identity, feature identity, required capabilities and
constraints, human explanation, acceptable alternatives, and the behavior on
denial or loss. Requirements support all-of and any-of groups. Optional features
have their own required groups rather than one ambiguous importance number.

Separate required-for-this-feature from preferred quality. An unmet requirement
blocks that feature; an unmet preference may select an explicitly supported
lower-quality mode. Unsupported fallback code cannot be invented by negotiation.

Resource estimates belong here by reference to the resource contract. They are
not grants and should remain unknown until measured rather than fabricated.

### Runtime grant

Contains an opaque grant ID, application instance, feature, chosen offer IDs,
object scope, allowed operations, negotiated settings, resource-grant reference,
sharing mode, lifetime, and revocation behavior. Clients receive usable handles
through the broker; private paths and credentials are not registry properties.

Enforcement is explicit: enforced, cooperative-only, or unavailable. A caller
requiring enforced isolation must not receive a cooperative grant as a substitute.
Do not describe a token as enforcing access while legacy programs can bypass it.

## Example offer and requirement

Illustrative values below are not measurements of the current Deck.

```json
{
  "offerId": "display-primary-surface",
  "providerId": "platform-display",
  "capability": "output.visual.surface",
  "interfaceMajor": 1,
  "endpointId": "display-primary",
  "revision": 12,
  "status": "ready",
  "properties": {
    "widthPx": 640,
    "heightPx": 480,
    "pixelFormats": ["xrgb8888"],
    "refreshHz": null,
    "sharingModes": ["exclusive"]
  },
  "evidence": "probed"
}
```

An adapted media application might express its local audio feature as:

```json
{
  "feature": "local-audio-playback",
  "requires": {
    "allOf": [
      {"capability": "content.selected.read", "scope": "selected-media-item"},
      {"capability": "media.decode", "constraintsFrom": "selected-audio-track"},
      {"capability": "output.audio.playback", "constraintsFrom": "decoder-output"}
    ]
  },
  "optionalFeatures": [
    {
      "feature": "remember-position",
      "requires": {"allOf": [
        {"capability": "storage.private", "purpose": "recovery-position"}
      ]},
      "onUnavailable": "Offer playback with an explicit position-will-not-be-saved notice."
    }
  ]
}
```

Matching must verify that the selected decoder's output fits the endpoint, or
select an available conversion provider. The existence of both offers alone is
insufficient. Codec, profile, dimensions, channels and other relevant constraints
are checked for the selected content. Actual playback can still fail and must
produce a specific runtime result.

## Requests suggested by current applications

These are proposed declarations based on source inspection. They do not claim
that the existing applications already accept negotiated handles or all fallbacks.

| Application/feature | Baseline request | Additional request and fallback |
| --- | --- | --- |
| Wikipedia saved reading | visual surface, navigation actions, private article store | Online search/read adds knowledge provider or scoped HTTPS adapter; offline mode keeps saved articles. A missing store is distinct from an empty store. |
| Wikipedia rich view | visual surface, input, owned local channel, installed renderer/runtime | Images need separately scoped fetching and decoding; text mode is an alternate implementation that must be explicitly selected. |
| General browser local home | visual surface, actions/text input, owned local channel, browser runtime and profile storage | External navigation requests HTTP(S) according to owner browsing policy. Unlike Wikipedia, a general browser cannot use one fixed destination allowlist. Per-site grants can follow user navigation without granting network administration. |
| Local audio playback | selected content read, compatible audio decoder, audio playback, playback controls | Private state enables resume. Bluetooth is an alternate endpoint, not a requirement to configure Bluetooth hardware. |
| Local video playback | selected content read, compatible video decoder, visual surface, controls | Sound adds audio decoding/output; subtitles add selected sidecar access and cue rendering. Silent playback is an explicit supported choice, not a hidden fallback. |
| Companion media playback | authorized companion session and selected media read, plus the relevant local playback requirements | Conversion on the Node is a separate remote offer with data-transfer, cost and cancellation policy. Local media remains independent of companion availability. |
| Doom/emulation | visual surface, game input, selected game data, compatible installed core/runtime | Audio when available; private storage for saves; selected firmware for cores requiring it. No networking requirement for current local play. No claim of general save-state support merely because battery saves exist. |
| Node Link | companion discovery and an authorized session | Capability inspection and selected media use are separate operations. Session authorization does not permit arbitrary remote execution. |
| Semiotic Engine client | authorized summarization provider and explicitly selected text | Entirely optional to reading; unavailable service leaves the source readable. No implicit tools, document search, or permission to retain supplied text. |
| Owner interface | suitable presentation/input providers for its installed implementation | Connectivity management, diagnostics and power requests are separate system grants. Ordinary applications do not inherit them. |

Source observations requiring adaptation:

- Browser and rich Wikipedia launchers currently configure loopback themselves
  and use fixed local ports. The system should supply a private local channel;
  applications should not need permission to administer network interfaces.
- These renderers currently launch with 640x480 arguments. This is an adapter
  constraint, not the hardware floor for GuideOS.
- Doom/emulation directly opens framebuffer, input and ALSA devices. A discovery
  record alone cannot enforce their access: migration needs brokered handles or
  an explicitly constrained legacy execution mode.
- Media supports periodic resume saving today. That is not proof that all
  applications implement checkpoint acknowledgments.
- A speech-only Wikipedia experience is a possible future feature, not an
  available fallback inferred from the existence of an audio endpoint.

## Minimal live operations

1. **Snapshot:** return a filtered capability inventory and its revision.
2. **Resolve:** evaluate a feature request against offers and policy; return a
   proposed compatible bundle, missing requirements, and consent/resource needs.
   This does not reserve devices or execute work.
3. **Acquire:** revalidate the proposal and obtain broker-authorized grants and
   supervisor resource allocations. For a required bundle, complete it or roll
   back provisional acquisitions. Do not retain a display while waiting
   indefinitely for another required capability or owner consent.
4. **Watch:** receive bounded changes after a revision: offer changed/removed,
   grant revoked, or resnapshot required. Reconnect with a snapshot if events
   were missed; never assume a missed event means continued availability.
5. **Release:** relinquish a grant idempotently; cancel caller-owned work and
   release its accounting without shutting down a shared provider used by others.

Requests carry IDs, deadlines and interface versions. Replies distinguish
unsupported, temporarily unavailable, occupied, consent required, denied,
resource unavailable, stale proposal, and provider failure. Enumeration order
must not determine provider choice. Apply owner preference, required constraints
and resource feasibility; ask when alternatives materially change disclosure or
cost. Never silently move private processing to a remote provider.

A changed registry revision alone does not invalidate every existing grant.
Track affected offers and revalidate relevant constraints. New acquisitions
cannot reuse an endpoint incarnation that disappeared and was replaced.

## Loss, revocation and preservation

Providers disappear on disconnect, failure, removal or supervised exit. Remote
offers expire without renewed validation. Persistent discovery caches are hints,
not proof of availability after reboot. Keep bounded records and bounded event
queues so a small device can implement the registry.

For a planned resource withdrawal, send a reason and deadline, request an
application checkpoint where appropriate, and record its acknowledgment through
the lifecycle contract. A storage grant records what durability the provider can
offer; a separate checkpoint result confirms whether a particular save succeeded.

Permission revocation can require immediate access removal. Saving must not
continue unauthorized network or content access. Preserve already-held work in
an authorized private recovery store when possible. A removed card or failed
device cannot be made available merely by giving an application more time.

Changing an audio route must not unexpectedly expose private playback through
speakers. Endpoint substitution follows owner policy and application support.
Release display/input leases on application exit; preserve a system control path
for the owner independently of an application's exclusive presentation lease.

## First implementation boundary

Start with a read-only in-memory registry and bounded snapshot/watch interface.
Populate it using adapters for display, input, audio route, private storage,
selected local content, installed media decoder and companion connectivity.
Keep code and schema independent of the RG35XX H adapter. Avoid making Python,
networking, a graphical interface, or any particular hardware mandatory merely
to host the registry. JSON examples are inspectable design notation, not a
decision that the transport or implementation must use JSON.

Add resolution reports for the current applications before changing launch
behavior. They should explain what is known, unknown, unavailable and still
unenforced. Integrate acquire/release with supervisor application identities
next, then migrate one application through brokered access and change events.

Initial meaningful checks: a local player does not require network access;
headphone removal respects private-audio policy; format recognition alone does
not guarantee decoding; a card removed between resolve and acquire fails cleanly;
two exclusive display requests cannot both succeed; full recovery storage is
reported as a failed save; restarting the registry cannot resurrect stale grants.

## Inspected implementation references

- `package/guide-supervisor/src/guide_supervisor_protocol.h`
- `package/guide-supervisor/src/guide-supervisor.c`
- `package/guide-hello-fb/src/guide-hello-fb.c`
- `apps/browser/guide-web-browser`
- `apps/wikipedia/guide-wikipedia-rich`
- `apps/wikipedia/guide_wikipedia_store.py`
- `apps/doom/guide_doom_frontend.c`
- `apps/emulation/README.md`
- `apps/node_link/guide_node_bridge.py`
- `apps/node_link/guide_node_client.py`
- `LOCAL_MEDIA_PLAYER_0.md`
- `SEMIOTIC_ENGINE_PROTOCOL_0.md`
- `CARTRIDGE_FORMAT_1.md`
- `FUTURE_FRAMEWORK_0.md`
