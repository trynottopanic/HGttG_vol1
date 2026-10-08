# GuideOS Media IPC 1

Status: initial executable interface contract, 26 September 2026. This specifies
messages and generated metadata for implementation. It does not claim that the
services are installed or physically verified.

## Boundary

Media IPC 1 defines two local Envelope 0 interfaces:

- `guide.media.library` 1.0 — paginated media discovery and trusted source open;
- `guide.media.session` 1.0 — acknowledged playback lifecycle and control.

Both use Unix `SOCK_SEQPACKET`, Envelope 0 framing and authenticated Foundation 0
connection identity. The interfaces carry control and bounded metadata only.
Media bytes move through a contained file descriptor or a provider-approved
stream directly to the supervised decoder.

The media application never receives a storage mount path, Node address, ticket,
resolved URL, credential or HTTP header. It selects an opaque `media_id`; the
trusted session service asks the library to open that identity after validating
the caller's grant and current availability generation.

## Common values

All maps use ascending unsigned integer keys. Unknown fields are rejected for
minor 0. Text limits are UTF-8 byte limits.

### Enumerations

```text
source_class:   1 storage, 2 node, 3 online
media_kind:     1 audio, 2 video
availability:   1 available, 2 checking, 3 preparing,
                4 unavailable, 5 incompatible, 6 failed
transport:      1 inherited read descriptor, 2 HTTPS stream
seekability:    0 unknown, 1 no, 2 yes

session_state:  1 resolving, 2 acquiring, 3 opening, 4 buffering,
                5 playing, 6 paused, 7 seeking, 8 reconnecting,
                9 unavailable, 10 failed, 11 checkpointing,
                12 stopping, 13 closed
```

IDs named `media_id`, `source_id`, `session_id`, `track_id`, `output_id` and
`open_id` are opaque 16-byte values. They are not interchangeable. A zero value
is invalid. Times use unsigned integer nanoseconds; media positions use unsigned
integer milliseconds to avoid floating-point CBOR.

### Media summary record

Returned inside a media-record array:

```text
{
  0: media_id bytes16,
  1: source_id bytes16,
  2: source_class uint,
  3: media_kind uint,
  4: display_name text <= 512,
  5: folder_display text <= 512,
  6: size_bytes uint or null,
  7: modified_ns uint or null,
  8: duration_ms uint or null,
  9: availability uint,
  10: availability_generation uint,
  11: compatibility uint,
  12: audio_track_count uint,
  13: subtitle_track_count uint
}
```

At most 32 summaries appear in one reply. `compatibility` is 0 unknown,
1 compatible with current measured offers, or 2 unsupported. Recognition by
extension alone produces unknown, never compatible.

### Track record

```text
{
  0: track_id bytes16,
  1: kind uint,                 # 1 audio, 2 subtitle
  2: display_label text <= 128,
  3: language text <= 32 or null,
  4: selected bool,
  5: external bool
}
```

At most 32 tracks are returned. Labels are provider data constrained for display;
they are not paths and are not copied to diagnostics.

## `guide.media.library` 1.0

Endpoint: `/run/guideos/brokers/media-library.sock`.

### Operation 1 — `SNAPSHOT`

Grant: `media.library.browse`.

Arguments:

```text
{0: grant_id bytes16}
```

Result:

```text
{
  0: library_revision uint,
  1: source_count uint,
  2: available_item_count uint,
  3: incomplete bool
}
```

Counts are bounded observations, not proof that every source has been fully
indexed. `incomplete` is true while discovery or indexing remains in progress.

### Operation 2 — `LIST`

Grant: `media.library.browse`. Cancellable.

Arguments:

```text
{
  0: grant_id bytes16,
  1: after_media_id bytes16 or null,
  2: limit uint,                       # 1..32
  3: source_class uint or null,
  4: media_kind uint or null,
  5: source_id bytes16 or null
}
```

Result:

```text
{
  0: library_revision uint,
  1: records array<media-summary>,
  2: more bool
}
```

Ordering is stable for one library revision. A stale cursor receives `STALE`
and the client takes a new snapshot; an empty array is reserved for a successful
empty page and never represents provider failure.

### Operation 3 — `DESCRIBE`

Grant: `media.library.browse`. Cancellable.

Arguments:

```text
{0: grant_id bytes16, 1: media_id bytes16, 2: availability_generation uint}
```

Result:

```text
{
  0: media_summary map,
  1: tracks array<track-record>,
  2: seekability uint,
  3: preparation_state uint,
  4: preparation_progress_per_mille uint or null
}
```

Preparation progress is 0..1000 and only describes a separately admitted Node
preparation job. It is not reported as playback buffering.

### Operation 4 — `OPEN`

Grant: `media.source.open`. Cancellable. This operation is intended for the
trusted media-session service, not ordinary media views.

Arguments:

```text
{
  0: grant_id bytes16,
  1: media_id bytes16,
  2: availability_generation uint,
  3: requested_audio_track bytes16 or null,
  4: requested_subtitle_track bytes16 or null
}
```

Result:

```text
{
  0: open_id bytes16,
  1: transport uint,
  2: expires_boottime_ns uint or null,
  3: seekability uint,
  4: source_private_record map or null
}
```

For transport 1, exactly one `SCM_RIGHTS` descriptor is attached with role
`media-read`. It is a close-on-exec, read-only regular file already contained
under the authorized storage generation. `source_private_record` is null.

For transport 2, no descriptor is attached. `source_private_record` contains a
bounded locator and headers readable only by the trusted media-session provider.
It must never be reflected through the session interface, diagnostics or UI.
Only HTTPS is accepted in minor 0. Expiry is required.

### Operation 5 — `WATCH`

