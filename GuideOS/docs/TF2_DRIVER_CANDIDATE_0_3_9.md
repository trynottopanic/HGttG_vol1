# TF2 driver and initial clock candidate, 0.3.9

27 September 2026. Candidate correction **installed and fully readback-verified**
at 12:03:18 UTC. Bootloader, root filesystem and data partition hashes match the
fresh returned capture. Physical acceptance remains pending.
The previous physical release plays both Music and Video after reinsertion,
but its external controller sometimes times out before initial enumeration.

## Changes and limits

The driver explicitly programs a 400 kHz module clock before enabling TF2 after
controller reset, both on initial probe and runtime resume. The quirk requires
both the `anbernic,rg35xx-h` board identity and `4022000.mmc`; the Seed and Wi-Fi
controllers retain their original clock setup. Subsequent normal clock setup
restores the requested card rate. There is no permanent hold-awake policy,
increased timeout, forced reset during transfers, or mount-owner change.

Shared driver error handling now propagates host-initialization and clock
restoration failures from runtime resume. A failed resume keeps interrupts
disabled, unwinds enabled clocks, and records the failure. A failed card supply
operation cannot be overwritten by successful clock setup. Failed clock setup
no longer advertises the previous actual clock. TF2 timeout logs retain the
registers, requested/module rates, power state and enable/disable direction.

The initial-clock change addresses dependence on an inherited clock setting.
That is a candidate cause, not an established physical root cause. The code-level
error propagation defects are independently reproducible. Passing software tests
does not prove that either correction resolves the physical timeout.

## Build and tests

- Patch: `board/rg35xxh/debian/tf2-clock-startup.patch`.
- Local kernel: `/home/hacker/guideos-work/debian-h700-kernel/linux-7.2.7`.
- Kernel release remains `7.2.7-guide-debian2`; module symbols/configuration match.
- Installed baseline Image SHA256:
  `2b2f6dbb90638021132e8858b78a5aa00e1ab56d9264daea3bca617d1f30f90d`.
- Candidate Image SHA256:
  `2bf1e30ceb1607b6140c313c9ea2fdc6e68b2d535c734263f545700f8b8345d1`.
- ARM64 kernel build passed. Kernel patch check: zero errors and warnings.
- Fault-injection tests compile the actual modified functions with hardware
  stubs and address/undefined-behavior sanitizers. They cover clock-rate-before-
  enable ordering, ordinary non-TF2 operation, each enable/unwind failure, invalid
  initial rates, resume initialization/clock failures, and supply-error retention.
  These tests verify software behavior; hardware clock settling is not simulated.
- Original missing panel/regulatory firmware was recovered from the retained
  original compiled objects. Rebuilt firmware objects are byte-identical.

## Preservation and physical gate

Fresh capture: `E:/DGttG/private-recovery/tf2-driver-return-20260927-075400/seed-used-region.img`.
SHA256 `5E3436DF256ECE0610D1C8B81F9A42F2E9F20A28F9EAD3FC323F09F575614CE7`.
The boot candidate replaces only `/Image` and adds `/Image.pre-tf2-0` containing
the exact preceding kernel. Boot configuration, DTBs and reports are preserved.
The writer guards the disk identity and exact capture match, writes only the
boot partition, reads it back, and verifies bootloader/root/data unchanged.
The previous kernel remains available in the recovery capture and on the Seed;
this is manual recovery, not a proven automatic boot-fallback mechanism.

After installation: boot with the external card already inserted, verify it is
recognized without reinsertion, then exercise at least three idle removal/
reinsertion cycles and another normal shutdown/boot. Confirm both players still
work. A timeout should now expose `GUIDE_TF2_CLOCK` evidence in the kernel journal.

Evidence and guarded writer: `build/tf2-driver-fix-0/` and
`build/install-tf2-driver-fix-locked.ps1`. The first writer attempt stopped
without changing any card region; the retry verified that exact original state,
locked/dismounted the boot volume, wrote it, and passed full readback. Source-only TF2 Wi-Fi probes from the preceding
work remain uninstalled; this boot-only update does not extend updater scope.

The combined startup patch supersedes the earlier diagnostic-only patch; do not
apply both. Kernel and user-facing OS versions remain unchanged.
