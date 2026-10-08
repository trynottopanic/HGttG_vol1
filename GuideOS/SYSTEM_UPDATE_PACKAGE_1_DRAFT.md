# GuideOS System Update Package 1 — Superseded Combined Draft

Status: superseded before approval by the common
[Guide Signed Bundle 1](SIGNED_BUNDLE_1_DRAFT.md) contract and separate
[Guide Release Profile 1](GUIDE_RELEASE_PROFILE_1_DRAFT.md) and
[Runtime Pack Profile 1](RUNTIME_PACK_PROFILE_1_DRAFT.md) drafts. Retained as
design history; it is not an implementation contract.

Related design: [System Update Framework 0](SYSTEM_UPDATE_FRAMEWORK_0.md).

## 1. Purpose

This document defines the first interoperable package and trust format for
GuideOS system updates. It applies equally to packages received over paired
Wi-Fi and packages imported from read-only cartridge storage.

System Update Package 1 supports only the `guide-release` update class. It does
not authorize Debian package transactions, kernels, modules, firmware, device
trees, bootloaders, partition changes, complete root filesystems or trust-store
changes.

Its 100,000,000-byte ceiling applies to this `guide-release` profile, not to all
Guide package classes. Large shared dependencies use the separately governed
[Runtime Pack 0](RUNTIME_PACK_0.md) profile and its own storage policy.

The words MUST, MUST NOT, SHOULD and MAY describe conformance requirements.

## 2. Design decisions proposed for approval

1. The package is a ZIP archive using stored entries only. ZIP64, encryption,
   data descriptors, split archives and nested archives are forbidden.
2. The archive contains canonical `manifest.json`, a raw detached Ed25519
   signature in `manifest.ed25519`, and regular files below `payload/`.
3. JSON conforms to I-JSON and is canonicalized using RFC 8785 JCS.
4. SHA-256 identifies manifests, public keys and payload files.
5. Ed25519 is the only signature algorithm in version 1.
6. Update and key authority is explicitly scoped. Transport authentication is
   additional evidence and never replaces package authentication.
7. Unknown critical manifest members cause rejection. Unknown members below
   `extensions` may be retained and ignored.
8. Release ordering uses a monotonically increasing integer `releaseSequence`;
   human-readable versions are labels, not security comparisons.
9. The initial archive ceiling is 100,000,000 bytes, with at most 4,096 entries
   and at most 99,000,000 total payload bytes.
10. No package-supplied commands, scripts, hooks or executable policy language
    exist in this format.

## 3. Archive contract

The only permitted archive layout is:

```text
manifest.json
manifest.ed25519
payload/<manifest-declared relative path>
```

Rules:

- `manifest.json` MUST be the first local file entry and MUST be no larger than
  262,144 bytes.
- `manifest.ed25519` MUST be the second entry and exactly 64 bytes.
- All entries MUST use ZIP method 0 (`stored`).
- ZIP64 structures, archive comments, per-entry comments, extra fields, file
  encryption and data descriptors are forbidden.
- Directory entries are unnecessary and forbidden.
- Every name MUST be UTF-8, relative, NFC-normalized and use `/` separators.
- Names MUST NOT be empty, contain backslashes, control characters, empty
  segments, `.` or `..` segments, or begin with `/`.
- Case-folded duplicate names are rejected even though the target filesystem is
  case-sensitive.
- Every entry below `payload/` MUST appear exactly once in `files`, and every
  `files` record MUST have exactly one archive entry.
- Entries are regular-file byte sequences only. Symlinks, hard links, devices,
  sockets, FIFOs and sparse-file metadata are rejected.
- Nested `.zip`, `.guide`, `.tar` or other container entries are ordinary files
  only if explicitly permitted by the component profile; System Update 1 does
  not recursively inspect or execute them.

The receiver MUST enforce limits while reading central-directory metadata and
again while copying entry bytes. It MUST NOT extract the archive using a generic
unbounded extraction operation.

## 4. Canonical manifest

