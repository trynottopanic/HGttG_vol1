# GuideOS Runtime Pack 0

Status: adopted architectural direction; package schema and implementation remain to be specified and tested.

## Purpose

A Runtime Pack installs a large, reusable dependency set without embedding it in every application or modifying the active Debian system libraries. Typical examples include media engines, browser engines, language runtimes, large font collections and emulation libraries.

Runtime Packs use the common signed, staged and reversible delivery framework. They may arrive over paired Wi-Fi or from a read-only cartridge payload. The transport does not affect their authority or installation rules.

## Installation model

Each pack is immutable and installed at:

```text
/opt/guideos/runtimes/<runtime-id>/<version>/
```

Applications declare an exact runtime identifier, version or compatible ABI profile. The runtime broker resolves that declaration to a specific installed pack. Applications do not search the general system library path, and installing a pack does not replace files under `/usr/lib`.

A pack declares:

- runtime identifier, version, ABI and architecture;
- complete file inventory and digests;
- capabilities or libraries it provides;
- compatible application/runtime interface versions;
- installed and staging space requirements;
- health checks that do not execute package-supplied commands;
- whether an older version must be retained for rollback;
- optional provenance of source Debian packages.

No pack contains maintainer scripts, arbitrary hooks or authority to modify services, users, boot files, trust records or unrelated runtimes.

## Storage representation

Small packs may use a normal immutable directory. Large packs SHOULD use a compressed, read-only SquashFS image when measurement shows that it reduces storage or file-count overhead without unacceptable startup latency.

A filesystem image is verified in full before it is made available and is mounted read-only with restrictive options. It is exposed only through the runtime broker. Applications never supply mount options or privileged paths.

## Lifecycle

Multiple versions may coexist. Installation activates no application automatically. The runtime broker tracks which installed applications and retained rollback releases reference each version.

A version can be removed only when:

- no installed application references it;
- no active or retained trial/rollback release requires it;
- no running process holds a lease on it;
- the owner has approved removal or an explicit storage policy applies.

Update trials retain both the new and previous runtime versions. Failure returns consumers to the prior mapping without reconstructing system libraries.

## Size policy

Package limits are class-specific rather than universal:

| Package class | Initial default admission limit |
| --- | ---: |
| Guide release | 100,000,000 bytes |
| Application | 100,000,000 bytes pending its own review |
| Runtime Pack | 1 GiB |
| Media or content pack | Storage-policy controlled |
| Boot-critical image | Separate recovery process |

The Runtime Pack limit is also bounded by actual available storage. Admission requires enough space for the incoming package, staged installed representation, required rollback retention and an operating reserve. The Deck may enforce a lower device-specific limit. Raising a local limit does not bypass signature, scope or free-space checks.

## Debian source material

A development Node may construct a Runtime Pack from an exact Debian `.deb` dependency closure. It records package names, versions and source provenance, extracts only the approved runtime files, and signs the resulting immutable pack.

The Deck does not invoke `apt`, contact repositories, resolve dependencies or run Debian maintainer scripts while installing such a pack. Direct Debian package transactions remain a separate deferred system-update class with different repair requirements.

## Initial acceptance requirements

Before Runtime Pack installation is enabled on a Deck, evidence must establish:

1. bounded parsing and signature verification;
2. architecture and ABI rejection behavior;
3. interrupted receipt and power-loss recovery;
4. read-only mounting or immutable-directory enforcement;
5. application resolution through the runtime broker;
6. simultaneous old/new version operation;
7. rollback while the prior runtime is retained;
8. refusal to remove referenced or leased versions;
9. host and ARM64 tests;
10. seed integration, readback and physical Deck acceptance.
