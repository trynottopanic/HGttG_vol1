# Working on the source

GuideOS is a personal experimental project targeting minimal Debian ARM64 on
the RG35XX H. Read the applicable `GuideOS/AGENTS.md`, feature contract and
design-alignment record before changing a component. Keep source checks,
assembled-image evidence and physical Deck testing distinct.

Python tools use Python 3 and standard-library modules unless their component
documents another dependency. The shell's host rendering checks require Pillow
and Linux's normal platform modules. Native providers document their own C,
systemd and display dependencies. There is no universal dependency installation
that builds every experiment in this repository.

From a Linux checkout, useful focused checks are:

```sh
python3 -B -m unittest discover -s GuideOS/package/guide-connectivity -p test_nearby.py
PYTHONPATH=GuideOS/board/rg35xxh/debian/shell0:GuideOS/package/guide-ui \
  python3 -B -m unittest test_public_source test_nearby_panel
python3 -B tools/repository/publication.py --check
```

The first two commands test provider lifecycle and actual shell navigation/render
boundaries with host fixtures. They do not exercise a Deck's radios or display.
Choose additional checks relevant to your change; legacy fixtures may reflect
earlier Home layouts and should not be rewritten merely to hide a mismatch.

Keep build outputs in ignored directories. Do not add credentials, runtime
databases, real owner captures, disk images or compiled cartridges. Public
keys and clearly synthetic fixtures are different from private signing keys.
Planegotchi-specific files are excluded at the owner's direction; the public
shell must remain usable without them. Preserve imported license notices and
use the existing policy in `LICENSE.md` for original material.
