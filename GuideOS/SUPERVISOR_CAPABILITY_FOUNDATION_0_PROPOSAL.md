# GuideOS Supervisor and Capability Foundation 0

Status: **approved architecture**, 25 September 2026. The owner approved the
complete package using the documented shorthand. Stages A through C are promoted
to implementation, and preparation of the recoverable Stage D candidate is
authorized. A raw card write remains gated by completed verification, exact card
identification, fresh capture/rebase and the owner's installation direction in
that context. Implementation, image verification, installation and physical
acceptance remain separate evidence stages.

## Purpose

This report selects the next architectural steps after successful ARM64 image
verification of IPC Envelope 0. Its scope is deliberately narrow:

1. define the common application lifecycle and ownership contract;
2. implement the systemd-era Guide Supervisor registry;
3. implement the first live capability registry and grant broker;
4. exercise them through one harmless application/provider path;
5. verify the result on the development host and in an ARM64 image; and
6. install it as a nonessential, recoverable foundation before migrating real
   applications behind it.

It does not redesign the shell, migrate media/emulation, add remote Nodes, create
a general package sandbox or place the Semiotic Engine in the control path.

## Design basis

The recommendation follows the established requirements rather than selecting a
process arrangement in isolation:

- The person and Deck remain the authority. An application, provider, cartridge
  or connected device cannot authorize itself.
- systemd remains PID 1. Guide Supervisor runs above it and supplies application
  meaning, ownership, preservation and resource policy.
- Discovery, permission and resource allocation stay distinct even when two
  logical responsibilities initially share a lightweight implementation.
- Ordinary use remains simple while permissions, sources, actions, limits and
  evidence stay inspectable underneath.
- Mature Linux mechanisms should do the work they already perform well. Guide
  adds the missing personal-computing contract rather than replacing systemd,
  cgroups, Unix credentials or file descriptors.
- Local operation remains useful if the broker, network or Semiotic Engine is
  unavailable.
- The global shell, Power path and shutdown remain independent of an application.
- Failure, uncertainty and incomplete preservation must be reported honestly.
- The RG35XX H's one gigabyte of memory favors bounded C services and avoids an
  always-resident interpreter or message-routing daemon without a demonstrated
  need.
- The system must respect other people and systems by bounding requests, queues,
  retries, descriptors, logging and resource consumption.

## Recommended architecture

```text
                 owner interface / shell
                          |
                  capability requests
                          v
        +-----------------------------------+
        | Guide Capability Broker           |  unprivileged
        | definitions, offers, policy,      |
        | grants, watches, health interface |
        +----------------+------------------+
                         | private authenticated IPC
                         v
        +-----------------------------------+
        | Guide Supervisor                  |  privileged, narrow
        | instances, lifecycle, agreements,|
        | resource reservations, reconcile |
        +----------------+------------------+
                         | typed sd-bus operations
                         v
        +-----------------------------------+
        | systemd system manager + cgroups  |
        | process containment/enforcement   |
        +-----------------------------------+

  applications ------ brokered handles ------ providers
        |                                         |
        +------- contained systemd unit ----------+
```

The Supervisor and broker are separate processes. The capability registry and
grant broker are separate logical stores inside one broker process for the first
implementation. Each broker interface has its own `SOCK_SEQPACKET` endpoint, but
one process may receive several systemd-activated sockets.

This is the smallest arrangement that preserves the accepted responsibility
boundaries:

- the root service does not parse general application capability requests;
- the application-facing broker cannot start, stop or reprioritize arbitrary
  system services;
- no central message bus is introduced;
- no separate registry daemon is paid for until measured isolation or contention
  requires it; and
- systemd remains responsible for kernel-facing process mechanics.

## Decision 1: identities and ownership

Adopt five distinct identities:

| Identity | Meaning | Persistence |
| --- | --- | --- |
| Application ID | Installed application record; initially the accepted numeric string form. | Persistent across execution. |
| Instance ID | Random 128-bit identifier for one admitted execution. | Exists through reconciliation of that execution only. |
| Launch generation | Monotonic application-local counter preventing old grants/actions from attaching to a replacement run. | Stored with the installed agreement before launch. |
| Component ID | Declared member role such as `main`, `worker` or `renderer`. | Part of the installed package/agreement. |
| Job ID | Bounded long-running work owned by an instance or system service. | Exists until terminal result/reconciliation. |

