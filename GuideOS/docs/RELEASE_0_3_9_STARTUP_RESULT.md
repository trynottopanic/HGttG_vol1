# GuideOS 0.3.9 startup and Applications continuation

27 September 2026. Source corrections and host evidence; see the candidate record
below for the image build result. The physical Seed remains the returned 0.3.7
installation. No Seed write is part of this continuation.

## Requirement and correction

The Supervisor owns whole-application lifecycle above systemd; provider discovery
and startup do not grant application permissions. The installer must commit only
a completed isolated health check and preserve previous programs, identity,
agreements and owner work on failure. Applications must distinguish retained
metadata from an installed program. These changes implement the existing
Supervisor foundation, application-host, installer and External Storage contracts.

The cold-provider race was reproduced using the actual systemd installer/host/
broker boundary with a one-second broker ExecStartPre delay. Before correction,
the first health check failed. No real owner data was used in the fixture.

Corrections:

- Application and health transient units require and order after the capability
  broker. Its startup has a two-second bound; application readiness retains its
  two-second bound, and the installer retains its five-second health observation
  deadline. Capability RPCs remain 200 ms. The adapter queues systemd work and
  returns; it does not block the Supervisor while the broker resolves peers.
- The Supervisor distinguishes a queued, inactive start job from a terminal
  process. It requires an actual process-start timestamp before interpreting an
  inactive exit-zero health check as a durable checkpoint. Delayed providers
  exposed the prior false-success case during integration testing.
- Failed same-version reinstall from an uninstalled record removes the failed
  candidate release. Previously the old version metadata caused cleanup to retain
  that candidate, so a later retry failed with `release already present`.
- Applications prefixes removed entries with **Not installed**, explains a record
  without a private store as **Installation record only**, and offers private-data
  deletion only when the catalog reports a private store. Open remains exclusive
  to committed programs. This is store-presence evidence, not a count of saved
  drafts or an assertion about note contents.
- Reinstall agreements say **reinstall** and retain the remembered version and
  permissions. Downgrade checks remain active, with wording that distinguishes
  remembered from currently installed versions.

## Evidence

Artifacts are in `build/release-0.3.9-startup/`:

- `cold-before.log`: reproduced baseline first-install health failure.
- `cold-after-2.log`: intermediate test exposed queued-job false success; not a
  passing release result. Earlier intermediate logs also retain build/property
  errors, rather than being overwritten as successful evidence.
- `cold-first-install-final.log`: first install with a cold, one-second-delayed
  provider; ordinary cold launch; cartridge-absent editing/save/relaunch;
  keyboard/Home checkpoint; uninstall retention; failed reinstall and retry
  preserving all saved objects.
- `cold-failure-retry-2.log`: five-second provider delay exceeds its two-second
  timeout, rolls back without false commit, retries successfully without deleting
  data, preserves identity and grants; all subsequent retained-work checks pass.
- `foundation-tests.log`: C core, sanitizers, codec, actual systemd adapter,
  systemd unit verification, and nine runtime tests pass.
- `installer-tests.log`: 31 tests pass, including UI states, failed-update
  preservation, transaction recovery and failed-reinstall retry.
- `arm64-build.log`: ARM64 Foundation build passes.

`apps/notepad/tests/live_cold_provider.py` and `live-cold-provider.sh` reproduce the
host scenarios. The shell fixture has exact-path preflight and temporary service
cleanup; do not run it with candidate images mounted. It uses fixture notes only.

## Recovery base and release boundary

The successful returned Notepad capture was SHA256-verified as
`D35855FB5D1F20079D29E2A86FFA74EAE09383C59A51A49A9B526CF37D2FF5E4`.
Disk identity was read again: Disk 4, TS-RDF5 SD Transcend, serial 00000000TS38,
62,239,277,056 bytes, neither boot nor system. This is identity evidence, not a
fresh byte comparison or authorization to write.

The image builder uses only this capture, preserves its installed Notepad and
owner state, and refreshes the immutable active shell release. The shell payload
inherits the captured release byte-for-byte except the installer panel and 0.3.9
label. It does not incorporate unrelated shared-checkout changes.

Authoritative image result: `build/release-0.3.9-startup/image/candidate.json`.
Preservation audit: `image/preservation.json`; full build output: `image-build.log`.
These files must report success before treating the image as validated. A root
candidate is not a written Seed or physical acceptance. Prewrite must compare the
actual card to the expected regions again and recapture/rebase if state changed.

TF2 remains unresolved; see [the controller investigation](TF2_REINSERTION_INVESTIGATION_0_3_9.md).
No kernel or persistent power workaround is included. Physical cold-start and
repeated-card-cycle acceptance remain outstanding.


Image build completed successfully: ARM64 core self-test, in-image Python syntax,
combined systemd verification, filesystem check and exact allowed-change audit
passed. Root SHA256 is
`b8ffbd82a5a5e1ae19facc9f84f1f5951661bd1e3e966ed54ddaeb1796021044`.
33 filesystem entries changed/added, including the new immutable release and its
directories. Existing owner-state entries and Notepad program/installation records
are unchanged. The original capture hash was verified again after the build.
