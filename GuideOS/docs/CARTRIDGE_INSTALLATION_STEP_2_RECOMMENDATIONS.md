# Step 2: cartridge installation recommendations

Status: accepted by the owner for implementation, 26 September 2026. The owner
approved all recommendations and instructed the build to proceed. The original
recommendation wording below is retained as the scope of that approval.
Implementation and evidence: [Cartridge Installer 0](CARTRIDGE_INSTALLER_0.md).

## Recommended outcome

Prove this complete path with the harmless reference application:

**External Card → Cartridges → inspect and verify → agree → install internally →
open from Home → remove cartridge → checkpoint, stop and relaunch.**

The same transaction should safely update that application, restore the previous
release when a candidate fails, and uninstall without deleting retained private
data. That establishes the delivery mechanism before the Notepad editor is ready.
It does not establish Notepad's external-document support or full release acceptance.

Implement one typed action, `application.install.v0`, for the bounded Python
application profile. Leave system images, kernels, firmware, drivers, privileged
services and native runtimes outside this action. They need separate action
contracts and recovery guarantees; an application cartridge must never acquire
those powers by changing its manifest. Preserve existing Format 1 data packages
and display unsupported actions honestly.

Source basis: [Notepad requirements](../NOTEPAD_CARTRIDGE_0.md),
[Cartridge Format 1](../CARTRIDGE_FORMAT_1.md),
[External Storage 0](../EXTERNAL_STORAGE_0.md),
[Application Host 0](APPLICATION_HOST_0.md) and
[the integration plan](NOTEPAD_INSTALLATION_INTEGRATION_0.md).
The historical [Cartridge Browser 0](../CARTRIDGE_BROWSER_0.md) supplies useful
empty-state wording, but its pinned Buildroot installer and unmount-on-exit
behavior are not the modern implementation baseline.

## 1. Resolve the host/installer boundary first

Step 1 is host-verified and staged, not installed or physically accepted. It
provides a useful bounded worker, not a complete package database. Address these
items before ordinary installation can be declared safe:

| Boundary | Recommendation |
| --- | --- |
| Package identity | Persist package ID, semantic version, whole-archive hash, inventory hash, runtime profile, data-schema version and agreement revision. Keep the source-module hash as a separate integrity check. |
| Numeric runtime code | Allocate a stable local alias for the package ID; retain it with saved data across uninstall/reinstall. Do not use a truncated hash that can collide or reuse a code while retained data still belongs to it. |
| Accepted paths | Converge on the Notepad specification's `/opt/guideos/applications/<id>/releases/<version>/` and per-ID records/private/recovery under `/var/lib/guideos/applications/`. Adapt the host's current digest/numeric-code layout explicitly. Do not silently create two competing stores. |
| Activation authority | Use one authoritative installation/activation record. The numeric `.policy` is a generated runtime projection, verified against the committed record's generation and digest. It must not become a second independently editable source of authority. |
| Isolated health checks | Add a trusted Supervisor health-check mode with a temporary, quota-limited private store. It must not inherit the owner's drafts, checkpoints, external-document grants or normal shell focus. |
| Complete agreement binding | Bind the instance to the full installed agreement, including quota, runtime profile and release identity. The current source-digest/permission-mask binding alone is insufficient for package updates. |
| Resource compatibility | Check actual host restrictions: single source module, no application-created threads/children, fixed current memory/task/descriptor profile, bounded private objects and available SDK functions. Do not accept metadata promising a capability the host cannot supply. |
| Bounded bookkeeping | Verify repeated install/update/uninstall cycles and many distinct package IDs reclaim terminal instance/grant records correctly; bounded tables must not become lifetime launch limits. |

Retain the systemd DynamicUser isolation if practical, but map its physical
private directory to the accepted logical per-application ownership model. Account
for ownership changes during reinstall. Do not copy live private files between
competing paths or use a launch shortcut around the host's no-symlink checks.

The full accepted Notepad store has category limits that the current generic
512 KiB/32-object store does not yet express. Record requested and supported
limits precisely. Implement the needed categories before advertising full
Notepad compatibility; the reference application's smaller profile can prove the
installer first.

## 2. Browser and owner-facing flow

Use the existing **External Card** screen as the entry point. Add **Cartridges**
and a clear count/status, then a scrollable list using the accepted readable
Field typography. Keep the installed application catalog separate from the card
catalog: an application remains available when its cartridge is gone.

