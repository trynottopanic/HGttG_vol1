# Guide Signed Bundle 1 — Draft for Approval

Status: approved common packaging contract. Source/host fixture evidence exists; image integration, seed installation and physical acceptance remain open.

## Purpose

`GUIDE-SIGNED-BUNDLE-1` is the common authenticated container for payloads delivered by Wi-Fi, cartridge or another future transport. It defines bounded parsing, content identity, signatures, targets and file inventory. A separately implemented profile defines what the payload means and what may be done with it.

## Archive

The bundle is a stored-entry ZIP:

```text
manifest.json
manifest.ed25519
payload/<declared files>
```

`manifest.json` is first and at most 262,144 bytes. `manifest.ed25519` is second and exactly 64 raw bytes. Version 1 forbids compression, ZIP64, encryption, data descriptors, comments, extra fields, directory entries, links, special files and nested executable packages. Names are unique NFC UTF-8 relative paths using `/`; absolute paths, backslashes, control characters, empty segments, `.` and `..` are rejected. Case-folded duplicates are rejected.

The format permits at most 4,096 entries and has an absolute structural ceiling of 2 GiB. Every profile sets a lower admission limit appropriate to its purpose and device. Available-space and rollback-reserve policy may impose a still lower local limit.

## Common manifest

The root contains exactly:

```json
{
  "format": "GUIDE-SIGNED-BUNDLE-1",
  "bundleId": "sha256:...",
  "profile": {
    "id": "org.hhgttg.guide-release",
    "version": 1,
    "manifest": {}
  },
  "target": {
    "product": "GuideOS",
    "architectures": ["arm64"],
    "boardProfiles": ["rg35xx-h"]
  },
  "requirements": {
    "archiveBytes": 1000,
    "payloadBytes": 500,
    "requiredFreeBytes": 3000
  },
  "files": [],
  "signing": {
    "algorithm": "Ed25519",
    "keyId": "sha256:..."
  },
  "extensions": {}
}
```

JSON is I-JSON canonicalized with RFC 8785 JCS. Duplicate keys, floating point, negative values, values above 9,007,199,254,740,991, invalid Unicode, byte-order marks and trailing data are rejected. Unknown root members are critical and rejected. Reverse-domain names under `extensions` are non-critical metadata and cannot change authority or installation behavior.

`files` is the complete payload inventory sorted by raw UTF-8 path bytes. Each record contains only `path`, exact `size`, and lowercase hexadecimal `sha256`. Archive entries and records correspond one-to-one.

## Identity and signature

To calculate `bundleId`, omit `bundleId`, canonicalize the remaining manifest and hash:

```text
ASCII("Guide signed bundle identity v1") || 0x00 || canonical_basis
```

Insert `sha256:<digest>`, canonicalize the complete manifest, then sign:

```text
ASCII("Guide signed bundle signature v1") || 0x00 || canonical_manifest
```

Version 1 uses SHA-256 and Ed25519 only. Stored `manifest.json` must already equal its canonical representation. Public-key identity is SHA-256 of the raw 32-byte Ed25519 public key.

## Profiles

A profile identifier is a lowercase reverse-domain string and its version is a positive integer. The pair `(profile.id, profile.version)` selects a controller-owned schema and behavior. Unknown pairs are never installed. They may be retained as inert files only under bounded storage policy.

A profile defines:

- its manifest schema and size limit;
- permissible targets and signer scopes;
- destination and ownership;
- admission, activation and health rules;
- references, leases and removal behavior;
- rollback and recovery requirements.

Profile data cannot weaken common parsing, signature, target or inventory rules. Adding a consumer adds a profile. Changing its semantics increments the profile version. The bundle format changes only when common encoding, identity, cryptography or archive behavior changes.

Multi-profile transactions and package-supplied scripts are forbidden in version 1. One bundle has exactly one profile and one independently reversible purpose.

## Trust scope

Trust records authorize exact profile identifiers and permitted version ranges, products, architectures and board profiles. Authority for one profile does not imply authority for another. Trust changes require local owner action; no bundle can enlarge its signer's authority. Exact one-bundle authorization binds both `bundleId` and `keyId` without adding durable trust.

## Common validation order

1. Enforce length, entry-count and ZIP structural bounds.
2. Parse and require canonical manifest bytes.
3. Validate common schema and recompute `bundleId`.
4. Resolve the exact known profile schema.
5. Resolve signer, revocation and profile-scoped authority.
6. Verify the Ed25519 signature.
7. Validate target and profile admission rules.
8. Verify space and recovery reserves.
9. Copy and hash every declared file into transaction-owned staging.
10. Run profile-specific non-destructive validation.
11. Durably record `validated`; activation remains a separate owner action.

## Initial profiles

- [Guide Release Profile 1](GUIDE_RELEASE_PROFILE_1_DRAFT.md)
- [Runtime Pack Profile 1](RUNTIME_PACK_PROFILE_1_DRAFT.md)

## Approval boundary

Approval adopts the common container, not either profile's implementation. After approval, the next artifacts are a machine-readable common schema, canonical positive fixture, rejection corpus, offline builder/signer and non-privileged verifier.
