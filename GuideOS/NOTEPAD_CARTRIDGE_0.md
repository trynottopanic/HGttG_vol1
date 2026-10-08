# Notepad Cartridge 0

Status: requirements accepted for implementation  
First test target for cartridge-installed Guide applications

## Purpose

Notepad Cartridge 0 is the first proof that an application can be carried on
external memory, inspected and installed through the cartridge path, remain
installed on the Deck independently of the cartridge, and work with user
documents on removable external storage through GuideOS mediation.

This document records accepted requirements separately from unresolved points.
Later decisions extend these requirements; they do not silently replace them.

## 1. Accepted identity and storage behavior

- Display name: `Notepad`.
- Stable package ID: `org.hhgtg.notepad`.
- Initial application version: `0.1.0`.
- Cartridge kind: `application`.
- Canonical cartridge filename:
  `GUIDE/CARTRIDGES/org.hhgtg.notepad-0.1.0.guide`.
- Installation copies the program into immutable internal Deck storage.
- Application settings and recovery state use a small private internal store.
- User documents remain separate ordinary UTF-8 text files.
- The preferred external document location is
  `GUIDE/DOCUMENTS/NOTEPAD/`.
- Removing the installation cartridge after a successful installation does not
  remove or disable Notepad.
- Removing external memory prevents access to its documents but does not crash,
  uninstall or corrupt the installed application.
- When external storage is unavailable, Notepad may use a deliberately limited
  internal draft area.
- When external storage returns, the user may explicitly save or copy an
  internal draft to external storage.
- Notepad never moves, merges or deletes documents automatically.
- Notepad does not receive the physical card mount path. It requests document
  access through the External Storage service.
- Version 0.1 supports create, list, open, edit, save and Save As.
- Delete and directory management are deferred until the initial write and
  recovery path has been proven.

The interface must always identify a document as one of:

- `External — GUIDE/DOCUMENTS/NOTEPAD`;
- `Internal draft`; or
- `Unsaved`.

Internal drafts are a recovery feature, not a second invisible document library.

## 2. Accepted document format and limits

- Documents are plain-text `.txt` files encoded as UTF-8.
- New documents are saved without a byte-order mark.
- A UTF-8 byte-order mark is accepted when opening an existing file and is not
  treated as document text.
- A document contains at most 5,120 Unicode code points and at most 20,480 UTF-8
  bytes, excluding an optional byte-order mark. Both limits apply.
- CRLF, CR and LF line endings are accepted on input. Text is normalized to LF
  internally and when saved.
- The format contains no rich-text markup, embedded images, executable content
  or hidden application metadata.
- Internal drafts use the same representation and limits.
- Invalid UTF-8, over-limit files and unsupported non-text files remain unchanged
  and produce a clear explanation. Notepad never truncates an existing file to
  make it fit.

Filename rules:

- The base name contains 1 through 32 Unicode code points.
- Notepad supplies the `.txt` extension; it does not count toward the limit.
- Names are normalized to Unicode NFC.
- Empty names, `.` and `..` are invalid.
- Control characters and `/`, `\`, `:`, `*`, `?`, `"`, `<`, `>` and `|` are
  invalid.
- Names may not end with a space or period.
- Windows-reserved names such as `CON`, `NUL` and `COM1` are invalid so files
  remain portable.
- External exFAT names differing only by letter case conflict.
- An existing name produces an explicit replace-or-return decision. Notepad does
  not silently add a suffix or overwrite the file.

For version 0.1, “character” means Unicode code point. Full grapheme-cluster
cursor behavior remains dependent on later text-engine work; stored text remains
valid UTF-8.

## 3. Accepted cartridge contents and manifest

The canonical archive layout is:

```text
org.hhgtg.notepad-0.1.0.guide
|-- GUIDE/
|   `-- manifest.json
`-- CONTENT/
    |-- application/
    |   |-- application.json
    |   |-- notepad.py
    |   `-- document_rules.json
    |-- assets/
    |   `-- icon.png
    |-- LICENSE.txt
    `-- README.txt