The root object has exactly these members:

| Member | Type | Required | Meaning |
| --- | --- | --- | --- |
| `format` | string | yes | Exactly `GUIDE-SYSTEM-UPDATE-1`. |
| `updateId` | string | yes | Calculated package identity. |
| `release` | object | yes | Resulting release identity and ordering. |
| `target` | object | yes | Product, architecture, board and base constraints. |
| `requirements` | object | yes | Space, power and interruption requirements. |
| `activation` | object | yes | One supported typed activation strategy. |
| `state` | object | yes | Persistent-state compatibility. |
| `files` | array | yes | Complete ordered payload inventory. |
| `signing` | object | yes | Signature and key identity. |
| `extensions` | object | no | Non-critical namespaced metadata. |

Duplicate keys are rejected before canonicalization. JSON numbers MUST be
non-negative integers no greater than 9,007,199,254,740,991. Floating point,
negative zero, `NaN`, infinities, byte-order marks and trailing data are
rejected. Strings MUST be valid Unicode and are not normalized by the parser;
fields that represent paths or identifiers have the additional constraints in
this document.

### 4.1 `release`

```json
{
  "version": "0.3.9",
  "releaseSequence": 39,
  "class": "guide-release"
}
```

- `version`: 1–64 printable ASCII characters, for display and diagnostics.
- `releaseSequence`: integer from 1 through 9,007,199,254,740,991.
- `class`: exactly `guide-release` in version 1.

### 4.2 `target`

```json
{
  "product": "GuideOS",
  "architecture": "arm64",
  "boardProfiles": ["rg35xx-h"],
  "baseReleaseSequences": [38]
}
```

- `product`: exactly `GuideOS`.
- `architecture`: exactly `arm64` in the first implementation.
- `boardProfiles`: 1–16 unique lowercase ASCII identifiers. The running board
  profile MUST exactly match one member.
- `baseReleaseSequences`: 1–64 unique integers. The currently active release
  sequence MUST appear in the array. Explicit full-replacement packages that
  intentionally support a wider base set must list every accepted base.

Ranges are not used: an explicit set is easier to audit and prevents accidental
claims of compatibility with an untested intermediate release.

### 4.3 `requirements`

```json
{
  "archiveBytes": 18350080,
  "payloadBytes": 18290102,
  "requiredFreeBytes": 73400320,
  "power": "external",
  "reboot": false
}
```

- `archiveBytes`: exact package length.
- `payloadBytes`: sum of every `files[].size` value.
- `requiredFreeBytes`: conservative required local free space before receipt is
  promoted to staged status.
- `power`: `external` or `battery-allowed`. The first release builder SHOULD use
  `external` until physical measurements establish a safe battery rule.
- `reboot`: MUST be `false` for `guide-release` version 1.

The Deck may apply a stricter local power or space rule. A package cannot weaken
local safety policy.

### 4.4 `activation`

```json
{
  "strategy": "immutable-release-switch-v1",
  "quiesceServices": ["guide-shell.service"],
  "startServices": ["guide-shell.service"],
  "trialSeconds": 60,
  "healthProfile": "guide-shell-v1",
  "rollback": "previous-release"
}
```

All identifiers come from controller-owned profiles. They do not name arbitrary
commands. Version 1 permits only:

- `strategy`: `immutable-release-switch-v1`;
- service arrays that exactly match the controller's `guide-release-v1`
  allowlist;
- `trialSeconds`: 15–300;
- `healthProfile`: `guide-shell-v1`;
- `rollback`: `previous-release`.

### 4.5 `state`

```json
{
  "resultSchema": 3,
  "acceptedInputSchemas": [2, 3],
  "migration": "none"
}
```

Version 1 permits `migration: "none"` only. The current persistent-state schema
MUST appear in `acceptedInputSchemas`, and `resultSchema` MUST equal the existing
schema. A future state-migration format requires a separate design because
rollback must remain coherent.

### 4.6 `files`

Each record is:

