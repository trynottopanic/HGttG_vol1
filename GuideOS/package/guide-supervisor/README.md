# Guide Supervisor source

`src/guide-supervisor.c` and its existing build recipe retain the earlier
custom-PID-1 prototype. The accepted Debian architecture uses systemd as PID 1;
the old executable is not the new application-supervision service.

`src/guide_resource_policy.c` is the isolated reference component for the
[resource contention contract](../../RESOURCE_CONTENTION_0.md). It implements
capacity decisions and a bounded interruption state machine. It emits decisions;
it neither applies systemd changes nor controls network transfers. Keeping this
component beside the existing C source does not wire it into the old executable.

Run its contract tests from Linux:

```sh
sh GuideOS/package/guide-supervisor/tests/run-resource-policy-tests.sh
```

The runner compiles in a temporary directory and removes only that temporary
output. It does not install software, signal applications or access the seed.
The synthetic fixtures are not board-profile defaults. Deployment still needs
the host adapter, installed-agreement store, authenticated lifecycle path and
physical acceptance described in the contract.

## Development host adapter

`host/guide_systemd.py` is an isolated Python standard-library adapter for a
systemd user manager. It launches a fresh transient unit per instance, groups
cooperating workers, checks CPU weight, memory pressure threshold and task limit
in the kernel, and requests asynchronous unloading after trusted authorization.
It distinguishes a stop request from observed empty process containment.
MemoryHigh is a pressure threshold, not a hard memory ceiling or reservation.

Four integration tests passed against the development host's real systemd user
manager on 22 September 2026: worker containment/controls and unloading guards,
a refused stop remaining unresolved without automatic SIGKILL, replacement
invocation rejection, and input/record bounds. Run explicitly with:

```sh
python3 GuideOS/package/guide-supervisor/tests/test_systemd_host.py --run-systemd-integration
```

The tests create disposable user units and force-clean only those units afterward.
These are Linux development-host results, not Debian image or Deck evidence.
The adapter is not installed or exposed to apps. The transfer-session integration
now runs a provider using the C allocator under this adapter; the C lifecycle
escalation state machine is still not wired into the host stop path.
It assumes a trusted, serialized caller and cooperative same-user programs;
it is not a security boundary against those programs. Its records are volatile,
restart recovery is unsupported, and absent accounting remains unknown. It does
not implement network control, checkpoint transport, forced escalation, or a
privileged system-manager service. Command timeouts require reconciliation rather
than blind retry. Instance records are bounded and retired only after observed
empty containment (or before any start attempt).

The choice of Python, user-manager testing, strict validation and stop guards are
implementation choices for this development slice, not additional owner mandates.
The owner has clarified that the earlier social cyberspace philosophy does not
impose universal anonymity, absolute separation or zero risk on GuideOS. Evaluate
these implementation choices by their concrete purpose and cost; the clarification
hold is resolved. For example, instance checks prevent acting on the wrong run,
and save guards implement the explicit data-preservation contract. They do not
require every trusted component to run in a separate security sandbox.

## Cooperating transfer provider

`host/guide_transfers.py` and `host/run_transfer_session.py` use
`src/guide-network-plan.c` to call the existing C allocator. Independent bounded
range workers implement pause acknowledgement, partial-file recovery and checked
completion. See [implementation and evidence](../../TRANSFER_PROVIDER_0.md).

```sh
sh GuideOS/package/guide-supervisor/tests/run-transfer-tests.sh
```

The package/build scripts produce a separate installable ARM64 acceptance package.
They do not modify the seed or replace the legacy supervisor executable.
