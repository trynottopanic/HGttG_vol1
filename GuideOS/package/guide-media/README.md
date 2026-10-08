# GuideOS Media Library 1 development slice

Status: host-tested read-only catalog, storage lifecycle adapter, Media Session
state machine and Envelope 0 broker cores. This package is not installed in a
seed image and is not physical Deck evidence.

`media_library.py` consumes a trusted External Storage 0 record and a root owned
by the storage provider. It performs a bounded scan beneath `GUIDE/MEDIA`, skips
links and non-media files, creates keyed opaque identities, paginates records and
revalidates generation, inode, size and modification time before returning a
close-on-exec read descriptor.

`media_library_broker.py` implements the SNAPSHOT, LIST, DESCRIBE and local OPEN
portion of `guide.media.library` 1.0 over Envelope 0. It resolves the peer through
Foundation 0 and validates the required runtime grant. WATCH, Node sources,
online sources, metadata probing and production socket wiring remain.

`storage_media_host.py` binds catalog refresh/invalidation to External Storage
0's insertion generation inside its private namespace. `media_session.py` and
`media_session_broker.py` provide owner-bound, revision-checked acknowledged
controls, bounded event catch-up, resource cleanup and grant-enforced IPC. A real
decoder engine, output service and installed service units remain open.

`install.sh` stages all production media modules. External Storage 0 invokes it
and constructs the catalog when `GUIDE_MEDIA_LIBRARY=1`; state identity and the
keyed-ID secret persist privately under `/var/lib/guideos-media`. No public media
socket or session service is activated until provider-side Foundation grant
validation and an engine adapter are present.

The selected adapters are now source-staged: `gst_audio_adapter.py` for
audio-only sessions and `mpv_video_adapter.py` plus `mpv_backend.py` for complete
video/audio sessions. `buffer_policy.py` supplies bounded high-water behavior;
`provider_grants.py` uses Foundation's restricted provider-validation socket.
See `../../docs/MEDIA_ENGINE_SOURCE_HANDOFF_0.md` for evidence and image-build gates.

The media view receives no mount path or descriptor. The eventual trusted media
session service will call OPEN and receive the descriptor.

Run the bounded host tests from WSL/Linux:

```sh
./run-tests.sh
```
