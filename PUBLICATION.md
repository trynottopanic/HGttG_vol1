# Public source scope

This repository contains GuideOS source, Windows NDI source, board integration,
public foundation documents, desktop prototypes and generic interface assets.
The [handbook](docs/HANDBOOK.md) describes the current component status.

## Included and local material

Build outputs, disk images, deployment receipts, credentials, signing keys,
saved owner data and packaged applications remain outside the public source.
Planegotchi-specific code, tests, documents, data and artwork also remain local.
The public shell handles the absent application with a generic placeholder.
Shared documents omit its private sections; general interface names can remain
in the shell without including the application's implementation.

Local editor and automation instructions are ignored. Useful contributor
guidance is maintained in the [development guide](docs/DEVELOPMENT.md).

## Source checks and exports

```sh
python3 -B tools/repository/publication.py --check
```

This checks the selected source for excluded files, oversized files and common
credential patterns without printing secret values. It does not audit Git
history or exercise runtime behavior. Ignoring a file prevents future additions;
it does not remove a file already committed.

The export option copies the selected source into a fresh publication worktree.
It does not push or rewrite history. Keep local audit reports outside the
repository, and preserve private sections in the original development files.

The installed release and a development checkout can differ. This repository
does not supply the private base image or a fully pinned recipe for rebuilding
the installed system. Component builds and initial Debian reference recipes
remain available; public release images require separate preparation.

## Licensing

Original software uses AGPL-3.0-or-later. Original documentation and visual
material use CC-BY-SA-4.0. File-specific and third-party notices retain their
own terms. See the [license policy](LICENSE.md).
