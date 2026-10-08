# Network delivery 0

Implementation date: 25 September 2026. Validation and physical-installation
status are recorded separately in `NETWORK_DELIVERY_0_VALIDATION.md`.

The owner-assigned release number for this bootstrap is **GuideOS 0.3.2**.
The installed [live diagnostic extension](LIVE_DIAGNOSTIC_LINK_0.md) adds paired-PC
health monitoring and bounded reports to this transport; its physical connection
test is pending. The first-bootstrap instructions below are historical context.
The already verified installation retains its original internal build identifier
`deploy0-20260925`; [`VERSION`](../VERSION) supplies the version for future assemblies.

The first implementation delivers a complete Guide shell and shared input release
from this PC. It includes the pending keyboard grid, stick gestures and pointer
changes. The receiver, launcher, recovery controller, Wi-Fi provider, Debian
packages, fonts, kernel and boot files remain outside that replaceable release.
Later scopes need their own restart and recovery contracts.

## Requirement and ownership mapping

| Owner requirement | Responsible component | Observable result |
| --- | --- | --- |
| Fewer card returns | PC client, paired SSH gateway, local receiver | Transfer and activate a small Guide release over the local network |
| No change over 100 MB | Package builder and receiver | Reject a whole archive over 100,000,000 bytes, or expanded contents over that limit; no dependent split jobs |
| Preserve work | Shell handshake and local controller | Private text entry and pending Wi-Fi actions defer activation |
| Recover from failure | Stable systemd worker, rescue service and boot recovery | Select and restart the preceding release after a failed trial; recover before the shell after interrupted activation |
| Owner control | Paired PC key and explicit activation request | No periodic update checks, unsolicited downloads or automatic version upgrades |
| Lightweight portable core | Python transaction core and Debian host adapter | Bounded chunks and one staged transaction; board-specific power and display remain separate |

The 100 MB cap measures complete archive bytes, including manifest and ZIP
overhead, and separately caps extracted bytes. SSH framing and base64 transport
encoding add wire overhead. This is a release-size cap, not a metered-link quota.

## First installation and subsequent use

The installed Wi-Fi seed predates the receiver. One card bootstrap is still
needed. Build the bootstrap against a fresh capture of the returned card before
physical installation so saved networks and reports from the latest test survive.
The `guide-deploy0-root.ext4` reference image is a development/validation artifact
based on the preserved `wifi3` image. The separately prepared
`guide-deploy0-seed-root.ext4` uses the fresh returned-card capture and preserves
its saved network state; see the validation record before installation.

After bootstrap, connect the Deck to Wi-Fi and open System Status for its local
address. Plug in external power, finish any password entry or Wi-Fi operation,
and leave the Deck at an ordinary menu. Run the PC helper
[`Guide-Deploy.ps1`](../build/Guide-Deploy.ps1) with that address. `Status` reads the
active release, preceding release, transaction and shell readiness. `Stage`
uploads and validates without restarting. `Update` packages current source,
uploads, validates and explicitly requests activation. `Rollback` selects the
preceding release through the same safe restart sequence.

Example from PowerShell, replacing the example address with the Deck's address:

```powershell
./Guide-Deploy.ps1 -DeckAddress 192.168.1.42 -Action Status
./Guide-Deploy.ps1 -DeckAddress 192.168.1.42 -Action Update -Version guide-next
./Guide-Deploy.ps1 -DeckAddress 192.168.1.42 -Action Rollback
```

The helper uses this PC's WSL environment. Its private key and pinned Deck host
key are in `/home/hacker/guideos-private/deploy0`, outside source and report
folders, with restrictive permissions. No password or Wi-Fi credential is put
in a release, deployment status response or client command. Keep this private
pairing directory for subsequent use; transferring it deliberately authorizes
another PC. Re-pairing and lost-key recovery currently require local access.

