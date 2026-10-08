# GuideOS hardware coverage and evidence contract

This is the minimum coverage plan for the RG35XX H diagnostic results provider.
It describes future checks as well as existing evidence; it does not claim that
diagnostic 3 has run on the handheld. Start, Power, and Reset remain excluded
from discovery, navigation, combinations, and requested physical testing.

## Ground truth and limits

The inspected physical run is diagnostic 2, boot ID
`2c89343f-d671-4e5e-93c1-e2101d2ac630`, archived under
`build/debian-diagnostic-2/hardware-tests/2026-09-21-234733/`.
`RESULT.md` records the owner's screen confirmation and hash-checked extraction.
The device clock was unset; the archive name is host time, not device boot time.

`cube.txt` records exit 0 and 1799 frames in 29.983287 seconds at 60.000092 fps
for the requested 1800-frame command. This supports short sustained graphics,
not a stress-test or a claim that every requested frame was logged.
`game-events.txt` supports press/release events for 14 button codes and four
axes reaching -1800 and +1800; it does not establish every physical label,
center quality, simultaneous combinations, or input latency.

`network.txt` and `wifi.txt` show an unassociated, DOWN `wlan0`; `audio.txt`
enumerates H616 Audio Codec. Wi-Fi connectivity and audible output are unknown.
`device-nodes.txt` and `dmesg.txt` do not show a Bluetooth hci0 controller on this
boot. Loaded Bluetooth protocol modules and absent packet warnings cannot
establish working Bluetooth. Absence is a finding about this boot, not a claim
that the product lacks Bluetooth hardware or that the earlier issue is fixed.

`DEBIAN_DIAGNOSTIC_3.md`, `board/rg35xxh/debian/controller-test.py`, and
`board/rg35xxh/debian/diagnostic3-boot.sh` describe the prepared guided workflow.
Its physical validation remains pending. Application regression tests and build
validation are separate evidence from handheld results.

## Status model

Keep evidence type and outcome separate. A single green hardware status would
hide important distinctions:

| Dimension | Values | Meaning |
| --- | --- | --- |
| Evidence basis | `enumerated`, `tested`, `user_confirmed`, `not_tested` | Enumeration sees a capability; a test records an actual bounded operation; a user confirmation records a subjective observation. Multiple bases can coexist. |
| Outcome | `pass`, `fail`, `inconclusive`, `not_tested`, `excluded` | Pass/fail requires a named criterion and valid evidence. Missing input or missing files is not automatically failure. |
| Presence | `present`, `absent`, `unknown` | Distinguishes a successful inventory with no device from an inventory command that failed. |
| Execution | `completed`, `skipped`, `timed_out`, `interrupted`, `blocked`, `error`, `not_started` | Explains whether the intended procedure ran. |

Examples: Wi-Fi can be `presence=present`, basis `enumerated`, connectivity
`outcome=not_tested`. Bluetooth is `presence=absent` for this run with pairing
`execution=blocked`; pairing must not be rendered as failed. A tone command can
complete while audibility remains inconclusive. A recorded user answer of
"no sound" is distinct from no answer. A timed event capture's expected exit
124 does not invalidate captured events; a cube timeout does not prove frame
completion. Start/Power/Reset appear as excluded, never as failed controls.

## Minimum coverage matrix

Each row should expand into individual test IDs in machine-readable results.
The baseline column refers only to the inspected diagnostic 2 run.

