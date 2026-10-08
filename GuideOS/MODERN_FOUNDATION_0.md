# Modern GuideOS foundation 0

Status: foundation direction selected 21 September 2026; status reconciled
22 September. The owner selected minimal Debian for software expansion and
portability. The full original seed backup is verified; subsequent Debian
diagnostics have been written and physically exercised. GuideOS 0.3's physical
run failed; see [the audit](docs/LIQUID_SNAKE_FAILURE_AUDIT.md).
Preserve source, recovery images and test evidence.
See [design alignment](docs/DESIGN_ALIGNMENT_0.md) for the current contract work
and `DEBIAN_BRINGUP_0.md` for bring-up history. The candidate comparison and kernel
discussion below record the evaluation at selection time, not a fresh release
survey or the exact inputs of the latest image.

## Targets

- Current physical bring-up target: Anbernic RG35XX H.
- Future compatibility target: Raspberry Pi Zero 2 W as a portable, optionally
  headless node. This target does not require a display, controller, media player,
  or inference engine to run the Guide core.
- Neither device defines the permanent minimum hardware specification.

Shared contracts cover application/service/job identity, capability negotiation,
resource grants, lifecycle events and durable recovery. Board profiles supply
boot firmware, kernel configuration, device descriptions, drivers and provider
adapters. Different boards may use different maintained kernel branches without
changing the Guide application contract.

## Accepted supervision boundary

Owner decision, 22 September 2026: retain **systemd as PID 1** for the Debian
implementation. **Guide Supervisor runs above it.** This supersedes the earlier
Guide-as-PID-1 arrangement retained in the Buildroot compatibility bridge.

- systemd supplies boot ordering and underlying process/service management,
  including configured resource enforcement, restart and system shutdown.
- Guide Supervisor coordinates complete application instances, their workers
  and jobs, lifecycle requests and outcomes, and resource policy. Capability
  discovery and authorization retain their separate registry/broker roles.
- Applications implement their meaningful pause, checkpoint and recovery
  behavior. Guide coordinates these outcomes with systemd operations; a process
  stopping or a service restarting does not prove that application state was saved.
- The Guide interface remains a replaceable supervised component. Guide
  permissions and owner-controlled update policy must be enforced explicitly;
  selecting systemd does not itself supply those policies.

The portable application contract should not expose systemd-specific unit names
or require applications to manage system services directly. A host integration
layer translates authorized Guide operations to systemd. Exact interfaces,
privilege boundaries, instance-to-service mapping and failure/restart rules
remain to be specified and tested. These are implementation details within the
accepted arrangement, not an unresolved choice of PID 1.

The Debian bootstrap already includes `systemd-sysv`. Retaining it does not prove
that Guide supervision has been integrated. The old supervisor's direct init
and power-off behavior must be adapted before reuse in this arrangement.

## Application selection, numbering and footprint

Owner direction: the person selects an application through the GuideOS interface.
Each application has an assigned number, illustrated as `00000000` through
`99999999`. This describes scalable identification, not preallocated slots,
reserved memory addresses or a fixed maximum application count. The identity
representation must permit expansion beyond the illustrative eight-digit form.

Keep the application number distinct from the fresh identity of a running
instance and from process IDs. The number identifies the selected application;
instance identities separate its executions and their work. Assignment scope,
reinstallation, number reuse and cross-device mapping still need explicit rules;
the numeric identifier alone confers no permission or publisher authenticity.

At installation, an application requests its required memory, processing and
other resource footprint in a form that can adapt to the installed hardware.
Guide evaluates that request against the installation's capabilities and owner
policy, then stores the agreed resource profile with the application record.
The application does not request or renegotiate this footprint on every execution.

At launch, Guide uses the stored agreement and checks current availability to
schedule and allocate resources within it. Runtime capability handles and
instance accounting remain necessary, but they do not constitute a new footprint
negotiation. The agreed budget and actual consumption are separate. Rules for
changing the agreement after installation remain to be specified explicitly.

Proposed contract structure: a minimum functioning profile, optional implemented
feature profiles with additional costs, and declared peak/temporary work needs.
Guide must select only a mode the application implements. Hardware-specific
measurements and enforcement belong in the host profile, while the application's
functional requirements remain portable. A missing minimum produces a clear
not-ready result; optional omissions produce an explained limited mode. Exact
resource units, budgets and post-installation revision rules remain contract work.

## Idealized Deck resource space

Owner model: the Deck's I/O, memory, storage, processing and networking form
"land" or "space" on which cartridges can be installed and which they can occupy.
The installation-time footprint describes a cartridge's agreed place within
that resource space. The model is independent of a particular board or layout.

Owner goal: adapt GuideOS to varied hardware while retaining communication
between compatible Guide installations. Each board maps its actual resources
and capabilities into the shared Guide contracts. Different installations may
agree different cartridge footprints without changing the meaning of the
application's operations or shared data.