```json
{
  "path": "payload/guide-shell/main.py",
  "size": 48291,
  "sha256": "7f...64 lowercase hexadecimal characters..."
}
```

Records MUST be sorted by raw UTF-8 path bytes in ascending order. `path` obeys
the archive path rules. `size` is the exact byte count. `sha256` is exactly 64
lowercase hexadecimal characters. No two paths or hashes imply deduplication;
each declared entry is independently copied and verified.

### 4.7 `signing`

```json
{
  "algorithm": "Ed25519",
  "keyId": "sha256:7f...64 lowercase hexadecimal characters..."
}
```

The algorithm is exactly `Ed25519`. `keyId` is `sha256:` followed by the
SHA-256 digest of the raw 32-byte Ed25519 public key.

### 4.8 `extensions`

Extension names MUST use reverse-domain ownership, such as
`org.hhgttg.releaseNotes`. Extensions MUST NOT alter validation, authority,
activation, health or rollback semantics. A feature that affects those concerns
requires a new format or a new explicitly supported typed profile.

## 5. Update identity and signature

### 5.1 Update identity

To construct `updateId`:

1. Construct the complete manifest except for `updateId`.
2. Canonicalize that object with RFC 8785 JCS.
3. Calculate SHA-256 over:

```text
ASCII("GuideOS update identity v1") || 0x00 || canonical_basis
```

4. Set `updateId` to `sha256:` followed by the lowercase hexadecimal digest.

The identity therefore binds all file hashes, target rules and activation
requirements while avoiding a recursive hash.

### 5.2 Signature

After inserting `updateId`, canonicalize the complete manifest. Sign exactly:

```text
ASCII("GuideOS system update v1") || 0x00 || canonical_manifest
```

Write the raw 64-byte Ed25519 signature as `manifest.ed25519`. Base64, JSON and
text wrappers are not permitted. Verification uses the key identified by
`signing.keyId` and the exact canonical bytes reconstructed from the parsed
manifest.

The stored `manifest.json` MUST already equal its canonical form byte for byte.
A semantically equivalent but non-canonical document is rejected rather than
silently rewritten.

## 6. Trust store

The trust store is owned by the system-update controller:

