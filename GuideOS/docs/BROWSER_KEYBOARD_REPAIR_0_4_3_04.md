# Browser keyboard follow-up, 0.4.3.04

The 0.4.3.03 physical capture narrowed the startup cost to WebKit view creation.
Google remained running within the unchanged session limits, but the owner
reported a frozen native keyboard while trying to back out. The Browser event
loop continued to emit periodic samples and memory-pressure events stopped
increasing. This was not a recorded new OOM or safeguard shutdown.

Source review identified three concrete input defects: unchanged stick snapshots
unconditionally rerendered the complete keyboard; overflow discarded queued
buttons; a timed-out request could replay a successfully applied edit.

The follow-up renders only when the keyboard model changes, suppresses repeated
identical neutral stick snapshots while retaining hold/release transitions, gives
owner Cancel priority over queued edits, and attaches monotonically increasing
packet sequences so ambiguous retries cannot insert twice. Focus tokens still
prevent stale input from affecting a new field. The metrics sampler now uses
bounded cgroup membership enumeration because WebKit may spawn outside the main
thread's direct child list; unavailable process readings are explicit.

Real Linux/WebKit tests exercised 100 neutral snapshots without a redraw and
retried a character packet without duplicate insertion. Native form/password/
multiline entry, address cancellation, transfers, the packaged Weston session
and cleanup still pass. Resource/control/Browser/native-keyboard/metrics/
board-diagnostic suites pass. The 212-test shell suite has 35 failures and
31 errors, all known baseline identities; there are no new failures.

Sequence 68 accepts installed sequence 67. The signed 26,902,901-byte package
was delivered over paired Wi-Fi and validated on 3 October 2026. Local approval
in Settings -> Updates is required by the Deck protocol. Close Browser before
installation, using the resident Start + Select recovery overlay if ordinary
controls are unresponsive. No remote activation bypass or Seed write was used.

The 0.4.3.03 renderer/cache changes, status-bar pending-update icon, native keyboard,
Planegotchi and input/assets are retained. Containment limits are unchanged.
The bootstrap journal query correction remains source-only; capture the full boot
journal for the allocation markers.

Physical acceptance remains open: repeat Google load, X keyboard opening,
navigation/text insertion, B cancellation and earth search while recording.
The new source tests do not establish that the frozen-input behavior is fixed
on the Deck. Current installed 0.4.3.03 evidence and this staged 0.4.3.04 candidate
remain separate.

Artifacts: build/release-0.4.3.04/candidate.json, source-tests.json and
GuideOS-0.4.3.04-browser-memory.guide-release.

## Installed evidence, 3 October 2026

After the owner rebooted and locally approved the update, paired inspection at
13:50:48 UTC confirmed version 0.4.3.04, sequence 68, the expected active archive
hash `887c68ba8cdf962fb51ce8e5564f9ba3487e6a729bcbc800b16e29bcaf8b88d0`, and Home
ready with PID 520. The private inspection is `inspect-20261003-095038.json`;
the post-install capture is `full-capture-20261003-095121.zip`.
Installation is confirmed; Google keyboard and search acceptance remains open.
The resident recovery failure and its source repair are documented separately
in `CONTROL_RECOVERY_FAILURE_2026_10_03.md`.