Cross-device communication uses versioned protocols, capability descriptions
and compatible data formats over an available authorized transport. Peers
negotiate supported functions and constraints; identical hardware, interfaces
or resource quantities are not required. Missing optional functions must not
prevent otherwise compatible communication. Unsupported required operations
receive an explicit outcome rather than an assumed substitute. Sharing capacity
across devices remains scoped by owner permission and provider availability.

An eventual portability proof must run shared contract checks on different
hardware profiles and demonstrate an authorized exchange between them,
including an honest response to unequal capabilities. A second successful boot
alone would not establish this goal.

The following mapping makes the metaphor usable without treating unlike
resources as interchangeable quantities:

| Resource space | What a footprint describes |
| --- | --- |
| Storage | Persistent program/data capacity and bounded temporary storage. |
| Memory | Working capacity needed while the application and its workers operate. |
| Processing | Scheduled computation, including sustained and temporary demand. |
| Networking | Connection and transfer capacity through available network providers. |
| I/O | Use of compatible input/output capabilities, including shared or exclusive access where appropriate. |

The installed agreement persists across executions; active occupancy can change
as the application runs, pauses or stops. Saved data can continue occupying
storage after its workers exit. A processor allocation describes work over time,
not a permanently occupied physical address. These distinctions belong inside
the resource model rather than requiring a new footprint request at each launch.

This model does not yet decide which allotments are guaranteed reservations,
shared capacity or maximum permitted use, nor whether unused allotments can be
temporarily used by others. Define those policies explicitly before promising
simultaneous operation of installed cartridges. Capacity and permission remain
separate: available network or I/O space does not authorize every destination,
device operation or piece of personal data.

## Accepted resource priority ordering

Owner direction: competing applications and system work are served through
numbered priority tiers. **Tier 0 is critical and highest priority**, including
power management and other hardware-immediate tasks. Increasing numbers mean
decreasing priority. Application numbers, running-instance identities and
priority numbers remain separate concepts.

Guide uses this ordering when eligible work competes for a constrained resource.
The installed footprint describes the application's resource agreement; priority
determines precedence during contention within the applicable resource rules.
Ordinary execution does not renegotiate that footprint.

Tier assignment is controlled by Guide under owner policy. An application's
declaration cannot promote itself to critical priority or grant additional access.
The owner accepted the initial remaining tiers: 1 foreground interaction,
2 communications, 3 background work, and 4 spare-capacity work. Preserve lower-tier
progress during normal contention. Specific assignment granularity and allowed
priority changes remain to be defined.

The ordering must be translated into actual scheduling and provider behavior
through the host integration. It does not prescribe identical mechanisms for
processor time, memory, storage, networking and exclusive I/O. In particular,
priority alone does not authorize deletion of saved data or abandonment of an
in-progress commit. A critical label alone is not evidence of a response deadline.

The accepted combination is protected critical headroom, preferential sharing,
bounded cooperative yielding, checkpoint-and-unload when needed, and permitted
forced escalation for expired critical deadlines or failed cooperation. The
[resource contention contract](RESOURCE_CONTENTION_0.md) specifies these rules
and identifies the tested reference component and remaining host integration.

The first contention scenario is a video stream and simultaneous file download.
If both cannot make adequate progress, the owner chose to preserve playback and
temporarily pause the download; restore its progress when capacity returns.
Within-tier service order, measured limits, dependency handoffs and final
reservation/allowance rules remain design work.

## Accepted personal-computing and network experience

Owner-adopted direction, 22 September 2026: use the early personal-computer
hobbyist community as the experiential model for the broader Guide network.
The [design philosophy](../HHG_Foundation/03_DESIGN_PHILOSOPHY.txt), under
"Personal machines, deliberate exchange," records the governing principle:
personally owned, understandable machines, useful individually and expanded
through deliberate exchange.

In the resource model, each Deck has its own computing space. Installed
cartridges use the footprint agreed at installation. An owner may offer bounded
services or information from that space to another participant. A connection
does not automatically create a common pool of memory, processing or storage.
Receiving a cartridge establishes a new local installation agreement appropriate
to the receiving hardware and owner policy; the sender's grants do not transfer.

Interfaces should make it possible to understand what is installed locally,
which machines or Nodes are known, what each offers, what access has been
granted, and what is currently unavailable. Discovery, verified identity and
authorization remain separate. A recognizable peer name aids understanding
without replacing those checks.

Derived checks for future implementation: inspect a local cartridge and its
footprint; exchange a compatible package between unlike devices and establish
the receiving installation's agreement; use and revoke one scoped Node service;
disconnect while retaining useful local functions and accurately reporting
remote work. These checks express the accepted experience, not passed tests.
Reservation/sharing policy, transport protocols and any particular visual style
are still separate design choices.

## Candidate bases