| Function | Baseline evidence | Minimum useful next check and acceptance |
| --- | --- | --- |
| Boot, CPU, memory, kernel health | Userspace reached; memory inventory; no final failed units or kernel WARNING/BUG traces in captured logs | Capture kernel/build identity, RAM, boot progress, deferred probes, failed units, temperature/frequency sensors if available. Reaching userspace is a boot pass only; bounded workload and memory tests are separate future tests. |
| LCD, GPU, orientation | 640x480 connector, Panfrost EGL, short cube run; owner confirms expected screen | Guided color/motion screen with explicit visibility, orientation, clipping and artifact answers; preserve GPU command results separately. No response means unconfirmed. |
| Brightness/backlight | No functional result | Inventory interfaces first; later offer bounded nonzero levels with original value restored and user visibility confirmation. Do not make the screen unreadable. |
| Face buttons A/B/X/Y | Four code press/releases | Diagnostic 3 physical label discovery, release/hold/tap per button; reject duplicates and ambiguous trials. |
| D-pad Up/Right/Down/Left | Four code press/releases | Individual mapping, held duration and selected diagonals; record the exact combinations actually tested. |
| L1/R1/L2/R2 and both stick clicks | Six code press/releases | Map physical labels, hold/tap/release, selected face/shoulder combinations and click while moving. |
| Select and Menu | Advertised codes without captured events | Guided discovery and exercise, with retry and no timeout-to-defect inference. |
| Volume + and - | Separate input device enumerated | Map both physical keys, hold/release/tap; distinguish key reporting from audible gain changes. |
| Start, Power, Reset | Not functionally tested | Explicitly excluded. Do not prompt, map, use to navigate, or require for completion. |
| Left and right stick X/Y | Four axes reached reported endpoints | Learn axis identity/polarity; preserve raw min/max, baseline/center spread, sweep coverage, return to center and click/motion results. Thresholds are guidance, not calibration or defect diagnosis. |
| Rumble | Force-feedback capability advertised | Optional bounded low/high pulses with explicit felt/not-felt/unsure answer and cleanup; successful effect upload alone is not a functional pass. |
| Speaker audio | Codec enumerated; initialization/routing questions open | Optional quiet left/right tones with channel identity and audible/not-audible/unsure answers. Record level, playback device and exit status. Do not infer speaker or routing operation from ALSA enumeration. |
| Headphone jack and output | Switch-capable input device enumerated | Optional insertion/removal transition test, then separate quiet channel playback and speaker-muting observation. Detection alone is not correct routing. |
| Wi-Fi | `wlan0` present, DOWN, no association | Inventory driver/firmware/rfkill; later opt-in bounded scan, association to a user-selected network, address acquisition and local reachability as separate checks. Internet reachability is a separate optional result. Never persist credentials in reports. |
| Bluetooth | hci0 absent this boot | First capture rfkill, firmware, UART binding, driver/probe logs and successful inventory exit statuses; compare repeat boots. Only after a controller appears offer discovery, pairing and actual accessory operation as separate checks. Avoid automatic firmware/reset experiments. |
| Primary SD and report persistence | Booted mmcblk0, mounted partitions, extracted reports verified | Inventory identity/mounts/free space; verify report save and mirror independently. On later planned boots, check distinct boot IDs and retained checksums. This is not a media endurance/performance pass. |
| Secondary SD | mmcblk1 and partition enumerated in kernel log | Identify the slot/card before any operation. Optional read-only listing/hash of a nominated file; no formatting, raw writes, repair or automatic writable mounting. Hot removal is not a baseline check. |
| USB host/accessories | Host controllers/root hubs enumerated | Later user-provided known accessory, per physical port: connection, enumeration, and actual HID/file-read operation. Record cables/adapters; controller registration is not port operation. |
| USB device/OTG role | No functional evidence | Inventory advertised role support; mark applicability unknown until supported configuration is established. Future host connection/function test must name role and host. |
| External display/HDMI and external audio | No attached-output functional evidence | Later accessory session: connector hotplug/mode inventory and user-confirmed picture/orientation, then separate audio if exposed. Record cable/display and return to internal display. |
| Battery, charging and indicators | One battery snapshot: discharging, 83%, 3959000 microvolts; USB supply not present | Preserve raw units and timestamps. Later compare bounded unplugged/plugged observations and user-visible indicator state with known charger/cable. No endurance, capacity-accuracy or full-charge claim from one reading. |
| RTC/time | rtc0 enumerated; clock unset | Record clock validity and monotonic duration. Future retention check needs known initial time and a separate boot; no wall-clock ordering assumptions. |
| Thermal/performance reliability | Short graphics run only | Read available temperature/frequency telemetry during bounded workload; separately plan repeated boot or longer stability sessions. No overheating/battery stress, governor changes or invented sensor values. |
| Orderly shutdown and suspend/resume | Completion file requests poweroff; no proof it completed | User observation of shutdown is separate evidence. Suspend/resume, wake sources and full power lifecycle remain deferred; do not press excluded buttons or silently add suspend. |

Peripheral rows are coverage candidates, not assertions that every role or
feature is wired or supported by this kernel. Report unknown applicability until
inventory or explicit product evidence establishes it. Do not demand accessories
for the core handheld session.

## Staged execution

