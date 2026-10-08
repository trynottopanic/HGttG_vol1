# Wi-Fi discovery 0

Current status, 24 September: the owner reported that this candidate did not
boot. Its previous root was restored with verified readback on 23 September.
The source and failed image remain preserved. A later full-system ARM virtual
boot starts NetworkManager and returns the expected no-adapter result; this
does not resolve physical boot or Wi-Fi acceptance. See the
[system audit](docs/SYSTEM_AUDIT_2026-09-24.md).

The subsequent [Wi-Fi discovery 1](WIFI_DISCOVERY_1.md) revision is now installed
with verified readback. It retains Shell 1's persistent diagnostics and fixes
the dense-response output-pipe issue. The owner skipped Shell 1's intermediate
physical test; the next test is discovery on the Deck.

22 September 2026. Owner narrowed the connection-service work to a basic discovery
tool. This slice lists nearby networks; it does not provision credentials, join a
network, implement transfers, or change AT Field policy.

## Behavior and ownership

The existing Debian Guide shell has a Wi-Fi Discovery page. Entering it starts a
scan; A rescans, D-pad scrolls, B returns, and Menu goes home. Rows show network
name, relative signal percentage and advertised security. Multiple access points
with the same display name/security show their strongest signal. Hidden networks
are labeled; malformed/control characters cannot become terminal control output.
Signal percentage is not a bandwidth or connectivity measurement.

NetworkManager and the existing wpa_supplicant provide the Linux implementation.
The discovery adapter only reads properties and requests scans over D-Bus. It
does not activate connections, modify saved profiles or switch radio power.
The owner interface retains system connectivity authority; this is not an
application-facing permission broker or a completed capability registry.

The shell runs each scan in an owned child process, outside its input loop. It
terminates that child on leaving the page or after a 15-second operation deadline.
There is no deadline for reading the screen. Previous/cached results are labeled;
radio off, hardware block, absent adapter, unavailable service and timeout are
distinct from a successful scan returning no networks. System Power remains
owned by logind. NetworkManager's wait-online unit is masked so offline networking
does not delay boot, and automatic internet probes are disabled for this slice.

## Evidence and limits

- Five adapter tests cover security labels, names, duplicate access points,
  absent/off/blocked hardware, and fresh versus cached results.
- Eight shell tests cover navigation, separate power confirmation, excluded Power
  ownership, scan cancellation navigation, bounded scrolling and child timeout.
- These 13 tests passed inside the ARM64 Debian userspace; systemd unit validation
  and package consistency checks passed. Generated 640x480 screens were inspected.
- The actual ARM64 NetworkManager aborted in its platform layer under QEMU in an
  isolated network namespace. That integration check failed. Its logs are in
  `build/debian-network-0/isolated-nm.log`; physical scanning remains unverified.
- NetworkManager and required dependencies added approximately 26 MB of installed
  storage to this Debian root. Running memory and scan latency require measurement.

The candidate was derived from a read-only copy of the current seed, which already
has guide-shell.service. Only the Linux root partition is targeted by the guarded
installer; boot metadata and the data partition are outside its write range. The
installer requires an exact current-root recovery hash and checks full readback.

## Physical acceptance

Installed on the verified seed on 22 September 2026. The installer first matched
the current root partition to its recovery copy, then wrote only that partition.
Full readback matched SHA-256
`D602925AD82C24B75CE89CAC301FDFACED5D5F3E6E59F2FB2A9DA1805CA8490F`.
See `build/debian-network-0/seed-install.txt`. The boot and data partitions were
not written. This is installation evidence; physical discovery remains pending.

Boot the Deck, open Wi-Fi Discovery, and check whether the expected local network
appears. Rescan, scroll if needed, and use B/Menu while scanning. Confirm these
actions remain responsive and a failed scan remains retryable. Shut down normally
and reconnect the seed for any failure investigation. This does not establish
association, a working IP connection or application network access.
