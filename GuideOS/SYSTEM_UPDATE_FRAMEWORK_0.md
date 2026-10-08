# GuideOS System Update Framework 0

Status: proposed design for approval. This document does not claim an installed updater, a written seed, or physical acceptance.

## 1. Decision

GuideOS should use one local system-update controller with two delivery adapters: paired Wi-Fi and cartridge import. Both adapters deliver the same authenticated update bundle into the same durable staging area. Neither transport may activate files, run hooks, or modify the active system directly.

```text
paired Wi-Fi receiver ----\
                           >-- durable receipt --> verification --> local approval
read-only cartridge ------/                              |
                                                          v
                                              staged activation and trial
                                                          |
                                           commit <--- health ---> rollback
```

The transport answers how bytes reach the Deck. The update controller alone answers whether those bytes are acceptable, when they may become active, and how the prior system is recovered.

## 2. Governing requirements

1. The owner controls discovery, download or import, activation, downgrade, cancellation and rollback.
2. A disconnected Node, interrupted transfer, or removed cartridge cannot damage the running system.
3. A package hash proves integrity, not authorship. System updates require an accepted signing identity in addition to transport authentication.
4. Update packages contain declarative, typed operations. They contain no maintainer shell scripts, arbitrary commands, or application-controlled activation hooks.
5. Validation and recovery remain local and work without network access.
6. Receiving an update yields to foreground input, audio and video. Activation waits for an explicit safe point and does not interrupt preserved work.
7. The system reports separately whether an update was received, validated, installed, machine-health-checked, and physically accepted by the owner.

## 3. Common update bundle

The proposed canonical format identifier is `GUIDE-SYSTEM-UPDATE-1`. A bundle is an archive containing a canonical manifest, payload files and a signature. The same bytes may arrive over Wi-Fi or inside a cartridge payload.

Adopted encoding and cryptographic choices for System Update 0 are:

- `manifest.json` encoded as I-JSON and canonicalized with RFC 8785 JCS;
- a detached `manifest.ed25519` signature using Ed25519;
- SHA-256 file digests, public-key identifiers and update identifiers;
- signature input consisting of the ASCII domain separator
  `GuideOS system update v1`, one NUL byte, and the canonical manifest bytes;
- `updateId` calculated from the canonical manifest with `updateId` omitted;
- no JWS, certificate-authority dependency or embedded certificate chain.

The verifier rejects duplicate keys, floating-point values, unknown critical
fields, undeclared archive members and mismatches between the archive and the
manifest. Sizes and sequence counters are bounded non-negative integers. The
ordered file list is authoritative and names every regular payload file exactly
once.

The manifest records at least:

- `updateId`, derived from the canonical signed manifest;
- product, target board profile and architecture;
- required base version or permitted base-version range;
- resulting version and update class;
- bounded stored and expanded sizes;
- every payload path, length and cryptographic digest;
- components and services affected;
- required free space and power condition;
- quiescence, restart or reboot requirements;
- typed activation and rollback strategy;
- health probes and trial deadline;
- persistent-state schema compatibility;
- signer identity, signature algorithm and key identifier.

Archive paths must be relative, normalized, unique and explicitly listed. Links, devices, special files, path traversal, undeclared files and compression bombs are rejected. Existing 100 MB network deployment ceilings remain the initial ceiling for this system-update profile; smaller classes may impose lower limits.

## 4. Trust and authorization

The Deck owns a small update trust store. Initial trusted keys can include the owner's development key and, later, explicitly chosen community or project release keys. Pairing a computer permits it to offer bytes; pairing does not make every offered package a trusted system update.

Cartridge origin likewise does not confer authority. Cartridge Format 1's file hashes are sufficient for its current application-integrity purpose but are not sufficient for unattended system replacement. A system-update payload therefore must carry the common signed system-update bundle.

An unknown signer may be approved for one exact bundle after the Deck displays its fingerprint and consequences. Trusting that signer for future updates is a separate owner action. Key addition, rotation and revocation are journaled and must remain possible offline. Explicit downgrade is permitted only after an owner warning and state-compatibility check.

