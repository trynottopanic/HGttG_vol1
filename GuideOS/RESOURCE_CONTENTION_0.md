# Resource contention contract 0

Status: accepted policy direction with a tested reference decision component;
22 September 2026. Host enforcement and physical acceptance are not implemented
by this document or the reference component. This extends the
[modern foundation](MODERN_FOUNDATION_0.md) and the
[Wikipedia application contract](apps/wikipedia/APPLICATION_CONTRACT_0.md).

## Accepted decisions

The owner accepted this initial ordering:

| Tier | Work |
| --- | --- |
| 0 | Critical: power management and hardware-immediate tasks. |
| 1 | Foreground interaction. |
| 2 | Communications. |
| 3 | Background work. |
| 4 | Spare-capacity work. |

Normal contention preserves some progress for lower tiers. Even tier 4 has a
small progress floor when admitted; capacity above that floor is opportunistic.
An authenticated critical deadline can temporarily suspend ordinary progress
floors. No application can assign itself critical priority.

The first owner-selected scenario is downloading a file while streaming video.
Use foreground tier 1 for playback and background tier 3 for this download.
Network transport alone does not make a job tier 2. When the connection cannot
sustain playback and meaningful download progress together, preserve playback
and temporarily pause the download. Reconsider it when capacity becomes available.
This is an explicit exception to its normal progress floor, not a changed
installation footprint. If even playback alone cannot fit, report the shortfall;
do not claim uninterrupted playback or silently substitute lower-quality media.

## Installation agreement and runtime evidence

Cartridges request their footprint at installation. Store its versioned agreement,
permitted modes, limits, and interruption rules. Runtime demand represents work
within that agreement; it is not a new footprint negotiation.

Before resource control is enabled, the host profile must supply measured capacity,
critical headroom, service/progress floors, ceilings, weights and operation
deadlines. Their units and accounting interval must be explicit. CPU time, memory
bytes, transfer rates and device leases are different resources. Do not substitute
one resource's allocation or evidence for another's.

The Supervisor derives effective tiers, verified application ownership and allowed
actions from trusted records. Provider measurements and authenticated lifecycle
acknowledgements supply outcomes. Raw application declarations cannot authorize
priority changes, forced termination or access to someone else's resources.

## Normal allocation

Protect measured critical headroom. For admitted ordinary work, honor its progress
floor, then distribute remaining divisible capacity preferentially toward higher
tiers up to declared demand and installed ceilings. Idle work gets no active
allocation. Any unused critical reserve stays protected in this initial model.

If the floors do not fit, return an explicit capacity shortfall. The caller must
apply a defined admission/deferral policy rather than silently treating the
failed plan as valid allocations. For the first video/download scenario, defer
the download and reevaluate playback alone. Resume scheduling the download when
both floors fit again. Scheduling eligibility does not itself prove the network
transfer resumed; the application/provider must acknowledge that separately.

The reference allocator works across tier aggregates. Selection and fairness
among multiple applications in one tier still need definition. Its weighted
sharing is not a strict real-time scheduling guarantee. Host measurements must
establish actual responsiveness and progress over the chosen interval.

## Bounded interruption

For a verified lower-priority resource holder, use the actions allowed by its
installed agreement:

1. Reduce optional consumption without dropping below protected requirements.
2. Request cooperative yielding and appropriate resource release.
3. If more capacity is needed, checkpoint work requiring preservation.
4. Unload only after a durable checkpoint and quiescence when state needs saving.
5. Escalate to forced stop only when the installed policy permits it and a
   verified critical deadline expires or cooperation times out.

Unsupported actions are skipped with their outcome recorded. An ordinary save
failure does not authorize unloading unsaved work. A forced stop may lose
uncommitted state; the outcome must preserve that fact. Each machine action has
a bounded deadline, including the force-stop observation. Reading has no deadline.

Freezing is not the memory-reclamation or checkpoint operation. A paused process
can retain its memory. Stop acknowledgement alone also does not prove that the
requested capacity became available: obtain fresh provider/host evidence.

Each action is identified by episode, sequence, instance and agreement revision.
Adapters dispatch a sequence at most once; repeated pending polls keep its
deadline. Reject stale/duplicate acknowledgements and backwards clock observations.
The host must validate the saved generation and durability before reporting a
checkpoint complete, and keep the application quiescent until unload or resume.

If critical work depends on a resource held by the proposed victim, do not blindly
freeze or terminate that dependency. Resolve the dependency through a supported
handoff or priority-inheritance mechanism. Detecting and managing those dependencies
is host/runtime integration work; the reference component blocks that escalation.

## Implemented reference component

[guide_resource_policy.h](package/guide-supervisor/src/guide_resource_policy.h)
and [guide_resource_policy.c](package/guide-supervisor/src/guide_resource_policy.c)
implement pure decisions in C, matching the existing supervisor source language.
They require no heap allocation, kernel calls, device access or background thread.
The API is internal and provisional, not a portable application wire format.

