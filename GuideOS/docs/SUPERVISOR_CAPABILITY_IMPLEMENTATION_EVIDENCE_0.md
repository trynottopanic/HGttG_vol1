# Supervisor and Capability Foundation 0 implementation evidence

Source follow-up: [Application Host 0](APPLICATION_HOST_0.md) extends this foundation to installed Python applications. Its new binaries and runtime are staged, not written to the Deck. The original Foundation installation status below remains distinct.

Installation status correction, 26 September 2026: the retained installation record at `build/supervisor-capability-0/install/foundation0-installation.json` reports `ROOT_WRITE_VERIFIED` at 05:50:40 UTC. The Supervisor and broker binaries in the later readability image byte-match the verified ARM64 build. The candidate/write-boundary prose below records the earlier preparation stage, not current installation status. Physical lifecycle/grant acceptance remains unconfirmed. See the [current integration review](NOTEPAD_INSTALLATION_INTEGRATION_0.md).

Status: **verified installation candidate; ready for an explicitly directed root-partition write**, 26 September 2026.

The seed card has not been written. Physical acceptance remains a separate post-write stage.

## Implemented

- Bounded C lifecycle, instance, grant and revision state with reconciliation gating.
- Typed `sd-bus` transient-unit start, observation, STOP and failed-unit reset.
- Persistent monotonic launch generation and volatile per-boot runtime ledgers.
- Supervisor restart reconciliation bound to systemd unit, cgroup and Invocation ID.
- Private Supervisor Envelope interface: launch, peer resolve and idempotent stop.
- Broker Envelope interface: snapshot, resolve, acquire, bounded watch/resnapshot and release.
- Runtime grants bound to instance, generation, interface, operation and expiry.
- Socket-activated unprivileged broker and a harmless probe with an owned worker.
- Group-restricted `/run/guideos` namespace; socket modes remain the authority boundary.
- Current Envelope 0 schema and ARM64 `libguide-ipc` in the candidate image.

## Development-host evidence

- Strict C compilation, deterministic schema generation, core tests: pass.
- AddressSanitizer and UndefinedBehaviorSanitizer: pass.
- Ten-second coverage-guided state fuzzing: 488,973 executions, 173 coverage edges, no finding.
- Live systemd transient-unit launch and typed sd-bus observation: pass.
- Real `SO_PEERCRED`, pidfd and cgroup peer resolution: pass.
- Snapshot, resolve, acquire, health access, watch/resnapshot and release: pass.
- Missing-grant and released-grant denial: pass.
- Broker restart invalidates volatile grants; reacquisition succeeds: pass.
- Supervisor restart reconciles without replacing the running application: pass.
- Tampered Invocation ID ledger is discarded and no longer authorizes STOP: pass.
- STOP removes the transient cgroup; the owned worker is reaped: pass.
- Full-table grant failure leaves revision/state unchanged: pass (foundation rollback case).
- Bounded revision overflow returns stale/resnapshot-required: pass.

Measured during the live host integration:

| Process | RSS | Open descriptors |
| --- | ---: | ---: |
| Supervisor | 3,800 KiB | 6 |
| Capability broker | 1,572 KiB | 5 |
| Probe | 1,848 KiB | 3 |

These are x86-64 WSL measurements, not RG35XX H ARM64 measurements. The configured ceilings remain conservative pending physical measurement.

## ARM64 and image evidence

- Final ARM64 cross-build and SHA-256 verification: pass.
- ARM64 foundation core and Envelope 0 transport under QEMU user mode: pass.
- Dynamic dependency and ELF architecture inspection: pass.
- Candidate systemd unit verification: pass. Two warnings concern pre-existing Debian `!!` modifiers, not Guide units.
- Current IPC schema and library byte-match their verified build inputs: pass.
- Candidate ext4 read-only integrity check: pass.
- Checksum/content diff against the fresh root contains only expected account files, Guide services/sockets, enabled-unit links, IPC/foundation payloads, tmpfiles policy and state directory: pass.
- Full ARM64 PID-1/systemd guest execution was not available. Real systemd/cgroup behavior was instead exercised on the x86-64 WSL host; physical ARM64 behavior remains Stage E evidence.

## Identity and recovery

- Fresh read-only seed capture: `39CC34A1E44489A817FEA2727E2AFFF20B18DAC3BE5AB8CF76BCDBD9F5EBA1FC`.
- Fresh root image: `814D944AD8E345721BA4E7865E3FEE9912CAE86EF70DCF6A98A886B46AAF3EF6`.
- Verified candidate: `2B44F01CECAA53F42397F73CC3659928A7D51826784662382F745A98424A5ECF`.
- Candidate path: `GuideOS/build/supervisor-capability-0/guide-foundation-root-verified.ext4`.
- A write script is prepared with fixed disk identity, partition geometry, candidate hash, recovery-capture hash, prewrite region hashes, root-only write and post-write readback verification.

## Write boundary

Foundation 0 is ready for the next explicit installation instruction. The prepared write script must not run unless the connected disk still matches the recorded Transcend reader/card identity, all three prewrite region hashes match the fresh capture, and the owner explicitly directs the write. It writes only partition 2 and verifies that the boot and data regions remain unchanged.

After writing, physical acceptance must still verify normal shell, audio and Power behavior; Supervisor/broker readiness; lifecycle and grant flow; restart and cleanup behavior; ARM64 resource use; and cold-boot non-resurrection. Installation does not itself establish those results.
