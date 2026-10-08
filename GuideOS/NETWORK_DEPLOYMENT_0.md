# Network deployment framework 0

Status: design draft, 24 September 2026; first implementation added 25 September.
See [implementation and current boundaries](docs/NETWORK_DELIVERY_0_IMPLEMENTATION.md)
and [validation/install status](docs/NETWORK_DELIVERY_0_VALIDATION.md).

Owner direction: make as many development changes as practical without returning
the seed to its reader; do not plan network delivery of changes larger than 100 MB.
The broader architecture below remains a proposal. The linked implementation
record identifies the narrower API now built and the parts still deferred.

## Outcome and present boundary

The development PC prepares a small, verified change. The Deck receives it while
its current version remains usable, stages it locally, activates it at an allowed
interruption point, and reports the result. The preceding usable version remains
available for recovery. The same path retrieves bounded diagnostic reports so
ordinary testing does not require card removal either.

The [current installed revision](docs/WIFI3_INSTALLATION_2026-09-24.md) is
`wifi3-20260924`. Its readback passed; the owner subsequently reported the seed
works as intended in its [physical result](docs/WIFI3_PHYSICAL_RESULT_2026-09-24.md).
That installed seed still requires the new deployment bootstrap; its package
inventory contains no OpenSSH server. The existing
[transfer provider](TRANSFER_PROVIDER_0.md) has tested range/resume and contention
behavior but is not installed on this seed and is not an authenticated updater.
The desktop Node's existing pairing does not grant deployment authority.

Plan for one bootstrap card installation to add the receiver, trusted PC key,
stable launcher, local recovery controller, and release-directory layout. A
working network connection alone does not install those components remotely.
After bootstrap, small ordinary revisions should need no card handling.

## Size agreement

Working interpretation: **100 MB = 100,000,000 bytes**, per complete deployment,
not per file. Use bytes in records and show MB in the interface.

- Count the manifest, all delivered payloads and required dependency downloads
  together. The Deck enforces the limit as bytes arrive, not just from a claim.
- As a conservative draft policy, also cap the aggregate expanded replacement
  files at 100 MB. Compression must not turn a large replacement into an apparent
  small change. This second cap is a proposal, not an additional owner decision.
- Do not divide one oversized or mutually dependent change into multiple jobs
  to evade the cap. Independent, usable revisions may be delivered separately.
- Reuse unchanged, verified local files. Version 0 sends complete changed files;
  binary patches are deferred. A tiny patch must not silently authorize replacing
  an otherwise excluded system image or transforming an arbitrarily large file.
- Count unique deployment artifact bytes; transport framing and retry bytes are
  separate measured traffic. Bound retries and expose total transferred bytes.
  This is not a promise that actual network traffic never exceeds 100 MB.
- Reserve disk space independently: download + expanded staging + retained prior
  release + rollback/configuration snapshots + a filesystem safety reserve.
  Copied unchanged files can consume space despite using no network bandwidth.
  Reject before activation if the space or memory budget cannot be met.

An oversized change reports its calculated size and stays a card-based operation.
Optional splitting of font/language features is valid only when each is a genuinely
independent feature with a complete, compatible resulting installation.

## Components and authority

| Responsibility | Proposed owner |
| --- | --- |
| Build, compatibility checks, size calculation, target selection and change preview | PC deployment tool, later exposed through the desktop Node |
| Authenticated transport, bounded receipt and resumable staging | Deck receiver |
| Owner authorization, allowed component scope and interruption policy | Guide policy under a named development-PC grant |
| Checkpoint/quiescence, dependent applications and release ownership | Guide supervision through the host adapter |
| Local activation, durable transaction journal, health checks and rollback | Small Deck deployment controller |
| Process management, boot recovery ordering and independent Power handling | systemd on Debian |
| Status, cancellation and rollback request | Guide shell and PC tool, using the same contract |

These are logical responsibilities; they need not become six resident daemons.
Keep the receiver/controller independent of the shell and Wi-Fi service being
replaced. Do not return to Guide-as-PID-1 or require the full future supervisor
to exist before implementing a bounded host adapter.