A PID is evidence about a live process, never durable application identity. An
instance owns its approved workers, jobs, temporary resource leases, broker
connections and grants. Shared providers are system-owned or have their own
provider instance; an application cannot stop them merely because it used them.

All application processes must remain in the instance's systemd cgroup.
`ExitType=cgroup` and `KillMode=control-group` make detached descendants visible
and prevent double-forking from escaping instance accounting. PID 1 performs
kernel child reaping; Supervisor observes cgroup population and terminal results
rather than becoming another PID 1 or depending on every application to reap
perfectly.

## Decision 2: lifecycle model

Do not force preservation, host execution and user-visible application state into
one oversized state enumeration. Record three related dimensions:

1. **Lifecycle phase:** `ADMITTED`, `STARTING`, `RUNNING`, `QUIESCING`, `PAUSED`,
   `STOPPING`, `EXITED` or `FAILED`.
2. **Requested action:** none, yield, checkpoint, pause, resume or stop, with
   episode, sequence and deadline.
3. **Checkpoint result:** unsupported, pending, durable, failed or stale, with
   checkpoint generation and durability class.

The Supervisor records desired phase separately from systemd's observed unit and
cgroup state. A requested stop is not an observed exit. A stopped process is not
a durable checkpoint. An empty cgroup is not proof that data was saved.

Normal transitions are:

```text
ADMITTED -> STARTING -> RUNNING
RUNNING -> QUIESCING -> PAUSED -> RUNNING
RUNNING/PAUSED -> STOPPING -> EXITED
active phase -> FAILED
```

Checkpoint is an operation that can occur while quiescing or at an application's
supported safe point; it is not automatically synonymous with pause. Resume is
allowed only for the same live instance and generation. Recovery creates a new
instance and generation unless reconciliation proves the original systemd unit
and invocation are still the same execution.

Applications declare which lifecycle operations they support in their installed
agreement. Unsupported behavior receives a typed result. Guide never fabricates
a save, pause or resume implementation.

## Decision 3: Supervisor host boundary

Implement a new small C system service, not an extension of the obsolete custom
PID-1 executable and not a permanent Python daemon.

The service should:

- use the verified Envelope 0 C runtime;
- use systemd's typed `sd-bus` API rather than invoking and parsing `systemctl`
  subprocesses in production;
- launch application instances as transient **system** units;
- derive unit properties only from validated installed agreements;
- keep fixed/bounded instance, action and reservation tables;
- expose only narrow Guide lifecycle, identity-resolution and reservation
  operations;
- refuse new application admission until boot/restart reconciliation completes;
- never accept application-originated tier, cgroup, unit-name or executable-path
  authority; and
- keep shutdown and Power under systemd/logind even if Supervisor fails.

The existing Python systemd adapter remains a development oracle. Its guards and
observations should inform tests, but it should not become the Deck's root daemon.

### Application unit baseline

For the first untrusted probe application, use a transient system unit with:

- `Type=exec`, `ExitType=cgroup`, `Restart=no`;
- `KillMode=control-group`;
- no shell command interpretation;
- a fresh dynamic or dedicated unprivileged identity;
- `NoNewPrivileges=yes`;
- strict filesystem and home protection;
- no device access and only `AF_UNIX` networking;
- bounded tasks and memory derived from the installed agreement; and
- null standard input/output except for bounded Guide diagnostics.

Do not make these exact restrictions universal for every future application.
Trusted shell components and providers have different concrete needs. Native
legacy applications that still open framebuffer, input or ALSA devices directly
remain explicitly outside the brokered application class until adapted or placed
in a documented constrained-legacy profile.

## Decision 4: state and reconciliation

Use two stores with different meanings:

### Persistent installed records

Store versioned, root-owned, inspectable records beneath
`/var/lib/guideos/supervisor/`:

- installed application identity and package revision;
- executable/component declarations;
- accepted resource agreement and lifecycle support;
- launch-generation counter; and
- owner policy references.

