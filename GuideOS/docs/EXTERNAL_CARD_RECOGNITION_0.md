# External card recognition 0

Physical follow-up, 26 September 2026: the owner reports that the card was missed initially, then recognized after removal/reinsertion. Startup recognition is not accepted. A cached-absence race is reproduced and corrected in source, but its connection to this physical failure is not yet confirmed. See [follow-up](CARD_STAR_FOLLOWUP_0.md).

Physical result, 26 September 2026: the owner confirmed external memory was recognized properly after the combined seed update. This confirms recognition in the observed case; removal, unsupported formats and installation remain separate acceptance items.

Installation update, 26 September 2026: included in the combined Field Theme seed
write and fully readback-verified. Physical acceptance remains pending. See
[installation evidence](FIELD_THEME_IMPLEMENTATION_1.md). Earlier staging evidence follows.

Status: implemented and candidate-image validated: **395 tests passed**.
Not installed or physically verified on TF2. The owner confirmed the preceding installed build's
onboard speakers work on 25 September 2026.

## Scope and ownership

Source requirements: [External Storage 0](../EXTERNAL_STORAGE_0.md),
[Cartridge Format 1](../CARTRIDGE_FORMAT_1.md), and the owner's request to let the
shell access the external slot and recognize Guide layout. Acceptance is a shell
screen that distinguishes no card, unreadable/unsupported card, ordinary readable
card, incomplete/invalid Guide layout, and recognized Guide layout, then clears
card evidence on removal.

`package/guide-storage/storage_service.py` is the single recognition and mount
owner. The RG35XX H board unit selects physical controller `4022000.mmc` (TF2),
checks SD device type and sysfs block identity, and tracks CID plus disk sequence
and partitions for insertion/removal. It does not assume that Linux assigns TF2
`mmcblk1`. It refuses a card if any of its volumes is already mounted and refuses
multiple supported volumes. Partitionless supported filesystems are accepted.

The provider mounts one exFAT, FAT or ext4 volume with
`ro,nodev,nosuid,noexec,noatime`; ext4 additionally uses `noload` to prevent journal
replay. It verifies mount flags before reading. Its private mount namespace keeps
the mount out of application namespaces. Only the provider inspects the card;
the shell reads a bounded internal status snapshot. Removing the card invalidates
its status and detaches the read-only mount. Service shutdown also releases it.
Discovery runs once per second. Failed recognition retries after ten seconds;
probe subprocesses have a 25-second deadline and shell status expires after 35
seconds. These bounds do not establish physical behavior under kernel I/O stalls.

The snapshot under `/run/guideos-storage/` is a provisional, trusted shell
integration detail. It is not a new broker protocol or application access grant.
The ongoing common IPC/broker work remains separate. No file-descriptor grants,
content streaming, installers, updates, writes, formatting, repair, archive
extraction, manifest admission or cartridge execution are implemented here.
There are no application leases to revoke yet. Safe-eject coordination for future
clients remains part of the shared service's later integration.

## What recognition means

A real root `GUIDE` directory containing at least one real canonical child is
recognized. Optional children are `CARTRIDGES`, `APPLICATIONS`, `MEDIA`,
`DOCUMENTS`, `GENERAL`, and `MISC`; `APPLICATIONS/GAMES` and `APPLICATIONS/BIOS`
are recognized when present. Missing optional directories do not invalidate a
card produced by the existing cartridge copy tool, which creates only
`GUIDE/CARTRIDGES`. An empty `GUIDE` is shown as incomplete. Case equivalents are
accepted; conflicting case duplicates and symlinks in recognized paths are
rejected. No new on-card marker or identity record is invented.

Directory enumeration is bounded at 512 entries per inspected directory. The
provider does not recursively index content. It counts regular `.guide` files in
`CARTRIDGES` within that bound and labels them **unverified**. It does not inspect
`.gde` or archive manifests in this slice. A directory match is evidence of layout,
not authenticity, package validity or permission to install.

## Board support and packaging

The installed 7.2.7-guide-debian2 kernel already has TF2 enabled but lacks exFAT
and UTF-8 NLS modules. `build/build-storage-modules.sh` builds `exfat.ko` and
`nls_utf8.ko` against that exact kernel's generated headers and exported symbols.
All exFAT dependencies are already built in. exFAT's default charset is explicitly
UTF-8; its UTF-16 conversion does not require the separate `CONFIG_UNICODE`
casefolding subsystem. This add-on build preserves the existing kernel config,
symbol table and working audio codec byte-for-byte. No kernel image, DTB or boot
partition change is needed. Future kernel rebuilds must include or rebuild these
modules for their own matching ABI; this is not a generic cross-kernel package.

`board/rg35xxh/debian/storage/install.sh` installs the modules and provider, runs
depmod, and enables the board service and shell feature. Module loading is done by
explicit privileged systemd pre-start commands; the running provider retains
only CAP_SYS_ADMIN for mounting within its private namespace.

The shell adds **EXTERNAL CARD** to Home. It shows card state, filesystem,
recognized folders and unverified cartridge count. B returns and Menu goes Home.
The five-item fallback Home layout and pointer hit targets are kept aligned.
The provider remains active when the screen is closed; navigation never owns a
mount's lifetime.

## Validation and remaining physical proof

Focused tests cover ordinary/minimal/full/case-varied layouts, Unicode content,
symlinks and duplicate roots, bounded enumeration, no writes, controller identity,
reinsertion generation, refusal of mounted seed and ambiguous cards, read-only
mount options, removal during recognition, lifecycle cleanup, and stale shell
snapshots. Candidate ARM64 regression tests and screen renders are recorded under
`build/external-storage/`. Module compilation and dependency checks are not proof
that physical TF2/exFAT works.

Next physical acceptance: install the candidate through the seed workflow after
rebasing onto a fresh seed capture; insert the prepared external card in TF2;
confirm EXTERNAL CARD shows exFAT and Guide layout; remove/reinsert and confirm
status follows. Then verify large/Unicode content and a 256 GB card as separately
required by External Storage 0. Do not format or alter the external card to force
a pass. Preserve the working audio build and all recovery captures.

Candidate: `build/external-storage/guide-external-storage-root.ext4`.
SHA256: `3917A912E603CD366E433B974D5240062D10D83DF667B93C396360AD70FF2777`.
The image comparison preserved 21,305 existing regular files and existing
symlinks, including the working audio module, gain configuration and owner state.
Service verification and module dependency resolution passed. The active packaged
shell was rendered with the feature enabled; normal and fallback Home, recognized
card and absent-card screens were inspected. A real temporary ext4 image test
confirmed read-only mounting, Unicode folder recognition, write refusal and
byte-identical image contents afterward. This does not substitute for exFAT or
physical TF2 acceptance.
