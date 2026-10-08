# GuideOS design alignment 0

6 October Nearby/network tools: [Nearby and network tools](NEARBY_AND_NETWORK_TOOLS_0.md)
adds owner-initiated Wi-Fi and Bluetooth observations, bounded signal watch,
and explicit Nmap/ping/DNS/route jobs in Settings. The shell retains input,
presentation and cancellation; one system connectivity provider owns radio
sessions and bounded unprivileged tool children. Sixteen focused checks and
native ARM loopback/cancellation fixtures establish source and image evidence;
physical radio/UI behavior remains a Deck retest. The private trusted-shell
adapter is provisional and does not close the shared broker/job protocol gap.
Observation or reported service data does not establish connection authority,
distance, or a confirmed vulnerability. See the feature record for footprint
and the unresolved monitor-mode/injection hardware boundary.

6 October video-track preparation: [Video options](VIDEO_OPTIONS_TRACKS_0.md)
adds Select-driven subtitle/audio controls to the current native player and
preserves alternative audio in Node-side FFmpeg preparation. Host control and
real conversion evidence remain separate from physical Deck rendering. The
native card-descriptor player still lacks its Node source-provider integration;
this menu work does not resolve that shared-source gap or establish streaming
acceptance.

Step 1 follow-up, 26 September 2026: the [installed application host](APPLICATION_HOST_0.md) is implemented and host-verified, with staged ARM64 binaries and runtime dependency. The earlier probe-only readiness assessment below is historical. No seed write or physical acceptance is claimed. Cartridge catalog/installer work remains step 2.

The [Notepad integration review](NOTEPAD_INSTALLATION_INTEGRATION_0.md) reconciles the Musings visual/runtime handoff with current application-host, cartridge installer and document-provider readiness. This is documentation integration only.

The [3 October Notepad UI review](NOTEPAD_UI_REVIEW_2026_10_03.md) identifies
the missing document viewport, chunked reading, generic text-field metadata and
clean-note recovery prompt. The owner-approved
[polish implementation](NOTEPAD_UI_IMPLEMENTATION_2026_10_03.md) adds semantic
notes/document surfaces, native field metadata and caret recovery while retaining
mediated storage and shell-owned input/display. The shared host extension must
ship with the cartridge; source checks and offline image staging remain distinct
from Seed installation and physical acceptance. [Quick Find 0](QUICK_FIND_0.md)
adds bounded offline filename/application search through existing owner-facing
providers; private Notepad drafts require a later mediated listing. The signed
0.4.3.06 candidate passes focused source/provider checks but is not installed.

26 September 2026 physical follow-up supersedes the earlier readability failure: new text is accepted and dynamic terrain visibly works. Stars remain invisible and initial card recognition required reinsertion. Source corrections remain separate from installed behavior; see [follow-up](CARD_STAR_FOLLOWUP_0.md).

26 September 2026: physical Field readability failed (status strip accepted); owner confirmed boot and external card recognition, but observed old fixed globe/no stars. A larger-type candidate is validated but not installed. Boot generator selection still needs card journal evidence. See [readability correction](READABILITY_CORRECTION_0.md).

Reviewed: 22 September 2026. This is a requirements index and reconciliation
record, not a replacement architecture or a frozen interface specification.

The owner reaffirmed that implementation must follow the existing GuideOS
documents. A local feature request carries those requirements with it. The
current diagnostic is evidence about one implementation, not the definition of
the product.

## Current direction and evidence

Boot visual follow-on, 2 October: the owner selected the finalized corona revision
2 from “Planegotchi 0.1 (2)” for the pending [0.4.2.06 update](BUILD_0_4_2_06.md).
The prepared root candidate replaces the baked 640×480 stream under the existing
native boot player. All 75 frames match the approved export. Source and installed
ordering validation now follow the existing shell drop-in and first-frame notify
contract; eight Linux lifecycle/cleanup tests pass. Seed deployment and physical
playback/handoff remain pending. Home artwork and runtime display ownership are
outside this asset replacement.

Field Theme/card integration, 26 September: [implementation evidence](FIELD_THEME_IMPLEMENTATION_1.md)
records the Musings visual handoff implemented across shell and keyboard surfaces,
with shared hit geometry and existing provider semantics. The combined image
passed 415 regression and 14 boot tests, was rebased onto a fresh seed capture,
and was written/readback-verified with boot/data unchanged. Physical acceptance
remains pending; existing architectural risks and shared contracts are unchanged.

Dynamic-globe follow-on, 26 September: [Dynamic globe prototype](DYNAMIC_GLOBE_0.md)
resumes the accepted atlas and per-boot world sequence under the existing boot
service. Generation is bounded, fixed assets remain the fallback, and display
ownership/lifecycle remain with the existing boot path. The cloud atlas, seeded ocean wave textures and 12 faint twinkling stars are integrated. Fourteen animation
tests, native runtime checks and GLES shader previews passed in ARM64 emulation.
Physical timing and shell handoff remain pending. Full coastline connectors
and courier animation remain deferred; no shared broker contract changes.