The adopted trust-store representation is a directory of individual public-key
records, revoked-key records and append-only journal entries rather than one
mutable database file:

```text
/var/lib/guideos/update/trust/
|-- policy.json
|-- keys/<full-key-id>.json
|-- keys/<full-key-id>.pub
|-- revoked/<full-key-id>.json
`-- journal/<sequence>.json
```

The Deck stores public keys only. A key identifier is the complete SHA-256
digest of the raw public key; the interface may display a shortened fingerprint
but internal comparisons always use the complete identifier. Every key record
limits authority by product, board profile and update class. Trust-store changes
require a local owner action and cannot be authorized by an ordinary update.

Revocation creates a durable record instead of deleting history. One-update
approval of an unknown signer is bound to the exact `updateId` and does not add
the key to the trust store. The controller tracks the highest accepted release
sequence per signing scope and requires explicit owner authorization for a
downgrade. Dates may be displayed but are not the sole enforcement mechanism
because the Deck clock may be incorrect.

The initial prototype trusts one owner development public key scoped only to:

```text
product: GuideOS
board profile: rg35xx-h
update class: guide-release
boot-critical authority: none
trust-management authority: none
```

Private signing material remains on the development computer or offline media.
Trust records use write-new-file, flush, atomic rename and directory-flush
ordering, followed by a journal commit. A protected recovery copy of the initial
owner trust baseline remains outside ordinary Guide release directories.

## 5. Delivery adapters

### 5.1 Paired Wi-Fi

The existing paired receiver may offer metadata and stream bounded chunks with resume support. The receiver writes only into an incoming transaction directory. It cannot select an activation time or bypass package verification. Losing the connection leaves either a resumable partial receipt or a safely disposable transaction.

### 5.2 Cartridge

The External Storage service discovers a candidate and supplies a contained, read-only descriptor. The update importer copies the complete bundle into local staging, verifies its received length and digest, and closes the descriptor. Installation never executes from removable storage; once durable receipt is confirmed, the cartridge may be removed.

The application cartridge installer remains separate. A system update uses a distinct typed action such as `system-update.import.v1`, which merely identifies the embedded common bundle; it does not grant installation authority.

## 6. Local transaction model

The controller permits one activating system transaction at a time. Receipt of other candidates may be queued within bounded storage limits.

```text
offered -> receiving/importing -> staged -> authenticated -> validated
        -> waiting-for-approval -> waiting-for-quiescence -> activating
        -> trial -> committed