Grant: `media.library.browse`. Cancellable and normally held on a separate
connection from ordinary requests.

Arguments:

```text
{0: grant_id bytes16, 1: after_revision uint}
```

The initial reply confirms the current revision. Later events are:

```text
1 LIBRARY_CHANGED       {0: library_revision uint, 1: change_class uint}
2 SOURCE_STATE_CHANGED  {0: library_revision uint, 1: source_id bytes16,
                         2: availability uint}
3 RESNAPSHOT_REQUIRED   {0: library_revision uint}
```

No event contains private filenames, paths, addresses or locators.

## `guide.media.session` 1.0

Endpoint: `/run/guideos/brokers/media-session.sock`.

The session service uses the authenticated connection context plus the supplied
grant. A caller may control only sessions owned by its application instance.
The shell uses a separately authorized system-control path for Power and global
display recovery; it does not impersonate the application.

### Operation 1 — `OPEN`

Grant: `media.session.control`. Cancellable.

Arguments:

```text
{
  0: grant_id bytes16,
  1: media_id bytes16,
  2: availability_generation uint,
  3: requested_audio_track bytes16 or null,
  4: requested_subtitle_track bytes16 or null,
  5: requested_output bytes16 or null,
  6: resume_position_ms uint or null
}
```

Result:

```text
{0: session_id bytes16, 1: state uint, 2: state_revision uint}
```

The service resolves the media identity, acquires the required admitted resource
bundle and asks the library to open the source. A returned session may still be
opening or buffering. Partial display/audio acquisition is rolled back.

### Operations 2–9 — acknowledged controls

Every control supplies:

```text
{0: grant_id bytes16, 1: session_id bytes16, 2: expected_state_revision uint}
```

Operations and additional fields:

```text
2 PLAY
3 PAUSE
4 SEEK              key 3 target_position_ms uint
5 SELECT_AUDIO      key 3 track_id bytes16
6 SELECT_SUBTITLE   key 3 track_id bytes16 or null (null means off)
7 SET_OUTPUT        key 3 output_id bytes16
8 CHECKPOINT
9 STOP
```

`STOP` is idempotent. Other controls return `STALE` when the expected revision no
longer matches. A successful result is:

```text
{0: state uint, 1: state_revision uint, 2: position_ms uint}
```

`OK` means the transition was acknowledged by the responsible engine/output,
not merely queued. If the deadline expires before acknowledgement, the reply is
`DEADLINE_EXCEEDED`; later events report the actual state.

### Operation 10 — `SNAPSHOT`

Grant: `media.session.control`.

Arguments:

```text
{0: grant_id bytes16, 1: session_id bytes16}
```

Result:

```text
{
  0: state uint,
  1: state_revision uint,
  2: position_ms uint,
  3: duration_ms uint or null,
  4: buffered_ms uint or null,
  5: selected_audio_track bytes16 or null,
  6: selected_subtitle_track bytes16 or null,
  7: selected_output bytes16 or null,
  8: source_class uint,
  9: failure_class uint or null
}
```

### Operation 11 — `WATCH`

Grant: `media.session.control`. Cancellable and normally held on its own
connection.

Arguments:

```text
{0: grant_id bytes16, 1: session_id bytes16, 2: after_state_revision uint}
```

Events:

```text
1 STATE_CHANGED       {0: session_id, 1: state, 2: state_revision}
2 POSITION_CHANGED    {0: session_id, 1: position_ms, 2: state_revision}
3 BUFFERING_CHANGED   {0: session_id, 1: buffered_ms or null,
                       2: state_revision}
4 TRACKS_CHANGED      {0: session_id, 1: state_revision}
5 SOURCE_LOST         {0: session_id, 1: failure_class, 2: state_revision}
6 OUTPUT_LOST         {0: session_id, 1: failure_class, 2: state_revision}
7 RESNAPSHOT_REQUIRED {0: session_id, 1: state_revision}
```

Replaceable position and buffering events may coalesce. State transitions,
revocation, source/output loss and resnapshot requirements may not be silently
dropped.

## Revocation, cancellation and cleanup

- Revoking browse access stops new listing and description operations.
- Revoking source access prevents new opens and begins the source-specific
  bounded release procedure for an existing open.
- Revoking session control prevents application commands but does not remove the
  system's Power and recovery authority.
- Application exit invalidates its sessions and grants. The Supervisor requests
  checkpoint, stops the decoder process group and releases display/audio leases.
- Cancelled list/describe/open work has no durable side effects. Cancellation of
  a control returns `CANCELLED` only if the transition was prevented.
- A local descriptor that cannot be recalled receives the documented release
  deadline; failure to release permits Supervisor termination.

## Generated registry boundary

`package/guide-ipc/schema/interfaces.json` is the checked-in registry source for
interface names, versions, operations, grants, top-level field types, descriptor
roles and event codes. `tools/generate.py` deterministically regenerates C,
Python, fixtures and readable interface tables.

The generated registry validates the common top-level shape. Service code must
also validate every nested record, enumeration, count and byte limit specified
here before using it. Generated metadata does not grant authority or prove that
the service exists.

## Initial validation requirements

- Generated outputs reproduce exactly.
- Operation and event codes are unique and nonzero.
- Unknown minor-0 fields, invalid opaque IDs and out-of-range limits fail.
- `LIST` cannot exceed 32 records or confuse empty success with unavailable.
- Only library `OPEN` may return a media descriptor, and its descriptor count
  matches transport.
- Session controls reject wrong owner, grant, session or state revision.
- Stream-private records never appear in session replies, events or diagnostics.
- Event loss produces `RESNAPSHOT_REQUIRED`.
- Broker restart requires reconnection and grant revalidation.