External-card follow-on, 25 September: [External card recognition 0](EXTERNAL_CARD_RECOGNITION_0.md)
adds a single read-only TF2 recognition owner, exFAT/UTF-8 modules and a shell
screen. The staged image passed 395 tests; physical TF2/exFAT acceptance remains
pending. This is a narrow provider integration, not a replacement for the shared
broker/IPC contracts. The owner also confirmed onboard speaker output works after
the installed audio-output-v2 and System Status Audio test changes.

Physical follow-up, 25 September: [Audio/control review](AUDIO_CONTROL_PHYSICAL_REVIEW_0.md)
records owner acceptance of menus and the overlay. Boot phase deadlines now
complete normally, but the globe has a mask-boundary artifact and several
seconds of setup delay. Decoder progress is confirmed but speaker output was
inaudible; low saved hardware gains are a lead. Bluetooth discovery failed with
inadequate feedback, and coarse error records do not establish the radio cause.

Control follow-on, 25 September: [Resident diagnostic overlay](CONTROL_OVERLAY_0.md)
owns input independently and freezes the current shell cgroup while displaying
diagnostics. Virtual acceptance covers pause, continuing audio, resume and crash
recovery. The physical chord, transparent display and Power behavior remain
pending. Boot animation is excluded by owner choice; future independent display
owners require an explicit handoff. Activation is deferred while the overlay is
open, preventing diagnostic pause from disrupting a deployment health trial.

Observability follow-on, 25 September: [Lightweight diagnostics 0](DIAGNOSTICS_0.md)
adds bounded process-tree/resource history, common error summaries, playback
metrics and aggregate command/navigation timing. It observes rather than assigns
resources. Five-second sampling misses short-lived work; physical display/audio
behavior and monitor overhead still require Deck measurements. The current video
instrumentation covers boot animation, not a future general video player.

Audio follow-on, 25 September: [Audio and Bluetooth integration 0](AUDIO_BLUETOOTH_0.md)
adds a staged, optional trusted-shell media provider with explicit output choice,
bounded pairing, global volume and independent shutdown. Its IPC is not yet the
shared capability broker. Local speaker routing, earbud stability and measured
resource use require physical acceptance. Visual boot animation is owner-confirmed;
the separate initialization/playback budgets are a subsequent staged correction.

- [AT Field](../AT_FIELD_0.md) is the approved Closed/Familiar/Open communication
  setting. Its first source integration is in desktop Node discovery, pairing and
  settings; Deck shell integration and physical interface validation remain open.