```

Terminal and exceptional states are `cancelled`, `rejected`, `rolled-back` and `repair-required`. Every transition is recorded durably and is safe to replay after loss of power. Status events are advisory; the journal is authoritative.

Cancellation before activation deletes only transaction-owned staging data. Failure during activation invokes the declared rollback strategy. A successful health trial produces a machine-committed result. Owner-reported physical acceptance is recorded separately and is never inferred from automated probes.

## 7. Update classes

### Class A: Guide release

Shell, interfaces, assets and closely coupled Guide components are installed as an immutable release directory. Activation changes one local active reference, restarts the governed services and begins a bounded trial. The previous accepted release is retained for rollback. This is the first supported class.

### Class B: selected system services

Supervisor, brokers and providers may be updated only when their complete file set, service ownership, state compatibility, health probe and rollback boundary are declared. These should also use immutable versioned directories where possible. Enable individual components only after their recovery tests exist.

Large shared dependencies use the separate [Runtime Pack 0](RUNTIME_PACK_0.md)
model. Runtime Packs install immutable, explicitly versioned dependencies under
`/opt/guideos/runtimes/` and never overwrite the general Debian library path.
Their larger class-specific admission limit does not enlarge the 100 MB
`guide-release` profile.

### Class C: Debian package set

An exact, offline dependency closure of `.deb` files can eventually be admitted as a typed transaction. `dpkg` is not falsely described as atomic: interruption requires an explicit repair state, recovery procedure and known-good package set. This class is deferred from the first implementation.

### Class D: boot-critical system

Kernel, modules, firmware, device trees, bootloader, partition layout and whole root filesystem updates require an independently bootable A/B or equivalent recovery design. Until boot selection and automatic fallback are physically proven, this class is excluded from ordinary Wi-Fi updates and from automatic cartridge activation.

## 8. Activation policy

Receipt and verification run at background priority and yield to interactive work and media. Activation requires:

- explicit owner approval for the exact update;
- an adequate measured power condition, normally external power for early prototypes;
- sufficient verified local space for staging and rollback;
- no protected foreground task that cannot be paused and restored;
- a completed local recovery preflight;
- satisfaction of all base-version, target and state-schema constraints.

The Deck may offer `Install now`, `Install when idle`, `Keep for later` and `Cancel`. It must not silently force activation. Reboot-required updates say so before approval and never simulate an ordinary service restart.

## 9. Owner interface

The Updates surface has five views: Available, Downloading/Importing, Ready, Installed and Recovery. A review displays source, signer, size, target version, affected components, required interruption, whether a reboot is required, and whether rollback is available. The source is descriptive (`Wi-Fi from <paired name>` or `Cartridge`); it never substitutes for the signer identity.

Failure text distinguishes an invalid package, untrusted signer, wrong device, incompatible base, insufficient space, unsafe power, failed health trial and recovery-required state. It offers a concrete next action without concealing diagnostics.

## 10. Service boundary

The privileged controller owns incoming storage, verification, activation, rollback and the durable journal. The UI receives only bounded status records and submits explicit requests through the common IPC envelope.

Initial operations are `updates.snapshot`, `updates.watch`, `updates.inspect`, `updates.authorize`, `updates.activate`, `updates.cancel` and `updates.rollback`.

Transport adapters use an internal receipt interface: begin, append/import descriptor, finalize and abandon. Network-specific concepts do not enter the activation API. The service accepts descriptors or transaction identifiers, not caller-controlled privileged paths.

```text
/var/lib/guideos/update/incoming/<transaction-id>/
/var/lib/guideos/update/transactions/<transaction-id>.json
/var/lib/guideos/update/reports/<transaction-id>.json
/opt/guideos/releases/<release-id>/
```

## 11. Reuse and migration

The current network deployment implementation supplies useful transaction, resume, release-switch, trial and recovery behavior. The current cartridge installer supplies useful bounded parsing, descriptor containment, journaling and power-loss recovery behavior. Their safety primitives should be extracted into shared libraries, but their formats should not be merged blindly:

- `GUIDE-DEPLOY-1` is currently shell/input specific;
- Cartridge Format 1 is currently an unsigned application package;
- application installation and system replacement have different authority and recovery consequences.

`GUIDE-SYSTEM-UPDATE-1` becomes the common system contract. The existing network path migrates to it first; the cartridge adapter then imports the same bundle.

## 12. First implementation boundary

System Update 0 should implement only:

1. Class A immutable Guide releases;
2. owner/development signing and a local trust store;
3. Wi-Fi receipt and cartridge descriptor import of identical bundles;
4. durable validation, approval, quiescence, activation, trial and rollback;
5. retention of the previous accepted release;
6. recovery before the Guide shell starts;
7. host tests, virtual ARM64 tests, seed write/readback, then physical Deck tests.

Class B remains component-by-component. Classes C and D remain rejected by policy until their own recovery models are designed and physically proven.

## 13. Acceptance gates

The framework is not considered complete until evidence separately establishes:

1. source and host tests;
2. ARM64 image integration and virtual boot;
3. interrupted Wi-Fi receipt and removed-cartridge recovery;
4. corrupt, wrong-target, oversized, unsigned, revoked and replayed bundle rejection;
5. power loss at every durable transaction boundary;
6. failed health trial and automatic rollback;
7. seed write and full readback;
8. physical installation from both transports;
9. physical rollback and retained personal data;
10. owner-reported acceptance on the target Deck.
