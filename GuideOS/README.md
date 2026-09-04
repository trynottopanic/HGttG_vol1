# GuideOS

GuideOS is the provisional name of the HHG-owned Linux distribution for Decks.
This directory is the beginning of its reproducible source tree.

Current status: **Stage 1 hardware integration — candidate build in progress
and not yet approved for flashing.**

## Human-accessibility requirement

GuideOS treats making software as an ordinary use of the Deck. A person who is
comfortable using a computer, but has no computer-science training, must be
able to make, test, understand, and share a small Guide program with minimal
new vocabulary.

The friendly layer will be the Guide Recipe system: small programs expressed
as readable connections between events, conditions, information, devices, and
actions. Recipes must not require knowledge of Linux administration, process
management, networking internals, package managers, or traditional build
systems for common tasks.

This does not remove the exact technical layer. Every friendly concept must map
to inspectable files, capabilities, protocols, logs, and source code. GuideOS
documentation will explain the ordinary-language idea first, define necessary
technical terms at first use, show a working example, and then provide the full
technical reference.

Finished Recipes and more advanced programs will be exchangeable as provisional
`.guide` packages. These are inspectable ZIP containers using existing open
formats for metadata, portable behavior, and assets. A receiving Deck grants
its own permissions; authority and private information never travel merely
because the package does.

The first hardware target is the Anbernic RG35XX H. The first functional
milestone is `CONTINUE-ON-DECK-0`: pause an authorized local video on a desktop
Node, connect the Deck by USB, transfer the video and its playback position,
disconnect, and resume locally on the Deck. `VISITING-SCREEN-1` follows after
that: the Deck joins an owner-approved local network and offers its video to a
compatible television through a temporary Node.

## Distribution boundary

GuideOS owns and defines:

- the root filesystem and service set;
- the Guide runtime, capability broker, interface, and protocol adapters;
- account, logging, update, recovery, and storage policy;
- reproducible image construction and dependency records.

The first RG35XX H image may temporarily reuse audited board-enablement work for
the bootloader, kernel patches, device tree, GPU, display, controls, audio,
power management, and wireless firmware. Every imported component must retain
its license and provenance. Hardware support is a replaceable layer, not the
definition of GuideOS.

## Build system

GuideOS uses a Buildroot `br2-external` tree. The three required integration
files are present:

- `external.desc`
- `Config.in`
- `external.mk`

The root filesystem overlay begins under `board/common/rootfs-overlay`.
The initial board layer provides separate LPDDR3 and LPDDR4 definitions, both
known panel descriptions, a Windows-readable boot partition, and a minimal
diagnostic userspace.

The approved build baseline is Buildroot 2025.02.17 from the 2025.02.x
long-term-support series. Linux 6.18.y remains the intended stabilization line,
but `BRINGUP-0` temporarily pins Linux 7.1.2 because that is the exact release
targeted by the currently tested H700 display and wireless patch set. Release
builds will never follow a moving branch implicitly.

Buildroot requires a Linux build host. The current workshop is Ubuntu in WSL2,
with generated files isolated under `/home/hacker/guideos-work`. GuideOS does
not depend on one Ubuntu release; the exact tools used for a release belong in
its build record.

## Image policy

The first image will use:

- a small read-only system filesystem where hardware support permits;
- a distinct writable data partition;
- no default remote password;
- development SSH enabled only with an explicitly installed public key;
- no cloud account or mandatory internet service;
- local Wi-Fi and receiver discovery;
- a temporary, read-only, single-file media share;
- visible failure states rather than automatic compatibility claims.

Disk 4 is the designated seed microSD card, currently observed through a
Transcend TS-RDF5 reader at 57.96 GiB. It must not be written until an image has
been built, inspected, hashed, and the physical target has been confirmed again.

## Stages

1. Import and audit an RG35XX H hardware-support baseline.
2. Reproduce a minimal boot to display with working controls and clean shutdown.
3. Enable both microSD slots and persistent data separation.
4. Enable a bounded USB data link and atomic media import.
5. Add local playback and resume-state handling.
6. Run `CONTINUE-ON-DECK-0` and record transfer and resume accuracy.
7. Enable Wi-Fi with an explicit local configuration flow.
8. Add development SSH using public-key authentication.
9. Add the Guide supervisor and semantic input events.
10. Add receiver discovery and the bounded media-share service.
11. Run `VISITING-SCREEN-1` and record compatible and failed routes.

## Non-goals for the first image

- A new kernel written by the project.
- A local general-purpose Semiotic Engine.
- Live video transcoding on the handheld.
- Emulation-console features unrelated to the first Guide test.
- Dependence on one television vendor or casting platform.
