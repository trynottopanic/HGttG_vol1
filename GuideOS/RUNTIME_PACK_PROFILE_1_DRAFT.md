# Runtime Pack Profile 1 — Draft for Approval

Status: approved profile contract. Profile: `org.hhgttg.runtime-pack`, version `1`.

This profile installs an immutable shared dependency set. Its initial admission ceiling is 1 GiB, further limited by incoming, installed, rollback and operating-reserve space calculations.

Its profile manifest declares `runtimeId`, `version`, `abi`, architecture, provided interfaces, compatible consumer requirements, representation (`directory` or `squashfs-v1`), provenance metadata and rollback retention. Runtime identifiers are lowercase reverse-domain names.

Files are installed only below `/opt/guideos/runtimes/<runtime-id>/<version>/`. Packs never overwrite `/usr/lib`, run Debian maintainer scripts, modify services or activate applications. SquashFS images are fully verified before restrictive read-only mounting through the runtime broker.

Multiple versions may coexist. Removal requires no application reference, rollback reference or active lease. Signer authority is scoped to this profile and may optionally be narrowed to named runtime identifiers.
