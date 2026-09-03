# GuideOS

GuideOS is the provisional name of the HHG-owned Linux distribution for Decks.
This directory is the beginning of its reproducible source tree.

Current status: **Stage 0 scaffold — not yet bootable and not safe to flash.**

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
milestone is `VISITING-SCREEN-0`: select one movie stored on the Deck, join an
unfamiliar household Wi-Fi network, discover an unknown smart television,
grant a temporary one-file capability, and play the movie without uploading it
to an internet service.

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
A board defconfig will be added only after the RG35XX H boot chain and required
firmware have been reproduced from reviewed sources.

The approved initial build baseline is Buildroot 2025.02.17 from the 2025.02.x
long-term-support series. The intended kernel line is Linux 6.18.y. A precise
kernel maintenance release will be locked only after RG35XX H bring-up tests;
release builds will never follow a moving branch implicitly.

Buildroot requires a Linux build host. This Windows computer currently has
neither Docker nor a WSL Linux distribution, so Stage 1 requires establishing
one isolated Linux build environment before compiling an image.

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
4. Enable Wi-Fi with an explicit local configuration flow.
5. Add development SSH using public-key authentication.
6. Add the Guide supervisor and semantic input events.
7. Add receiver discovery and the bounded media-share service.
8. Run `VISITING-SCREEN-0` and record compatible and failed routes.

## Non-goals for the first image

- A new kernel written by the project.
- A local general-purpose Semiotic Engine.
- Live video transcoding on the handheld.
- Emulation-console features unrelated to the first Guide test.
- Dependence on one television vendor or casting platform.
