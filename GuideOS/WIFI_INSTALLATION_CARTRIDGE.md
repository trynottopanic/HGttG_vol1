# Wi-Fi Installation Cartridge — prototype plan

The first installation cartridge will add persistent onboard Wi-Fi support to
the Anbernic RG35XX H Deck. Success means the cartridge can be removed after
installation, the Deck can discover nearby networks, the user can select one
and enter its password locally, and GuideOS can reconnect after a safe reboot.

## Known hardware facts

- The onboard radio is connected through SDIO and is expected to be a Realtek
  RTL8821CS-family device.
- The temporary working image uses the vendor Linux 4.9.170 kernel.
- That kernel contains the cfg80211 wireless framework but the captured kernel
  does not expose an RTL8821CS driver marker.
- The open, mainline GuideOS target already enables the upstream `rtw88`
  RTL8821CS driver and its firmware; that does not make its module compatible
  with the temporary 4.9 kernel.
- The current userspace has DHCP and archive/hash tools but does not contain
  `iw` or `wpa_supplicant`.

## Diagnostic gate

The browser image records the following on physical boot before any driver is
selected:

- exact kernel release and architecture;
- network interfaces;
- SDIO device names, modaliases, and uevent data;
- currently loaded modules;
- whether `wlan0` already exists.

We will capture that log after the first browser boot. The SDIO identity and
kernel ABI determine which driver can be safely packaged.

## Intended package contents

The final `guide.prototype.wifi` cartridge is expected to contain:

- the exact kernel-compatible Wi-Fi module if the kernel requires one;
- redistributable RTL8821CS firmware with its license and source recorded;
- `iw` for discovery and radio information;
- `wpa_supplicant` for WPA2/WPA3 authentication as supported by the hardware;
- a minimal DHCP/client configuration using the existing BusyBox client;
- a declarative `GUIDE-INSTALL-PLAN-1` file;
- a rollback manifest;
- no saved network name or password.

## Persistent installation layout

The prototype currently has a writable root filesystem rather than the final
separate Guide data partition. The installer will therefore stage under
`/var/lib/guideos/install-staging`, back up every replaced path, verify the
staged hashes, synchronize storage, atomically activate the feature, and write
an installed-feature record. Safe shutdown remains available throughout.

The eventual production design will place mutable state and installation
records on the Guide data partition and keep the base system immutable.

## First executable installer

The Deck shell now contains a narrowly pinned installer for version 0.1.0.
It trusts neither the card index nor the package's self-declared identity on
their own: installation is offered only after ordinary cartridge verification
and an exact archive hash compiled into the trusted seed matches. A second
physical confirmation is required before any persistent write.

This milestone installs and activates the driver and command-line networking
tools. Network selection and password-entry screens remain the next Wi-Fi
interface milestone; no credentials are present in or disclosed to the
installation cartridge.

## Wi-Fi interface requirements

After installation, the main menu gains **Wi-Fi**. Its first interface will
provide:

- radio state and connection state;
- scan/rescan;
- a D-pad-selectable network list;
- signal-strength and security indicators;
- password entry without displaying the saved password;
- connect, disconnect, forget, and retry actions;
- explicit errors such as missing hardware, unsupported security, rejected
  password, and DHCP failure.

Network credentials stay on the Deck with owner-only file permissions. A
cartridge never receives them, and connection to a network grants no inbound
authority to the Deck.
