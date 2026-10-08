# Deck diagnostic and experience work plan

Current scope is diagnostic 4's untimed digital-button baseline. The complete
diagnostic 3 run has been archived and audited; its mapping-dependent navigation
and capture deadlines made several results inconclusive. Establish the simple
baseline before restoring broader exercises. Start, Power and Reset remain
excluded. See [diagnostic 4](../DEBIAN_DIAGNOSTIC_4.md) for the current implementation.

The current deliverable is an instrumented diagnostic installation, not a claim
that the whole handheld is validated. It is a reusable way to ask clear physical
questions, gather measured evidence, record the owner's experience, and preserve
what happened for the next engineering decision.

## Division of work

| Responsibility | Work | Evidence produced |
| --- | --- | --- |
| Integration agent | Implement test flow, package images, verify installation, compare run evidence and resolve defects | Versioned code, software checks, image hashes, reports |
| Usability review | Review prompts, physical diagrams, pacing, recovery, accessibility and observation questions | `DIAGNOSTIC_UX_REVIEW.md`, operator guide |
| Edge-case review | Challenge false positives/negatives, timestamp handling, event loss, mappings, exclusions and interruptions | `DIAGNOSTIC_EDGE_REVIEW.md`, regression tests |
| Hardware coverage review | Separate what devices advertise from what tests demonstrate; identify next component checks | `DIAGNOSTIC_HARDWARE_COVERAGE.md` |
| Owner holding the deck | Perform prompted physical actions; judge visibility, audibility, vibration, comfort and confusing interactions | On-deck answers and short follow-up notes tied to a boot ID |

## First package

Full-screen input discovery with two confirming taps, hold/release exercise,
stick coverage, selected simultaneous inputs, mapping review, missed-step retries,
pause/finish stage menus, and six short experience questions. Optional checks cover
visible display behavior, rumble, quiet audio tones and headphone detection.

Each run retains an offline `results.html`, machine-readable `results.json`,
structured control summary, raw timestamped events, system logs, storage inventory,
Wi-Fi link snapshot, and periodic exposed temperature/power/memory/load samples.
The boot partition's `diagnostics/index.html` links all retained report folders.
Reports distinguish measured, detected, user-confirmed, explicitly negative,
unanswered, excluded, unavailable, and incomplete evidence. Calendar time is not
trusted until the device has a clock source; use boot IDs and monotonic time.

Do one ordinary run first. After reconnecting, inspect technical and experiential
results together. Fix confusing prompts before adding more tests. A deliberate
recovery/edge-case run is separate so its injected mistakes cannot pollute the
ordinary baseline. Never ask the owner to exercise Start, Power or Reset.

## Subsequent component passes

1. Resolve missing or confusing physical mappings and controls. Confirm the
   full guided interface actually behaves on the handheld, not just in simulation.
2. Diagnose Bluetooth controller enumeration and audio routing; then test actual
   pairing/playback and Wi-Fi association using owner-selected peripherals/network.
3. Test USB roles, headphones/routing and removable storage with appropriate
   accessories and clearly scoped actions. Inventory alone is not a functional pass.
4. Plan charging, suspend/resume, stability and thermal runs with explicit scope,
   observation periods and recovery expectations. They are not hidden inside the
   first quick controls test. Power/reset buttons remain excluded unless the owner
   changes that instruction.

At every stage: save partial evidence, state what was not tested, and keep a
working image/recovery path. Do not convert a user perception into a measured
latency, a missing event into a broken button, or enumeration into functionality.
