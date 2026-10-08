# GuideOS 0.4.1 Home v3 r23

r23 addresses the browser failure recorded on the returned r22 Seed and repairs the installed full diagnostic exporter. Release sequence: 58; previous release: r22, sequence 57.

## Diagnosis

The retained journal records a browser attempt on r22 followed by `UInputError`, shell exit, and shell restart. The browser requires virtual keyboard and mouse devices through Linux uinput. The running kernel's build configuration disabled `CONFIG_INPUT_UINPUT`, and the captured root contained no uinput module.

The shell also imported the bootstrap browser frontend from `/usr/lib/guideos/browser`, bypassing the frontend supplied by its active signed release. That prevented r22's error handling and display recovery changes from taking effect.

The installed full diagnostic exporter called `report()` without importing it. The root helper is repaired to import `report` from `deploy_diagnostics`.

## Changes

- Prefer the browser frontend packaged with the active release, retaining the bootstrap fallback when no release frontend exists.
- Install the current frontend in the bootstrap location as well.
- Build and install `uinput.ko` against the existing `7.2.7-guide-debian2` kernel, with module autoload configuration and refreshed dependency metadata. The kernel image and boot partition are unchanged.
- Install the full diagnostic exporter import correction.

## Verification and evidence

The candidate is based on a fresh read-only capture of the connected Seed. Signature and every installed release payload were verified; ARM Python successfully imported the repaired exporter. Module metadata matches the existing kernel. Filesystem and service configuration checks passed. An independent inventory confines root changes to the new release, activation records, the two bootstrap helpers, and uinput installation metadata.

Owner state, pairing records, network credentials, SSH state, application data, and retained logs match the captured root. No repository test suites were run. Physical boot, browser launch, and full diagnostic export remain pending a check on the Deck.

Evidence is under `build/release-0.4.1/seed-current-audit-r23`, `build/release-0.4.1/r23-uinput`, and `build/release-0.4.1/candidate-v24-home-v3-r23`. The installation receipt records whether the bounded root write and complete readback succeeded; `cardWritten` alone is not physical acceptance.

## Seed installation

The guarded root-only installation completed on 2026-09-30 at 23:55:21 UTC. The complete 2 GiB root readback matched `F3EC3B720BCC8D4C6BA44C5911FB889585171F8AF3392744BF25040731ECEA1F`. The partition table and boot region, data partition, and checked tail region were rehashed and remain unchanged. Receipt: `build/release-0.4.1/candidate-v24-home-v3-r23/installation.json`, status `GUIDE_HOME_V3_R23_ROOT_READBACK_VERIFIED`.

Next physical checks: boot the Deck with this Seed, open Web Browser, then run diagnostics from NDI. These checks have not been performed by the offline installation.
