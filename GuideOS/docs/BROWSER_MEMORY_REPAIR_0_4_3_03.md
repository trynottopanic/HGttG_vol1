# Browser memory repair and pending-update icon, 0.4.3.03

## Changes and ownership

The captured 0.4.3.02 Browser startup and Google-only load exhausted the usable
session budget before image search or a second keyboard activation. No leak
was established. The source repair targets avoidable rendering/cache overhead:

- Browser's GTK toolbar and native-keyboard scene uses Cairo rather than a
  separate default GPU renderer. Weston and WebKit page acceleration remain
  unchanged. This is Browser-local, not a global graphics policy.
- A dedicated WebKit context uses DOCUMENT_BROWSER rather than WEB_BROWSER
  caching, retaining navigation while reducing cache assumptions for one view.
- WebKit page and network memory-pressure handlers use a 256 MiB reference
  limit, conservative cleanup at 128 MiB, strict cleanup at 192 MiB and a
  two-second polling interval. These are internal reclaim settings, not a hard
  cap or new process-kill policy. WebKit's default disabled kill threshold is
  preserved. The whole-application 320/384 MiB guard and swap limit are unchanged.
- Address-free phase markers record toolkit import, WebView creation, window
  presentation, keyboard initialization/closure and navigation start/finish.
  Periodic samples include process PSS/private/shared memory, swap and session
  cgroup charges/statistics. Descendant enumeration is capped at 24 processes
  and a 50 ms scheduling budget; inaccessible/raced process readings are omitted.
  No page addresses, keyboard text or command lines are recorded.
- The pending update banner is replaced with a small exclamation glyph in the
  status bar, immediately left of Wi-Fi. Validated/queued updates remain visible
  until their state changes; Home A is no longer intercepted to dismiss a notice.
  Both software and layered status rendering reflect the icon.

This serves the documented bounded application/resource/recovery contracts.
No memory-limit increase, shared-compositor migration or component suspension
is introduced. Native text-entry and the installed Planegotchi/input/assets are
preserved by byte-level comparison against the signed installed payload.

## Validation and limits

Linux/WebKit runtime checks passed: original/adapted display modes, navigation,
native address cancellation, literal form/password/multiline insertion, download
handoff, packaged Weston/frontend integration and child cleanup. Metrics,
Browser, native keyboard, resource, control and board-diagnostic suites passed.

A same-page host comparison measured main-process PSS of approximately 256 MiB
with GTK GL versus 115 MiB with Cairo at page finish. This host uses a virtual
display/software graphics path. It identifies a substantial renderer cost in
that fixture; it does not establish the amount saved on the Deck. Physical
Google/keyboard/search acceptance remains required after installation.

The shell suite ran 212 tests with 35 failures and 31 errors, all existing
baseline identities. There are no new failures. The changed pending-update
tests and status-bar rendering checks pass; the legacy suite is not wholly fixed.

The Browser-specific journal filter was also corrected in bootstrap source,
using explicit field-match OR terms. The real host journal parser accepts the
new query, and board-diagnostic tests pass. This bootstrap file is outside the
immutable UI payload and is NOT delivered by this update. The complete boot
journal remains the retrieval path for the new Browser phase samples.

## Delivery and acceptance

Signed sequence 67 accepts installed sequence 66. The 26,900,881-byte package
was delivered over paired Wi-Fi and validated on 3 October 2026. The owner installed the update, and paired status confirmed committed 0.4.3.03.
The update
protocol requires a local owner action; remote activation is not permitted.
Installation is confirmed; complete physical repair acceptance remains open.

After installation, repeat blank/address-screen startup, Google load, native
page-keyboard opening and earth search while recording. Verify a lower stable
startup cost, usable navigation/input, reduced reclaim pressure, continued
system responsiveness and recovery protection. A heavy page may still require
containment; source/runtime checks cannot promise arbitrary websites fit.

Artifacts: build/release-0.4.3.03/candidate.json, source-tests.json,
GuideOS-0.4.3.03-browser-memory.guide-release and update-icon-preview.png.
Private device delivery receipts remain under private-recovery/live-link.

## Physical follow-up

The owner installed 0.4.3.03 and repeated startup and Google load. The main
process settled near 177 MiB RSS / 111 MiB PSS. Creating the WebKit view raised
PSS from 27.3 MiB to 99.2 MiB; opening the initial native keyboard raised it
from 102.6 MiB to 106.0 MiB. Thus the dominant startup allocation is WebKit view
initialization, not native keyboard creation.

Google loaded and the session remained running at roughly 300-310 MiB charged
memory with its swap allowance filled. The owner then opened a keyboard and
reported that it froze while trying to back out. Periodic Browser event-loop
samples continued; memory.high stopped increasing at 2,911. No new safeguard
closure or OOM was recorded at that point.

Review identified unconditional keyboard rendering on unchanged stick snapshots,
queue overflow dropping buttons, and an ambiguous timeout retry capable of
replaying an edit. The 0.4.3.04 follow-up fixes those input paths and extends the
metrics enumeration from main-thread children to actual slice membership.
Capture: full-capture-20261003-093811.zip under private-recovery/live-link.
