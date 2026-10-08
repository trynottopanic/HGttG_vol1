# Interface status bar and internet time

The shared interface reserves its top 28 pixels for battery charge, local time,
date (MM/DD/YY), Wi-Fi radio state, Bluetooth connection state and software
volume. The bar covers menus, text entry and the diagnostic overlay. Keyboard
keys remain in their existing positions. It does not cover the boot animation.

Status is checked once per second; battery and radio files are read once per
five seconds. No Wi-Fi discovery is triggered by the bar. Missing readings are
shown explicitly, and audio/Bluetooth readings older than twelve seconds become
unknown.

The Wi-Fi portion of the bar is icon-only: it must not display phrases such as
"Wi-Fi connected." Its three visible states are:

- Wi-Fi off: a Wi-Fi symbol with a simple diagonal slash.
- Wi-Fi on but not connected: an unfilled or outline Wi-Fi symbol.
- Wi-Fi connected: a colored, filled Wi-Fi symbol.

The distinct slash, outline, and filled forms carry the state in addition to
color. Detailed network names, failures, and connection controls remain in the
network interface, where they do not consume global status-bar space.

The staged Debian image includes systemd-timesyncd, enabled at boot, using the
Debian NTP pool. It can synchronize when an internet connection becomes
available. Neither boot nor the interface waits for successful synchronization,
and it does not enable Wi-Fi or override an intentional disconnect. Polling
adapts between 32 and 2048 seconds; the saved clock timestamp is updated hourly.
Local display uses America/New_York, matching the development PC, including
daylight-saving changes. A future timezone setting can replace this default.

An asterisk after the time means internet synchronization has not succeeded in
the current boot. It disappears when timesyncd creates its synchronization
marker. That marker records synchronization this boot, not current connectivity
or a guarantee of continued clock accuracy. Offline operation retains the best
available clock. Scheduling and duration measurements should use monotonic time
so correcting the calendar clock cannot distort them.

Validation: 90 shell tests, 135 input tests and 9 control tests passed in the
ARM64 Debian chroot. The timesyncd unit passed systemd configuration verification;
the home preview was visually checked. Candidate image:
`build/debian-statusbar-0/guide-statusbar0-root.ext4`. This is staged locally,
not written to the seed. Actual NTP synchronization, timezone display, battery,
radio and volume readings remain subject to physical acceptance. The previously
reported boot-artifact, silent-speaker and Bluetooth discovery issues remain
open in AUDIO_CONTROL_PHYSICAL_REVIEW_0.md.

Deployment update: the status bar and time service were subsequently included
in AUDIO_RECOVERY_1.md's verified seed installation. The initial statusbar-only
candidate above was not written separately. Physical synchronization and display
acceptance remain pending.
