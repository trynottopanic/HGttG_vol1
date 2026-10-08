# Transient volume display

Installation update, 26 September 2026: included in the combined Field Theme seed
write and fully readback-verified. Physical acceptance remains pending. See
[installation evidence](FIELD_THEME_IMPLEMENTATION_1.md). Earlier staging evidence follows.

Status: implemented and staged; 410 regression tests passed. Not installed.

Owner request: show volume adjustments as a transparent bar on the left with the
level out of 100, fading quickly. The existing shell-owned status chrome observes
the audio service's confirmed volume; it does not change audio authority, routing,
volume commands, the common IPC design or broker contracts.

A 76 by 252 pixel translucent panel appears 10 pixels from the left edge, below
the permanent status strip. Its vertical fill and `N/100` label reflect the actual
reported value. It holds for 650 ms and fades over 450 ms, disappearing 1.1 seconds
after the last observed adjustment. A further change restarts that interval.
First observation and provider reconnection establish a baseline without a flash;
stale or invalid status clears the transient display. Pressing against an already
reached limit does not claim a level change.

The shared status reader checks at most ten times a second; hardware enumeration
remains every five seconds. Fade state alone requests redraws, including the final
clear frame. No animation timer requests redraws after disappearance. The shell
composites onto a clean background, including cached pointer-only redraws. The
resident diagnostic view uses the same rendering code and briefly increases its
redraw rate only while the transient display is visible; input ownership and its
existing volume-key behavior are unchanged.

Acceptance checks: confirmed adjustment, repeated changes, zero and maximum,
transparency, time-based disappearance, provider loss, silent startup, and exact
restoration of a cached screen. Rendered verification does not establish physical
latency or appearance on the handheld. The candidate includes the pending external
card work and preserves the preceding candidates for recovery.

Candidate: `build/volume-overlay/guide-volume-overlay-root.ext4`.
SHA256: `ADC6FE32F50D1F6E7194BB1CF80DA567750BD6E3A00798F3CA5824F23ACEFCD1`.
The installed ARM64 rendering dependency passed all transparency and fade tests.
Visible, fading, cleared, zero and maximum screen renders are in the same folder.
A Wi-Fi scan subprocess test failed on the first broader run, then the complete
103-test shell suite passed unchanged on rerun; the initial failure log is retained
as `first-run-shell0-failure.log`. No Wi-Fi implementation was changed.

Use this cumulative candidate for the next seed update after a fresh-state rebase.
It includes the pending external-card implementation. Physical display appearance
and latency remain unverified until installation.

The cumulative candidate also includes the owner-requested pointer appearance:
same 11-pixel circle, a 2-pixel opaque white outline and a black center at 25%
opacity (75% transparent). The click hotspot remains at its center. The existing
135-test input suite passed after this change, and the packaged screen was
rendered and inspected. This is presentation-only; pointer motion and actions
are unchanged.