Owner control remains explicit without demanding a confirmation for every file.
Proposed development mode authorizes a named PC to deploy chosen component classes
and restart their declared services. Outside that mode, present a change for
approval. A desktop **Build and install** action can authorize that transaction;
pairing alone cannot. An application cannot grant itself deployment authority.
Reboot permission and state-losing interruption are distinct from ordinary
restart permission. No scheduled or forced update behavior is implied.

Honor [AT Field](AT_FIELD_0.md): Familiar can accept an authorized known PC;
Closed can use an explicit development-PC exception or an owner-initiated session;
Open does not authorize installations. Preserve existing connections when the
preset changes, as the existing contract specifies. Device identity and its
trusted host key must survive an IP-address change or ordinary software rollback.

## First transport

Recommend **OpenSSH on the local network** for the first development transport,
with a dedicated key-authenticated deployment account and a fixed command
dispatcher. Its narrow operations are inspect, receive/resume, validate, activate,
status, cancel, rollback, and export diagnostic reports. Use a length-bounded
protocol over the SSH channel; a generic remote shell is not the deployment API.

OpenSSH provides public-key authentication, forced commands and forwarding
controls; these are building blocks, not the installation transaction itself.
Verify supported directives against the Debian-installed version when implementing.
See the [OpenSSH server configuration manual](https://man.openbsd.org/sshd_config).
Disable password login and forwarding for this account; authenticate the Deck's
host key on the PC. Keep the PC's private key on the PC. This is proportionate
to allowing a remote machine to replace executable system components.

Start with a saved address/displayed IP. Discovery and friendly Node integration
can follow; neither is necessary to prove deployment. No cloud relay, new account
service, anonymous listener, or continuously polled update feed is required.
Do not assume the existing HTTP transfer prototype supplies authentication or
that SSH automatically provides its contention control. Reuse its tested
pause/resume/accounting concepts through an explicit transport adapter.

## What can change

| Change | Proposed delivery and interruption | Initial scope |
| --- | --- | --- |
| Guide shell, keyboard, pointer, interface assets | Coherent Guide release; restart affected interface after preserving work | First implementation |
| Guide applications and their workers | Replace one compatible application release; coordinate its whole instance | First implementation where lifecycle adapter exists |
| Guide configuration | Typed configuration transaction, validation and prior-value snapshot | First implementation for named settings |
| Guide providers and services | Stage code, check dependents, restart selected service and test its real operation | Extend after ordinary update recovery passes |
| Wi-Fi provider, receiver or deployment controller | Independent local recovery path, trial activation and reconnection checks | Separate recovery milestone |
| Small fonts, libraries or Debian packages | Pre-resolved exact package set, offline installation, compatibility and recovery plan | Later qualified package class |
| Kernel, modules, firmware, device tree and boot configuration | Board-specific trial boot and fallback needed even below the size cap | Card-based until boot recovery is proven |
| Partition changes, whole-root images, changes over 100 MB | Existing guarded image/card workflow | Outside network version 0 |

Small does not necessarily mean safe to restart. A two-kilobyte networking change
can cut the only remote path; an interface image can be replaced with little
interruption. Classify by affected function as well as size.

Do not treat Debian package installation as an atomic release-directory switch.
Maintainer scripts and dependency changes may affect shared files and services.
Pre-download the complete approved package set within the cap; forbid unplanned
dependency fetching during activation. Package changes need package-specific
recovery or an established snapshot/image mechanism. Failed package configuration
must report repair required, not claim that restoring old application files undid
the operation. Debian's [package-management reference](https://www.debian.org/doc/manuals/debian-reference/ch02.en.html)
describes these distinct package operations. Do not use the development channel
to issue an unrestricted distribution upgrade.

## Deployment record

Proposed metadata, to be finalized alongside the first receiver:

- Transaction ID and canonical manifest hash; human summary and component set.
- Expected current component versions/hashes, resulting release identity,
  runtime/architecture requirements, and board constraints only where relevant.
- Every payload path, byte count, hash, explicit deletion and allowed destination.
  Include changed files and hashes of reused files; reject undeclared payloads.
- Download, expanded-data, temporary-storage and working-memory bounds, including
  dependency closure. Validate paths, archive structure and counts before unpacking.
- Changed permissions or installation footprint, dependent components, required
  checkpoint/stop/restart actions, and whether a reboot is necessary.
- Health probes and deadlines, rollback eligibility, configuration/state schema
  compatibility, previous release identity and retained recovery requirements.
- Authorized PC and applicable owner-policy revision; no passwords or private
  keys in package metadata or reports.

Hashes identify content; authentication supplies origin authority in this first
paired-PC workflow. Reuse the inspectable file rules from
[Cartridge Format 1](CARTRIDGE_FORMAT_1.md), but keep the deployment transaction
envelope separate. Format 1 currently defines neither arbitrary system install
commands nor signed publishers; this draft does not silently add either.
Use typed operations interpreted by the installed controller, not shell commands
embedded in an ordinary package. Installing trusted executable code is itself a
significant grant, even when the transport account has no general shell.

## Transaction and recovery

Proposed states: offered, receiving, staged, validated, waiting-for-quiescence,
activating, trial, committed; with cancelled, rejected, rolled-back and
repair-required outcomes. Report actual state and a reason, not just progress.

1. **Inspect/admit:** authenticate the target and PC, compare the installed base,
   enforce size/scope/space/power constraints, and record the permitted operation.
2. **Receive:** stream to disk, with bounded memory. Resume only the same manifest
   and base. Interrupted receipt never changes the active version.
3. **Validate:** verify the complete candidate, hashes, compatibility, dependencies,
   archive boundaries and health-plan availability. Recheck the installed base
   before activation. Serialize conflicting deployments and package operations.
4. **Quiesce:** request meaningful saves from affected applications; require their
   durable acknowledgements where needed. An unsupported save defers the update
   or requires a separately authorized state-losing action. Do not equate SIGSTOP,
   a quiet screen or a service stop with a saved application.
5. **Activate locally:** persist intent, retain the previous version, switch the
   release reference, then start the affected components. Once activation begins,
   the local controller owns completion/recovery independent of the SSH session.
6. **Trial/check:** verify the release actually loaded, expected services and their
   meaningful operations. Machine health can pass without physical UI acceptance;
   record those separately. A generic process heartbeat is insufficient evidence
   of working graphics, input, networking or application behavior.
7. **Commit or recover:** record durable completion or restore the previous
   compatible release/configuration and verify recovery. Preserve failure evidence.
   Keep one previous usable release; promote a last-known-good baseline only with
   the relevant acceptance evidence, not merely after copying or starting it.

Proposed storage: immutable `/opt/guideos/releases/<release-id>` directories and
one active-release reference, with private transaction state outside release
content. A stable launcher resolves a release once; running applications and
helpers keep that generation rather than lazily importing a changing `current`
path. Group mutually dependent components in one release. Bootstrap must adapt
today's fixed `/usr/lib/guideos` imports/launch paths; adding a symlink alone does
not establish consistent generation ownership.

Prepare a new reference and rename it on the same filesystem. Linux
[rename semantics](https://man7.org/linux/man-pages/man2/rename.2.html) supply an
atomic name replacement, not a multi-service or crash-durable transaction.
Synchronize staged content, transaction records and containing directories in
the required order; test sudden loss of power at each durable boundary.
Do not rewrite Debian-owned base files through this release mechanism.

At boot, an independent recovery unit examines incomplete activation records
before starting affected components. Pre-activation records leave the old release
active; an unresolved trial restores the old release unless explicit recovery
evidence permits completion. Repeated failures must not cause endless restart
or rollback loops: enter a reported maintenance state with bounded attempts.

Cancellation during receipt/staging discards or retains resumable partial data
under policy. During activation it requests the next safe recovery boundary;
it does not kill filesystem writes mid-commit. Power handling remains independent.
Critical shutdown preempts download work; activation ordering must tolerate power
loss rather than promise to delay shutdown indefinitely.

Keep user files, credentials and mutable application state outside code releases.
Version 0 admits backward-compatible state/configuration changes only. A migration
that prevents the previous version reading current data needs a separate recovery
plan; restoring old binaries must never silently discard new user data.

## Protect the remote recovery path

Ordinary application updates should leave networking and the controller running.
For their own updates, later introduce a stable recovery controller outside the
replaceable candidate, with a systemd-managed local watchdog and trial record.
The candidate must demonstrate local function and reconnection to the paired PC;
the peer acknowledges the transaction/release it observed. Do not make internet
access or a public ping service a condition for a usable local deployment.

If the trial cannot re-establish the management path within its measured machine
deadline, restore the previous components locally. A temporarily unavailable PC
can cause a conservative rollback; report that as unconfirmed remote recovery,
not proof of a broken candidate. These deadlines govern unattended probes, not
the person's reading time. Permit UI review without a human countdown.

Bootstrap recovery can still be broken by kernel/storage/base-system failures.
Network deployment reduces card handling; it cannot eliminate physical recovery.
Keep the existing private seed capture and card-writing workflow available.

## Scheduling and diagnostic return

Deployment receipt is background tier 3, or tier 4 for optional prefetch, using
the [accepted contention policy](RESOURCE_CONTENTION_0.md). Preserve playback
when transfer capacity is insufficient; support acknowledged pause/resume.
Do not self-promote deployment to critical tier 0. Admission should require a
measured power margin or external power before disruptive activation; select
thresholds from RG35XX H measurements rather than inventing a universal number.

Use existing Wi-Fi connectivity; do not add another periodic discovery/ping loop
or override deliberate Disconnect. Resume an interrupted transfer only when an
authorized connection and resource grant are available.

Return a bounded report containing release identities, transaction stages,
probe results, restart outcomes and relevant logs. Exclude credentials and user
content by default; allow specifically selected diagnostic exports. Keep reports
on the Deck until acknowledged by the PC, subject to a bounded retention policy.
Use the same 100 MB logical-job ceiling for a diagnostic export in this first
design; report truncation rather than silently generating unlimited archives.

## Implementation sequence and acceptance

1. Confirm physical Wi-Fi association/addressing and saved reconnection. Build a
   bootstrap containing transport, release launcher and independent recovery.
   Validate on a disposable guest, then install through the card workflow once.
2. Deliver one small keyboard/asset revision, retrieve its report, and roll it
   back over the network. Verify actual visible behavior and retained credentials.
3. Expand to coherent shell/application releases and named configuration changes.
   Test checkpoint refusal, dependent workers and shared-provider interruptions.
4. Prove controller/Wi-Fi self-update recovery on a local watchdog before enabling
   those classes. Qualify bounded Debian package sets individually afterward.

Acceptance examples for the first implementation:

| Condition | Required observation |
| --- | --- |
| 100,000,000-byte complete job versus one byte more | At-limit job is size-eligible; over-limit job rejected before activation; expanded and dependency bounds also checked |
| PC disappears halfway through transfer | Old version remains usable; same verified job resumes without installing partial content |
| Wrong target/base, corrupt payload, path escape or unpack expansion overflow | Rejected; active files and user data unchanged |
| Low space/power, busy application or failed save | Explain/defer; no forced loss of work |
| Lost response or duplicate activate request | Same transaction queried/resumed; operation is not applied twice |
| Power loss before/after release switch | Next boot selects a complete compatible release and reports recovery |
| Candidate exits, loops or fails a functional probe | Prior release restored; attempt bounded and evidence retained |
| Wi-Fi/controller update removes management connectivity | Independent recovery restores the former path without the PC issuing another command |
| Existing user data was modified during the trial | Recovery preserves it; incompatible downgrade is refused/requires repair |
| Successful network install | Installed identity, functional result and rollback availability are recorded; physical acceptance remains distinct |

Before implementation, settle exact receiver protocol/schema, local privilege
boundary, recovery-unit ordering, probe deadlines, free-space/power margins and
development-mode controls. These are bounded implementation decisions to test;
they are not reasons to postpone drafting the framework or demand another
general approval of theoretical work.