Use bounded canonical JSON for this first control-plane store because the records
are small, locally inspectable and not on the application wire. Write through a
same-directory temporary file, `fsync` the file, atomic rename, then `fsync` the
directory. Reject unknown required fields and incompatible major versions.
Applications never write these files.

### Volatile runtime ledger

Store root-owned runtime instance records beneath `/run/guideos/supervisor/`.
Each record binds instance/generation to the exact systemd unit, Invocation ID,
cgroup, package/component identity and agreement revision. `/run` survives a
service restart but not a reboot, which matches the lifetime of transient
instances.

On Supervisor restart:

1. close admission and identity-resolution readiness;
2. enumerate Guide-owned systemd units;
3. compare unit name, Invocation ID, cgroup and runtime ledger;
4. reject ambiguous or replacement units;
5. mark missing units terminal and preserve honest checkpoint status;
6. write a new Supervisor epoch; and
7. reopen resolution only after the complete bounded set is reconciled.

A reboot does not resurrect runtime instances or grants. Persistent application
data and durable checkpoints remain, but execution receives a new generation.

## Decision 5: capability broker

Implement one unprivileged C broker process containing:

- a read-only capability-definition table generated from the checked-in registry;
- bounded live provider offers;
- filtered snapshots and watches;
- owner/install policy evaluation;
- pending acquisition transactions; and
- the authoritative volatile grant table.

The broker uses separate filesystem sockets under `/run/guideos/brokers/` for
each interface family. systemd owns the sockets. The broker receives peer
credentials, opens a pidfd and asks Supervisor to resolve the process. Socket
mode and group membership are coarse admission only.

Keep the initial grant limit at 128 and broker connection default at 32, matching
the tested bounded models. Treat these as board-profile defaults, not protocol
limits. Exhaustion produces a typed outcome rather than eviction of an unrelated
live grant.

Runtime grants remain random opaque 128-bit values bound to:

- instance and launch generation;
- provider and interface major;
- capability and allowed operations;
- object scope and sharing mode;
- resource-reservation revision;
- expiration and revocation state; and
- provider incarnation/registry revision where relevant.

Grants are volatile. Broker restart, Supervisor epoch change or application
replacement invalidates them. Clients reconnect, obtain a filtered snapshot and
reacquire. This is preferable to persisting stale authority across a crash.

## Decision 6: acquisition transaction

Use the existing `Snapshot -> Resolve -> Acquire -> Watch -> Release` model.
`Resolve` remains side-effect free. `Acquire` is one bounded transaction:

1. authenticate and resolve the application instance;
2. revalidate the proposal and owner/install policy;
3. request a provisional resource reservation from Supervisor;
4. provisionally acquire required provider leases in deterministic order;
5. roll back every provisional lease if any required member fails;
6. commit the resource reservation;
7. publish the complete grant bundle; and
8. return handles and the registry revision.

No partial required bundle becomes visible to the application. Optional features
are separate acquisition groups so their failure cannot silently weaken a
required operation. Enumeration order never selects a provider; policy,
compatibility, owner preference and measured feasibility do.

Owner consent is represented by a broker-held pending decision tied to the exact
instance, proposal digest and expiry. The shell displays the human explanation
and records the decision through its trusted owner-interface channel. An
application cannot replay another instance's consent. Routine operations covered
by an installed standing policy should not repeatedly prompt the person.

## Decision 7: failure and revocation

- **Application exit:** Supervisor reports terminal containment; broker revokes
  that generation's grants; providers cancel/release owned work and descriptors.
- **Broker failure:** systemd may restart the broker, but no runtime grant is
  restored. Clients receive disconnect/unavailable and reacquire after readiness.
- **Supervisor failure:** applications are not killed merely because the
  Supervisor restarted. Broker closes application connections and stops new
  acquisitions until a new reconciled Supervisor epoch is available. Existing
  provider operations are cancelled or allowed only to finish their already
  committed bounded step according to the operation contract.
- **Provider failure:** remove its offer/incarnation, revoke affected grants and
  emit a bounded event or `resnapshot required`.