Insertion may update availability but must not run code or install anything.
Browse bounded `.gde` metadata first; mark it unchecked until its corresponding
archive is verified. Hash only a selected candidate, asynchronously. Do not scan
all card content or hash every package on insertion.

A verified detail screen should show name, version, short purpose, package ID,
**Unsigned — author not verified**, compatibility, installation/update state,
internal space needed and readable permission explanations. Offer package hash
and technical inventory in an optional Details view. Hashes establish consistency,
not publisher identity; a familiar package ID does not authenticate an update.

Show one installation agreement after verification and compatibility checks. It
should distinguish required powers from optional features and show changed powers
on update. It is the consent for that exact package hash and agreement; rebuilding
or selecting another package invalidates it. Do not prompt again for every file.
An unavailable required runtime prevents installation; unavailable optional
external documents are shown as unavailable, never as a working feature.

After success offer **Open** and **Back**; do not launch the normal application
automatically. Preserve selection when returning to the browser. Distinguish no
card, unreadable card, ordinary non-Guide card, no cartridges, malformed indexes,
unsupported package, incompatible runtime, insufficient space and an installation
failure. Do not mislabel malformed metadata as absent hardware.

Show actual phases—Checking, Copying, Preparing, Testing, Installed—with byte
progress where measured. Avoid invented overall percentages. Keep Menu and Power
responsive. Leaving the view must not silently cancel a transaction: retain a
system-owned status item and explicit Cancel. During the short commit boundary,
finish or recover the recorded transaction; say when cancellation is no longer
possible. A clean shutdown must coordinate with this boundary, while hard power
loss is handled by the journal.

## 3. One external-storage owner, read handles, no external writes

Extend the current storage provider; do not let the browser or installer mount
the slot. Keep the card read-only with the accepted mount restrictions. Leaving
the browser must not unmount a card another consumer uses.

Recommend typed catalog/list, inspect-index and open-cartridge operations.
Return opaque item identities and read-only regular-file descriptors, not mount
paths. Bind selection and handles to provider epoch, physical slot, card identity,
insertion generation, catalog revision and the selected archive identity. Card
identity prevents stale access; it is not a claim that the medium is trustworthy.
Provider restart, removal and reinsertion invalidate old authority.

The installer reads directly from its descriptor. Use no-follow directory-relative
opens, containment checks and explicit size bounds. Reopening a remembered filename
must never accidentally select a replacement card. Lease expiry and cancellation
close handles; do not rely on unmounting to revoke every reader.

Removal during an incomplete copy fails visibly and leaves the previous installed
version intact. Once every archive byte is in internal staging, verification can
finish without the card; after durable staged verification the rest of installation
is independent of external memory. Close the card lease promptly. Safe eject can
then proceed while internal testing finishes.

The pending startup-recognition correction belongs in the eventual combined
candidate and physical acceptance. A manual reinsert must not be a hidden normal
installation prerequisite. Writable external document access remains separate work.

## 4. One application profile across builder and Deck

Extend `New-GuideCartridge.ps1`, `Test-GuideCartridge.ps1`, the card-copy tool and
the Deck verifier together. Today the builder emits a null entrypoint and the
verifier rejects non-null entrypoints and `application.install.v0`.

Define a versioned application profile that keeps Format 1 packaging and accepts
only the declared runtime/module/callable form. Keep old data packages valid.
Unknown required profile fields or interfaces produce an explicit incompatibility,
not a guessed interpretation. Do not broaden the old pinned action allow-list
into a general privileged installation route.

Maintain one language-neutral profile and a shared valid/invalid fixture corpus
for PowerShell and the Deck implementation. Include deterministic archive ordering,
normalized timestamps and permissions, repeat-build hashes and independently
verified output. The current tooling already normalizes timestamps; extend and
test that behavior rather than replacing it without need.

Bind `.gde` ID/version/kind/action/capability metadata to the verified manifest.
An index is a catalog hint, not authority for a different archive or agreement.
Reject missing/undeclared entries, duplicate JSON keys, duplicate or ambiguous
paths, traversal, absolute names, backslashes/alternate-stream forms, links,
special files, case/normalization collisions and unsupported ZIP features.
Restrict the small profile to stored/deflated ordinary files; reject encryption,
multivolume and ZIP64 packages. Enforce actual streamed expanded bytes, not only
ZIP header claims. Do not extract with a generic unchecked `extractall` call.

Validate syntax without importing or executing application code. Decode icons in
a bounded helper and verify the actual 64×64 dimensions. Do not trust a PNG header
or a claimed expanded size. Reject arbitrary installer scripts, bundled native
libraries/interpreters and dependency-download instructions.

