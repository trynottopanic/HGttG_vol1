# Returned Seed: hotplug and installation failures

26 September 2026. Physical report supersedes earlier image-only acceptance.
The combined image boots. External card recognition works when present at boot,
and the first insertion after an absent-card boot works. Removing and reinserting
again fails. Notepad preview verification succeeds; installation fails after Accept.

## Captured physical evidence

Read-only returned Seed capture:
`build/card-install-followup-0/capture-return.json`.
SHA256: `190E7081E02626917D521E5A41B4C3EBE7C82C05331F75AAFAF5BB1F508FB816`.
Service and kernel extracts are in that same build directory.

Previous boot kernel evidence:
- 53.532 s: external SDXC detected and mmcblk1p1 enumerated.
- 76.924 s: card removed.
- 139.156 through 143.720 s: repeated `4022000.mmc: fatal err update clk timeout`.
No successful second enumeration follows. This is a controller/clock failure
below filesystem recognition. Runtime power/clock restoration is a candidate
cause; the exact driver correction is not yet established or physically tested.
Do not reset or unbind arbitrary MMC controllers: the Seed is on another host.

Installation boot evidence:
- Supervisor started at 9.673 s.
- D-Bus closed an unauthenticated connection at 39.708 s, after its 30 s timeout.
- Cartridge parser inspection and extraction completed normally.
- At 52.235 s, Supervisor application start failed with `System.Error.ENOTCONN`.
- Installer reported `PermissionError` at 52.540 s. That is its generic rejected
  Supervisor request exception, not evidence that the archive was malformed.
- Transaction 2aaa462147404bb59a0a03243f4e020d ended failed after health-check.
  Its archive hash matches the delivered Notepad preview exactly.

The adapter opened sd-bus asynchronously but did not finish authentication before
an idle Supervisor waited for a first application. Host fixtures used the bus
immediately, masking the timeout. The correction finishes the handshake through
`sd_bus_get_unique_name` before returning success and checks readiness in the
integration test. This does not change authorization, application footprint,
cartridge integrity requirements or the owner's capability agreement.

## Source changes and current boundary

- Supervisor connection handshake corrected. Foundation tests pass.
- A live systemd fixture waited 35 seconds before its first Notepad installation:
  install/health, cartridge-absent save/relaunch, keyboard/Home recovery and
  retained data after uninstall all passed. ARM64 Foundation cross-build passed.
  Evidence: `build/card-install-followup-0/live-notepad-idle.log`.
- Storage cleanup now uses the namespace mount table rather than stat-based
  `ismount()`, which can fail on a departed filesystem. Twenty-nine storage tests
  pass, including three insertion/removal cycles with failed filesystem inspection
  and a check that unrelated mounts are never detached.
- That cleanup is a separate confirmed code weakness; it is not the cause proven
  by the controller clock-timeout log and must not be presented as fixing it.

The owner subsequently requested the Seed write. Both corrections were applied
onto that exact returned Seed, installed and fully readback-verified on
26 September 2026 at 23:21 EDT. Exactly two files changed; 24,551 other files/links
were preserved. Boot and data regions are verified unchanged. Root SHA256:
`2211786B2D3E11A7A6C65B97D2E50826D366B9A18C3440D9840EE7ADD7546A0A`.
Evidence: `build/card-install-followup-0/install/installation.json`.
Board clock recovery and physical retry acceptance remain outstanding.

## Subsequent physical result

The owner confirmed installation and the first-note test succeeded. Returned
logs confirm a committed release, successful health check, normal launch and
durable checkpoint. An additional cold-service startup failure and misleading
uninstalled-record display remain; see
[Notepad physical result](NOTEPAD_PHYSICAL_RESULT_0.md). The latest returned Seed
was read only. Repeated external-card reinsertion remains unresolved.