For an interrupted transfer, rerun the Python client's `deploy` command with the
same ZIP from `build/network-releases`. It resumes at the last durable byte
offset. The PowerShell `Update` helper creates a new package; inspect `Status`
and resume or cancel the existing job before starting another. Explicitly
cancelled/rejected packages can be uploaded again. A candidate that rolled back
requires a newly built release/version after correction, not an automatic retry.

## Transport and admission

OpenSSH listens on IPv4 TCP port 2222 using a dedicated `guide-deploy` account.
Only the installed public key can authenticate. The host key is pinned by device
identity rather than IP address. A forced command accepts a fixed, bounded JSON
protocol. Interactive shells, arbitrary commands, forwarding, PTYs and SFTP are
unavailable. The general Debian SSH service/socket is masked. Configuration is
based on Debian's [OpenSSH server options](https://manpages.debian.org/trixie/openssh-server/sshd_config.5.en.html).

This is an explicitly paired development access path on a trusted local network,
not anonymous discovery, public Internet access or a complete AT Field policy
implementation. No router forwarding, multicast discovery or periodic polling is
introduced. The listener is idle until contacted. The paired key authorizes Guide
code updates, which execute with the shell's existing privileges; it is a trusted
developer capability, not a sandbox for hostile applications.

Local owner administration can disable admission with:

```text
python3 /usr/lib/guideos/deploy/deploy_server.py disable
```

`enable` reverses it. Stopping `guide-deploy-ssh.service` also closes the listener.
These are local maintenance operations; a Deck-facing on/off selector and richer
grant management remain future UI work. Status remains readable when admission
is disabled. Disabling does not abandon an activation that already began; that
transaction completes or restores the previous release.

## Transaction and recovery

The receiver uses 256 KiB chunks, one archive, one staging directory and a durable
JSON transaction. It verifies the whole archive hash, device identity, base
release, declared file set, per-file lengths/hashes and allowed paths. Compressed,
encrypted, duplicate, symlink and undeclared archive entries are rejected. The
first package format is deliberately not a `.guide` cartridge install contract.

An isolated unprivileged systemd process parses/imports the candidate and renders
a menu and keyboard. It has no network, a read-only system view and bounded
memory/time. This catches ordinary dependency/rendering failures; it does not
prove hardware display behavior or protect against an intentionally hostile
developer-authored release after activation.

Activation is a separate systemd job, so loss of SSH does not strand a restart.
The host adapter requires recognized external power, a fresh ready heartbeat
from the actual shell PID, and no private text or pending Wi-Fi operation. It
asks the shell to park input, checks acknowledgement, stops it and requires a
clean cleanup report. Power remains independently owned by systemd/logind.

The controller records recovery intent before changing the active generation,
atomically switches a small active record, and starts the candidate. The candidate
must report a first rendered frame and stable process identity for three seconds
within a 20-second health window. Failure selects and restarts the old release.
A failed worker invokes a separate rescue service. After a power interruption,
boot recovery selects the old generation before launching the shell; its record
says `pending-boot` until runtime readiness is independently observed in status.

Successful releases retain one preceding generation. User data, saved Wi-Fi
profiles and reports stay outside release directories. Available storage must
cover the archive, up to 100 MB of staging and a 32 MB reserve. The current Debian
adapter does not implement a full application save/checkpoint contract, persistent
data migrations, kernel rollback, Wi-Fi-provider replacement or updater self-update.
Those changes cannot be delivered by this first channel.

## Boundaries still requiring physical evidence

Virtual tests replace framebuffer, physical controls and external-power detection.
They can verify SSH, filesystem transactions, service restart and rollback, but
cannot prove Deck display/input cleanup, battery detection, Wi-Fi reliability or
radio power use. The first real update must check those boundaries. Process health
also cannot prove that every interface looks right; explicit rollback remains
available after a visually bad release that stays alive.

Traffic uses this standalone SSH connection. It is not yet connected to Guide's
future foreground-stream contention broker. The receiver runs at lower CPU
priority; transfer bandwidth coordination and richer diagnostic export are later
work. Current diagnostic retrieval is bounded deployment status and failure codes,
not arbitrary filesystem access or raw logs that might contain private material.