There is a documentation conflict to resolve explicitly: Notepad's installation
sequence says to verify the sidecar, but its deployment section places only the
`.guide` and `.gde` on the card. I recommend treating `.guide.sha256` as a build
receipt, with the archive hash in `.gde` sufficient for the runtime consistency
check. If a sidecar is present, it must agree. This is a proposed clarification
to Notepad's wording, not a claim that a hash proves authorship or a silent format
change. Alternatively, copying all three files preserves a mandatory-sidecar rule.

## 5. Privilege and service shape

Use one on-demand, system-owned installer coordinator, separate from the shell
and Supervisor. Permit one active transaction initially. The shell presents the
owner decision; the Supervisor launches/quiesces instances; the storage provider
owns external access; the installer owns internal package transactions.

Run ZIP/manifest/image inspection in a bounded unprivileged helper with access
only to the selected read handle or staged copy. Keep final privileged publication
narrow: known application directories, validated identifiers, fixed operation
vocabulary and a rechecked inventory. Helper output must not become arbitrary
root paths, shell commands or systemd properties. Validate the final staged tree
again before granting it immutable-release status.

Define typed Envelope requests for inspect, begin, status, cancel, rollback and
uninstall. Names are recommendations to register with the shared schema work.
Replies should carry transaction identity/revision, phase, bounded progress,
typed failure and retry/cancel availability. Use a bounded snapshot with revision
tracking rather than an unbounded event stream. Restarted clients can resume
observation without repeating an installation.

Use structured logs with package hash, transaction, phase and outcome. Do not log
application document contents, keyboard input or arbitrary archive exception text.

## 6. Transaction and recovery design

Preserve the accepted verification-before-agreement sequence, then make the
internal copy authoritative:

1. Verify the selected external archive and profile; compute compatibility and
   peak space; obtain agreement bound to the exact package.
2. Allocate a durable transaction and reserve bounded staging space.
3. Copy to an exclusive internal temporary file; hash while copying, flush it,
   reverify it and its directory before declaring the staged copy durable.
4. Extract only declared files into a private temporary release directory on
   the destination filesystem. Recheck inventory, syntax, assets and metadata.
5. For an update, request a bounded checkpoint and observed stop of the old
   instance. A failed checkpoint must not be represented as safely saved.
6. Write the durable activation intent, including old/new release and agreement
   identities and enough information to restore the old runtime projection.
7. Publish the immutable release and approved records, then atomically replace
   the authoritative activation record and flush its directory. Keep the package
   in a testing state; ordinary catalog launch remains unavailable until success.
8. Run the bounded health check with synthetic private data through the Supervisor.
   Require ready and an observed clean stop. Do not infer success from launch
   acceptance, file presence or a checkpoint message alone.
9. On success, durably mark committed, expose the installed app and retire only
   transaction-owned staging. On failure restore the previous committed activation
   and policy; a failed first install produces no installed catalog entry.

A rename is not a transaction across several files. Every reader must use the
committed activation generation and reject mismatched policy/record projections.
Recovery repairs a projection from its authoritative committed record. The journal
must record intent before irreversible visibility changes, use durable replacement
and tolerate malformed/truncated records without guessing what should execute.

Use a finite state machine such as AGREED, COPYING, STAGED_VERIFIED, PREPARED,
ACTIVATING, TESTING, COMMITTED, ROLLING_BACK, ROLLED_BACK or FAILED. Reconcile it on
boot before making affected application entries launchable. Recovery may complete
filesystem reconciliation or roll back a pending test; it must not unexpectedly
launch an ordinary application. Recheck any artifact retained across interruption.

Make request identities idempotent: a retried begin returns the same transaction;
completed requests return the recorded result. Never delete unknown directories
as cleanup. Discard incomplete bounded staging, preserve the last committed
release/private store, and quarantine inconsistent records for an understandable
recovery action. Keep other shell functions available when one application is
under recovery.

## 7. Updates, rollback, permissions and uninstall

