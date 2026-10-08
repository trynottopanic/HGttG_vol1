# Transfer provider implementation 0

22 September 2026. Implements the cooperating transfer mechanism for the
[contention contract](RESOURCE_CONTENTION_0.md). This is an acceptance component
for the developing Guide runtime, not a replacement OS shell or media player.

## Implemented path

The existing C policy decides how many payload bytes each transfer may request
in an accounting interval. A small command bridge makes that same policy usable
from the Python provider and builds as a static ARM64 executable. The provider
loads one recorded agreement revision; executions do not negotiate a new footprint.

Two independent workers issue bounded HTTP range requests. A stalled download
does not block the other worker. Allowances expire and unused credit does not
accumulate. After a pause request, a bounded in-flight request may finish;
the provider acknowledges pause after the connection closes and its partial
file is saved. Resumption continues from that byte offset. Source size and
SHA-256 bind the saved content, including recovery after provider restart.

Finished content is published only after checksum verification. Failed ranges,
incomplete responses and mismatched hashes produce failure rather than a
successful completion claim. Logs record instance identity, agreement revision,
allocations, worker state and byte offsets without copying ticket URLs.

The session runner is an application process containing its two workers. An
integration test launches it through the development systemd host adapter,
verifies its actual resource controls and observes empty containment on exit.
Completed, empty retained units are now retired by the adapter as well.

## Scope and evidence

| Check | Result |
| --- | --- |
| Five real-HTTP provider tests | Passed: pause/recovery, independent progress during a stalled download, restart recovery, invalid range/checksum rejection and capacity shortfall. |
| Recorded-session integration | Passed: saved pause/resume evidence, verified completion, fresh instance on restart without redownloading completed files. |
| Four systemd host tests | Passed after the empty-unit retirement change. |
| Combined systemd/provider integration | Passed with real user-manager controls and observed worker exit. |
| Debian ARM64 userspace under emulation | Both 131,072-byte and 262,144-byte payloads completed with verified content. |
| ARM64 pause evidence | Download held at 76,800 bytes across eight paused observations; stream transfer advanced 43,008 bytes, followed by download resumption. |

The capacities, progress floors, weights, payloads and timing in these tests are
synthetic fixtures, not measured board defaults. HTTP requests are real; the
capacity schedule is injected. This does not prove physical shared-link shaping,
Wi-Fi behavior, video decoding, display/audio continuity or production fairness
against unrelated applications. A receiver-side allowance is not a kernel network
shaper: wire overhead, peer buffering and already-running requests remain separate.

The provider uses Python already present in the Debian staging image. It has no
general privileged service or remote API, no automatic link estimator and no
hardware driver changes. Request timeouts and bounded requests aid recovery;
Python threads and host I/O do not supply a hard real-time guarantee. A worker
that cannot stop is reported as unconfirmed, rather than described as stopped.

## Prepared artifacts

- [ARM64 Debian package](build/transfer-provider/guide-transfer-provider_0.1.0_arm64.deb).
- [ARM64 recorded result](build/transfer-provider/arm64-validation/session-output.json).
- [Host/ARM build script](build/build-transfer-provider.sh).
- [Package script](build/package-transfer-provider.sh).
- [ARM userspace validation](build/validate-transfer-arm64.sh).
- [PC fixture source](package/guide-supervisor/tests/serve_transfer_fixture.py).

The package installs `guide-transfer-session` and its provider files. It does not
enable a boot service, change the shell or install remote access. It has not been
installed on the seed. The fixture source serves exactly two generated payloads;
it does not expose the PC's files and is separate from the Node/AT Field service.

## Next physical acceptance

First establish how the Deck will reach the PC on the local network. The current
diagnostic image is not a completed Guide shell; its presence on the card does
not establish usable networking or remote operation. The 22 September read-only
audit found Wi-Fi software but no network profile in the last validated Debian
staging root, and no successful association or address assignment in the archived
physical boot logs. A later read-only copy of the connected seed confirmed no
saved Wi-Fi profile in the inspected standard locations. Network setup and an
actual Deck boot are needed to establish connectivity. See
[Wi-Fi readiness evidence](docs/WIFI_READINESS_0.md).

Once the network path and launch method are available, run the PC fixture with
an explicitly selected LAN bind address and copy its manifest to the Deck. Install
the prepared package and run `guide-transfer-session --manifest PATH --output DIR`.
Read the saved event and summary files to verify pause, resume and content integrity.
Then measure the real link and integrate a decoder for the owner-selected
video-plus-download test. Do not infer smooth playback from file-transfer results.
