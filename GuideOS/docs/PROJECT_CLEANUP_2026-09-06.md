# Project Cleanup — September 6, 2026

## Removed

- nine superseded experimental Desktop Node build trees;
- the old `node/desktop/build`, `node/desktop/dist`, and Python cache trees;
- three obsolete generated PyInstaller specifications;
- the reproducible compiler work directory from the retained build.

Approximately 411.54 MiB was removed. Approximately 385.06 MiB was sent to
the Windows Recycle Bin. The remaining 26.48 MiB belonged to the locked
`node-dpi-native` build and was permanently removed after its exact absolute
path was validated inside the repository.

## Retained Desktop Node build

`GuideOS/build/node-governed-input/dist/GuideNode-GovernedInput.exe`

SHA-256:
`AF639DB480F87FDA2737ABD722B8564298946862C601AC2FD09950BB0D6CEA69`

The temporary compiler output was removed, but the executable, specification,
source, and one-click build script remain. The build script now runs every
desktop test and builds the governed native interface.

## Anbernic images retained pending a real failsafe

Neither existing public candidate is a proven safe boot, so both were retained:

- DDR3: `E397679AD14CA7DFE454F5F2E3ADF2B78ECC81B7B576CCFA263F0C3FB60C61E4`
- DDR4: `1F4166A488C96494075D412805F8FB6A47078F96CE80D144CD3D7DBD1FC56256`

The card reader reported no media during cleanup. The next storage-cleanup
step is to connect the known-working seed and follow
`ANBERNIC_FAILSAFE_STATUS.md` to capture and verify a real safe-boot image.

## Verification

All 28 Desktop Node tests passed after cleanup. Only the governed-input Node
build remains under `GuideOS/build/node-*`.