- **Revocation:** reject new operations immediately. Request descriptor release;
  terminate a noncompliant instance after the declared deadline when immediate
  descriptor revocation cannot otherwise be enforced.
- **Checkpoint failure:** do not unload stateful work through the ordinary path.
  Report the preservation failure. Forced loss remains a distinct authorized
  critical escalation.

Automatic application restart is disabled initially. systemd may restart the
Supervisor and broker services; only Supervisor decides whether a failed
application gets a new instance after policy and recovery evaluation. This avoids
competing restart policies and loops that resurrect revoked authority.

## Decision 8: service privilege and hardening

### Guide Supervisor

- dedicated root system service;
- no network sockets other than local `AF_UNIX`;
- narrow writable paths under its `/run` and `/var/lib` directories;
- no dynamic plug-ins or application code;
- bounded diagnostics without arguments, paths, grants or private content; and
- access to systemd through the system bus only for Guide-owned units.

### Capability broker

- dedicated unprivileged `guide-broker` identity;
- `NoNewPrivileges`, strict filesystem/home protection, private temporary space,
  no device access, no internet protocol families and memory-deny-write-execute;
- read-only access to installed policy/definition records;
- one private Supervisor socket; and
- writable access only to its runtime directory.

Do not add an application-accessible D-Bus policy. Applications use Envelope 0
sockets. Do not place Supervisor and broker in the shell process. The shell is a
client and owner interface, not the authority implementation.

## Decision 9: first integrated proof

Use a new harmless `guide-ipc-probe` application and the existing
`guide.broker.health` interface. Do not migrate the shell, media player, storage
service or emulator first.

The probe package has:

- no filesystem write, device or network capability;
- one installed agreement with a very small measured resource profile;
- one main process and an optional owned worker for containment testing;
- a standing test policy for `system.diagnostics.read` limited to broker-health
  metadata; and
- no user content.

The proof must exercise:

1. admission, launch and instance/generation creation;
2. peer resolution through real `SO_PEERCRED`, pidfd and cgroup membership;
3. snapshot, resolve, acquire, health read and release;
4. denial without a grant and denial from an unrelated instance;
5. worker containment and no orphan buildup after main-process exit;
6. grant expiry and explicit revocation;
7. broker crash/restart with grant invalidation;
8. Supervisor crash/reconciliation without application replacement;
9. stale runtime-ledger, PID-reuse and Invocation-ID rejection;
10. failed partial acquisition rollback;
11. bounded event overflow producing `resnapshot required`;
12. stop, observed empty cgroup and terminal result; and
13. continued shell navigation and orderly Power behavior throughout.

The health response contains only service state and registry revision. It must
not become an undocumented general diagnostics capability.

## Decision 10: resource policy for the foundation

Do not copy synthetic allocator numbers into the Deck profile. Measure the C
services and probe first.

For development admission:

- use fixed table bounds already specified by Envelope 0;
- set `TasksMax` narrowly for each service and probe;
- measure idle and peak RSS, CPU time, socket queue depth and start/reconcile time;
- set initial `MemoryHigh` above the measured peak with explicit headroom;
- set `MemoryMax` as a failure ceiling, not a promised reservation;
- retain system and Power headroom; and
- verify shell responsiveness during broker stalls and restart loops.

The Supervisor control plane does not become tier 0 merely because it is
privileged. Tier 0 remains hardware-immediate and Power work. Lifecycle requests
inherit their authorized purpose and deadlines; ordinary health queries remain
normal interactive work. Applications cannot choose their own tier.

## Implementation sequence after approval

### Stage A — contract and source implementation

1. Check in the lifecycle/identity schema and generated constants.
2. Implement the C Supervisor state core as pure bounded decisions.
3. Implement the sd-bus host adapter separately from the state core.
4. Implement the C capability/offer/grant core as pure bounded decisions.
5. Implement Supervisor-private and application-facing Envelope interfaces.
6. Build the probe package and health provider.

No image is created merely because individual source tests pass.

### Stage B — development-host verification

Require:

