# Media Library 1 implementation evidence

Date: 26 September 2026.

## Implemented boundary

The first host-testable read-only implementation of `guide.media.library` 1.0 is
under `package/guide-media/`.

Implemented:

- bounded discovery beneath an authorized `GUIDE/MEDIA/` root;
- common initial audio/video extension recognition without claiming decode;
- opaque keyed 16-byte media identities;
- stable bounded pagination and source/kind filtering;
- storage insertion-generation and stale-cursor rejection;
- description records without physical paths;
- component-by-component no-follow opening;
- final device, inode, size and modification-time revalidation;
- close-on-exec, read-only descriptor transfer;
- Foundation peer resolution and grant validation in the Envelope 0 broker;
- SNAPSHOT, LIST, DESCRIBE and storage OPEN operations; and
- distinct absent, not-found, stale, denied and invalid outcomes.

External Storage 0 now publishes a non-secret insertion generation in its status
record. The generation changes when the observed card changes or is removed; a
transient retry of the same observed card retains the generation. Its service
loop also owns a media-host lifecycle seam in the same private mount namespace:
card transitions invalidate the catalog, recognized records refresh it, its
listener can join the bounded poll loop, and shutdown closes it before unmount.
The host keys refreshes by generation, state and recognized folders so an
invalidation and successful recognition in the same generation cannot be
mistaken for duplicates.

## Preserved boundary

The external card remains mounted inside the storage service's private mount
namespace. The implementation does not expose or weaken that mount. The catalog
is now shaped to be hosted by the storage owner; production construction of the
host, socket endpoint, persistent identity/key material and Foundation objects
still must be wired into the image. Applications must not receive the mount root.

The media application receives catalog records only. The future trusted media
session service, not the UI, calls OPEN and receives the media descriptor.

## Validation

Linux/WSL results:

- External Storage 0 suite: 19 tests passed.
- Combined Media Library/Session package suite: 14 tests passed.
- IPC production-preparation suite: 7 Python tests plus the C transport passed.

The media tests cover pagination, filtering, ignored links/non-media files,
private identities, absent storage, stale generations and cursors, changed-file
rejection, descriptor containment, broker grant enforcement and end-to-end
descriptor receipt over `SCM_RIGHTS`.

## Evidence limit and next work

This is source and host-integration evidence only. It does not establish an
installed broker, systemd/socket activation, physical exFAT behavior,
Node/online sources, library WATCH event delivery, metadata extraction or
playback.

The production storage package now installs the media cores, enables
`GUIDE_MEDIA_LIBRARY`, constructs the catalog in the storage process, and keeps
its opaque source identity and keyed-ID secret in a systemd-managed private
state directory. The application-facing library socket remains deliberately
gated until Foundation supplies provider-side peer-grant validation.

## Storage-owned socket candidate (27 September 2026)

Source now wires a systemd-owned `SOCK_SEQPACKET` endpoint at
`/run/guideos/brokers/media-library.sock` into the External Storage process.
The socket is limited to `guide-apps`; the storage owner receives access to the
restricted Foundation provider-validation socket through `guide-providers`.
Local peer credentials are treated only as pinned input. The Foundation
provider remains authoritative for resolving the process instance and binding
the requested grant.

The board installer now enables the socket, places `GUIDE_MEDIA_LIBRARY=1` on
`guide-storage.service` rather than the shell, and removes that environment
variable from the shell drop-in. The catalog, listener and read-only mount
therefore share one storage-owner lifecycle and private mount namespace.

Focused lifecycle and endpoint-construction tests pass, and the changed Python
sources pass syntax compilation. The broader Linux-only suite could not be
rerun in the current Windows host because it requires AF_UNIX sequential-packet
sockets, pidfds, `O_DIRECTORY`, symlinks and the WSL runtime, which was
unavailable. This is therefore an integration-ready source candidate only. It
is not assembled into an ARM64 image, installed on a seed, boot-tested or
physically accepted. Those gates and removal of legacy direct application
traversal remain open.
