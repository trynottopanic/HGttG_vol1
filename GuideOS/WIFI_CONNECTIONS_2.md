# Wi-Fi connections 2 — Debian implementation

Owner request, 24 September 2026: connect/disconnect, remember networks and
credentials, low-power background reconnection no more often than five minutes,
nearby signal monitoring, and switching within five seconds. The owner explicitly
selected persistent manual disconnection until Connect is chosen again.

The installed Wi-Fi 2 image failed its first physical connection run; discovery
and signal display worked. The
[returned failure analysis](docs/WIFI2_CONNECTION_FAILURE_2026-09-24.md) records
premature cancellation during radio preparation. Current source includes the
local correction and [shared prototype-style keyboard](TEXT_ENTRY_0.md);
these changes are not yet installed or physically accepted.

## Responsibility and behavior

`guide-wifi.service` is a shared system provider above NetworkManager. The shell
owns presentation and ordinary controls; NetworkManager owns authentication, IP
configuration and credential storage. systemd retains process/shutdown ownership.
Leaving the Wi-Fi page does not drop an established connection or stop the provider.
This is a bounded implementation of the shared-provider boundary in
`MODERN_FOUNDATION_0.md`, not a completed general capability/grant API. AT Field
settings do not choose an SSID or authorize incoming application access.

- Open **Wi-Fi**, select **Rescan nearby networks**, then select a network.
- Connect uses saved credentials or opens a masked on-Deck keyboard. CASE and
  MORE expose upper/lower case and punctuation; SPACE and DELETE are explicit.
  D-pad moves, A selects, B cancels, Menu returns home. Reading/typing is untimed.
- Open networks and WPA2/WPA3 Personal are supported. The first keyboard accepts
  8–63 printable ASCII password characters. Enterprise, WEP, WPA1, hidden SSIDs,
  raw hexadecimal PSKs and non-ASCII passwords need a later configuration path;
  they are not silently treated as open networks.
- Initial authentication/address assignment has a 30-second budget. **Connected**
  requires an activated link with an IPv4 address; it does not claim internet access.
- A manual switch starts against an already discovered target, with no preliminary
  rescan. It has a five-second outcome budget including cancellation and UI update.
  Slow authentication/DHCP produces a timeout, not a false success. A failed switch
  may leave the Deck disconnected; select a saved network to reconnect. This is
  best-effort timing on ordinary Linux, not a hard real-time or access-point guarantee.
- Disconnect persists an auto-reconnect hold across reboots. Connect clears it.
  Forget has a confirmation screen and removes the selected saved credentials;
  forgetting the active network also disconnects it and sets the hold.
- Background discovery/connection attempts start no sooner than five minutes
  after startup or the preceding manual discovery/connection. Repeated absent
  networks increase intervals to 10, 20 and 30 minutes. Battery below 20% increases
  the minimum to 15 minutes. No scheduled attempt replaces an existing connection.
- Signal monitoring reads NetworkManager's cached strength every ten seconds,
  without internet pings or a scan for each display update. Rescan explicitly
  refreshes sightings. Saved networks not seen recently remain listed out of range.
  NetworkManager/driver link maintenance and native scan behavior are separate
  from Guide's scheduled reconnection checks; this is not proof of total radio duty
  cycle or measured battery savings.

## Persistence and recovery

Network identities use raw SSID bytes and authentication family, so identical
display names do not conflate an open and secured network. A selected access point
is revalidated before activation. Guide profiles have native autoconnect disabled;
the Guide provider decides when to reconnect. Wi-Fi power saving is requested.

New profiles initially live in NetworkManager memory and are saved only after
activation/address assignment succeeds. Credentials reside in root-only
NetworkManager keyfiles on the current writable Debian root. They are not encrypted
against physical card access. The persistent manual-disconnect flag is atomically
saved under `/var/lib/guideos-wifi`; runtime status and a root-only local control
socket live under `/run/guideos-wifi`. No network listener is added.

Passwords are neither command-line arguments nor Guide diagnostic fields. Wi-Fi
key/cursor events are excluded from shell reports to prevent reconstruction of
typed passwords. Core dumps are disabled for the shell and provider. Python clears
references after submission/cancellation; this is not guaranteed memory erasure.
NetworkManager's system journal may contain network identifiers and must remain
private. Credentials must never be copied into shared build evidence.
The provider records operation starts, deadlines and results with monotonic times,
without network names or credentials. Idle polling sleeps for up to ten seconds;
a signal wakeup pipe lets shutdown interrupt that sleep immediately.

Cancellation stops pending activation. A failed cleanup is shown and retried, not
reported as a successful disconnection. Startup recovery removes abandoned unsaved
Guide profiles and cancels incomplete Guide activations. Existing saved active links
survive an ordinary provider restart. Saving failure is visible separately from
connection success.

## Acceptance and evidence

Source/model tests cover timing floors, backoff, manual hold, credential privacy,
identity distinctions, cancellation, failed saving, keyboard reachability and IPC.
Image and real NetworkManager checks, then physical results, are recorded separately
under `build/debian-wifi-2`. No physical result is implied by these source claims.

Physical check with the currently available network:

1. Rescan, select the network, enter its password locally, and connect. Confirm an
   address is obtained, the network is marked connected/saved, and navigation works.
2. Disconnect. Wait over five minutes; confirm it remains disconnected.
3. Select that saved network and reconnect without typing the password again.
4. Shut down safely and reboot. After at least five minutes, check automatic
   reconnection. Inspect returned logs/status without disclosing credentials.
5. If possible, make the access point temporarily unavailable and later restore it;
   verify delayed reconnection and signal changes. This interrupts that network.

Two-network switching, slow authentication/DHCP, radio recovery, actual timing and
battery consumption require later physical tests. The owner has only one source
available, so multi-network physical acceptance remains explicitly open.

API references: [NetworkManager profile persistence](https://networkmanager.dev/docs/api/latest/gdbus-org.freedesktop.NetworkManager.Settings.Connection.html),
[active connection state](https://networkmanager.dev/docs/api/latest/gdbus-org.freedesktop.NetworkManager.Connection.Active.html),
[Wi-Fi power saving](https://networkmanager.dev/docs/api/latest/settings-802-11-wireless.html).
