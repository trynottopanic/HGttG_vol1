# Wi-Fi status indicator

Installation update, 26 September 2026: included in the combined Field Theme seed
write and fully readback-verified. Physical acceptance remains pending. See
[installation evidence](FIELD_THEME_IMPLEMENTATION_1.md). Earlier staging evidence follows.

Status: implemented and staged; not installed or physically verified.

Owner request: a small indication beside Wi-Fi of network connection and relative
strength. The shared shell/diagnostic status strip reads the existing Wi-Fi
provider snapshot once per second. It does not scan, connect, change radio policy,
or introduce an IPC/broker interface.

A green check marks a confirmed network connection; a cross marks disconnected,
blocked or disabled service status. Four bars show the connected access point's
reported 0-100 strength, with thresholds 1, 25, 50 and 75. Nearby networks never
supply the displayed strength. A connected network with no usable signal reading
keeps its check and shows `--`. Missing, malformed, failed or more-than-15-second-old
provider status shows `?` and empty bars. Radio ON/OFF and network connection remain
separate indications. Connection does not imply verified internet access.

The provider's existing refresh cadence bounds observation latency; the display
cannot detect a change before the provider reports it. The permanent status strip
and transient volume behavior retain their existing ownership.

Validation: the affected 108-test shell and 9-test control suites passed. The
cumulative candidate record includes 415 passing regression tests across all
suites, with unchanged-suite results retained from earlier work. Packaged renders
cover weak, medium, strong, disconnected, unknown signal and missing provider;
strong and disconnected status-strip screenshots were visually inspected.

Candidate: build/volume-overlay/guide-volume-overlay-root.ext4. It also contains
external-card recognition, the fading volume bar and the outlined mouse pointer.
Rebase onto a fresh seed capture before installation.
