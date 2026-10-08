# Nearby and network tools

Owner direction, 6 October 2026: implement Wi-Fi survey, Bluetooth explorer and
signal watch, and add Nmap and other network investigation tools.

The new **Settings / Nearby** entry opens Wi-Fi survey, Bluetooth explorer and
Network tools. Wi-Fi observations preserve each access point's address instead
of collapsing a shared network name. They show advertised security, channel,
frequency, signal and the age of the last sighting. Bluetooth exposes available
names, addresses, device class/appearance, paired/connected state, advertised
services, manufacturer IDs and optional RSSI. It includes cached observations,
explicitly labelled when a fresh sighting is unavailable. A separate action can
enable Bluetooth before discovery; it does not make the Deck discoverable.

Inspecting an observation does not join, pair, trust, disconnect, or probe it.
Signal watch runs for sixty seconds, stores at most sixty readings, and preserves
gaps. Wi-Fi scan requests are spaced ten seconds apart during watch; cached
strength is not promoted to a fresh reading. Bluetooth freshness comes from
BlueZ observation signals. Signal strength is not converted into distance.

Network tools offer an editable IP address/DNS target and an explicit Run action:

- Nmap TCP connect scans of fifty common ports, optionally with light service
  identification. Service names/versions are reported evidence, not a vulnerability
  finding. IP targets are literal single IPv4/IPv6 addresses in this first UI.
- Ping, DNS lookup (including reverse lookup for IP targets), and route tracing
  limited to eight hops.

Nmap, ping, tracepath and dig run as unprivileged children; no shell command is
constructed from input. Jobs have operation/output bounds, retain visible
results, and can be cancelled. B returns one level; Menu leaves the Nearby page.
Leaving cancels the job. A missing UI heartbeat cancels work after five seconds.
Replacing a survey with signal watch releases the old discovery session first.
Other clients' Bluetooth discovery sessions are retained.

## Ownership and installation

`guide_nearby.py` is a system connectivity provider. The shell owns presentation,
text entry, semantic targets, focus and global controls. The current prototype
uses the existing Wi-Fi adapter pattern: root-owned private runtime files and
a credential-checked Unix datagram control socket. This is not a claim that the
full shared capability/job protocol is complete. Application workers cannot gain
these powers merely by declaring them. A future public application provider must
use the shared authorization/lifecycle contracts.

The service permits one job, eight tasks, 96 MiB memory and 25% of one CPU, at
nice 10. Its capability set permits dropping child identity and cancelling those
children (SETUID, SETGID, KILL), without raw-packet capabilities. Radio work stays
outside the shell thread. Observation rows, history and
tool output are bounded. The native install footprint consists of Nmap, its data
and dependencies, iputils-ping, iputils-tracepath and bind9-dnsutils. No changes
are made to saved Wi-Fi credentials, Bluetooth trust or Planegotchi world format.
The image installer is `package/guide-connectivity/install-nearby.sh`.

Wireless monitor-mode capture, packet injection, credential testing and a larger
exploit suite are not implemented by this first toolset. Monitor/injection
support has not been measured on the actual Deck adapter. The native Nmap binary
is present independently of the first Guide UI presets.

Focused checks exercise target parsing, actual child cancellation, replacement
and orphan cancellation, stale observations, graph/control regions, editor
cancellation and real shell D-pad/A/B/Home dispatch. Native image tool versions
and a loopback-only Nmap fixture establish the added ARM dependency boundary;
radio behavior and physical UI remain Deck retest items.

Deployment: 0.4.4.03, signed sequence 75, was written to the Seed's system
partition and fully read back on 6 October 2026 (receipt time
2026-10-07T02:17:11Z). The current root matched the verified .02 base before
writing. The separate data partition was outside the writer's bounds and was
not scanned. See `../build/release-0.4.4.03/installation.json` and
`../build/release-0.4.4.03/START_HERE.md`. Boot and actual radio/UI behavior
remain unverified until the Deck retest.