| Situation | Recommended result |
| --- | --- |
| Same ID/version and identical package | Already installed; offer Open if healthy. No new transaction or duplicate data. |
| Same ID/version with different contents | Reject conflict. Ask the author to publish a new version; no Force shortcut on Deck. |
| New version, compatible data schema | Explain the change; stage beside current release, checkpoint/stop, test and activate. |
| Additional authority or larger footprint | Obtain an amended agreement before activation. Preserve declined optional permissions. |
| Lower version | Offer explicit rollback/downgrade only when its data schema can read retained state. Do not treat lexical version order as semantic version order. |
| Failed health check | Restore prior release and its agreement; do not erase private data. |
| Unsupported migration | Refuse that update in the first implementation. Later irreversible migrations require the accepted durable backup and explicit warning. |
| Uninstall | Stop the instance, revoke grants and transactionally remove program availability; retain private data and external documents. |
| Delete retained private data | Separate explicit choice with no checked-by-default deletion. Never traverse the external documents collection. |

Retain at most two program releases for the Notepad profile. Count transient
staging separately. Do not discard the last known-good release before proving the
new one. The reference installer should initially support equal private-data
schema versions; advanced migration is not needed to prove this path.

## 8. Initial limits and scheduling

Preserve the accepted Notepad limits: archive 1 MiB, expanded release 2 MiB,
64×64 icon ≤32 KiB, two retained releases, installer working data ≤4 MiB,
journal ≤64 KiB and installation record ≤32 KiB. Do not silently generalize these
as permanent limits for all future software.

Additional recommended first-profile ceilings:

- One installer transaction, one verification helper and one health-check instance.
- At most 512 examined directory entries and 128 cartridge indexes, with explicit
  capacity status; small paged batches, never a whole-card traversal.
- Index ≤4 KiB, manifest/application metadata each ≤32 KiB, at most 64 archive
  files, path ≤128 UTF-8 bytes and depth ≤8; strict narrower identifier rules
  for executable module/callable and package IDs.
- A bounded metadata-only catalog cache, approximately 128 KiB, stored internally.
  Cached entries are stale after card-generation change until revalidated.
- Start with 64 KiB copy/hash chunks and cooperative scheduling. Measure UI latency
  and adjust chunk scheduling; do not promise an unmeasured hardware throughput.

Capacity checks must include old retained releases, new release, the staged
archive, temporary extraction, journal/record updates, filesystem block rounding
and a system free-space reserve. Never count the same temporary directory twice,
and never omit it. If two existing releases plus a candidate exceed policy,
explain which inactive release must be removed; never remove private data to make
room. Choose the device free-space reserve from measurements and the system
storage budget, not a fabricated universal number.

Verification/copy work runs below foreground input and playback. Bound stalled I/O
and helper work, expose cancellation, and use physical measurements to set phase
deadlines. Reading an agreement has no arbitrary session deadline.

## 9. Implementation sequence and acceptance gates

1. Reconcile the active-record/layout and sidecar decisions; freeze the small
   application profile and shared adversarial fixtures.
2. Add isolated health-check mode and complete agreement/release binding to the
   host. Verify no test reads or changes normal private data.
3. Implement the read-only storage catalog and generation-bound read handles;
   connect browser states and asynchronous verification.
4. Implement internal staging, publication, journal recovery and a generated
   runtime projection. Prove updates and failures before exposing Install.
5. Add owner agreement, progress/cancel, installed-app catalog, launch, rollback
   and uninstall/private-data separation in the shell.
6. Build reproducible reference cartridges: initial version, compatible update,
   failing candidate and intentionally malformed cases.
7. Combine the exact validated host/installer payload with the pending boot and
   card-recognition fixes using a fresh seed capture and preservation audit;
   perform the physical campaign before claiming Deck acceptance.

Required evidence includes cross-tool format agreement; corrupt/ambiguous archives;
wrong hashes; missing required providers; permission escalation attempts; low space;
source replacement and card removal; cancel/retry; provider/installer/Supervisor
restart; interrupted writes at every journal/rename/fsync boundary; failed ready,
failed checkpoint and crashed/OOM health checks; concurrent launch/update attempts;
repeat installation cycles; uninstall/reinstall with drafts; and preservation of
unrelated files. A malformed unrelated cartridge must not prevent inspecting a
valid one unless the documented catalog capacity is exceeded.

Measure actual ARM64 memory/descriptor use, input responsiveness while copying,
and health-check timing. The physical success criterion is cold boot with the
card already inserted, install, remove the cartridge, launch from Home, edit
synthetic private text, checkpoint, reboot and recover it; then update, deliberately
fail an update, confirm rollback, uninstall without data deletion and reinstall
with that data intact. External-document saving is a later separate campaign.

The deliverable is a complete installation mechanism and recorded evidence, not
merely a package copier or an Install button. The current host proof reduces the
work, but isolated health testing, agreement publication and crash recovery are
essential remaining parts of step 2.
