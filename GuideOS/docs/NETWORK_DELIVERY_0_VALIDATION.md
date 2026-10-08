# GuideOS 0.3.2: network bootstrap validation and installation

25 September 2026. **Installed on the seed; complete root-partition readback
passed at 04:21:40 UTC.** Physical network delivery and the pending
keyboard/pointer changes still require Deck acceptance.

The owner designated this installed release **GuideOS 0.3.2** after installation.
Its immutable installation evidence retains the internal build identifier
`deploy0-20260925` and the image hash below. The current Deck status screen still
shows that internal identifier. Future bootstrap assemblies read the release
number from [`VERSION`](../VERSION); the next network release can carry `0.3.2`
as its displayed version. No second card write was needed to record the release
designation, and no second installation is claimed.

## Completed evidence

- 219 ARM64 input, keyboard, pointer, Wi-Fi panel and shell checks passed.
- 24 ARM64 deployment transaction/handshake tests passed, including busy-state
  deferral, cancellation, corruption rejection, durable resume, worker rescue,
  failed-launch rollback and interrupted activation recovery.
- Real SSH, systemd services and ext4 storage ran in an ARM64 virtual machine.
  Paired/pinned access worked; an unpaired key and arbitrary remote commands were
  rejected. An interrupted transfer resumed. Activation finished after the SSH
  client disconnected. A candidate that imported successfully but failed at
  actual launch triggered local rollback. Explicit owner rollback also passed.
- The VM was forcibly stopped while the new release was in trial. On reboot,
  the preceding release was selected and the actual shell process reported ready.
  The subsequent shutdown was orderly and reached `reboot: Power down`.
- Virtual display, input and external-power availability were substituted.
  These results do not establish physical display/input cleanup, charger
  detection, Wi-Fi reliability or battery consumption.
- The tested ordinary network package was **142,667 bytes**, including manifest
  and archive overhead. Whole-package and expanded limits are 100,000,000 bytes.
- The fresh installable image has the same deployment modules, services,
  package inventory and shell/input content as the VM-tested reference.
  Guest-only substitutions are absent. Filesystem checks and package audit passed.

Pre-install validation: [`validation.json`](../build/debian-deploy-0/validation.json).
Completed write/readback: [`installation.json`](../build/debian-deploy-0/installation.json)
and [`seed-install.txt`](../build/debian-deploy-0/seed-install.txt).
Transport run: [`network-integration.log`](../build/debian-deploy-0/network-integration.log).
Reboot recovery: [`boot-recovery.log`](../build/debian-deploy-0/boot-recovery.log).

The first exploratory VM run was stopped without an orderly guest shutdown and
its journal could not be read cleanly. Its evidence is retained in
`build/debian-deploy-0/initial-evidence`. The final run above deliberately tests a
power interruption, then recovers and shuts down cleanly. The installable image
has never been booted as that fault-injection guest.

## Fresh capture and candidate

The connected card was identified as USB Disk 4, `TS-RDF5 SD  Transcend`, serial
`00000000TS38`, size 62,239,277,056 bytes. Its root partition was subsequently
written under the owner's explicit approval.

The 3,490,709,504-byte used region was captured read-only at:

`E:\DGttG\private-recovery\deploy0-return-20260925-001100\seed-used-region.img`

Capture SHA-256:
`22C8D53773C2C45B2015B86B525532B22716FDDB3EC3E734B05D70DADC9BE7DE`

The installable candidate is
[`guide-deploy0-seed-root.ext4`](../build/debian-deploy-0/guide-deploy0-seed-root.ext4),
2,147,483,648 bytes, build `deploy0-20260925`.

Candidate SHA-256:
`FD38D8DFA0BC9FC07BAFFFC850FF44741264AA5BEB3323B6C345B288F341784D`

It was built from this fresh capture. The seven regular files in the saved
NetworkManager/Guide state directories have identical combined hashes before
and after assembly. Original resolver configuration, machine identity and hostname
also match the capture. An offline-build DNS failure was resolved with a temporary
PC resolver; the original Deck resolver was restored and verified.

The separate `guide-deploy0-root.ext4` is the older reference used for virtual
testing. The **seed-root** candidate above is the one installed on the card.

## Completed installation

The [guarded installer](../build/install-deploy0-seed.ps1) targeted only
**Disk 4, partition 2**, offset **135,266,304**, length **2,147,483,648**. It verified
the expected image hash, passing validation receipt, recovery-capture hash,
matching disk identity/layout, no mounted drive letters, and pre-write hashes
matching the fresh capture for the boot/root/data regions.

It wrote and flushed the root region, read back the entire 2 GiB, and matched the
candidate SHA-256 above. The boot and data regions remained byte-identical to the
fresh recovery capture. The installer completed successfully; no further raw
write is pending for this revision. The recovery capture remains retained.

The first physical check is: boot the
Deck, connect to the saved Wi-Fi, attach external power, open System Status for
the address, then make a small paired-PC update while observing restart and input
recovery. The PC helper is [`Guide-Deploy.ps1`](../build/Guide-Deploy.ps1). Its
`Status` action retrieves the active version and deployment state without writing
a release. See [implementation](NETWORK_DELIVERY_0_IMPLEMENTATION.md) for scope,
resume, owner rollback and current limitations.
