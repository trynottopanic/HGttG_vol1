# Cartridge Browser 0

Cartridge Browser 0 is the first Deck-side interface for `.guide` packages.
It replaces the one-manifest Payload Format 0 screen while preserving the same
read-only external-card boundary.

## User experience

1. Insert a prepared microSD card in TF2/EXT.
2. Open **Cartridges** from the GuideOS menu.
3. Move through as many as eight packages with the D-pad.
4. Press A to open one.
5. GuideOS checks the archive byte count and SHA-256 before showing the result.
6. Press B to return. Leaving the browser unmounts the card.

The detail screen identifies the package, version, first requested capability,
known installation action, verification result, and the fact that Format 1 is
unsigned. A valid checksum means the archive matches its card index; it does
not prove who authored either file.

The empty states distinguish physical storage from package recognition:

- **No ext storage** means TF2 contains no detectable card.
- **Ext storage detected — storage could not be read** means a card exists but
  its filesystem could not be mounted safely.
- **Ext storage loaded — no Guide cartridges on storage** means the card and
  filesystem are readable, but no Cartridge Format 1 package was found.
- **Ext storage loaded — package format not recognized** means cartridge-like
  indexes were present but none passed the bounded Format 1 parser.

Older Payload Format 0 cards therefore appear as readable external storage
without being misreported as absent.

## Card index

The host card-copying tool creates one bounded `.gde` index beside every
`.guide` archive. This avoids putting a complete ZIP/JSON implementation into
the small bring-up shell. Index fields are strict ASCII lines, unknown fields
invalidate the index, filenames cannot contain path separators, and the
archive must be a regular file of the declared size.

The card remains mounted read-only with `nodev`, `nosuid`, and `noexec`.

## Installation milestone

The prototype now recognizes one pinned privileged operation:
`feature.wifi.rg35xxh` from the exact verified Wi-Fi Installation 0.1.0
cartridge. The Deck shows a second local confirmation screen, checks the
machine and Linux 4.9.170 kernel, rechecks the complete cartridge against a
hash built into GuideOS, extracts only seven named files into private staging,
checks every file hash, and creates only previously absent destinations.

If any check or write fails, all files created by that attempt are removed.
Existing system files and links are never overwritten. The card itself stays
read-only and no code executes from it. Other actions and all unsigned package
identities remain view-only; this is a narrow prototype bridge, not a general
package execution mechanism. Cartridge Browser 0 extracts content only through
this one trusted Wi-Fi installation action and never executes code directly
from the cartridge.

## General installation boundary

Any additional browser installation action may offer **Install** only when all
of these hold:

- archive verification succeeded;
- its `installAction` exactly matches an operation built into GuideOS;
- the action supports this Deck model and current system version;
- the UI explains every requested capability and persistent change;
- the user confirms;
- files are staged and verified before an atomic activation;
- a rollback record is written before activation;
- removing the cartridge after success cannot remove the installed feature.

Arbitrary scripts from a cartridge are never executed as root. A cartridge
may carry a declarative patch plan and data, but trusted GuideOS code interprets
and enforces that plan.
