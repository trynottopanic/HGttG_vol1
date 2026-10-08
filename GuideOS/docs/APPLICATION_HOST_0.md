# Installed application host 0

3 October follow-up: [Notepad's approved UI implementation](NOTEPAD_UI_IMPLEMENTATION_2026_10_03.md)
adds optional bounded notes/document/menu metadata and labelled text requests
with caret results. Legacy requests remain compatible. Notes support seventeen
actions for New plus sixteen drafts; the eight-action limit below still applies
to other views. The root-resident host and matching cartridge must ship together.
The original status below is historical; current evidence is in the follow-up.

Status: step 1 implemented and verified on the development host, 26 September
2026. ARM64 binaries and the matching Python dependency are staged. No root
image or seed has been updated with this work. Device sandbox/lifecycle/resource
acceptance remains pending.

## Requirement and ownership

This implements step 1 of [the Notepad integration plan](NOTEPAD_INSTALLATION_INTEGRATION_0.md),
using the accepted [Supervisor foundation](../SUPERVISOR_CAPABILITY_FOUNDATION_0_PROPOSAL.md),
[modern systemd boundary](../MODERN_FOUNDATION_0.md) and
[Notepad runtime restrictions](../NOTEPAD_CARTRIDGE_0.md).

The existing C Supervisor launches installed application records through typed
systemd operations. The C broker resolves the actual peer against its live
systemd identity, generation and installed agreement. The shell owns display,
focus, global controls and shared text entry. No cartridge can create its own
installed agreement.

The additional Python process is a trusted, per-instance runtime/provider host;
it is not an always-resident replacement Supervisor or broker. It compiles the
verified source without executing it, forks one application worker, closes every
worker descriptor except its private sequential-packet channel, and installs an
irreversible kernel seccomp allow-list **before** executing application code.
The worker cannot open files/devices, create/connect sockets, execute programs,
create children, signal other processes, use ptrace/process-memory operations,
or mount filesystems. This boundary is enforced outside the application.

The trusted host accesses only the application-specific private store through its
provider methods and forwards bounded semantic views/input to the root shell.
It obtains and revalidates grants from the existing C broker, not from application
claims. Its independently releasable capabilities are private storage (code 2),
visual presentation (3), semantic actions (4), and text entry (5). Code 1 remains
the harmless health probe. Live grants renew without imposing a reading deadline;
revoked or broker-restart-invalidated grants fail closed.

## Installed runtime record

The root-owned, non-group/world-writable registry is
`/var/lib/guideos/applications/<numeric-code>.policy`. Codes are stable local
aliases in 10000..4294967295; 9001 remains the old probe. A canonical record is:

```text
format=1
code=10001
id=org.hhgtg.runtime-proof
module=reference
entry=application
sha256=<64 lowercase hex digits>
capabilities=30
private_bytes=524288
```

The source is an immutable, root-controlled single Python module at
`releases/<sha256>/<module>.py` under the registry. The host validates every path
component without symlinks and verifies its source digest before compiling it.
The Supervisor binds the generation and permission mask to that digest and
rejects changed release/permission records for an existing instance. Generation
counters are durable; runtime identity records do not restart apps on cold boot.

This is a deliberately small **runtime record**, not a replacement cartridge
manifest, package-version database or installation agreement UI. Step 2 must
verify the entire archive, record its package version/hash and owner agreement,
allocate a stable code, stage immutable files and atomically publish this runtime
record. Updates must stop the old instance before changing its active record.
Module/callable identifiers are validated identifiers, never command text.
Arbitrary native extensions and dependency downloads are unsupported. The initial
module can use the preloaded standard-library facilities and SDK; broader module
and asset loading needs a separately bounded extension to this profile.

## Bounds and lifecycle

- At most four admitted services; one active instance per application code.
- One unprivileged application worker plus its trusted host; systemd `TasksMax=5`,
  32 descriptors, 48 MiB memory high and 64 MiB hard ceiling for the whole service.
  The host overhead is charged conservatively inside that ceiling. Child creation
  and new threads in the application worker are denied in this first profile.
- Dynamic service user, private devices/network/temp, protected system/home,
  no privilege escalation or executable writable memory. The application worker
  has no ambient file handles, including journal output handles.
- Two-second ready deadline; no automatic application restart loop.
- Stop gives a one-second cooperative checkpoint interval inside systemd's
  two-second stop bound. Private-storage authority remains valid during that
  interval while interactive grants cease authorizing work.
- A checkpoint is successful only after a new `checkpoint` object is fsynced,
  atomically replaced, its directory fsynced, and the application acknowledges
  that provider receipt. A timeout or missing acknowledgement reports failure.
- The Supervisor retains the systemd unit long enough to observe its terminal
  result. It does not report a successful checkpoint when StopUnit merely accepts
  a request. The host reaps its worker; systemd controls the full service cgroup.
- Private storage: at most 512 KiB including staging, 32 bounded logical objects,
  and 24,576 UTF-8 bytes per object. No paths from an app. Old committed values
  survive a failed replacement; an interrupted staging file is discarded on
  provider restart. No external document writes are enabled.
- Views: title 64 characters, body 5,120 codepoints/20,480 UTF-8 bytes, at most eight
  actions of 32 characters. Text entry uses the same body bounds. Events are
  bounded to 16 entries; grants are bounded to 32 records per session.
- Logs contain typed lifecycle outcomes, not entered text or document contents.

The runtime profile provides ready, checkpoint and stop. General pause/resume,
full Notepad editor layout, external documents and arbitrary application surfaces
are not claimed by the reference service.

## IPC and shell integration

All channels use the existing Envelope 0 framing, canonical bounded CBOR and
`SOCK_SEQPACKET`; descriptors are rejected on the private host profile. The
registered C control interfaces now include resolved application code/policy,
observed lifecycle STATUS, grant VALIDATE and live-grant RENEW. Generated C/Python
metadata and fixtures are updated together.

The internal Python host/SDK profile is version 1 and uses these operations:

| Code | Application operation | Authority |
| ---: | --- | --- |
| 1 | Acquire capability | Installed mask and C broker |
| 2 | Release grant | Current instance and opaque grant |
| 3 | Ready | Private lifecycle channel |
| 4 | Present title/body/actions | Visual grant |
| 5 | Poll bounded events | Action/text grants checked before delivery; lifecycle remains available |
| 6 | Request shared text entry | Text grant |
| 7 | Read logical private object | Private-storage grant |
| 8 | Atomically write private object | Private-storage grant |
| 9 | Acknowledge checkpoint receipt | Pending checkpoint and durable provider receipt |

The private channel is created before the worker exists and is not a public
socket endpoint. Its semantic validators live in `Session.dispatch`; it is not
advertised as a general generated C application SDK. The root-only shell endpoint
is `/run/guideos/apps/<code>/shell.sock`; its operations are snapshot, action,
text result, checkpoint request, independent capability release and text cancel.
Application-controlled maps cannot address the shell endpoint directly.

`ShellState.open_application(code)` is the integration point for the future
installed-app catalog. `ApplicationPanel` performs IPC on one bounded worker so
it does not block the input/render loop. It uses Field Theme models and the
existing owner-bound keyboard, clears revoked presentation/text sessions, and
waits for confirmed checkpoint status on Home. The installed-app menu and
cartridge browser are step 2, not a hidden shell shortcut added here.

## Verification and payload

Current evidence is in `build/application-host-0/`:

- Nine runtime tests: real seccomp denial of ambient file, network, process,
  execution, device and peer-signal operations; quota/path checks; grant scope and
  revocation; interrupted replacement; acknowledged checkpoint semantics.
- C core/control tests, sanitizers, real systemd adapter and the original live
  probe/restart/reconciliation/grant/cgroup tests pass.
- Live installed-app test: non-root worker with active seccomp, actual systemd
  memory/task/descriptor ceilings, ready, semantic action/text exchange,
  Supervisor restart, checkpoint stop, private-data relaunch and independent
  presentation release. Modified source is rejected. Missing readiness and
  ignored checkpoints fail. The real shell adapter/shared keyboard/Field model
  runs through the same live service; `reference-shell.png` is its rendered view.
- Shell/UI/input/IPC regression suites: 249 tests run, one existing input skip.
  Including runtime tests: 258 run, 257 pass, one skip.
- ARM64 cross-build passes. The core self-test and application imports run against
  the saved Debian image under emulation. The image already has libseccomp but
  lacks Python CBOR; its repository-matched `python3-cbor2_5.6.5-1_arm64.deb` is
  downloaded and repository-hash verified in `runtime-debs/`, with SHA256SUMS.
  The package was extracted into a test overlay, not installed onto the seed.

`package/guide-foundation/install-arm64.sh ROOT ARM64_ARTIFACTS RUNTIME_DEBS`
installs the host, foundation and shell adapter into a prepared root filesystem,
using the verified offline dependency when needed. It creates no application
agreement. The harmless source in `python/reference_application.py` and its
installed record are created only by the development-host integration test.

A fresh capture/rebase and preservation audit are still required before making a
combined seed image. Keep the pending boot captions/stars and card startup retry
fix. Physical seccomp, systemd behavior, resource use, power interruption and
input/render timing remain unverified on the Deck; emulation does not prove them.
The next implementation task is the bounded cartridge catalog and transactional
internal installer described in step 2.


## Step 2 implementation follow-up — 26 September 2026

The owner-approved cartridge catalog, internal installer, agreement flow, isolated
health checks and recovery implementation are now described in
[Cartridge Installer 0](CARTRIDGE_INSTALLER_0.md). Its evidence supersedes the
earlier statement that the installer is the next implementation task.

The harmless reference application exercises delivery and retained private data;
it is not Notepad. The next application task remains implementing Notepad from
its accepted specification, including its storage categories and internal draft
recovery. External document writes still require the separate provider/broker
work. Seed installation and physical Deck acceptance remain separate gates.
