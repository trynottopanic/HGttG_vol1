# Media Session 1 implementation evidence

Date: 26 September 2026.

## Implemented boundary

The first decoder-independent Media Session 1 control core and Envelope 0 broker
are under `package/guide-media/`.

Implemented:

- opaque, owner-instance-bound session identities;
- bounded concurrent sessions and bounded event history;
- acknowledged open, play, pause, seek, track, output, checkpoint and stop;
- expected-revision checks on every mutating operation;
- explicit state, position, track and resnapshot events;
- resource-admission acquisition and deterministic release;
- descriptor closure after the trusted engine accepts a source;
- rollback when open fails and cleanup when an application instance exits;
- Foundation peer and `media.session.control` grant enforcement; and
- WATCH catch-up delivery over Envelope 0 without exposing source descriptors to
  the media view.

The state machine does not select a decoder. Engines and admission/checkpoint
providers are injected, keeping mpv, FFmpeg, audio routing and future Node
sources behind the same session contract.

## Validation

Linux/WSL results:

- combined Media Library/Session package suite: 14 tests passed;
- External Storage 0 suite: 19 tests passed; and
- IPC production-preparation: 7 Python tests, C transport and generated-registry
  checks passed (`GUIDE_IPC_PRODUCTION_PREP_PASS`).

Tests cover normal acknowledged lifecycle, stale revision rejection, wrong-owner
rejection, failed-open rollback, owner-exit cleanup, bounded resnapshot behavior,
broker open/play/snapshot/watch flow and grant denial.

## Evidence limit and next work

The session core is now included in the media source-install layout, but no
session unit or socket is enabled. It is not image-verified or physically
accepted. It does not yet include a real decoder process, output
broker, checkpoint persistence, systemd/socket units, continuous live event
subscriptions, source-loss recovery or Pocket Mode behavior.

The split engine direction is selected: GStreamer for audio-only and mpv for a
video item's synchronized video and audio, with FFmpeg retained as fallback.
The next boundary is to implement those adapters under
`MEDIA_ENGINE_ADAPTER_1.md`, add Foundation's trusted provider-side
grant-validation channel, then activate the session unit. Backend acceptance
remains dependent on physical Deck evidence.