```

The package-level manifest uses:

- `format`: `GUIDE-CARTRIDGE-1`;
- `id`: `org.hhgtg.notepad`;
- `name`: `Notepad`;
- `version`: `0.1.0`;
- `kind`: `application`;
- a plain-language summary;
- `installAction`: `application.install.v0`;
- an entrypoint selecting runtime `guide.python-application`, interface major 1,
  module `notepad` and callable `application`;
- capability requests established under point 10; and
- every `CONTENT/` path, byte count and SHA-256 digest.

`application.json` records the icon and display information, Guide runtime and
display compatibility, private and temporary storage requests, minimum and peak
memory requests, lifecycle operations, offline behavior, document collection,
application-data schema version and health-check definition.

Accepted restrictions:

- `installAction` is an installed typed operation, never a command.
- Entrypoint module and callable values are validated identifiers, not arbitrary
  paths or command-line text.
- The cartridge contains no interpreter, shared libraries, package manager,
  dependency downloads, Debian packages, post-install commands or shell scripts.
- It cannot replace system files or services.
- The Deck supplies the Python application host, shared Guide UI, text entry and
  storage interfaces.
- Source remains inspectable before installation.
- The application runs as an unprivileged supervised instance.
- The application host exposes only its granted broker connections and private
  storage. It exposes no physical card path, ambient filesystem, network or
  device access.
- The external sandbox and brokers enforce the boundary; `notepad.py` is not
  trusted to enforce its own limits.
- The `.guide` archive has a bounded `.gde` index and SHA-256 sidecar.

## 4. Accepted installation, rollback and uninstall model

Installed files are separated as follows:

```text
/opt/guideos/applications/org.hhgtg.notepad/releases/<version>/
/var/lib/guideos/applications/org.hhgtg.notepad/installation.json
/var/lib/guideos/applications/org.hhgtg.notepad/private/
/var/lib/guideos/applications/org.hhgtg.notepad/recovery/
/var/lib/guideos/installer/transactions/
/var/lib/guideos/installer/staging/
```

Release payloads are immutable. The installation record stores the accepted
agreement and active version. Private settings/drafts and recovery checkpoints
remain separate from program versions.

Installation proceeds through these durable states:

1. Discover the bounded `.gde` index and label the Format 1 cartridge unsigned.
2. Verify the `.guide` archive against its index and sidecar.
3. Validate manifest fields, archive paths, file count, compressed/expanded
   bounds and every declared content digest.
4. Check runtime/interfaces, internal capacity, footprint and compatibility.
5. Show and obtain the owner's installation agreement.
6. Assign a transaction identity and copy the archive into bounded internal
   staging; code is never executed from external memory.
7. Reverify the internal staged copy.
8. Extract only declared files into a temporary release directory.
9. Validate application metadata, entrypoint identifiers, source syntax, assets
   and footprint without executing the application.
10. Durably write the application/agreement record, atomically place the release
    directory and atomically select the active version.
11. Launch a bounded health-check instance through Guide Supervisor.
12. Report success only after the application reaches ready state and the health
    check exits cleanly.

Card removal before the internal copy completes fails visibly. Partial copies or
extractions never become active. Failed initial installation leaves no installed
application entry. Staging residue is bounded and reconciled by transaction ID.
The durable journal reconciles power interruption on the next boot. A transaction
is idempotent. Identical installed content reports already installed; the same ID
and version with different contents is rejected.

Updates install beside the active immutable version. The current release remains
active during staging. Activation atomically switches the active-version record;
the prior release remains until health checks pass and is restored on failure.
Data-schema compatibility is checked before activation. Irreversible migration
requires a durable backup and explicit warning. Removing an old release never
removes user documents or private data.

Application removal and private-data removal are separate choices. External
documents are never deleted by uninstall. Retained private data can restore
settings and internal drafts after reinstall. Deleting private data requires a
separate confirmation. The external cartridge remains unchanged.

After successful installation, Notepad launches without the installation
cartridge or external card. Only external-document access depends on the card.

## 5. Accepted footprint and resource ceilings

Cartridge and installation limits:

- The `.guide` archive is at most 1 MiB.
- One expanded release is at most 2 MiB.
- The cartridge contains one 64 by 64 PNG icon of at most 32 KiB.
- At most two Notepad releases are retained simultaneously for update rollback.
- Installer staging and temporary working data are bounded to 4 MiB.
- The installation transaction journal is bounded to 64 KiB.
- The permanent installation record is bounded to 32 KiB.
- Two retained releases should normally occupy less than 4 MiB in total.

Private-storage limits:

- Settings and private metadata are bounded to 64 KiB.
- The active recovery checkpoint is bounded to 32 KiB.
- Notepad retains at most 16 internal drafts.
- Each internal draft obeys the document limit of 20,480 UTF-8 bytes.
- All internal drafts together are bounded to 384 KiB.
- The entire persistent private store is bounded to 512 KiB.
- Disposable cache data is separately bounded to 128 KiB.
- When a limit is reached, Notepad asks the user what to retain or remove. It
  never silently consumes additional storage or discards user text.

Runtime accounting includes the Python application host and all work owned by
the Notepad instance. Shared Guide shell, renderer, brokers and system text-entry
services are not charged to the application instance.

- Minimum admitted memory: 24 MiB.
- Normal memory ceiling: 48 MiB.
- Temporary bounded startup peak: 64 MiB.
- One process, no child processes, at most four threads and at most 32 open file
  descriptors.
- One open document, no background jobs, no network connections and no device
  leases.
- These are acceptance ceilings, not entitlements. They must be measured on the
  prototype and changed only by an explicit later revision.

Notepad runs at foreground application priority. It cannot raise its own
priority. It uses no polling loop or periodic full redraw; the renderer owns and
coalesces cursor blinking, and layout is recomputed only when state changes.
Version 0.1 performs no background indexing and has no periodic autosave loop.
A save remains cancellable until commit begins and is bounded once commit has
started. Suspend or stop causes Notepad to yield display and input resources.

Performance acceptance targets on the prototype are:

- ready for input within two seconds of launch;
- navigation and inserted text visible within 100 milliseconds;
- opening or saving a maximum-size document normally completes within one
  second;
- idle state causes no recurring writes and negligible wakeups; and
- exit after a completed save releases all instance-owned resources.

## 6. Accepted external-storage access

Notepad accesses external documents only through the logical collection
`documents.notepad`. The External Storage service maps that collection to
`GUIDE/DOCUMENTS/NOTEPAD/`; Notepad never receives or constructs the physical
card mount path.

- Read and write authority are separate grants.
- The service exposes bounded requests to list, open, create, save, replace and
  query the status of documents in the collection.
- After authorization, an opened document is supplied through a direct file
  handle. Ordinary document bytes do not need to be streamed through the
  service process.
- Notepad cannot mount, unmount, eject or scan the card, and cannot address any
  external directory outside its collection.
- Only regular `.txt` files satisfying the accepted name and document-size
  rules are presented as Notepad documents.

Every external handle is bound to both a stable card identity and the current
insertion generation. Removal invalidates outstanding handles. A later card,
including the same physical card after reinsertion, receives a new insertion
generation; stale requests cannot accidentally operate on it.

External saves are system-owned storage transactions:

1. Notepad submits the intended collection, card identity, insertion generation,
   normalized filename, expected destination state and bounded UTF-8 content.
2. The service revalidates the grant, destination, filename, type and size.
3. It writes and flushes a temporary sibling object without exposing partial
   content as the destination.
4. It commits or replaces the destination according to the explicit user choice.
5. It retains a small internal recovery record until the exFAT write and
   directory update are confirmed or reconciled.

The broker must verify the precise replacement and durability behavior of the
target exFAT implementation. Where the filesystem cannot provide the required
atomic guarantee, the internal recovery record and deterministic reconciliation
procedure provide the safe boundary; the interface must not claim stronger
atomicity than the platform supplies.

Removing the card while editing leaves the current buffer visibly unsaved or
preserves it as an internal recovery draft. Notepad never silently redirects an
external save to internal storage or to another card. Stale-handle, removed-card
and changed-destination errors are explicit and leave the user's text intact.

Safe eject asks Notepad to finish or cancel any active commit, prevents new
transactions, closes its external handles and then permits the service to
unmount the card. A commit already in its bounded non-cancellable phase finishes
before unmount or produces a recoverable transaction for the next insertion.

External Storage 0 begins read-only. Notepad therefore depends on implementing
the first narrowly scoped mediated-write capability and its recovery procedure;
this dependency must be completed before the Notepad cartridge can satisfy its
write acceptance tests. It does not authorize a generally writable mount for
Notepad or any other application.

## 7. Accepted GUI screens and controls

Notepad targets the Deck's 640 by 480 display and uses Field Theme 1 as defined
by `THEME_FIELD_1.md`. This supersedes the former Paper Theme 0 visual target
for Notepad only; it does not claim that Field Theme 1 is already deployed in
the installed shell. Every essential operation is reachable with D-pad, A and
B. Menu retains the system-owned return-home behavior, and Power remains
system-owned. The shell owns the persistent header and footer, focus, overlays
and display handoff.

Field Theme 1 gives Notepad a dark status strip, light context band, pale work
field and dark control strip. Note lists, editor surfaces and modal overlays use
compact dark translucent panels; selection uses a soft ice-blue field with one
amber/orange vertical marker at its outer-left edge. Names, note text and
ordinary instructions use the clean modern sans role; compact location, saved
state, limits and other technical values may use the monospace role. The theme
does not change an action's meaning or authorize it. It introduces no paper
texture, handwriting treatment, unlabeled icon, decorative illustration or
animation requirement.

### Document list

- External documents and internal drafts appear in visibly separate sections.
- Each row shows the document name and storage location.
- A visible status identifies whether external memory is available.
- The list follows the Field Theme list pattern: a compact dark translucent
  panel, thin internal rule, readable title and one optional metadata line per
  row. Focus is visible without relying on color alone.
- D-pad moves selection, A opens the selected row and B returns to the preceding
  screen.
- A visible `New document` row creates a blank unsaved buffer.
- Long lists use the standard proportional scrollbar.

### Editor

- The header shows the document name.
- A location label always identifies the document as `External`, `Internal
  draft` or `Unsaved`.
- An unsaved-change marker is continuously visible when applicable.
- The main panel displays multiline text, the caret and vertical scroll position.
- The editor uses a dark translucent text panel on the pale work field. Saved,
  unsaved, unavailable and failed states are rendered as explicit text in
  addition to their semantic color treatment.
- A opens the shared system text-entry interface at the current caret.
- Outside text entry, D-pad moves the caret and scrolls when the caret crosses
  the visible area.
- Shoulder buttons provide page-up and page-down.
- The footer exposes visible actions for Edit, Actions and Back.
- A failed save remains visibly failed; the interface never presents unsaved
  text as saved.

### Document actions

- The action screen contains `Save`, `Save As`, `Document information` and
  `Close document`.
- Until a destination exists, `Save` is unavailable or explicitly behaves as
  `Save As`.
- Delete, rename, directory management, formatting, search and sharing are not
  included in version 0.1.
- Destructive or lossy choices require a separate confirmation screen.

Supporting overlays provide filename entry, replace-existing confirmation,
unsaved-changes confirmation, external-card unavailable or changed, storage-limit
handling, save progress, save success and actionable error details.

The first Notepad visual fixtures are maintained under
`design/ui-theme-drafts/` as `guideos-field-theme-notes-list.png`,
`guideos-field-theme-notes-editor.png` and
`guideos-field-theme-notes-empty.png`. They define intended presentation only;
the shared system keyboard remains the text-entry surface and its actual
semantic controls continue to come from the input contract.

No operation depends only on color, an unlabeled icon, a hidden gesture or a
timed prompt. Text remains readable without animation. Modal overlays preserve
the underlying document buffer.

## 8. Accepted text-entry behavior

The Editor has separate viewing and text-entry modes. Pressing A in viewing mode
opens the shared multiline keyboard at the current caret. Entering text mode
creates a working copy of the current document buffer; it does not alter the
saved file.

- The shared keyboard provides insertion, newline, space, backward deletion,
  forward deletion, left/right movement and start/end movement.
- D-pad operates the on-screen keyboard while text entry is active. Existing
  visible keyboard actions and layer switching remain consistent with the
  system keyboard.
- `Done` commits the working copy exactly once to Notepad's in-memory document
  buffer and marks the document unsaved.
- B or the visible `Cancel` action exits immediately when nothing changed. When
  the working copy changed, Notepad asks whether to discard those session edits.
- Cancelling the current text-entry session never discards changes committed by
  an earlier session.
- Menu retains the shell's global return-home behavior. Durable preservation
  during that interruption is specified separately under point 9.

A visible counter reports use of the 5,120-code-point allowance. Approaching the
20,480-byte UTF-8 limit also produces a warning. An insertion that would exceed
either limit is rejected with an explanation; existing text is never truncated.
Lines wrap visually to the display width without inserting newline characters.

Existing valid Unicode is displayed and preserved even when a character cannot
be entered through the initial controller keyboard. Version 0.1 initially enters
printable ASCII and newline through that interface. Additional input adapters
and layouts may extend entry without changing the document format. Caret and
deletion operations count Unicode code points in version 0.1, consistent with
point 2.

Held activation cannot insert or submit repeatedly outside the keyboard's
defined repeat behavior. Version 0.1 provides no predictive text, autocorrection,
clipboard, selection, cut, copy, paste or multi-level undo. Document text,
selected keys and editing activity are excluded from ordinary diagnostic reports.

## 9. Accepted save, recovery and card-removal behavior

Notepad maintains one bounded internal recovery checkpoint for the currently
open document. It writes the checkpoint after a text-entry session is committed
and before yielding to Home, suspension, shutdown or supervised termination.
Checkpointing is event-driven and does not introduce a periodic autosave loop.

The checkpoint records the document text, caret, filename, location type, dirty
state, card identity, insertion generation and expected external-file state. It
is written to a temporary internal object, flushed and durably replaced. A
checkpoint is recovery data rather than a saved document, and the interface
never labels it as saved. It remains until the document is successfully saved,
explicitly retained as an internal draft or explicitly discarded.

For an ordinary save:

- success is displayed only after the storage broker confirms completion;
- failure leaves the working buffer and recovery checkpoint intact;
- before replacing an external file, the broker compares its current state with
  the state observed when it was opened; and
- when another program changed or replaced the file, Notepad refuses an
  automatic overwrite and offers Save As, explicit replacement or cancellation.

Notepad never merges conflicting versions automatically.

If the card is removed, the open buffer remains available and its label changes
to show that the external destination is unavailable and the document is
unsaved. Outstanding external handles become unusable. The user may wait for the
card, explicitly retain the work as an internal draft or select another
destination through Save As.

Reinsertion permits saving to the original destination only when card identity
and file state still match. A different card, changed file or changed insertion
state requires an explicit new decision.

Closing a dirty document offers `Save`, `Keep as internal draft`, `Discard
changes` and `Cancel`. Discarding requires confirmation. Returning Home or losing
application focus does not imply discard.

After an interrupted session, Notepad offers to restore the last valid
checkpoint as an unsaved buffer. It never writes recovered text over an external
document automatically. Corrupt or incomplete checkpoints are rejected without
affecting documents. Recovery makes no claim of encryption or secure erasure.

## 10. Accepted capabilities and supervision

Required capability requests are:

- `output.visual.surface`, interface 1, for exclusive foreground presentation on
  the current 640 by 480 Deck display;
- `input.actions`, interface 1, for semantic navigation and action events rather
  than direct input-device access;
- `input.text`, interface 1, for one system-owned text-entry session while
  editing; and
- `storage.private`, interface 1, for bounded access only to Notepad's private
  settings, drafts and recovery areas.

External-document support is an optional feature governed by a scoped collection
capability for `documents.notepad`. Its read operations are `list`, `status` and
`open`; its separately granted write operations are `create`, `commit` and
`replace`. The grant is restricted to regular `.txt` files and the accepted name
and size limits. The broker supplies authorized handles and transactions without
exposing a mount path. If this feature is unavailable or denied, Notepad remains
usable with its bounded internal-draft area and clearly reports that external
documents are unavailable.

Notepad receives no authority for networking; audio; cameras, microphones,
Bluetooth or other devices; arbitrary filesystem access; child processes or
program launching; package management; diagnostics; power management; or direct
display and input-device access.

The collection-capability name remains provisional until the broker vocabulary
is frozen. Its object scope, operation separation and restrictions are normative.

The Supervisor launches one unprivileged Notepad instance under its installed
package identity and enforces the point 5 memory, process, thread, descriptor,
storage and priority limits. It acts as the instance's subreaper and reaps any
unexpected descendants even though child creation is prohibited.

- Lifecycle states include `starting`, `ready`, `foreground`, `checkpointing`,
  `stopping` and `exited`.
- The application reports ready within two seconds or fails its launch health
  check.
- Pause, Home, shutdown and revocation include a bounded checkpoint opportunity
  while the necessary authorization remains available.
- Display, action-input, text-input and external-storage grants are released
  independently and idempotently.
- Revoking external access does not terminate the editor or erase in-memory text.
- Failure to stop by the declared deadline permits forced termination after the
  last acknowledged checkpoint attempt.
- A resource-limit or capability violation terminates the instance with a
  user-readable reason.
- Repeated crashes cannot create an unlimited restart loop; recovery is offered
  from the last valid checkpoint.
- Health checks use synthetic private data and cannot read owner documents.
- Logs may contain lifecycle states, bounded resource figures and typed error
  codes, but not document contents, entered text, selected keys or complete
  filenames.

The installation agreement explains the required private-storage access and the
optional external read/write feature in plain language.

## 11. Accepted testing and acceptance requirements

Notepad requires four distinct evidence levels.

### Deterministic unit tests

- UTF-8, optional input BOM and newline handling.
- Both document-size limits.
- Filename normalization, reserved names, case-insensitive conflicts and invalid
  characters.
- Caret movement, insertion, deletion, wrapping and edit-session cancellation.
- Dirty-state transitions and checkpoint encoding.
- Absence of truncation, silent overwrite and automatic filename suffixing.

### Service integration tests

- Cartridge validation, installation, update, rollback and uninstall.
- Private-store quotas and internal-draft limits.
- Collection-scoped listing, opening, creating, committing and replacement.
- Separate read/write grants and the denied-feature fallback.
- Card identity, insertion generation, stale handles and safe eject.
- External modification conflict detection.
- Supervisor launch, readiness, checkpoint, stop, forced termination, resource
  enforcement and orphan reaping.
- Capability loss without loss of the in-memory document.

### Failure-injection tests

- Card removal before and during each save phase.
- Power interruption during checkpoint, external temporary write, flush,
  replacement and transaction cleanup.
- Full internal storage and full external storage.
- Corrupt cartridge, corrupt checkpoint, invalid UTF-8, oversized document and
  malformed broker reply.
- Application crash and storage-broker crash.
- Reinsertion of the same card and insertion of a different card.
- Destination alteration between opening and saving.

Every injected failure preserves the last confirmed document and leaves either a
valid recoverable transaction or safely removable residue.

### Physical Deck acceptance

- Install from the prepared cartridge on the RG35XX H.
- Remove the cartridge and launch Notepad independently.
- Create, edit, save, reopen, replace and recover documents on the 256 GB exFAT
  card.
- Exercise every required operation with the physical D-pad, A and B.
- Confirm readable 640 by 480 rendering, visible focus, scrolling, overlays and
  location/dirty indicators.
- Measure the point 5 launch, input, open/save, memory, descriptor, idle-wakeup
  and storage ceilings.
- Remove and reinsert the card during realistic editing and save scenarios.
- Confirm Home, Power, safe eject, forced termination and restart behavior.
- Confirm there are no orphaned processes, leaked handles, repeated restart
  loops, exposed external mount paths or recurring idle writes.

Simulated tests cannot establish physical display, controls, timing, exFAT
durability or removal behavior. Physical success cannot replace deterministic
validation and failure injection. Tests use dedicated fixtures and never modify
the owner's source documents.

Data loss, silent overwrite, incorrect saved-state indication, sandbox escape or
a cross-card write blocks release. Results record software versions, package and
image hashes, card identity, test time, measured resource figures and failures.
Version 0.1 is accepted only when every mandatory test passes; exceptions remain
explicit unresolved defects rather than being relabeled as success.

## 12. Accepted packaging and first-cartridge release

The canonical maintained source location is:

```text
GuideOS/apps/notepad/
|-- cartridge/
|   |-- application/
|   |   |-- application.json
|   |   |-- notepad.py
|   |   `-- document_rules.json
|   |-- assets/
|   |   `-- icon.png
|   |-- LICENSE.txt
|   `-- README.txt
|-- tests/
`-- README.md
```

The canonical build output is:

```text
GuideOS/build/notepad-cartridge-0.1.0/
|-- org.hhgtg.notepad-0.1.0.guide
|-- org.hhgtg.notepad-0.1.0.gde
|-- org.hhgtg.notepad-0.1.0.guide.sha256
|-- manifest.expanded.json
|-- validation.json
|-- test-results/
`-- BUILD_README.txt
```

