# Bluetooth runtime sources

The repository contains only GuideOS integration scripts. The prototype image
is assembled privately from separately fetched components:

- **BlueZ 5.79** — Linux Bluetooth user space; GPL-2.0-or-later and
  LGPL-2.1-or-later components, built by Buildroot 2025.02.17.
- **BlueALSA 4.3.1** — MIT license, built by Buildroot 2025.02.17.
- **D-Bus, ALSA, SBC, and their runtime dependencies** — their respective
  upstream licenses, built by Buildroot 2025.02.17.
- **Realtek UART initializer** — Radxa `rtkbt` commit
  `72ef9b75374fdde945e0a19f6aba68e13d4d426d`; its source headers declare
  GPL-2.0-or-later.
- **RTL8821CS firmware and board configuration** — exact prototype inputs from
  PanicOS commit `114788bd4374cc5a380a6b909a9f9a59b4eabfc6`. The configuration
  MD5 is `37338e0b8861a20ce877c0a10cbaaae3`.

The last firmware snapshot does not state sufficiently clear redistribution
terms for those two binary files. They are therefore kept out of the public
repository and used only on the privately owned development Deck. A public
GuideOS image must replace them with an equivalently tested, redistributable
upstream firmware package and carry its license notice. Public release must
also include the corresponding source and notices required by every copyleft
runtime component.
