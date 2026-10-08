# Wikipedia application contract 0

Status: proposed first application contract, 22 September 2026. This describes
target behavior, not current Debian implementation or passed hardware tests.
Names below are semantic operations; message encoding and exact APIs are not frozen.

## Purpose and sources

A person can search Wikipedia, read an article, follow its article links, save
an offline copy and return to their reading position. Losing network access or
interrupting the application should preserve available local work and owner control.

Sources: [reader design](DESIGN.md), [existing implementation](README.md),
[rich renderer integration](NETSURF_INTEGRATION.md),
[Guide View](../../GUIDE_VIEW_1_DRAFT.md),
[capability registry](../../LIVE_CAPABILITY_REGISTRY_0.md), and
[accepted systemd boundary](../../MODERN_FOUNDATION_0.md#accepted-supervision-boundary).

Existing requirements are carried forward. The lifecycle protocol, recovery
record and first-profile choices below are proposals that make them concrete.
Historical direct framebuffer ownership and fixed gateway ports are migration
details, not application privileges established by this contract.

## 1. Application boundary

The application includes its session controller, article requests, parsing work,
private state, and any dedicated gateway or renderer workers. One application
instance owns all of that work even when it spans several processes.

The shell, capability registry/broker, shared storage and network providers, and
systemd are system services. Stopping Wikipedia releases its use of them; it
does not stop services that other applications use.

Proposed first profile: one active Wikipedia instance per owner session. Opening
Wikipedia again returns to that instance. Multiple-instance behavior is deferred.

| Participant | Contract |
| --- | --- |
| Wikipedia | Produces content and actions; tracks reading and jobs; implements pause, checkpoint, resume and orderly stop; reports failures. |
| Guide Supervisor | Identifies the complete instance and workers; coordinates admission, lifecycle requests, grants through the broker, resource allocations and recovery; keeps global control available. |
| systemd through the Guide host adapter | Starts and tracks the configured processes, applies supported isolation/limits and carries out stop/restart operations. Applications do not receive authority to manage systemd themselves. |

A process exit or service restart alone does not establish a successful save,
application-ready state or recovered session. Exact service/group mapping and
host privileges remain integration work. One restart policy must govern each
worker; Guide and systemd must not independently create duplicate instances.

## 2. Capabilities and feature admission

The following are functional requirements, not finalized capability identifiers.
Declaration, provider availability, owner permission and actual acquisition are
separate. All required acquisitions succeed together or provisional holdings
are released. Refusal explains what is missing without implying hardware failure.

| Feature | Needs | Unavailable or denied |
| --- | --- | --- |
| Baseline saved-article reading | Compatible visual Guide presentation, semantic navigation actions and access to the application's private article store. | Missing store is reported as unavailable; an empty accessible store is an ordinary empty state. Missing presentation prevents this installed profile from running. |
| Online search and article retrieval | A compatible authorized knowledge provider or scoped HTTPS adapter, plus semantic text entry for search. | Saved reading remains usable; search explains its limited mode. A different provider is not silently substituted when disclosure changes. |
| Save article and reading checkpoint | Write access to the application's private store, with declared durability and available quota. | Reading can continue with visible save/recovery limitations. No successful-save acknowledgement is issued. |
| Rich article presentation | Installed compatible renderer, its allocated resources and a system-provided private channel if needed. | Use the implemented text path with visible mode change; preserve content and position where representable. No invented speech or alternate renderer fallback. |
| Article images | Separately authorized retrieval and compatible bounded decoding. | Preserve captions/alternative text where supplied; explain omitted images. No image fetching without the relevant policy. |

The existing text reader is the first baseline. NetSurf remains the selected
first rich-renderer path, subject to its integration gates. Neither exact display
dimensions nor a particular controller is part of the portable application contract.
AI, audio, a desktop environment, network administration and unrestricted file
access are not required. A headless or speech-only Wikipedia profile is future work.

Online operations disclose search terms and requested article identities to the
selected provider. Explain this before first use; standing owner policy may
authorize subsequent requests. No background prefetch or automatic refresh,
telemetry, unrelated private data or arbitrary browsing is included. Preserve
verified HTTPS, destination/redirect restrictions and bounded parsing from the
existing design. Article content never grants permissions or executes code.

## 3. Identity and request outcomes

The person selects Wikipedia through the GuideOS interface. Its assigned
application number identifies that application independently of any execution.
The owner's illustrative `00000000` to `99999999` numbering is scalable, not a
fixed array of application slots or reserved resources. No specific Wikipedia
number is assigned by this draft. See the
[shared numbering and footprint direction](../../MODERN_FOUNDATION_0.md#application-selection-numbering-and-footprint).

Guide assigns a fresh instance identity on each launch. Requests identify the
contract version, instance, operation ID, operation, relevant state generation,
and deadline for bounded machine work. Responses identify the same operation,
observed state, outcome and a useful failure reason where applicable.

Outcomes distinguish pending, complete, rejected, unsupported and failed.
Cancellation has its own acknowledged outcome; a cancellation request alone is
not proof that a worker stopped. Repeated operation IDs must not repeat effects.
How deduplication survives restart must be specified with the persistence format.

Content jobs also identify the intended view generation. A late search/article
response from a cancelled job, older navigation or previous instance cannot
replace the current view or claim a completed save. A timeout is uncertainty
about completion until the worker/provider outcome or enforced termination is known.

## 4. Lifecycle

Lifecycle, work activity and presentation are distinct. An active instance may
be idle, fetching or saving; it may be foreground or background. Showing another
application does not itself constitute a pause.

| Operation | Required behavior | Completion evidence |
| --- | --- | --- |
| Start | Use the resource agreement stored at installation, check current availability and acquire permitted instance handles, then start owned workers and load validated local state. No new footprint negotiation or automatic online request. | Ready includes active features and restored-state status; failure releases acquired resources. |
| Pause | Stop admitting content jobs; cancel outstanding fetch/parse work; settle or safely abort an in-progress local commit; retain reading state. Request a checkpoint where permitted. | Paused means owned content jobs are quiescent, with retained/released grants listed. Checkpoint success or failure is reported separately. |
| Resume | Revalidate affected grants and restore the reading session. | Active with feature status. Interrupted network work is not automatically replayed in this first profile; offer Retry. |
| Checkpoint | Capture a consistent session generation in permitted private storage. | Durable acknowledgement identifies the saved generation and storage guarantee, or explicitly reports failure/unsupported durability. |
| Stop | Reject new jobs; cancel pending work; attempt the permitted checkpoint; release workers and grants. | Report checkpoint result separately from cleanup and stopped state. Guide confirms process/resource release through the host adapter. |
| Recover | Start a new instance from the last valid committed checkpoint, with newly acquired grants. | Report what was restored and any missing content. Do not resurrect old grants or replay previous external requests. |

Proposed transitions: starting to active or failed; active to pausing to paused;
paused to resuming to active; starting/active/pausing/paused/resuming to stopping
to stopped. A transition failure reports the actual resulting state; it never
silently claims its requested destination. Fatal failures enter failed, followed
by cleanup and a separately identified recovery launch. Checkpoint is an operation
on a coherent state generation, not a claim that the application is paused.

Pause itself does not require killing the application or freeing all its memory.
Reclaiming it requires a reported checkpoint result and a separate stop. A static
reading view may remain visible while paused, but content actions wait for resume;
the shell's inspect, resume, exit and global controls remain available.

Reading has no session deadline. Machine-operation deadlines come from the
negotiated profile and are visible when they affect the user. If cooperation
fails, Guide may request enforced worker termination through the host adapter
under the declared policy; it must report incomplete saves rather than block
global controls or claim graceful completion.

## 5. Saved information

Distinguish three kinds of storage:

- **Explicit offline articles:** title, language, source URL, page/revision
  identity where available, retrieval context, content and licensing/provenance.
  Explicitly saved articles are not disposable cache entries.
- **Session checkpoint:** current saved/content identity, revision, section/block
  anchor and position, bounded navigation context and current input draft. This
  is private recovery data, not permission to retain an unlimited search history.
- **Disposable cache:** bounded temporary results and decoded images. Eviction
  must not remove explicit saves or the committed recovery record.

Saving an article and checkpointing a reading position are separate operations.
A checkpoint containing only a locator does not make the article available
offline. Recovery with missing content shows that fact and offers authorized
retrieval; it does not silently contact a provider.

Commit a new valid record before acknowledging durability or replacing the last
valid record. Full/read-only storage, removal, revoked write access and corrupt
records have explicit failure results. An interrupted write must leave either
the previous valid version or the new valid version recoverable. Position
anchors must tolerate a different layout; changed revisions may permit only an
approximate position, which must be identified as such.

## 6. Resources and access changes

Under the [Deck resource-space model](../../MODERN_FOUNDATION_0.md#idealized-deck-resource-space),
Wikipedia's installed footprint describes its place across storage, working
memory, processing, networking and I/O. Saved articles occupy persistent storage;
running workers and content jobs use the other agreed resources as needed.
Guaranteed reservations versus shared capacity remain an explicit policy decision.

Contention follows the [shared priority ordering](../../MODERN_FOUNDATION_0.md#accepted-resource-priority-ordering):
tier 0 is critical, including power management and hardware-immediate work;
larger numbers are lower priority. Wikipedia's ordinary reading, retrieval and
rendering work does not acquire tier 0 merely by requesting it. Its exact tier
assignment and any differentiation among its jobs remain to be specified under
Guide policy. The accepted tier catalogue and interruption sequence are in the
[resource contention contract](../../RESOURCE_CONTENTION_0.md). Priority governs
runtime precedence without replacing the installed footprint or bypassing save,
permission and resource-handoff rules. A successful checkpoint while work keeps
changing is insufficient for ordinary unload: the application must also be
quiescent until unload or resume.

Wikipedia requests its memory, processing and other resource footprint at
installation. Guide evaluates the request against this installation and stores
the agreed profile with the application record. The footprint covers the
controller and dedicated workers together. Each execution uses that stored
agreement; it does not submit a new footprint request.

Guide checks current availability and tracks each instance's actual allocation
within the agreement. A temporary shortage is a runtime admission/scheduling
condition, not a reason to silently renegotiate the installed footprint. Fresh
instance identities and capability handles do not replace the stored agreement.
Post-installation changes to the footprint require a defined revision path.

Proposed feature profiles distinguish baseline text reading from online work,
rich rendering and image decoding, including their temporary peak needs.
Profiles must describe implemented behavior; Guide cannot invent a smaller
application merely by granting fewer resources. The installation request,
stored agreement, live allocation and observed consumption are separate records.

The first profile allows one foreground content request at a time and no
unsolicited background content jobs. A named job owns its parsing and optional
image work. Implementation must bound worker counts, queues, requests, decoded
content, navigation history and storage; limits apply to the entire instance,
not independently unlimited workers.

Exact RAM/CPU ceilings, byte limits, storage quota, image concurrency and machine
deadlines need measurement and a versioned host profile before implementation
acceptance. Historical figures such as eight search results and 32 saved articles
are existing prototype limits, not universal hardware requirements. Guide must
report which limits are enforced and which are only cooperative.

Under pressure, discard disposable cache and reduce optional presentation first
where supported; then checkpoint/stop according to policy. Do not silently
delete saved articles, truncate content as if complete or lower requested work
quality without reporting the change.

Network loss cancels affected jobs while retaining readable local content.
Revocation removes access promptly; checkpointing cannot extend a revoked grant.
Loss of storage reports unavailable storage rather than an empty library.
Loss of a required presentation provider requests pause and re-resolution.
Release affects only this instance's jobs and grants, not the shared provider.

## 7. Presentation and failure containment

The shell owns global controls, focus and the approved display/input handoff.
Wikipedia provides semantic actions: Search, Open, Back, Follow link, Save,
Saved articles, Retry and Exit. Adapters map them to available controls. The
application receives neither unrestricted hardware ownership nor network
administration solely because a legacy renderer required those mechanisms.

Each worker is attached to the application instance before it can perform work.
Renderer/gateway failure must remain escapable and must clean up owned work.
Guide Supervisor failure needs reconciliation with surviving host-managed
processes and durable state before new work is admitted; the exact fail-closed
mechanism remains part of the host integration specification.

On system shutdown, Guide coordinates the permitted checkpoint and stop sequence
within the host shutdown budget. systemd performs underlying shutdown. The
application cannot power off the system or veto shutdown indefinitely. Unavoidable
loss of uncommitted work is reported when possible, not represented as saved.

## 8. Acceptance examples

These are required evidence for the proposed contract, not tests already passed.

1. Offline launch opens a saved article with network permission denied and
   produces no outbound request. An empty library and missing storage differ.
2. Online search requires its scoped grant. Revocation stops affected access;
   late results do not overwrite newer navigation or paused state.
3. Pause during fetching and during a save produces truthful quiescence and
   checkpoint outcomes; resume preserves position and does not replay the fetch.
4. Full storage or interrupted commit never yields a false Saved indication;
   the last valid committed data remains recoverable after restart.
5. A renderer/gateway crash or hung worker cannot block global exit; its workers
   and leases are released without stopping another application's providers.
6. Resource pressure affects the whole instance and preserves explicit saves.
   Supervisor restart does not duplicate the instance or revive expired grants.
7. Real display/input handoff leaves one coordinated owner; repeated entry/exit
   and shutdown do not produce competing console writes or orphaned renderers.
8. Recovering after an interrupted session restores only committed state, explains
   missing content and retains meaningful position across supported layouts.
9. Repeated launches use the resource agreement established at installation,
   without new footprint requests. A temporary shortage is reported or scheduled
   under runtime policy without silently changing that agreement.

Validate application logic, provider/host integration and physical behavior
separately. Before implementation, close the remaining details: versioned message
schema, persistence/deduplication format, host unit/isolation mapping, supervisor
failure policy, and measured limits. No new image is authorized merely by the
existence of this draft.