1. Buildroot 2025.02 LTS: considered for a controlled, minimal Guide system
   image. Official release inventory currently lists 2025.02.18 and maintenance
   through March 2028. Buildroot is a system builder, not an installable general
   purpose distribution. It does not provide a target binary package repository;
   Guide application installation and runtime compatibility remain our work.
2. Alpine 3.24: strongest ready-made small distribution candidate. musl,
   BusyBox, OpenRC and apk provide a compact, extensible base. Test third-party
   binary/library compatibility rather than assuming glibc-built software works.
   Main repository support and community repository support have different
   lifetimes; track the actual packages used.
3. Debian 13 stable: candidate when broad existing Linux software and package
   integration are more important than tightly minimizing the base. Supports
   arm64; that alone does not establish boot support for either exact board.
4. Yocto/OpenEmbedded: alternative custom distribution engineering framework,
   especially if board variants and package-feed requirements outgrow Buildroot.
   Its extra build and maintenance machinery is not presently justified merely
   by having two hardware targets.

ROCKNIX is a hardware-support reference and potential boot diagnostic control,
not the proposed Guide user environment. Raspberry Pi OS Lite is a useful Pi
hardware diagnostic control; adopting it for the Pi does not solve the handheld
port or establish a shared base.

## Kernel decision

The working seed's vendor Linux 4.9.170 is a temporary hardware compatibility
path, not a requirement imposed by Buildroot. Previous open boot-chain candidates
failed to produce a visible display, without proving which boot stage failed.

Prefer a maintained Linux LTS branch, with 6.18 an initial candidate. Before
pinning it, compare board-support patches with a currently working upstream-based
H700 reference. A maintained newer stable branch may be needed for initial
hardware validation; document the upgrade/backport maintenance cost explicitly.
Do not declare an exact release suitable merely because it compiles.

First diagnostic milestone: identify progress through firmware, bootloader,
kernel and userspace independently. Establish an available early logging route
before repeating blank-screen image tests. UART may require physical equipment;
do not assume a serial connection exists or promise USB logs before its driver
initializes. Validate the device's actual memory and panel variant.

## Storage and runtime principles

Keep boot/system, application packages and private data distinct. Final partition
geometry follows the validated boot chain. ext4 remains the development baseline;
evaluate compressed read-only system images and benchmark ext4 versus F2FS for
writeable state after the kernel works. No filesystem format guarantees that an
application's unsaved memory will survive power loss.

Durable capability definitions and owner policies belong on disk. Live offers,
grants and endpoints are rebuilt after startup. Recovery state is stored apart
from disposable caches; application versions are stored apart from their data.

The Pi Zero 2 W has 512 MB RAM. Treat that as an acceptance constraint for its
profile, not a mandate to burden every installation with the same services.
Buildroot provides Pi Zero 2 W configurations, including a 64-bit configuration.
Begin evaluation with a common ARM64 userspace where feasible; measure memory
and verify binaries against the selected ABI rather than assuming portability.

## Acceptance sequence

1. Finish and verify the full current-card backup. No card writes before this.
2. Pin reviewed source inputs for a minimal diagnostic boot image separately
   from the existing prototype configuration.
3. Prove boot-stage visibility, kernel startup and a minimal userspace.
4. Validate display/input, storage, power/charging/shutdown, audio and networking.
5. Implement capability registry and supervisor contracts against these adapters.
6. Add a headless Pi profile and run the same core contract checks there.
7. Add richer applications incrementally; do not use a monolithic interface as
   the implementation of all system services.

## Verified backup

Full read-only capture completed and verified on 21 September 2026:
`E:\DGttG\private-recovery\guideos-seed-full-2026-09-21.img`.
Verified logical size: 62,239,277,056 bytes, including the complete card and
partition metadata. The `.txt` manifest contains `CAPTURE_OK`; the saved image's
SHA-256 matched a separate full source reread:
`133149EBF6410D17662EFA4E48856C91A9E4E12B9502836FEACBBD741CE72280`.
The initial buffered read failed at the final partial buffer; exact-length reads
captured the remaining bytes before full verification. No source writes occurred.
Restore and physical boot testing of this capture have not been performed.
This private backup is outside the
`HGttG_vol1` source repository. It uses bounded streaming buffers, not a RAM image.

## Sources checked

- https://buildroot.org/download.html
- https://buildroot.org/downloads/manual/manual.html
- https://alpinelinux.org/about/
- https://alpinelinux.org/releases/
- https://www.debian.org/releases/stable/
- https://www.yoctoproject.org/development/releases/
- https://www.kernel.org/releases.html
- https://rocknix.org/devices/anbernic/rg35xx-h/
- https://github.com/buildroot/buildroot/blob/master/board/raspberrypi/readme.txt
- https://www.raspberrypi.com/news/new-raspberry-pi-zero-2-w-2/
- Local hardware history: `board/rg35xxh/HARDWARE_AUDIT.md`
