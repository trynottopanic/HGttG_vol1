# Reference Debian build recipes

These six scripts preserve the initial Debian ARM64 userspace and H700
diagnostic assembly recipes previously mixed with local output in `build/`.
They write staging files and image files, not physical cards. The original
local scripts and deployment records remain outside the public source boundary.

The default project location is this checkout's `GuideOS` directory. Set
`GUIDE_PROJECT_ROOT` to override it and `GUIDE_WORK_ROOT` for a separate Linux
workspace (default `$HOME/.cache/guideos`). Outputs still go to the ignored
`GuideOS/build/` directory.

`bootstrap-debian-minimal.sh` creates a Debian trixie ARM64 minbase. It requires
Linux root privileges, debootstrap, Debian archive keys and working ARM64
execution support. It refuses an existing rootfs. It does not create a bootable
Deck release.

The five kernel/diagnostic scripts retain historical Linux 7.2.7, toolchain,
firmware and previously prepared workspace dependencies. They are reference
recipes, not a complete reproducible build of 0.4.4.03. Consult
`../../DEBIAN_BRINGUP_0.md` and the board patches before using them. The script
named prepare-debian-kernel applies patches to an already obtained source tree;
it does not download that tree.

Keep physical-card writers and owner-specific recovery state out of this folder.
