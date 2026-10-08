# GuideOS IPC Envelope 0 pre-ARM64 report

Status: recommendations finalized through ARM64 runtime-image verification, 25
September 2026. Physical Deck acceptance and the live Supervisor/broker service
remain pending. See `docs/IPC_ARM64_IMAGE_VERIFICATION_0.md`.

## Recommendation

Retain the ARM64-verified Envelope 0 transport, profile and generated interface
registry as the common IPC substrate, subject to the service-enablement boundary
below. Do not install the Python reference broker as a permanent Deck daemon.
Use it as the behavioral oracle while moving persistent authority into the
single trusted Supervisor/capability-broker implementation.

## Choices recommended for adoption

1. **Common transport library:** retain the small C `libguide-ipc` layer over
   Unix `SOCK_SEQPACKET`. It owns bounded receive buffers, strict header/profile
   validation, `SCM_RIGHTS` correlation, close-on-exec descriptors and cleanup on
   every rejected receive. It does not interpret permissions.
2. **Schema source:** keep `schema/interfaces.json` as the interface registry and
   `schema/envelope0.cddl` as the common payload-shape contract. The deterministic
   generator emits C metadata, Python metadata, field constants, fixtures and
   readable documentation. Validation must fail when regeneration differs.
3. **Interface version boundary:** the common decoder validates that an interface
   major is nonzero but does not decide service compatibility. The selected broker
   checks its generated major/minor and can therefore return the required typed
   `INCOMPATIBLE_INTERFACE` result before closing.
4. **Supervisor resolution:** incorporate `guide_instance_registry.py` behavior
   into the accepted systemd-above-Supervisor implementation, not the obsolete
   custom-PID-1 executable. Resolve `SO_PEERCRED` PID/UID/GID against one reconciled
   registered cgroup, instance generation, package, component and agreement; pin
   the process with a pidfd. Reject unresolved or ambiguous peers.
5. **Capability authority:** retain opaque random 128-bit grant identifiers and an
   authoritative bounded store. Bind every record to instance and generation,
   provider/interface, capability, operations, scope, resource revision, sharing
   and expiry. Revoke and expire records centrally; never treat possession of an
   ID as sufficient without authenticated connection matching.
6. **Initial process topology:** let the first capability registry and grant broker
   share one lightweight trusted process while retaining separate records and
   operations. This minimizes memory and scheduling overhead without conflating
   discovery, permission and resource feasibility. Split them only when measured
   contention, privilege separation or fault isolation justifies another daemon.
7. **Reference integration:** retain `guide.broker.health` as the first harmless
   interface. It returns only service state and registry revision, requires the
   `system.diagnostics.read` grant and demonstrates identity, deadline, version
   and grant enforcement without exposing user content.
8. **Language boundary:** use C for persistent Deck brokers and Supervisor-facing
   authority. Keep the Python implementations as executable specifications,
   development fixtures and low-rate application bindings. Do not pay a resident
   Python-interpreter cost merely to translate IPC.
9. **Activation:** use one systemd `ListenSequentialPacket=` socket per broker
   under `/run/guideos/brokers/`. Socket filesystem permissions remain only a
   coarse admission boundary; peer resolution and grants remain mandatory.
10. **Diagnostics:** retain categorical, rate-limited protocol diagnostics. Never
    log payloads, grant identifiers, retry tokens, document text or private paths.

## Implemented development-host candidate

The repository now contains:

- deterministic registry generation and checked generated outputs;
- generated C operation/field validation metadata and Python equivalents;
- a position-independent shared C transport build;
- a bounded Supervisor process/cgroup resolver with reconciliation gating;
- a bounded grant store with expiry, revocation, release and generation invalidation;
- a grant-enforced health broker reference integration; and
- strict unit, cross-language, mutation and sanitizer tests.

The shared-library development build reports 9,339 bytes of text/data/BSS. This is
an x86-64 WSL figure, not an installed-size or ARM64 measurement.

## Corrections found during implementation

- The first generator draft emitted constants but not field-validation metadata;
  it now emits both.
- Expired grants initially retained bounded-table capacity; expiry now purges the
  authoritative record.
- The common decoder initially rejected unfamiliar interface versions too early;
  compatibility now belongs to the broker so it can send a typed result.
- Truncated ancillary receives now close every descriptor visible to the process
  before rejecting the message.

## Evidence obtained

On Ubuntu 24.04 under WSL2, x86-64:

- deterministic regeneration check: pass;
- strict C shared-library compilation with warnings as errors: pass;
- C descriptor transport test: pass;
- Supervisor reconciliation, membership and generation tests: pass;
- grant binding, expiry, revocation and invalidation tests: pass;
- grant-enforced health broker and incompatible-interface reply tests: pass;
- bidirectional C/Python compatibility spike: pass;
- systemd sequential-packet activation spike: pass;
- AddressSanitizer and UndefinedBehaviorSanitizer: pass; and
- 250,000 deterministic mutated payloads: pass without sanitizer findings.

These tests do not prove behavior under Deck memory pressure, a real Supervisor
restart, a real systemd application cgroup, or capability revocation involving an
already transferred descriptor.

## ARM64 image-verification outcome

The C runtime library and inspectable schema/registry payload were installed into
a copied ARM64 GuideOS staging image and passed loader, dependency, schema,
descriptor-transport, preservation and filesystem verification. The verified
candidate SHA256 is
`307223B9B70E703D941D3C71348E5541F1EA30B9D17A30F300023E19DB32C41B`.

The authority behavior was not installed as a Python daemon or represented as a
finished service. No broker is enabled: the missing systemd-era Supervisor
reconciliation and capability-authority boundary remains a prerequisite. This is
the safer result than installing a service whose grants cannot yet be provisioned
by the actual Supervisor.
## Evidence still deliberately open

- live broker dependencies, idle/peak RSS and service startup behavior;
- actual system-service and cgroup reconciliation;
- idle and peak RSS on the RG35XX H;
- behavior during broker or Supervisor restart;
- descriptor-lease revocation through application termination;
- physical latency and contention; and
- independent cryptographic/security review and coverage-guided fuzzing.
