GUIDEOS BRINGUP-0 - SCREEN SELECTION

The default extlinux/extlinux.conf uses the original RG35XX H screen.

If the Deck boots but the screen is blank or displays corrupted colors:

1. Turn the Deck completely off.
2. Put the microSD card back into the computer.
3. Open the GUIDEOS_BOOT drive, then open the extlinux folder.
4. Rename extlinux.conf to extlinux-standard.conf.
5. Copy extlinux-rev6.conf and rename the copy to extlinux.conf.
6. Eject the card safely and try the Deck again.

Changing this file selects a hardware description. It does not erase data.
