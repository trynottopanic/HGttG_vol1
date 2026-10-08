# Envelope 0 compatibility evidence

Date: 25 September 2026  
Environment: Ubuntu 24.04 under WSL2, x86-64, Linux 6.18.33.2-microsoft-standard-WSL2  
Evidence class: development host only

## Selected dependencies

- `libcbor` 0.10.2 for C object conversion.
- `python3-cbor2` 5.6.2 for Python object conversion.
- Guide-owned bounded raw-profile validation before generic decode.

Observed installed development-host footprint:

- libcbor shared object: 60 KiB allocated filesystem blocks;
- libcbor development headers: 132 KiB;
- Python cbor2 package: 220 KiB;
- optimized spike executable: 13,904 bytes across text/data/bss as reported by
  `size` (13,888 bytes file-backed text/data plus 16 bytes bss).

These are x86-64 development-host figures, not ARM64 image measurements.

## Passing tests

`tests/run-spike.sh` established:

- Python profile validation and seven explicit invalid-profile cases;
- Python client to C `SOCK_SEQPACKET` service;
- C client to Python service;
- `SO_PEERCRED` acquisition;
- successful `pidfd_open` for the connected peer;
- one `SCM_RIGHTS` descriptor transferred and validated;
- matching 24-byte header and deterministic CBOR interpretation;
- close-without-reply behavior for wrong magic, duplicate map keys and declared
  length mismatch;
- systemd `systemd-socket-activate --seqpacket` compatibility; and
- optimized C spike text/data/bss size reporting.

Observed successful output included:

```text
PY_PROFILE_PASS invalid_cases=7
PY_CLIENT_PASS reply_bytes=35
C_SERVER_PASS ... pidfd=5 descriptor_mode=20000
C_CLIENT_PASS reply_bytes=35
PY_SERVER_PASS ... pidfd=5
PY_MALFORMED_PASS kind=magic
PY_MALFORMED_PASS kind=duplicate
PY_MALFORMED_PASS kind=length
SYSTEMD_ACTIVATION_PASS
GUIDE_IPC_SPIKE_PASS
```

`tests/run-sanitizers.sh` passed C/Python exchanges under AddressSanitizer and
UndefinedBehaviorSanitizer. Its raw validator then processed 250,000 deterministic
mutated or random payloads without a sanitizer finding:

```text
C_MUTATION_PASS cases=250000 accepted=46606
GUIDE_IPC_SANITIZERS_PASS
```

## Development-host microbenchmarks

These are directional measurements, not Deck acceptance:

```text
C_PROFILE_BENCH iterations=1000000 elapsed_ms=34.839 ns_per_validation=34.8
PY_PROFILE_BENCH iterations=100000 bytes=26 validate_us=4.46 decode_us=14.50 encode_us=12.37
```

The Python profile command's observed maximum resident set was 14,968 KiB,
including the Python interpreter and imported modules; it is not incremental
Envelope memory.

## Defect found by the spike

The first C exchange exposed an incorrect libcbor reference-ownership release in
the fixture reply builder. AddressSanitizer localized it and the ownership error
was corrected before the passing runs. This supports retaining sanitizer coverage
and not treating cross-language compilation alone as evidence.

## Not established

- ARM64 package footprint or performance.
- Native minimal-Debian package installation.
- Real systemd socket/service units in the Deck image.
- Supervisor instance/cgroup registry resolution.
- Capability grant lookup, revocation or cache invalidation.
- Durable retry records and provider restart reconciliation.
- Full generated CDDL validators.
- Physical RG35XX H latency, memory pressure, suspend or shutdown behavior.
- Independent security review or coverage-guided production fuzzing.

The next implementation stage should convert this spike into a shared library and
schema generator only after its ARM64 Debian dependencies and target image package
policy are confirmed.
