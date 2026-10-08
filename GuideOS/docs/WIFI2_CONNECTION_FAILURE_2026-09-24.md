# Wi-Fi 2 returned connection failure

The owner reported that discovery and signal-strength display worked, but
connection failed despite entering the correct password. The displayed result
was "Connection failed or unavailable." The seed was returned to USB.

## Preserved evidence

The identified Transcend reader (Disk 4, serial 00000000TS38, 62,239,277,056 bytes)
was opened read-only. The boot/root/data layout matched the installed build.
A private 3,490,709,504-byte capture was preserved with SHA-256:

C77B1981D9DF75A1B570A635D5CA212E826A4637D1596583977BCA9BB86434FB

Inspection used a read-only loop device and ext4 mounts with journal replay
disabled. No seed write was performed. Raw journals and reports remain in private
recovery storage; credentials and network identifiers are excluded from the
[public diagnostic summary](../build/keyboard-0/wifi2-return-summary.json).

The physical boot was d5d61704-585e-40d6-a1b5-7a87d27f7f39,
build wifi2-20260924. The shell recorded an orderly shutdown request and no
cleanup errors.

## Findings

| Attempt | Start, seconds after boot | D-Bus error after start | Guide cancellation after start |
| --- | ---: | ---: | ---: |
| 1 | 33.356 | 0.302238 s | 0.595739 s |
| 2 | 72.620 | 0.302134 s | 0.614596 s |
| 3 | 89.644 | 0.302755 s | 0.622147 s |
| 4 | 108.224 | 0.302123 s | 0.615997 s |

All four were initial connection attempts with approximately thirty seconds
available. None used the five-second switching policy or reached its overall
connection deadline.

NetworkManager was preparing the radio, including resetting its scanning MAC
address, when Guide reported the D-Bus exception. Preparation took roughly half
a second. NetworkManager then confirmed that credentials were present, but
Guide's cleanup requested disconnection during configuration. The kernel recorded
authentication being aborted locally with reason 3, DEAUTH_LEAVING.
NetworkManager's "user-requested" reason here describes Guide's Disconnect call;
it is not evidence that the person pressed Disconnect.

This establishes premature cancellation by Guide before authentication and DHCP
completed. The implementation's universal 300 ms per-call timeout is strongly
implicated by the repeatable 302 ms error timing. The old log records only
DBusException, so its exact error name and failed method cannot be recovered.
There is no completed password rejection in this evidence; password correctness
also cannot be independently established from an interrupted authentication.

A separate source fixture found that ActiveAccessPoint was incorrectly treated
as proof of connection, even during IP configuration. That status defect could
shorten later retries by misclassifying them as switches, but the four physical
attempts above were all correctly classified as initial connections.

## Correction and acceptance

The local correction now preserves the operation deadline while allowing replies
up to two seconds, retries temporary observation failures without restarting
authentication, tracks uncertain activation outcomes for bounded cleanup, and
reports connected only after activation and address assignment. Diagnostics retain
state/reason numbers and known error names without credentials. Initial connection
and switching budgets are unchanged. Unconfirmed cleanup stops retrying after
eight seconds and leaves a visible result with automatic reconnection held.
Explicit Disconnect applies to the whole device; cancelling an individual
attempt preserves unrelated connections. Shutdown gets one bounded cleanup pass.

Validation passed 47 ARM64 connectivity tests (42 service, 5 discovery), in
addition to the keyboard/shell revision's 84 ARM64 tests. The
[connectivity validation record](../build/keyboard-0/wifi-regression-validation.json)
contains source and log hashes. The
[private D-Bus probe](../build/keyboard-0/wifi-dbus-result.json) exercised real
D-Bus transport with a delayed fixture, using the production Backend and Controller:

- A 600 ms property reply failed under the former 300 ms limit at 0.304 seconds.
- Three delayed property reads completed under the corrected code in 1.821
  seconds, producing connected state without Disconnect, Deactivate or Delete.
- A remaining 200 ms operation deadline still timed out at 0.201 seconds.

The fixture supplies activated/address-ready properties. It verifies delayed
transport handling, not real radio authentication or DHCP.

Source and ARM64 regression results belong with the new candidate, not the
issued Wi-Fi 2 validation. The shared keyboard revision uses the earlier
prototype appearance and the [text-entry contract](../TEXT_ENTRY_0.md).
Successful physical connection, credential persistence, reconnection, and
two-network switching remain unproven. A new Deck test is required after a
corrected candidate is installed.
