# RG35XX H board layer

Status: hardware-enablement baseline imported; candidate image build in
progress. Nothing in this directory is yet declared safe for unattended use.

The board layer must establish and test all of the following before a GuideOS
image is offered for flashing:

- Boot ROM, SPL, and U-Boot chain
- Linux kernel source and configuration
- `sun50i-h700-anbernic-rg35xx-h.dtb`
- LCD and backlight
- Directional, action, shoulder, menu, power, and analog controls
- Audio output and volume controls
- Battery gauge, charging, suspend, wake, and clean power-off
- Both microSD interfaces
- 2.4 and 5 GHz Wi-Fi
- Bluetooth
- USB-C host/device behavior
- Mini-HDMI behavior
- Thermal limits and watchdog behavior

For each component, record source repository, immutable revision, license,
patches, firmware redistribution terms, and a hardware test result. Do not copy
binary firmware from the factory card into a public image until redistribution
rights are established.