1. **Offline evidence now:** ingest existing logs, keep original files and
   provenance, derive conservative scoped findings. Record malformed/missing
   evidence explicitly. No card writes or handheld runtime changes are needed.
2. **Next normal diagnostic 3 boot:** validate the 18 allowed digital controls,
   four axes, diagram/prompt legibility, retry behavior, remaining-time display,
   optional graphics/rumble/audio/jack checks, and partial-result saving. Keep
   the existing eight-minute guided bound and overall service shutdown budget.
   Unanswered optional prompts skip cleanly. Do not expand this into a long
   radio/accessory session before its basic interface is physically validated.
3. **Inventory and radio investigation:** add bounded read-only collections
   with exit statuses and repeat-boot comparison, particularly for absent
   Bluetooth. Then run optional Wi-Fi and Bluetooth functional checks with
   explicit network/accessory selection. Preserve partial results on failure.
4. **Accessory and persistence session:** test known headphones, display,
   USB accessory and nominated secondary-card reads; verify repeat-boot report
   retention, unplugged/plugged telemetry and observed orderly shutdown.
5. **Reliability later:** bounded longer workloads, repeated boots and time
   retention with explicit scope. Suspend/power lifecycle require a separate
   plan; Start/Power/Reset remain excluded from this diagnostic contract.

Every phase ends with a readable partial-results summary. A timeout, missing
device, full report volume, unavailable command, lost events, disconnected input
or absent accessory must leave a reason and next action, not a false pass.

## Result-provider fields

Use a versioned envelope and a list of independently scoped checks:

- `schema_version`, `generator_version`, `generated_at_host`, `run_id`/`boot_id`,
  `diagnostic_revision`, `kernel_release`, source archive path and source hashes.
  Device/image identity may be unknown; do not substitute a guessed revision.
- `device_wall_time`, `clock_validity`, `uptime_start_s`, `uptime_end_s` and
  monotonic event times. Keep host extraction time distinct from device time.
- `check_id`, `subsystem`, `label`, `scope`, `applicability`, `presence`,
  `evidence_basis` (array), `outcome`, `execution`, `reason_code`, `summary`,
  `acceptance_criterion`, `next_action`, `prerequisites` and `exclusion_reason`.
- `procedure_version`, `attempt_id`, `device_identity` (name, bus/vendor/product,
  sysfs identity and observed path), command/operation, `exit_status`, timeout,
  start/end, and event validity. An event path alone is not stable identity.
- `measurements`: value, unit, raw value/range, threshold and threshold source.
  Preserve requested and logged frame counts independently; preserve advertised
  and observed axis ranges independently.
- `evidence`: relative file path, SHA-256, parser/version, line range or event
  IDs, evidence role and parse warnings. Resolve paths inside the archive;
  never follow untrusted report paths outside it.
- `user_observation`: exact prompt, answer (`yes`, `no`, `unsure`, `no_response`),
  optional comment, attempt and monotonic time. Inferred answers are forbidden.
- `artifacts`: expected/present/parsed status; checkpoint and mirror status,
  truncation/partial flags, write errors and source completeness.
- `related_checks` and `limitations`: pair a command result with a user
  observation without merging their meanings; record contradictions explicitly.

Use absent/null for unavailable measurements rather than zero. Retain raw logs
even when parsing fails. A retry is a new attempt; do not erase an earlier
failure. A later successful run does not rewrite historical evidence.
Redact credentials and offer redaction of SSIDs/MAC addresses for shared reports.

Recommended summary counts are eligible checks tested, passed, failed,
inconclusive, not tested and excluded, with the denominator defined. Separately
count user-confirmed checks and enumerated-only capabilities. Do not publish a
single "hardware health percentage" that treats enumeration as functionality.
The first screen should state what worked, what needs attention, what remains
unknown and one useful next step; raw evidence stays available for inspection.

## Boot collector considerations

The current diagnostic 3 collector saves many inventories using `|| true`, so
missing output can mean tool failure. Future collection should record each
command's exit status and timeout separately without aborting the entire run.
`save()` mirrors text files; the controller separately mirrors its JSON/JSONL.
The provider must verify both artifact groups rather than treating a successful
text copy as proof that controller evidence is mirrored. `completion.txt` must
remain described as a shutdown request. A log saved before poweroff cannot
certify the final shutdown path.
