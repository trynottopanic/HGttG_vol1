# Wi-Fi connections 2 installation

Build `wifi2-20260924` was installed on 24 September 2026 at 21:21 EDT
(25 September 01:21:26 UTC). Full system-partition readback passed. Physical
connection, reconnection and switching acceptance are still pending.

## Contents and ownership

The [feature contract and physical check](../WIFI_CONNECTIONS_2.md) describe local
Connect/Disconnect/Forget controls, masked password entry, saved profiles,
five-minute-or-longer reconnection checks, cached strength monitoring and the
five-second switching attempt budget. Router authentication/address assignment
can cause a timeout; successful switching within five seconds is not established.

`guide-wifi.service` owns background policy independently of the shell page.
NetworkManager owns link/IP configuration and persistent credentials. The shell
retains display/input ownership; systemd retains the physical Power path.
The existing kernel, boot partition and data partition were preserved.

## Verified evidence

- 58 tests executed in the ARM64 Debian root: 20 existing shell, 11 panel/input/IPC,
  22 policy/identity/recovery, and 5 discovery tests.
- Two final 512 MB ARM64 virtual boots passed against the final candidate code.
  Actual NetworkManager D-Bus profile creation, saving, secret retrieval, keyfile
  permissions and deletion passed. Only disposable fixture credentials were used.
- The real provider's Unix-socket interface, absent-adapter result, persistent
  manual hold across restart, and prompt shutdown from an idle wait passed.
- Service definitions, package consistency, filesystem checks, installed source
  comparison and persistent journal checks passed. The new screens were rendered
  and inspected; that does not establish physical framebuffer behavior.
- Compatibility packaging helpers were updated to include the new panel module;
  their shell syntax passed. Older historical images were not rebuilt.

The guest substitutes AP/activation responses for its profile-storage exercise.
It has no Wi-Fi adapter. Neither that exercise nor the policy model tests establish
radio association, DHCP timing, battery savings or two-access-point switching.

## Installation identity

Target: Transcend TS-RDF5 USB reader, serial `00000000TS38`, Windows Disk 4,
62,239,277,056 bytes. The writer rechecked identity, partition offsets and all
preserved-region hashes before writing.

Only partition 2 was replaced: offset 135,266,304, length 2,147,483,648 bytes.
Candidate and full raw readback SHA-256:

`E9329D6774F02D0DE2325A1827BBA59801593CC3C4C2585F64ABE608BBCC20D4`

The matching prewrite recovery capture remains in private recovery storage; its
whole-capture SHA-256 is
`6DFAF1016C339C32F4F8362FA9BA2E6B8119FABA325C69953151C042658267C8`.
Boot-prefix and data-partition hashes matched before and after installation.

Machine-readable records: [validation](../build/debian-wifi-2/validation.json),
[installation](../build/debian-wifi-2/installation.json), and
[write transcript](../build/debian-wifi-2/seed-install.txt).

## Returned physical result

The owner performed this run and returned the seed. Discovery and signal display
worked, but connection failed. Four attempts were cancelled by Guide following
D-Bus exceptions approximately 302 ms after each start, before authentication
completed. See the [failure analysis](WIFI2_CONNECTION_FAILURE_2026-09-24.md).
The installed image and original validation records remain preserved.

## Acceptance still required after correction

Boot the Deck, open **Wi-Fi**, select **Rescan nearby networks**, then choose
**the wifi** and **Connect**. Enter the password on the Deck. Confirm it becomes
connected/saved, disconnect it, and reconnect from the saved entry. A deliberate
Disconnect must remain in effect after five minutes and across reboot until
Connect is selected. After an ordinary connected shutdown/reboot, automatic
reconnection starts no sooner than five minutes after provider startup.

Use the longer physical check in the feature document when convenient. Return the
seed after an orderly shutdown for log analysis. Two-network switching remains
deferred because only one test network is currently available.
