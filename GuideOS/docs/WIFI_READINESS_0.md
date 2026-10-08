# Wi-Fi readiness evidence

22 September 2026. Read-only investigation before the physical transfer test.

## Established

The last validated Debian diagnostic 4 staging root contains Wi-Fi support but
has no configured network connection in the standard locations inspected:

- `/etc/wpa_supplicant` contains only helper scripts; no network profile.
- `/etc/wpa_supplicant.conf` does not exist.
- `/etc/systemd/network` and `/etc/network` contain no configuration files.
- NetworkManager's system-connections directory and the inspected iwd
  configuration/state directories do not exist.
- The generic wpa_supplicant service is enabled; no interface-specific supplicant
  or network manager configuration was found.

Staging root: `/home/hacker/guideos-work/debian-diagnostic-4/rootfs`.

The archived physical boot's dmesg records the Realtek rtw88_8821cs driver loading
firmware version 24.11.0. Its journal records successful initialization of the
generic wpa_supplicant service. Neither service startup nor reaching network.target
establishes connection to an access point. No successful association or DHCP
address assignment was found in these logs.

Evidence archive: `build/debian-diagnostic-4/hardware-tests/2026-09-22-022635`,
boot `40d0b767-26f0-43c6-b578-ac09008f9444`.

The boot also reports a malformed or unsigned regulatory.db. This is a separate
warning to investigate during network bring-up; these logs do not establish it
as a connection failure cause.

## Initial physical limit

Windows detects the TS-RDF5 SD Transcend reader, serial 00000000TS38, as Disk 4,
but reports Size 0 and OperationalStatus No Media. H: is absent. Current seed
contents therefore could not be read and must not be equated with the staged
image. No seed changes were made during this investigation.

Reinsert or reseat the seed to inspect its current configuration. The staged
build needs network setup before a LAN transfer test. Confirm association,
address assignment and reachability to the explicitly selected PC fixture before
claiming readiness. A successful transfer still does not establish video playback.

## Connected-card verification

Later on 22 September, the reader reported Online with the expected
62,239,277,056-byte seed. The verified root partition (offset 135,266,304,
length 2,147,483,648 bytes) was copied through a read-only device handle to
private recovery storage. The copy was mounted read-only with journal replay
disabled and unmounted after inspection. No card writes were performed.

The current root has no saved Wi-Fi profiles in the locations above, nor in
`/etc/netplan`; no NetworkManager, iwd or DHCP state directories were present.
The generic supplicant remains enabled, but no interface-specific connection
service was found. The current enabled Guide service is guide-shell.service,
so this card must not be described as identical to the older diagnostic archive.

Snapshot SHA-256:
`5F258056BDA054AED7B97B89EBCE10ABED4F5E605B470F83D1DBC1E6FF245997`.

Current conclusion: network setup is needed. The earlier No Media obstruction
is resolved; successful wireless association and LAN reachability still require
configuration and an actual Deck boot.

The owner then narrowed implementation to discovery only. NetworkManager and
the Guide Wi-Fi discovery page were installed with verified root-partition
readback. After the reported boot failure, that image was preserved and the
previous shell root was restored on 23 September. See
[Wi-Fi discovery 0](../WIFI_DISCOVERY_0.md) and the
[24 September audit](SYSTEM_AUDIT_2026-09-24.md). No network profile was created
or installed. Joining a network and the transfer test remain deferred.
