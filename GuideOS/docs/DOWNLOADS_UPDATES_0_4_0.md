# Downloads, transfers and update installation — 0.4.0 integration

Status: implemented and tested in source on the Linux development host. This is
an integration package for the consolidated Home v3 image, not an installed or
physically accepted Deck release. No physical card or owner data was modified.

## Implemented flow

The browser's Transfers button opens a working GTK destination picker and job
history. Ordinary HTTP/HTTPS GET downloads pass to the independent transfer
service, with scoped website cookies held only in memory. Jobs continue when the
browser closes. The service also copies a selected internal/external file through
storage-owned descriptors. Progress, unknown totals, cancellation, restart from
the beginning, and explicit Keep both / Skip / Cancel decisions are implemented.
There is no silent overwrite. New files remain hidden partials until atomic
publication. Completed jobs include a stream hash, explicitly not an independent
source checksum. Buffering/opening media pauses transfer reads; background work
has lower CPU and I/O priority.

The storage provider remains the sole external mount owner. Internal files live
under `/data/guideos/files`; this is not arbitrary access to the OS or application
stores. FAT/exFAT external destinations can be remounted writable by that owner.
The current ext4 probe uses noload and remains read-only. Each external selection
is tied to a card generation, so queued work cannot silently target a replacement
card. Existing files, symlinks and partials are never overwritten as a shortcut.

Guide-native Transfers and Updates screens are implemented as semantic models,
with a small frontend adapter. Updates can receive a signed release through the
existing paired, pinned SSH Wi-Fi channel or import a selected internal/external
file. Both routes use the same signature, target, base, inventory and space
checks. Receipt does not authorize installation. The Deck review shows source,
version, signer, size, components, interface restart and recovery; installation
requires a local action and external power. Older/same sequence installation has
a distinct approval. The controller quiesces the shell, switches an immutable
release, checks health and restores the previous release on failure/interruption.

This implements the approved `GUIDE-SIGNED-BUNDLE-1` and
`org.hhgttg.guide-release` v1 contracts for the qualified shell profile. Local
admission is deliberately smaller than the common container limits: 100 MB and
512 payload files. Supported payloads are flat `shell0`, `input`, `assets` and
`browser` files. The active browser launcher follows the same immutable release.
No update-supplied commands or service names are executed. System services, kernel,
DPKG packages, engine/runtime packs and state migrations require the separate
image/runtime work; they are not disguised as shell releases. Local policy
requires external power even if a package permits battery operation.

## Frontend integration

See [browser display/input lease](../apps/browser/gtk/INTEGRATION.md). Add
`/usr/lib/guideos/ui` to the trusted shell import path and construct
`guide_operations_frontend.OperationsPages` once:

- Home Settings/Tools entry: `pages.open('updates')` or `pages.open('transfers')`.
- File browser Copy action: `pages.copy(entry_id, display_name)` using the opaque
  ID returned by this storage provider; never pass an arbitrary filesystem path.
- Each UI tick: call `pages.poll()`; redraw when it returns true or input changes.
- Render `pages.model()` using GuideUI/the replacement schema renderer. Keep
  disabled informational rows scrollable; activate only enabled rows.
- D-pad navigation: `pages.move(-1 or 1)`; confirm: `pages.activate()`;
  pointer selection: `pages.activate(region.identity)`; Back: `pages.back()`.
  A `home` result returns to the owning page.
- On shell teardown: `pages.close()`. This does not cancel background transfers
  or an already authorized update.

The adapter never grabs input, draws over the browser, restarts services directly,
or substitutes for the existing shell heartbeat/quiescence contract. Keep the
restart gate false during browser/video display ownership, unsaved editing,
shutdown and other unsafe operations. Keep the existing `ShellBridge` integration
when consolidating Home v3. Review/install is only in trusted Guide UI, never in
web content. The independent GUI chat must attach these page entries and its
normal input/render loop; the old Home layout is not rewritten by this package.

## Offline image bootstrap

Use `package/guide-deploy/stage_operations.py --root OFFLINE_ROOT --data
OFFLINE_DATA --public-key PUBLIC_KEY --sequence CURRENT_SEQUENCE --state-schema 1`.
Run as the image-building owner/root on an offline copy. `PUBLIC_KEY` is a raw
32-byte Ed25519 public key whose private signer stays on the development machine.
Use the known current sequence, not the proposed release number. The stager
preserves active release references and existing owner files, copies fixed service
code, enables Transfers, creates the internal files directory on the separate data
partition, configures signed-only admission and provisions scoped public trust.
It emits before/after hashes; retain that output with the image audit.

Prerequisites: the existing deployment/storage/installer IPC stack, current Guide
schema/text runtime, guide-browser sysuser (create using systemd-sysusers), and the
resolved ARM64 WebKitGTK/Weston/GI/evdev/cryptography runtime. Browser remains an
on-demand service. Stage into the returned-Seed-derived image, not the old generic
root. Dependency/space verification and GUI integration still belong to image
assembly. Fixed service bootstrap cannot be delivered by the old shell-only updater.

Build a complete immutable release with `build_signed_release.py RELEASE OUTPUT
--key PRIVATE_KEY --version 0.4.0 --sequence NEW_SEQUENCE --base-sequence CURRENT`.
The output is a new file; existing output is not replaced. Send via
`send_signed_release.py OUTPUT --profile PAIRED_PROFILE --host DECK_IP`, then review
and install on Deck. Alternatively copy the signed bundle onto the external card
and choose it in Updates. No signing private key is copied to the image/handoff.
A signer is provisioned at image assembly; interactive arbitrary-key enrollment
is deferred. Trust supports root-owned revocation markers under the configured
trust directory; such a marker prevents a queued package from activating.

## Bounded prototype limitations

- Downloads refetch GET with scoped cookies. POST/blob, HTTP-auth headers,
  one-use URLs that do not survive refetch, uploads, FTP and Node transfers are
  not implemented. Unsupported request types report failure, never completion.
- Retry restarts, not range-resumes. After a service restart, cookie-dependent
  downloads must be requested again from the browser. Jobs never auto-run on boot.
- A provider crash may retain an owned hidden partial. The job reports interrupted
  state; it does not rename that partial into a completed file. Power loss after
  final rename can leave a saved file with an interrupted job; retry still uses
  collision decisions and cannot overwrite it. No broad partial-file cleanup runs.
- History is bounded to 128 jobs with 16-row pages; directories to 4096 entries
  with 32-row pages. Unsupported Replace/Pause/Move actions are not advertised.
- Import/verification is asynchronous to drawing but serialized at the updater;
  cancellation is available before activation, not halfway through a critical
  release switch. An interrupted Wi-Fi receipt can resume at its verified offset.

## Evidence and remaining acceptance

Development-host checks cover real WebKit GET download through the transfer and
storage implementation, real root-owned Unix descriptor passing, local copies,
collisions, cancellation during media backpressure, card replacement/removal,
truncated responses, restart reporting, signature/trust rejection, explicit local
approval, health rollback, service umask readability and offline owner-data
preservation. Native 640x480 review/collision screens were rendered and inspected;
label overflow and notice overlap found there were corrected.

These are source/host results. No new image, installed release or physical result
is claimed. Consolidated 0.4.0 acceptance must test both receipt routes, approval,
external power gating, actual shell restart/recovery, browser download to each
supported location, unplug/reinsert, and music/video continuity on Deck. Capture
the returned Seed first, preserve all owner data, perform image preservation and
write/readback checks, then record the user's physical results separately.
