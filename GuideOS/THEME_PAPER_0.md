# GuideOS Paper Theme 0

Paper Theme 0 translates the approved home-screen mockup into the live 640 x 480
framebuffer shell. It applies to the home menu, cartridges, Wi-Fi, Wikipedia,
on-screen keyboards, tests, system information, installation, Developer Link,
power, progress, success, warning, and error states.

## Visual vocabulary

- Warm pale field: `#EFEDE1`
- Charcoal-olive primary ink: `#3A3B30`
- Muted blue interface ink: `#446470`
- Rust selection and attention ink: `#9D4E22`
- Muted green success ink: `#416F4B`
- Muted red danger ink: `#973930`
- Thin outlined panels with a pale selected fill
- Mixed-case navigation labels and persistent “The Guide” / “Don't Panic.” header
- Five-row scrolling home window for the seven current destinations
- A real proportional scrollbar on scrolling menus and search-result lists
- Three-position home footer for movement, open, and back controls
- Monochrome rose seal reading “Cultivando la rosa blanca” and
  “En junio como en enero”, without a final period

## Installable pieces

The Buildroot package installs both the shell and rose asset. The cross-compiled,
checksummed staging bundle in `GuideOS/build/theme-update/` now contains the
same combined shell as the next Deck build, including the QWERTY keyboard,
held-stick navigation, and Wikipedia 0.3 integration. The canonical
`GuideOS/build/prepare-next-cartridge-rootfs.sh` helper creates and verifies the
next private root filesystem image without changing the seed or writing to a
physical card.

Writing the prepared root filesystem to removable media remains a separate step.
The physical target must be re-identified and confirmed immediately beforehand.