Packaging rules:

- The build starts only from the maintained source tree, never from files
  recovered from a card.
- The builder generates `GUIDE/manifest.json`; it is not maintained as a second
  independent source file.
- Archive entry order, timestamps and stored permissions are normalized so the
  build is deterministic.
- Build caches, bytecode, editor files, logs, tests and development credentials
  are excluded.
- The completed archive is reopened and independently checked against its
  manifest.
- A second build from unchanged sources must produce the same archive hash.
- The `.gde` index records archive filename, size, SHA-256, display metadata,
  typed installation action and requested capabilities.
- The SHA-256 sidecar remains build evidence. It detects changes but does not
  establish authorship.
- Format 1 remains visibly labeled unsigned.
- `validation.json` records every format, size, digest, source-syntax,
  resource-contract and compatibility check.
- A package cannot be called installable while a required runtime or broker
  interface is absent. The build may instead emit a clearly labeled
  non-installable development artifact.

Card deployment places only the verified package and index at:

```text
GUIDE/CARTRIDGES/org.hhgtg.notepad-0.1.0.guide
GUIDE/CARTRIDGES/org.hhgtg.notepad-0.1.0.gde
```

The physical card is reidentified and confirmed immediately before any write.
Copying uses temporary names, verifies the copied content and only then exposes
the final filenames. Deployment never formats the card or removes unrelated
files.

The first release is complete only when the exact packaged hashes pass point 11,
install successfully, remain usable after cartridge removal and appear in a
dated physical acceptance report.

## Installer clarification accepted with step 2

The runtime `.gde` archive SHA-256 is sufficient for cartridge integrity checking.
The `.guide.sha256` sidecar is build evidence and is not required on the card;
when present it must agree. Any earlier installation wording requiring the
sidecar is superseded by this clarification. Format 1 remains unsigned.

## Implementation dependencies

The [current integration review](docs/NOTEPAD_INSTALLATION_INTEGRATION_0.md) maps
these requirements and the Musings visual handoff to implemented components,
remaining contract gaps and the installation acceptance sequence.

The requirements are complete. Implementation still depends on completing and
integrating the application runtime, capability grants, scoped external-storage
writes, recovery transactions and Supervisor lifecycle interfaces specified
above. These are dependencies, not exceptions to the accepted behavior.