- Capacity planning protects headroom, enforces input ceilings, preserves normal
  progress floors and reports insufficient capacity.
- The stream/download wrapper implements the accepted playback-first exception
  and returns separate pause-download and below-playback-floor indicators.
- A contention episode emits bounded actions with identity/sequence checks,
  checkpoint/quiescence guards and permission-checked escalation.

The component does not implement authentication, persistence, a network shaper,
real-time scheduling, per-application victim selection, or the systemd adapter.
Trusted caller state is an API precondition, not a sandbox provided by the C
structs. Plans require atomic host accounting before they can be applied.
Late capacity reports cannot justify acting on a replacement instance.
On resolution, the adapter must settle any already-dispatched action and restore
temporary restrictions when appropriate; this library never claims that an
in-flight stop was cancelled or that a stopped application resumed.

It is deliberately not wired into the earlier custom-PID-1 executable. The Debian
path keeps systemd as PID 1. Linking the library into a new host service and
proving its enforcement are separate remaining work, not implied by host tests.

## Host integration requirements

Guide sends authorized host operations through a narrow systemd adapter. Resource
controls must cover the application and its workers together. Configured CPU/I/O
weights express relative service, while memory protection and limits have their
own semantics. A configured weight is not a hard response-time guarantee.
[Debian systemd resource controls](https://manpages.debian.org/trixie/systemd/systemd.resource-control.5.en.html)

Checkpoint acknowledgement must precede the normal host stop path for stateful
work. Coordinate stop timeouts and final termination with the installed agreement;
systemd's service-stop behavior must not independently bypass Guide's declared
grace/save policy. Record termination and observed resource release separately.
[Debian systemd process termination](https://manpages.debian.org/trixie/systemd/systemd.kill.5.en.html)

Network flow control needs an actual per-transfer/provider mechanism and a
conservative estimate of the shared bottleneck. CPU weights do not enforce the
stream/download bandwidth plan. Remote sources, buffered data and changing link
capacity require real measurements and interruption/resumption evidence.

## Verification and material still needed

Run the [contract tests](package/guide-supervisor/tests/run-resource-policy-tests.sh)
on a Linux development host with a C11 compiler. The fixtures use synthetic units
and deadlines, never deployment defaults. They check sustained stream/download
progress, link loss of capacity and recovery, the playback-first exception,
critical-demand precedence, unchanged installation agreements, invalid profiles,
allocation conservation, failed saves, quiescence, stale replies and bounded
escalation. These are policy tests, not actual video/network or hardware tests.

### Selected physical test arrangement

The owner selected their personal computer to supply both the video stream and
the downloadable file over the local network. The Deck runs the receiving work
under GuideOS policy. This arrangement keeps the first test focused on scheduling;
it does not require an internet service or a complete Node implementation.

Test procedure (implementation plan, not completed physical evidence):

1. Measure playback and download separately, then run both with sufficient capacity.
2. Restrict their shared available bandwidth so playback fits but both progress
   floors do not. The test fixture changes total capacity; GuideOS decides which
   transfer yields. Do not pre-pause the download at the source to manufacture success.
3. Verify continued playback, an acknowledged download pause and retained partial data.
4. Restore capacity and verify download resumption without lost progress, then
   verify the completed file against the source checksum.
5. End playback and verify that the download can use the newly available capacity.

Record actual playback stalls/buffer state, transferred bytes, policy decisions,
pause/resume acknowledgements and timing together. Check source-computer load so
an overloaded source is not misdiagnosed as Deck scheduling failure. This first
case validates network contention; CPU, memory and storage contention need their
own subsequent tests.

Remaining design/measurement inputs:

- Select the actual video and test file on the personal computer, a compatible
  serving method and the controlled shared bandwidth limit for physical testing.
- Measure stream requirements, available link capacity, memory demand and worst
  observed checkpoint/stop delays on the target. Then select headroom, floors,
  weights, accounting interval and deadlines with recorded evidence.
- Define equal-tier scheduling, recovery after Supervisor failure, dependency
  handoff, and stable behavior when capacity fluctuates around a threshold.
- Specify durable agreement/action records, authenticated acknowledgements,
  application worker containment and the actual systemd/network provider adapter.

No numeric limits are promoted from the synthetic tests into a device profile.

## Subsequent implementation evidence

The [transfer provider](TRANSFER_PROVIDER_0.md) now connects this C allocation
policy to real bounded HTTP workers, including acknowledged pause, resumable
partial files and checksum verification. Host, systemd integration and emulated
Debian ARM64 checks pass. The capacity inputs remain synthetic; physical shared-link
contention and video playback acceptance remain open.
