# Developer Link Installation Cartridge

The Developer Link cartridge installs an intentionally limited maintenance connection on the RG35XX H Deck prototype. It is for development and diagnosis, not ordinary day-to-day operation.

## User-visible behavior

- The connection never starts automatically.
- The user must turn it on from the Deck itself.
- It listens only on the Deck's current local Wi-Fi address, on port 2222.
- The Deck shows whether the link is off, unavailable, or active.
- Turning the link off ends the server process and removes its active marker.

## Security boundary

- Public-key authentication is required; passwords are disabled.
- The desktop's private key is never placed on the cartridge or committed to this repository.
- TCP forwarding, agent forwarding, X11 forwarding, compression, and remote root-password login are disabled.
- The Deck creates its own SSH host key on first use. A shared host identity is not distributed on the cartridge.
- The package and every installed file are accepted only when their exact SHA-256 hashes match the values compiled into the trusted Deck shell.
- Installation refuses to overwrite pre-existing system files and rolls back partial installation.

The link grants a trusted key a root maintenance shell while it is active. That authority is deliberate for prototype development and must remain physically controlled, visible, and independently security-reviewed before this feature is considered suitable for general use.

## Private material

Build outputs and the desktop keypair are kept under `G:\GuideOS-private\developer-link`. Only the public key enters the cartridge package.
