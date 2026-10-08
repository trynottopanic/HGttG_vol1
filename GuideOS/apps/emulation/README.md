# GuideOS native emulation runtime

The cartridge is a delivery and licensing package, not a permanent execution
layer. Installation places one small native libretro frontend and fixed ARM64
cores in internal storage. Game and firmware files remain on removable storage,
mounted read-only by GuideOS; saves, states, configuration, and indexes belong
under `/data/guideos/emulation/`.

Initial system mapping:

- GB/GBC: Gambatte
- GBA: mGBA
- Genesis/Mega Drive: Genesis Plus GX
- SNES/Super Famicom: Snes9x 2010
- NES/Famicom: FCEUmm
- PlayStation: PCSX-ReARMed

No ROM, disc image, or proprietary BIOS is included. The installer must retain
all license notices. Genesis Plus GX and Snes9x are approved here only for the
owner's personal, non-commercial prototype.
