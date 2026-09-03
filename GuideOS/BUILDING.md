# Preparing a GuideOS build workspace

GuideOS is assembled on Linux with Buildroot. On Windows, the current reference
workshop is Ubuntu 24.04 under WSL2. WSL2 lets Linux build tools run alongside
Windows; it is not installed on the Deck.

The first image is not available yet. These instructions currently verify only
the build workshop and GuideOS project structure.

## Install the workshop tools

In an Ubuntu 24.04 terminal:

```sh
sudo apt update
sudo apt install -y build-essential bc bison flex cpio unzip libncurses-dev libssl-dev
```

Command dictionary:

- `sudo` temporarily runs a command with system-administrator permission.
- `apt update` refreshes Ubuntu's catalogue of available software.
- `apt install` installs the named software.
- `-y` approves the listed installation without a second confirmation.
- `build-essential` supplies the C and C++ compilers and Make build tool.
- The remaining names supply parsers, archive tools, configuration menus, and
  encryption support used while constructing Linux systems.

## Acquire the pinned Buildroot source

Choose a private build-workspace location in Ubuntu. The following example
uses `/home/hacker/guideos-work`:

```sh
mkdir -p /home/hacker/guideos-work
git clone --depth 1 --branch 2025.02.17 \
  https://gitlab.com/buildroot.org/buildroot.git \
  /home/hacker/guideos-work/buildroot-2025.02.17
cd /home/hacker/guideos-work/buildroot-2025.02.17
git rev-parse HEAD
```

The final command must print:

```text
d0820dd09916edcefc44e525355afbea30d5bee4
```

Command dictionary:

- `mkdir -p` creates the workspace and any missing parent folders.
- `git clone` obtains a local copy of a source repository.
- `--depth 1` downloads only the selected revision's immediate history.
- `--branch` selects the named release tag.
- `cd` changes the terminal's current folder.
- `git rev-parse HEAD` prints the exact source revision currently selected.
- A **commit** is an immutable Git snapshot identified by a long hexadecimal
  value; it is more precise than a branch name, whose contents can change.

## Verify the GuideOS external tree

From the Buildroot source folder, substitute the actual path of the public
repository if it differs:

```sh
make BR2_EXTERNAL=/mnt/e/DGttG/HGttG_vol1/GuideOS list-defconfigs
```

Command dictionary:

- `make` runs Buildroot's construction instructions.
- `BR2_EXTERNAL=...` tells Buildroot where GuideOS keeps its independent
  configuration and board material.
- `list-defconfigs` checks the project structure and lists available starting
  configurations without building an image.
- A **defconfig** is the small saved list of choices needed to reproduce one
  hardware target's initial configuration.

No GuideOS defconfig exists yet. It will be created only after the RG35XX H
boot and hardware requirements have been audited.