```text
/var/lib/guideos/update/trust/
|-- policy.json
|-- keys/<key-id-hex>.json
|-- keys/<key-id-hex>.pub
|-- revoked/<key-id-hex>.json
`-- journal/<16-digit-sequence>.json
```

The filenames use the 64 hexadecimal characters without the `sha256:` prefix.
Public-key files are exactly 32 raw bytes.

### 6.1 Active key record

```json
{
  "format": "GUIDE-UPDATE-KEY-1",
  "keyId": "sha256:...",
  "algorithm": "Ed25519",
  "name": "Owner GuideOS development key",
  "status": "active",
  "scopes": [{
    "product": "GuideOS",
    "boardProfiles": ["rg35xx-h"],
    "updateClasses": ["guide-release"],
    "maximumReleaseSequence": null
  }],
  "addedBy": "local-owner",
  "addedSequence": 1
}
```

`name` is display-only and confers no identity. `maximumReleaseSequence` is
either null or an inclusive integer ceiling useful during controlled key
rotation. Version 1 accepts only `addedBy: "local-owner"`.

### 6.2 Revocation record

```json
{
  "format": "GUIDE-UPDATE-REVOCATION-1",
  "keyId": "sha256:...",
  "revokedSequence": 4,
  "reason": "owner-revoked",
  "replacementKeyId": null
}
```

A revoked key is rejected even if its active record remains. Revocation never
depends on wall-clock time. Restoring a revoked key requires a new local owner
trust action and journal record; deleting the revocation file is not sufficient.

### 6.3 One-update authorization

Approval of an unknown signer is stored with the update transaction, not under
`trust/keys/`. It binds the complete `updateId`, complete `keyId`, transaction
identifier and local approval event. It expires when that transaction reaches a
terminal state and cannot authorize another package from the same key.

### 6.4 Trust changes

Trust changes require a local owner interaction. Wi-Fi senders, cartridges,
applications and system-update payloads cannot add, widen or restore key
authority. Each mutation follows:

1. write and flush a new record;
2. atomically rename it into place;
3. flush the containing directory;
4. write and flush the next journal record;
5. update and flush `policy.json`.

Recovery replays complete journal records and ignores uncommitted temporary
files. A protected baseline copy of the initial owner key remains outside the
ordinary release tree.

## 7. Validation order

The controller performs these checks in order and makes no active-system change
during validation:

1. bounded archive length and ZIP structural rules;
2. exact permitted entry names and ordering;
3. canonical, bounded manifest parsing;
4. format and known critical-member validation;
5. recomputed `updateId` equality;
6. signing-key lookup or exact one-update authorization;
7. revocation and authority-scope checks;
8. Ed25519 signature verification;
9. target product, architecture, board and base-release checks;
10. anti-rollback release-sequence policy;
11. requirements, power and local free-space preflight;
12. file inventory, lengths and SHA-256 verification while copying into a new
    transaction-owned staging directory;
13. state-schema, activation-profile and recovery preflight;
14. durable transition to `validated`.

Signature verification occurs before payload hashing to reject unauthorized
large packages cheaply, but archive structural limits are always enforced first.

## 8. Stable rejection codes

The machine-facing result contains one stable code and may contain bounded
diagnostic detail. Initial codes are:

```text
UPDATE_ARCHIVE_INVALID
UPDATE_LIMIT_EXCEEDED
UPDATE_MANIFEST_INVALID
UPDATE_MANIFEST_NOT_CANONICAL
UPDATE_ID_MISMATCH
UPDATE_SIGNER_UNKNOWN
UPDATE_SIGNER_REVOKED
UPDATE_SIGNER_OUT_OF_SCOPE
UPDATE_SIGNATURE_INVALID
UPDATE_WRONG_PRODUCT
UPDATE_WRONG_ARCHITECTURE
UPDATE_WRONG_BOARD
UPDATE_BASE_INCOMPATIBLE
UPDATE_DOWNGRADE_REQUIRES_APPROVAL
UPDATE_POWER_UNSAFE
UPDATE_SPACE_INSUFFICIENT
UPDATE_PAYLOAD_MISMATCH
UPDATE_STATE_INCOMPATIBLE
UPDATE_PROFILE_UNSUPPORTED
UPDATE_RECOVERY_UNAVAILABLE
```

Diagnostics MUST NOT disclose private key material, unrelated filesystem paths
or data from another transaction.

## 9. Conformance fixtures

Before implementation is accepted, the source tree MUST contain immutable
fixtures generated from a documented fixed Ed25519 test seed:

1. one minimal valid manifest and package;
2. its manifest-basis canonical bytes;
3. expected `updateId` input and SHA-256 result;
4. complete canonical manifest bytes;
5. signature input and expected 64-byte signature;
6. public key and expected `keyId`;
7. expected payload digests;
8. a valid trust record and one-update authorization record;
9. one invalid fixture for every rejection code;
10. equivalent verifier results on the development host and ARM64 image.

The fixed private test seed is test material only and MUST be structurally
prevented from becoming a production trusted key. Production key generation
uses the operating system cryptographic random source and never occurs during a
reproducible image build.

## 10. Approval boundary

Approval of this draft adopts:

- the archive and byte-level signature format;
- the manifest field set and first supported values;
- explicit base-release sets and release-sequence anti-rollback;
- the scoped public-key trust-store model;
- the validation order and stable rejection-code family;
- the required conformance-fixture suite.

Approval does not authorize implementation on a seed, generation of production
signing keys, installation on the Deck, or physical activation of an update.

After approval, the next step is to create the JSON schemas, canonical test
fixtures, package builder and non-privileged verifier library. The privileged
controller should be wired only after those artifacts agree on both host and
ARM64 tests.
