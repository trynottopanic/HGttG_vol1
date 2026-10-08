# Envelope 0 production-preparation evidence

Date: 25 September 2026  
Environment: Ubuntu 24.04 under WSL2, x86-64  
Evidence class: pre-ARM64 development host only

`tests/run-production-prep.sh` checks deterministic generated outputs, compiles
`libguide-ipc.so` with strict warnings, exercises descriptor transport and runs
the Supervisor-resolution, grant-store and health-broker integration tests.

Observed passing summary:

```text
C_TRANSPORT_PASS
Ran 4 tests ... OK
text data bss dec
8515 816 8 9339 libguide-ipc.so
GUIDE_IPC_PRODUCTION_PREP_PASS
```

The complete compatibility and sanitizer suites also passed after these changes:

```text
GUIDE_IPC_SPIKE_PASS
C_MUTATION_PASS cases=250000 accepted=46606
GUIDE_IPC_SANITIZERS_PASS
```

The tests use a synthetic `/proc` and cgroup tree for deterministic Supervisor
membership cases while retaining a real pidfd for the live test process. They do
not establish real systemd-unit reconciliation. The health service runs across a
real Unix sequential-packet socketpair but is not installed as a daemon.

At this stage no ARM64 image, seed card or physical Deck had been modified. The
later continuation created a new copied staging image; it did not alter its source,
a seed card or the physical Deck.

## ARM64 continuation

The stripped C runtime was subsequently cross-compiled for AArch64 and exercised
inside the copied GuideOS filesystem under QEMU. The image, payload and evidence
are recorded in `../../docs/IPC_ARM64_IMAGE_VERIFICATION_0.md`. This adds runtime
image evidence only; the service remains disabled and physical evidence remains
open.