- The owner clarified that early social "cyberspace" guidance does not impose
  universal anonymity, absolute separation or zero risk on GuideOS. Security
  measures should fit actual exposure and practical costs. Distinguish explicit
  requirements from philosophical preferences and implementation choices; see
  [the working guidance](../../docs/DEVELOPMENT.md#design-and-source-guidance).
- Minimal Debian is the selected new system base. The retained Buildroot tree
  records earlier implementation work.
- The owner accepted systemd as PID 1 for Debian, with Guide Supervisor above
  it. This supersedes the earlier custom-init arrangement. The accepted boundary
  is recorded in [Modern foundation 0](../MODERN_FOUNDATION_0.md#accepted-supervision-boundary).
- RG35XX H is the present physical target. Pi Zero 2 W is a future portable,
  optionally headless Node target. Neither establishes universal minimum
  hardware, a mandatory display, or mandatory AI.
- The owner adopted the personal-computer hobbyist experience for the broader
  network: useful personal machines, inspectable/exchangeable cartridges, known
  peer services and deliberate sharing across different hardware. See the
  [accepted experience and resource implications](../MODERN_FOUNDATION_0.md#accepted-personal-computing-and-network-experience).
- GuideOS 0.3 "Liquid Snake" booted, but its physical diagnostic run failed.
  [The failure audit](LIQUID_SNAKE_FAILURE_AUDIT.md) is the current evidence for
  that run. Image readback and simulated tests did not establish a working
  interface or clean shutdown.
- Earlier application implementations remain useful source and historical
  evidence. Their existence does not establish integration into the Debian
  image. Porting and acceptance must be recorded per component.

## Source map

| Source | What it establishes | How to use it |
| --- | --- | --- |
| [Guide and prototype definition](../../HHG_Foundation/02_GUIDE_AND_PROTOTYPE_DEFINITION.txt) | Person-owned Deck, independent Nodes, normalized devices, bounded services, portable personal data and continuity milestones. | Product scope and acceptance intent. |
| [Design philosophy](../../HHG_Foundation/03_DESIGN_PHILOSOPHY.txt) | Agency, accessibility, local usefulness, inspectability, recovery and adaptable technology. | Invariants across implementation changes. |
| [Future framework](../FUTURE_FRAMEWORK_0.md) | Application contract, Guide View/Media/Remote surfaces, global controls, component responsibilities and conformance. | Shared architecture; proposed schema names and example budgets remain provisional. |
| [Modern foundation](../MODERN_FOUNDATION_0.md) | Debian selection, board profiles, application/service/job contracts and storage separation. | Later foundation direction; dated build observations remain historical. |
| [Live capability registry](../LIVE_CAPABILITY_REGISTRY_0.md) | Definitions, offers, requirements, grants, evidence, resolution and revocation. | Proposed registry/broker/supervisor boundary, not an implemented API. |
| [Guide View draft](../GUIDE_VIEW_1_DRAFT.md) | Semantic UI, focus, actions, accessibility, error behavior and global escape. | Presentation contract under development. |
| [Cartridge format](../CARTRIDGE_FORMAT_1.md) | Inspectable packaging and integrity; requests do not confer authority. | Packaging contract, distinct from runtime admission and permissions. |
| [Network deployment draft](../NETWORK_DEPLOYMENT_0.md) | Owner-requested network development updates up to 100 MB, proposed transport, staged activation and local recovery. | Theoretical implementation plan; not an installed remote-access service or a completed update contract. |
| [System update framework](../SYSTEM_UPDATE_FRAMEWORK_0.md) | One signed system-update bundle, Wi-Fi and cartridge receipt adapters, local authorization, staged activation, health trial and rollback. | Proposed common system-update contract; initially limited to immutable Guide releases and not yet installed or physically accepted. |
| [Guide Signed Bundle 1 draft](../SIGNED_BUNDLE_1_DRAFT.md) | Common byte-level container, canonical identity, Ed25519 signature, profile-scoped trust and validation contract. | Draft for owner approval; consumer behavior belongs to separately versioned profiles. |
| [Guide Release Profile 1 draft](../GUIDE_RELEASE_PROFILE_1_DRAFT.md) | Immutable Guide releases with a 100 MB ceiling, explicit bases, bounded trial and previous-release rollback. | Draft profile; not implemented, installed or physically accepted. |
| [Runtime Pack Profile 1 draft](../RUNTIME_PACK_PROFILE_1_DRAFT.md) | Immutable shared dependencies with a 1 GiB ceiling, broker resolution, coexistence, leases and safe removal. | Draft profile; not implemented, installed or physically accepted. |
| [Superseded combined package draft](../SYSTEM_UPDATE_PACKAGE_1_DRAFT.md) | Earlier combined packaging and Guide-release proposal. | Design history only; superseded before approval by the common bundle and profile split. |
| [Runtime Pack 0](../RUNTIME_PACK_0.md) | Immutable, versioned shared dependencies, broker resolution, reference-aware removal and class-specific storage limits. | Adopted architectural direction; schema, enforcement and physical behavior remain unimplemented. |
| [Local media player](../LOCAL_MEDIA_PLAYER_0.md) | Existing ownership, pause acknowledgement, bounded cleanup and saved-position requirements. | Preserve the behavior when extracting shared services; distinguish historical mechanisms and controls from the common interface. |
| [Media Services 1](../MEDIA_SERVICES_1.md) | Adopted pre-0.4.0 local, Node and provider-ready media service boundary. | Governs library, session, source, buffering, supervision and acceptance design; engine support remains evidence-dependent. |
| [Media Engine Adapter 1](../MEDIA_ENGINE_ADAPTER_1.md) | Adopted GStreamer audio/mpv video split, bounded high-water buffering, clock and recovery rules. | Initial thresholds are provisional until physical Deck measurement; FFmpeg remains fallback evidence. |
| [Media engine source handoff](MEDIA_ENGINE_SOURCE_HANDOFF_0.md) | Steps 1–4 source evidence and exact next-image integration requirements. | Handoff only; no assembled image, seed write or physical acceptance. |
| [Media IPC 1](../MEDIA_IPC_1.md) | Versioned Envelope 0 operations, records and events for media discovery and acknowledged playback. | Generated metadata plus first host-tested enforcing brokers; production activation and playback remain open. |
| [Media Library 1 evidence](MEDIA_LIBRARY_1_IMPLEMENTATION.md) | Host-tested bounded storage catalog, same-namespace lifecycle adapter, opaque records and contained descriptor open. | Source/host evidence only; production socket activation, events and physical media remain open. |
| [Media Session 1 evidence](MEDIA_SESSION_1_IMPLEMENTATION.md) | Host-tested owner-bound acknowledged state machine, bounded events, cleanup and enforcing broker. | Source/host evidence only; decoder/output adapters, installed services and physical playback remain open. |
| [Semiotic Engine protocol](../SEMIOTIC_ENGINE_PROTOCOL_0.md) | Bounded jobs, cooperative cancellation, response validation and limited authority. | An existing service-specific contract, not a complete OS lifecycle contract. |

Owner instructions additionally establish control over updates and permissions,
whole-application supervision, a deliberately low hardware floor, preservation
of work where possible, and the current diagnostic exclusion of Start, Power
and Reset. Those exclusions do not remove finished-system global controls.

## Requirements carried into implementation

The owners below are logical responsibilities. This table does not require one
process, daemon, programming language or network service for every row.

| Requirement | Responsible boundary | Observable acceptance |
| --- | --- | --- |
| The owner controls consequential actions and updates. | Policy/capability broker and system update service. | Denial or revocation stops the scoped action; an application cannot grant itself access or override update policy. |
| Hardware varies without redefining applications. | Board adapters, providers and capability registry. | An absent optional provider produces an honest limited mode; a missing required provider prevents that feature from starting with a useful reason. |
| Availability, permission and resource possession are distinct. | Registry discovers; broker authorizes; supervisor assigns resources. | A discoverable display cannot be used solely because it exists; a failed required acquisition releases the resources already acquired for it. |
| GuideOS manages complete applications. | Supervisor and application runtime, with explicit ownership of helpers, jobs, grants and state. | Closing or failing one application accounts for its owned work and releases its resources without stopping an unrelated shared provider. |
| System duties remain available across application failures. | System-owned services and global-control path. | A stalled application cannot prevent navigation, cancellation or coordinated power handling; shared services have their own lifetime. |
| Presentation adapts to available interfaces. | Shell, semantic renderer, input and display services. | Focus and control meanings are visible and predictable; display handoffs have one accountable owner; a missing rich surface is explained. |
| Interruption preserves work where supported. | Supervisor, application, storage and power services together. | Pause or checkpoint has a reported outcome; saved means the stated durability was achieved; cleanup failure does not silently become successful shutdown. |
| Optional intelligence has no independent authority. | Agent broker, capability broker and bounded Engine provider. | Losing an Engine leaves deterministic local functions usable; generated requests still pass authorization. |
| Creation and exchange remain accessible. | Recipe tools, package validator and runtime. | A person can inspect access, try, stop and share a small program; receiving its package transfers no existing grant. |

Sources: the product definition and philosophy establish the cross-cutting
requirements; the framework and Guide View define presentation/control;
the registry draft defines discovery and acquisition; modern foundation and
the media/Engine contracts supply lifecycle, resource and recovery requirements.
The acceptance statements above are derived checks, not claims of passed tests.

## Reconciled differences

| Difference in the records | Working interpretation |
| --- | --- |
| Buildroot baseline versus later Debian selection. | Debian governs new foundation work. Keep the old pins and instructions as reproducibility history, not current deployment instructions. |
| Older feature-first stage lists put the supervisor late. | The later modern-foundation sequence calls for shared registry/supervisor contracts before richer application integration. Hardware probes establish adapter evidence; they do not become the product runtime. |
| Capability trees versus endpoint and format compatibility. | Use the tree for discovery vocabulary. Use typed relationships and constraints for compatible combinations; a parent category never grants everything below it. |
| Existing player A/B controls versus the semantic Guide View controls. | Record the legacy mapping and resolve the surface action mapping explicitly during integration. Do not copy a local mapping into global policy. |
| A device is present versus a feature is usable. | Preserve separate evidence, readiness, authorization and allocation results. Do not infer success from enumeration or a request being sent. |
| "Finished" diagnostic report versus failed cleanup/service exit. | Preserve test coverage, operator action, saved-state outcome and system completion separately. The physical failure audit takes precedence over the test's optimistic summary. |

## What remains to be specified

The post-0.4.2 GPU UI adapter preserves semantic focus/input and releases display
ownership before Browser or Video acquisition. Its source/build/preview evidence
and outstanding hardware acceptance are recorded in
[GPU UI compositor](GPU_UI_COMPOSITOR.md). It has bounded textures and an explicit
software recovery path. Actual display release, performance, memory pressure and
global-control responsiveness remain physical evidence gaps; a compiled renderer
does not close the shared presentation/lifecycle risks.

The [0.4.2.02 follow-up](BUILD_0_4_2_02.md) refreshes the saved framebuffer before
handoff and supplies a cached static video-opening graphic. It moves output and
earbud controls into Settings → Audio, separating player/provider presentation.
It invalidates abandoned media launches, ignores stale catalogue replies, and
serializes cleanup of an in-flight open before replacement work. Display release
waits for cleanup acknowledgement. Stopped/completed media uses Play to reopen
through source-generation and display admission checks; Resume is reserved for
paused playback. Source transition inspection uses simulated provider replies,
and does not establish native cleanup or display ownership on hardware.
The fresh 0.4.2.01 capture and owner feedback also exposed browser address-target
ambiguity and a reproducible offscreen details-button rectangle failure after
Media return. Explicit address submission and bounded details drawing are in the
same 0.4.2.02 generation. Leased display polling avoids an expired draw deadline;
host fixtures and renders support these corrections, while Deck input, Internet
navigation and CPU improvement remain physical checks.
Desktop HandBrake preparation produces a smaller copy while preserving owner
originals. The signed UI/browser update is now installed over Wi-Fi, committed
as 0.4.2.02/sequence 61, and its current GPU shell is ready. Copied media is
readback verified; playback/display performance remains a physical acceptance
gap. The updater retains an earlier external-power error after commit and still
displays it; this misleading reason persistence remains an update-status defect.

The design already names the necessary components. The missing work is a shared,
implementable contract between them. It is inaccurate to say that no lifecycle
or resource design exists: the media and Engine documents already define parts
of it. The reviewed documents do not yet provide a complete common contract for
these points:

1. **Ownership and identity:** distinguish an installed application, a running
   instance, its jobs and helpers, and system-owned or shared services. Define
   attachment, detachment and crash consequences without treating a PID as
   durable application identity.
2. **Lifecycle transitions:** specify initiation, admission, running, pause,
   resume, checkpoint, stop, failure and recovery; define requests, actual
   outcomes, unsupported behavior and allowed transitions. Loss of focus,
   application pause, process suspension and whole-device sleep need distinct
   meanings.
3. **Resource contract:** connect requested and granted ceilings, scheduling
   priority, device leases, pressure handling and enforcement evidence. Define
   what happens when a required bundle is only partly available. Example
   budgets are not universal minimums or measured guarantees.
   Footprints are requested at installation and reused at execution. The owner
   established critical tier 0 as highest priority, with larger numbers lower;
   [priority ordering](../MODERN_FOUNDATION_0.md#accepted-resource-priority-ordering)
   records this decision and the remaining contention-policy details.
   The [contention contract](../RESOURCE_CONTENTION_0.md) records the subsequently
   accepted tier names, lower-tier progress, bounded interruption and playback-first
   exception. Its C decision component has host tests; actual host enforcement
   and hardware acceptance remain open.
   Subsequent [transfer-provider integration](../TRANSFER_PROVIDER_0.md) connects
   the C allocator to real HTTP workers and exercises them under systemd and
   emulated Debian ARM64. Device networking, real link measurements and decoded
   playback remain unverified; this is not a completed Guide runtime.
4. **Interruption and durability:** identify what is being saved, when its
   acknowledgement is durable, how pending work is cancelled, and what survives
   restart. Specify bounded recovery/escalation without making reading time a
   countdown or falsely promising that arbitrary work can always be saved.
5. **System integration:** implement the accepted systemd-PID-1/Guide-Supervisor
   boundary. Define authorized host operations, application-to-service mapping,
   shell replacement, input/display transfer, emergency control and coordinated
   shutdown. Distinguish systemd service restart from application-state recovery;
   avoid competing restart policies and dependence on an application's cleanup.

`IPC_ENVELOPE_0.md` now fixes the local message transport, fixed header, profiled
CBOR shapes and limits, connection identity boundary, descriptor correlation,
outcomes, request lifecycle and interface-evolution rules. Its WSL development
spike and production-preparation suite pass C/Python exchange, generated-registry,
shared-transport, identity-resolution, grant and harmless health-service tests.
`IPC_PRE_ARM64_REPORT_0.md` records the recommended installable boundary. These
are not real systemd reconciliation or physical-Deck evidence. The C runtime
subsequently passed bounded ARM64 image verification without enabling a broker;
see `IPC_ARM64_IMAGE_VERIFICATION_0.md`. Application/service/job transition names, the production
schema generator and shared library, Supervisor resolution, capability-service
integration, resource enforcement and coordinated restart policy remain work.

## Existing supervisor: useful starting evidence, incomplete contract

Its [package description](../package/guide-supervisor/Config.in) and
[compatibility bridge](../board/rg35xxh/post-build-vendor-bridge.sh) identify the
earlier supervisor as PID 1. That deployment arrangement is superseded for
Debian. Preserve this code as earlier implementation evidence; adapt its init,
process-management and shutdown paths before reuse above systemd.

The inspected [protocol header](../package/guide-supervisor/src/guide_supervisor_protocol.h)
and [implementation](../package/guide-supervisor/src/guide-supervisor.c) provide
RUN/SHUTDOWN requests, four fixed application identifiers, one active session,
process-group cleanup, child reaping and scheduling priorities.

They do not yet express application pause/resume, checkpoint acknowledgement,
capability grants, resource reservations or durable instance recovery. Session
execution waits for the child before returning to the main request loop.
Priority adjustments and a fixed process-record array are not an enforced
per-application resource budget. This is a source inspection, not evidence that
this supervisor is installed in the current Debian diagnostic.

## Next implementation boundary

The owner approved `SUPERVISOR_CAPABILITY_FOUNDATION_0_PROPOSAL.md` on 25
September 2026. It now governs the common lifecycle/identity model, the separate
privileged C Supervisor and unprivileged C capability broker, volatile grants,
restart reconciliation, harmless probe proof, verification stages and recoverable
installation gate. Its filename is retained for link stability; its status is
approved architecture. Stages A through C are the active implementation boundary.

`DEBIAN_SHELL_0.md` now records the first implementation of this boundary. Its
source tests, ARM64-rootfs checks and assembled-image validation pass. It masks
the competing tty1 getty, installs one supervised shell owner, excludes the
dedicated Power input from the shell and retains systemd-logind as the independent
orderly-power path. It was installed and seven saved runs now record navigation and
shell-requested shutdown. A later Wi-Fi candidate was reported not to boot and
the previous shell root was restored. The full hardware acceptance remains open;
see the [24 September audit](SYSTEM_AUDIT_2026-09-24.md).

The next controlled revision, [Shell 1](../DEBIAN_SHELL_1.md), added reporting
fault tolerance and persistent boot evidence with verified root readback.
The owner explicitly skipped its intermediate physical test and directed work
to continue until Wi-Fi testing. [Wi-Fi discovery 1](../WIFI_DISCOVERY_1.md) is
now installed with verified readback: 25 ARM64 tests, two virtual boots, live
no-radio discovery/rescan/cancellation and journal recovery pass. Physical
acceptance is now partially established: the owner reports a successful run,
and returned logs confirm a fresh nine-network scan, scrolling, B cancellation
of a rescan and orderly shutdown. See the
[physical result](WIFI1_PHYSICAL_RESULT_2026-09-24.md). Bluetooth initialization
warnings predate this build and remain a separate unvalidated hardware path.

The first concrete application draft is the
[Wikipedia application contract](../apps/wikipedia/APPLICATION_CONTRACT_0.md).
It supplies an initial case for the shared lifecycle/resource contract, with
explicit proposals and acceptance examples; it is not yet an implemented API.

The next implementation artifact is the common application/service/job lifecycle
and resource contract built on Envelope 0, derived from the requirements above.
Its first integrated
proof should exercise one small local application, its owned worker, a shared
provider, and the system control path. It should demonstrate resource denial,
interruption with acknowledged state, resource release, failure recovery and
continued owner control before adding richer applications.

That proof should use both controlled failures and the actual Linux/display/input
integration. On hardware, separate boot, display, input, state durability and
power results. A simulated UI or successful image copy cannot stand in for
those observations. Existing evidence remains preserved; this alignment work
does not create or install another image.

## Active architectural risks

The owner subsequently narrowed Wi-Fi work to a basic discovery tool.
[Wi-Fi discovery 0](../WIFI_DISCOVERY_0.md) records the shell integration, owned
scan child, NetworkManager adapter and evidence limits. Source/ARM userspace
tests pass. An earlier user-mode emulator check failed, but full-system ARM
guests now start NetworkManager and run the real discovery adapter successfully
with no radio present, including a 512 MB guest. A physical discovery run now
passes as recorded above. The owner subsequently requested connection controls,
saved credentials, low-power reconnection and nearby signal monitoring.
[Wi-Fi connections 2](../WIFI_CONNECTIONS_2.md) implements that next slice as a
shared provider above NetworkManager, with local password entry and persistent
manual-disconnect policy. It retains the shell's display/input ownership and
systemd's power path. Source and virtual integration evidence are distinct from
pending physical association, reconnection, timing and power-consumption tests.
The five-second switching budget produces success or a visible timeout/cleanup
state; it cannot guarantee another network's authentication or DHCP response.
The owner currently has only one network available for physical testing.
The returned Wi-Fi 2 run failed connection: Guide aborted four attempts following
roughly 302 ms D-Bus errors before authentication completed. The
[failure analysis](WIFI2_CONNECTION_FAILURE_2026-09-24.md) records the distinction
between working discovery, premature provider cancellation, and unproven
association/credential persistence.

The [6 October returned-Seed cold-boot failure](WIFI_COLD_BOOT_FAILURE_2026-10-06.md)
is a separate lower-level fault: the radio enumerated, but SDIO transfers and
firmware/chip initialization failed before a Wi-Fi interface existed. Seven
earlier retained boots with the same kernel created the interface. The owner
confirmed a full power-off before this failure. The authorized 0.4.4.01 image
includes a board/device-specific bounded driver re-probe after this exact
current-boot timeout, plus a specific missing-adapter discovery result. Image
and emulated recovery checks passed; the Seed root write/readback is complete.
The owner stopped the remaining full-data scan and directed lighter verification
for this hobby project; the release record distinguishes those outcomes.
Repeated cold-boot discovery/connection acceptance remains open. Re-probing
has not yet been shown to resolve this intermittent failure on the Deck.

The [shared text-entry implementation](../TEXT_ENTRY_0.md) separates portable
editing/session ownership from controller mapping and the prototype renderer.
Wi-Fi is its first shell consumer. Application-wide focus arbitration, other
input methods and full international text support remain future integrations;
the internal routing token does not replace application permissions.

The experimental [menu pointer](../MENU_POINTER_0.md) and keyboard stick controls
share the shell's existing input owner. Complete controller frames feed portable
models; switching modes, dropped input and device loss clear pending gestures.
Menu context actions retain their target identity through Wi-Fi refreshes.
Cursor movement redraws the interface without repeated report writes. Source
tests and rendered screens do not establish physical stick calibration, readable
on-device output or successful display/input handoff; those checks remain open.

The owner requested continuing oversight on 22 September 2026. These entries
identify unresolved risks for implementation; they are not additional approval
gates. Update them as evidence changes, keeping the original acceptance intent.

The [audio recovery revision](AUDIO_RECOVERY_1.md) responds to the returned-seed
silent-speaker and hidden-Bluetooth-failure observations. Analog gain is isolated
in the RG35XX H board profile; playback/pairing remain provider-owned, and the
shell retains display/input. Fixed error categories and bounded route/mixer
samples provide evidence without continuous discovery. The shared status bar
and nonblocking internet time service are included. Unit and virtual service
checks cannot establish audible output, board radio initialization, or accessory
compatibility. The previous animation artifact remains explicitly unresolved.

The fixed globe boot-animation prototype is now source-complete, ARM64-compiled
and installed in the non-physical Debian staging root. It discovers the DRM card
with the connected display rather than assuming a card number, runs as a bounded
oneshot before the shell, and restores the prior CRTC before exit. Its baked
terrain/cloud rendering, page-flip behavior and shell handoff have not yet run on
the Deck. This work therefore adds a controlled display-owner transition to the
existing physical arbitration risk; it does not resolve that risk.

| Risk | Consequence | Evidence needed to close it |
| --- | --- | --- |
| Shared lifecycle and ownership remain incomplete. | UI pause can leave work running; helpers or grants can outlive their owner; an app can stop shared services. | Common contract and an integrated application/worker/shared-provider failure and recovery exercise. The 0.4.2.05 development candidate bounds discovery, browser observation and directory workers with cancellation and generation checks; these focused checks do not close the shared lifecycle risk. |
| Network deployment can replace the components needed to recover it. | A failed Wi-Fi, shell or updater change can strand the Deck; binary rollback can disagree with mutable state. | The network deployment draft requires independent local recovery, coherent release ownership, compatible state, and disconnect/power-loss exercises before these update classes are enabled. Physical Wi-Fi connection and one bootstrap installation remain prerequisites. |
| Display, input and emergency controls lack physically demonstrated arbitration in the new foundation. | Competing services corrupt the interface; ordinary input is consumed by navigation; stalled work can block owner control. | The shell-0 candidate and bounded boot animator supply reviewed service configuration; physical evidence is still needed for animator-to-shell DRM handoff, visible focus, interruption, cleanup and independent Power recovery. |
| Completion and durable state are not yet coordinated end to end. | A successful-looking report can coexist with failed cleanup or lost work. | Distinct checkpoint, cleanup and power outcomes, including injected failures and restart verification. |
| Legacy implementations can be mistaken for validated Debian features. | Planned applications inherit unsupported assumptions about drivers, services and available resources. | Per-component integration records tied to the exact image and measured board profile. The [GPU video source follow-on](GPU_UI_COMPOSITOR.md#video-rendering-follow-on--2-october-2026) distinguishes observed rendering from decoding; The baseline lacked H700 hardware-decoding support; the 0.4.2.05 Cedrus boot/root candidate now has matching kernel/device-tree/runtime integration and verified Seed readback, with physical use still unverified. |
| Prototype shortcuts can become permanent shared policy. | Local fixes raise the hardware floor or contradict global controls, permissions and portability. | Each substantial change identifies its source requirement, owner, assumptions and acceptance evidence before and after implementation. [0.4.2.05](BUILD_0_4_2_05.md) records bounded caches and asynchronous I/O owners; CPU weights, memory limits and decoder tuning remain dependent on measured Deck behavior. The [0.4.3.01 Browser freeze investigation](BROWSER_FREEZE_0_4_3_01.md) confirms PAM migration bypassed launcher-service limits. The [0.4.3.02 containment and resident recovery candidate](BUILD_0_4_3_02.md) implements whole-session limits, protected global controls, early Browser closure, bounded zram and confirmed Start + Select recovery. The [3 October controlled capture](BROWSER_STARTUP_CAPTURE_2026_10_03.md) confirms physical pressure closure and memory recovery on Google alone; shortcut and broader workload acceptance remain open. The [0.4.3.03 repair](BROWSER_MEMORY_REPAIR_0_4_3_03.md) reduces GTK rendering/cache overhead and adds allocation measurements without raising containment limits. The owner installed 0.4.3.03; paired capture confirms lower main-process startup RSS and Google remaining active, but exposed frozen native keyboard input. The [0.4.3.04 follow-up](BROWSER_KEYBOARD_REPAIR_0_4_3_04.md) fixes redundant redraws, cancellation queueing and retry duplication; it is installed, with physical input acceptance unconfirmed. The owner subsequently paused web browsing; [0.4.3.05](BUILD_0_4_3_05.md) removes its Home/controller routes and refuses service launch while preserving source for a later engine. Initial Wi-Fi delivery was rejected for insufficient storage. A freshly captured Seed now contains the signed offline .05 image, expanded to the full card with a 4 GiB system partition, Browser-exclusive dependency/cache removal and only .04 retained as rollback. The [resident recovery repair](CONTROL_RECOVERY_FAILURE_2026_10_03.md) is installed with full-root readback verified; owner-data filesystem/content readback and ARM64 image checks also passed. Deck boot and physical UI/recovery acceptance remain pending. The installed Planegotchi assets and unchanged containment remain preserved. |

Oversight should make the next decision clearer: report the specific conflict,
likely consequence and recommended correction. It should not turn routine work
into repeated permission requests or substitute documentation for a functioning
system. The [development guide](../../docs/DEVELOPMENT.md) carries this practice forward.

## 0.3.7 integration checkpoint (25 September 2026)

The [0.3.7 handoff](RELEASE_0_3_7_HANDOFF.md) supersedes stale implementation
status above where it lists newer physical evidence. Normal speaker playback
is now audible with the board-scoped DMA transfer correction; low volume remains
open. Wi-Fi boot reconnection, time synchronization, corrected globe appearance
and running-interface diagnostics overlay have owner confirmation. Shared
application lifecycle, broader resource enforcement, full UI migration and
cross-device capability contracts remain unfinished. The 0.3.7 final image
passed 349 tests and integration checks, was rebased onto the returned seed, and
was written with full readback verification. Boot/data are unchanged. Its next
physical boot and louder-tone test remain pending.

Audio output follow-up, 25 September: [Output correction](AUDIO_OUTPUT_CORRECTION_0.md)
implements speaker gain, board-specific ramp/line-out ownership and deterministic
stereo routing after the audible-but-quiet 0.3.7 result. Physical loudness,
distortion and power-transition acceptance remain unresolved. No further
listening tests were run; broader media conformance is not established.


### 0.3.9 cold-start and TF2 continuation, 27 September 2026

The application/provider lifecycle risk now has actual systemd evidence for
cold-provider ordering, bounded provider failure, retry without data deletion,
ordinary cold launch, and preservation of saved work. Queued inactive jobs no
longer count as completed health checks, and failed reinstalls clean up only
the candidate release. The owner record and grants persist. Applications makes
uninstalled identity records explicit. See [the result](RELEASE_0_3_9_STARTUP_RESULT.md).

This closes the reproduced host startup cases, not the shared lifecycle risk in
full and not physical acceptance. The 0.3.9 root image is preservation-audited;
the installed physical Seed remains 0.3.7. TF2 has no demonstrated controller
repair: kernel enumeration fails before storage mounting, and runtime power is
still a hypothesis. [The investigation](TF2_REINSERTION_INVESTIGATION_0_3_9.md)
defines a controller-specific physical comparison while preserving single-service
mount ownership and leaving Seed/Wi-Fi controllers untouched.


### Native card players, 0.3.9 continuation

The native Music/Video slice now connects storage-owned descriptors, bounded
systemd-owned decoders, atomic audio admission, selected-output loss handling,
root-only shell controls and shell display return. This follows the existing
trusted system-component boundary; it does not activate the public grant-bound
Media Session endpoint or complete the cartridge media SDK. Do not infer those
contracts from the native player result. Source and installed null-output tests
are recorded in [the media continuation](RELEASE_0_3_9_MEDIA_RESULT.md). Physical
DRM/audio/output-loss and Power responsiveness remain acceptance gates. Broader
resource priority/registry integration, Node/online playback and full media tracks
remain open. Existing owner data and Notepad are preserved by the release audit.

### TF2 driver candidate, 27 September 2026

The installed 0.3.9 system has physically confirmed Music and Video playback
after reinsertion. Storage startup was corrected, but TF2 can fail clock updates
before enumeration. The new driver candidate sets a board/controller-specific
initial clock and propagates resume/supply failures. It is installed and readback
verified, with bootloader/root/data preserved, but controller reliability remains
open until cold-boot and repeated insertion tests pass. See
[the driver record](TF2_DRIVER_CANDIDATE_0_3_9.md). Native media Wi-Fi replacement
remains a subsequent task; current deployment scope is still shell/input only.

### File browser contract, 27 September 2026

The owner approved [File Browser Contract 0](FILE_BROWSER_CONTRACT_0.md): common
locations/entries, provider-reported actions, bounded listings, separate opening
and transfers, explicit collisions and interruption handling. Future Planning's
GUI handoff is `build/handoffs/file-browser-gui-0/START_HERE.md`. This is an approved
functional contract, not a frozen wire API or an implemented general browser.
External-card writes remain storage-owned work; FTP/SFTP and general transfers
are not inferred from existing media playback.

### WebKitGTK selected for browser 0.4.0

The owner selected WebKitGTK for component reuse and implementation efficiency.
The existing shell remains in place. See [decision and runtime evidence](WEBKITGTK_BROWSER_0.md).
A GTK 4/WebKitGTK 6.0 prototype passed real development-host rendering,
reversible adaptation/form-state and download-interception checks. ARM64 image,
Deck display/input integration, actual transfer completion and physical acceptance
remain open. This supersedes the WPE-first recommendation, not the shared storage,
transfer or application ownership contracts.

### H700 hardware-decoding risk, 0.4.2.05 development

The approved downstream Cedrus path now has an isolated kernel/device-tree build
and private player integration. See [the integration record](../board/rg35xxh/debian/cedrus/README.md).
The existing native media owner retains descriptors, single-reader IPC, selected
audio, display leases and bounded stop. Admission is separate from observed hardware
use, and software fallback remains available. The owner-authorized fresh 0.4.2.05
boot/root deployment has matching full Seed readback. Subsequent live diagnostics
confirm 0.4.2.05 boot and Mali-G31/Panfrost shell rendering. They also expose missing
exFAT, UTF-8 filesystem and uinput modules: Storage cannot start and Browser controls
cannot open. Node A incorrectly selected Back because semantic Node focus was absent
from the shell action adapter. The [0.4.2.06 repair](BUILD_0_4_2_06.md) adds matching
service modules and corrects that adapter; fresh Seed deployment and physical feature
acceptance remain required. Actual decoder use and hardware performance remain pending.
Compilation and ARM64 emulation do not prove them.

The downstream SRAM workaround, 32 MiB contiguous-memory envelope, correct H.264
frames, output synchronization and repeated display/control return remain shared
physical acceptance risks. The new kernel must travel with both DTBs, all matching
modules and the rebuilt external joypad. A UI-only update or UI rollback is insufficient.

## Public-source scope

Private application-specific alignment sections are omitted from this export.