- strict compilation and deterministic generation;
- unit/state-transition and property-based invariant tests;
- AddressSanitizer and UndefinedBehaviorSanitizer;
- coverage-guided malformed-envelope and state-sequence fuzzing;
- real systemd transient-unit integration;
- real cgroup worker containment and observed release;
- broker/Supervisor crash and reconciliation exercises;
- bounded memory and descriptor-leak measurements; and
- an adversarial review of identity, grant and rollback boundaries.

### Stage C — ARM64 image verification

Build a new cumulative candidate from the latest validated source image. Install:

- C Supervisor and broker binaries;
- verified `libguide-ipc` and generated schemas;
- systemd users, groups, directories, sockets and services;
- one probe application agreement; and
- verification-only fixtures outside the normal boot path.

Verify ARM64 execution, dynamic dependencies, systemd unit syntax/security,
service ordering, disabled-network policy, writable-path limits, schema hashes,
reconciliation gates, probe behavior, filesystem integrity and preservation of
all unrelated files. Use a full ARM64 systemd guest where possible; user-mode
QEMU alone cannot verify service ordering or cgroups.

### Stage D — installation candidate

The first physical candidate should enable Supervisor and broker but leave the
existing shell and real applications independent of them. The services must not
be `RequiredBy=guide-shell.service`. Failure therefore degrades the new probe
foundation without blocking navigation, audio, recovery or Power.

Before writing:

1. obtain a fresh read-only capture of the identified seed card;
2. verify exact device identity and partition layout;
3. rebase the already verified payload onto that fresh root capture;
4. preserve boot and data partitions byte-for-byte;
5. run the complete ARM64/image suite again;
6. record candidate and source hashes; and
7. retain a recoverable previous root image.

Write only the identified root partition, then close/reopen and hash readback.
Installation evidence must not be inferred from a successful write command.

### Stage E — physical acceptance

After boot, verify separately:

- normal boot, shell, audio and Power remain functional;
- Supervisor and broker reach reconciled/ready state;
- probe lifecycle and grant flow;
- process tree, cgroup containment and absence of accumulating children;
- broker and Supervisor restart behavior;
- revocation and terminal cleanup;
- idle/peak memory, CPU and latency;
- shell responsiveness during injected failures; and
- cold reboot without resurrected instances or grants.

If the services fail, disable their units through the recovery path and restore
the prior root if necessary. Do not alter expected behavior merely to make the
candidate appear successful.

## Alternatives considered and rejected for this stage

| Alternative | Reason not recommended |
| --- | --- |
| Use systemd without Guide Supervisor. | It cannot supply Guide application identity, checkpoint meaning, grant ownership or owner policy by itself. |
| Put Supervisor, registry and broker in one root daemon. | Saves one small process but expands the application-facing parser's authority to host control. |
| Use one daemon per logical registry/broker role. | Clear but unnecessary resident/process overhead before measured isolation needs exist. |
| Install the Python reference authority. | Fast to prototype but adds a resident interpreter and is not the selected low-floor production boundary. |
| Persist runtime grants across restart. | Risks resurrecting authority detached from current process/provider incarnations. |
| Let systemd automatically restart applications. | Competes with Guide recovery policy and can revive revoked or unreconciled state. |
| Migrate the shell or media player first. | Makes failure affect essential controls and mixes architectural proof with complex device behavior. |
| Deliver this through the shell-only network updater. | Supervisor/broker are root-provider changes beyond that updater's accepted recovery scope. |
| Require a prompt for every operation. | Creates control clutter; installed standing policy plus visible inspection/revocation better serves ordinary use. |

## Approval record

The owner approved Supervisor and Capability Foundation 0 on 25 September 2026.
The ten architectural decisions are adopted. Stages A through C are active
implementation work, and preparation of a recoverable Stage D candidate is
approved.

A raw card write should occur only after:

- Stages A through C pass;
- the exact seed card is connected and re-identified;
- the fresh capture/rebase candidate passes verification; and
- the owner directs installation in that context.

Approval does not mark the services implemented, verified, installed or physically
accepted. Each status must be recorded from its own evidence.

## Recorded approval shorthand

The owner approved the package as a whole by stating:

> Approve Supervisor and Capability Foundation 0.

Any requested exception should name the decision or stage to revise. Unmentioned
future applications, remote protocols, UI redesigns and Semiotic Engine authority
remain outside this approval.
