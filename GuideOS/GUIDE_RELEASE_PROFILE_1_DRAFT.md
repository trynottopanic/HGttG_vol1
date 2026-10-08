# Guide Release Profile 1 — Draft for Approval

Status: approved profile contract. Profile: `org.hhgttg.guide-release`, version `1`.

This profile installs an immutable Guide shell/interface release. Its admission ceiling is 100,000,000 archive bytes. It cannot install Debian packages, shared runtimes, state migrations or boot-critical files.

Its profile manifest declares `version`, monotonic `releaseSequence`, explicit `baseReleaseSequences`, `power` (`external` or `battery-allowed`), `strategy` (`immutable-release-switch-v1`), controller-owned service and health profiles, a 15–300 second trial, `previous-release` rollback, and equal current/result persistent-state schemas.

Files are installed only below `/opt/guideos/releases/<bundle-id>/`. Activation atomically changes the active release reference, starts the declared controller-owned trial and retains the previous accepted release. Machine commit and owner-reported physical acceptance remain separate records.

The initial development key is scoped to this profile, GuideOS, ARM64 and `rg35xx-h`, with no Runtime Pack, trust-management or boot-critical authority.
