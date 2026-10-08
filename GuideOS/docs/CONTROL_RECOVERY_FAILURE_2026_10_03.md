# Recovery failure after the frozen Browser keyboard

The owner reported a frozen native keyboard on installed 0.4.3.03, then a
guide-deck console login with no gamepad response after using recovery.
Private evidence is preserved in `inspect-20261003-094532.json` and
`full-capture-20261003-094550.zip` under the owner-private live-link directory.

Browser stopped at approximately 1672 seconds since boot. Home was then killed
and stopped at 1672.954 seconds. Diagnostics recorded CONTROL_ERROR at 1672.96
and CONTROL_CLOSE at 1673.15; there was no subsequent Home start. Control,
resource protection, deployment and Wi-Fi services remained alive, with about
666 MiB available. The recorded resource counters showed no OOM kill. The
owner used an orderly Power shutdown and rebooted; installed 0.4.3.04 and Home
readiness were confirmed after local update approval.

The code explains the missing Home restart: a force-close exception had no
specific handler. Once Home was gone, drawing the overlay automatically invoked
ordinary resume, which restored the original console without starting Home.
The event omitted the exception, so its initiating cause is unresolved. A
check-then-read race during cgroup removal is a plausible cause, not a captured
fact. Earlier keyboard captures also showed periodic Browser timers continuing
while memory-high events remained stable; they do not establish a memory leak.

## Source repair and validation

Recovery completion checks now pin the group directory and read its events
relative to that descriptor. A removed original group counts as exited;
replacement identity or missing evidence in a still-present group fails closed.
Force-close errors keep the resident overlay and controls available, block
ordinary resume, and retain the original application records for a deliberate
retry. A successful retry follows the existing verified-close, display-return,
Home-start ordering. Failed-step, exception-class and errno diagnostics use a
fixed vocabulary and exclude raw exception text and paths.

The resource, control/recovery, diagnostics and status-bar suites passed all 59
tests under unprivileged WSL/Linux on 3 October 2026. Tests include removal
between opening the group and reading events, rejected replacement/missing
evidence, a failed force-close after Home exits, retry target retention and
successful Home return. These are source checks, not physical recovery proof.

The pending-update glyph is also prepared for the next app update: its overall
height is 15 pixels instead of 18 (the closest whole-pixel reduction to 15%),
and the upper stroke and lower dot are both four pixels wide. Its placement
remains immediately left of Wi-Fi.

## Delivery boundary

0.4.3.04 remains the immutable signed Browser keyboard update and sole rollback
version. Its app payload does not include these later resident-service changes.
The returned Seed was freshly captured and expanded for 0.4.3.05; the resident
control/resource/diagnostic repairs and smaller pending-update icon are now
installed with full-root readback verified. The offline maintenance and evidence
are recorded in [BUILD_0_4_3_05.md](BUILD_0_4_3_05.md). Browser is paused and its
exclusive runtime dependencies are removed. Boot and physical acceptance of
the repaired recovery path remain pending; source and ARM64 image checks do
not prove on-device display return or Home restart.
