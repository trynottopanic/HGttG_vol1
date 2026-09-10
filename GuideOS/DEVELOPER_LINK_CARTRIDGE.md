# Developer Link Installation Cartridge

The Developer Link cartridge installs an intentionally limited maintenance connection on the RG35XX H Deck prototype. It is for development and diagnosis, not ordinary day-to-day operation.

## User-visible behavior

- The connection never starts automatically.
- The user must turn it on from the Deck itself.
- It listens only on the Deck's current local Wi-Fi address, on port 2222.
- The Deck shows whether the link is off, unavailable, or active.
- Turning the link off ends the server process and removes its active marker.
- The trusted desktop key may use SSH commands and legacy SCP file transfer.
  Transfers land in an explicitly chosen staging path; they are not silently
  installed or executed.

## Security boundary

- Public-key authentication is required; passwords are disabled.
- The desktop's private key is never placed on the cartridge or committed to this repository.
- TCP forwarding, agent forwarding, X11 forwarding, compression, and remote root-password login are disabled.
- The Deck creates its own SSH host key on first use. A shared host identity is not distributed on the cartridge.
- The package and every installed file are accepted only when their exact SHA-256 hashes match the values compiled into the trusted Deck shell.
- Installation refuses to overwrite pre-existing system files and rolls back partial installation.
- Maintenance updates are staged, hashed, and installed atomically. Boot-critical
  files are updated from the removable seed while the Deck is off, not replaced
  through a running remote shell.

The trusted desktop already receives a root maintenance shell, so SCP increases
convenience rather than authority. SFTP, port forwarding, password login, remote
activation, and background auto-update remain disabled. Every future graphical
maintenance tool must preserve those boundaries and display the exact staged
artifact, destination, hash, and rollback point before installation.

The link grants a trusted key a root maintenance shell while it is active. That authority is deliberate for prototype development and must remain physically controlled, visible, and independently security-reviewed before this feature is considered suitable for general use.

## Diagnostic report

Once the link is active, `guide-diagnostics` prints one bounded, readable
snapshot covering the kernel, memory, storage, display, input devices, network
state, Wi-Fi driver, Bluetooth/audio route, battery, temperature, media codecs,
active Guide processes, the most recent player state, and recent system logs.

`guide-diagnostics --json` prints the same information in a machine-readable
form suitable for automated comparison. `guide-diagnostics --save` also stores
private copies at `/data/guide-diagnostics/latest.txt` and `latest.json`.
Passwords, connection tokens, private keys, hardware addresses, and private
media paths are removed before any report is printed or saved. Collection has
fixed timeouts and output limits and does not alter hardware state, play test
sounds, connect to a network, or open user media.

Brief command dictionary:

- `guide-diagnostics` — inspect the Deck and print a human-readable report;
- `--json` — use structured data instead of prose;
- `--save` — retain the latest report on the Deck for later retrieval.

## Private material

Build outputs and the desktop keypair are kept under `G:\GuideOS-private\developer-link`. Only the public key enters the cartridge package.
