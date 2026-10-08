# Debian hardware diagnostic 2

This revision follows the physical diagnostic 1 boot: the owner saw console
text, a brief cube flash, then more console text. Captured reports initialized
Panfrost EGL contexts, registered the panel and gamepad, and enumerated radios.
Those results do not yet establish sustained graphics, correct control mapping,
or working wireless connections.

## Changes

- Linux release `7.2.7-guide-debian2`, with the working dependency configuration
  retained. Remove the optional panel-orientation property call from `get_modes`:
  diagnostic 1 traces show it registering DRM properties too late. Hardware
  confirmation that the warnings disappear is pending; no orientation feature
  is claimed by this removal.
- Give kmscube an idle FIFO as stdin instead of service-provided EOF, which its
  event loop treats as an interruption. Request 1800 frames with a 40-second
  limit and a further three-second forced-termination bound. Record exit status
  and uptime at start/end; timeout is not proof of completed frames.
- Recognize `H700 Gamepad`. Run a dedicated 30-second, line-buffered event
  capture before graphics so controls are not competing with another prompt.
  Exit 124 is normal for this timed event capture; actual events must be checked.
- Store reports on both data and boot partitions under the kernel's unique boot
  ID, independent of the unset device clock. `diagnostics/latest-boot.txt` points
  to the newest folder. Save at startup, after controls, and after graphics.
  `completion.txt` records a shutdown request, not proof shutdown completed.

## Build and checks

Use `build/prepare-debian-diagnostic2.sh`, then
`build/build-debian-diagnostic2-kernel.sh`. Run assembly and validation with
`GUIDE_DIAGNOSTIC_ID=2`. Artifacts and logs are in `build/debian-diagnostic-2/`.
The former revision's image and archived hardware reports are preserved.

`build/check-diagnostic2-input.py` reproduces readable EOF and checks the actual
shell FIFO approach remains idle under `select`, then verifies forced time
bounding with a sleeping substitute process. This does not test the real GPU.
The userspace script passes shell syntax and systemd service validation.

## Physical test

Boot the card in the RG35XX H. When the controls prompt appears, exercise all
game buttons, the D-pad, and both sticks for 30 seconds. Avoid the power button
during this capture. Watch for a sustained rotating cube, then console output.
Allow up to three minutes for automatic poweroff before removing the card.
Repeating the test should retain a separate report folder for each boot.

Wireless association/pairing, audio output, suspend, and the earlier Bluetooth
packet warnings remain outside this revision's acceptance claims.

## Installation result

Image assembly completed successfully. Partition, FAT/ext4 filesystem, ARM64
kernel, and controls-module version checks passed. The image was installed on
the identity-checked seed card; full raw readback matched SHA-256
`B384F8F26FB5C3E6C9D2F8AD9576E116732C0D9E33A4DE495CC31578DC0521C3`.
The cleared backup-GPT tail was separately verified. See
`build/debian-diagnostic-2/flash-result.txt` and `validation.log`.
Physical test now confirms visible graphics, approximately 30 seconds of
Panfrost cube rendering at 60 fps, four stick axes across their reported range,
and press/release events from 14 buttons. Prior DRM warnings are absent.
Start/Select/Menu were not captured. Bluetooth hci0 did not appear on this boot,
despite appearing in diagnostic 1; this remains unresolved. See
`build/debian-diagnostic-2/hardware-tests/2026-09-21-234733/RESULT.md` for evidence
and remaining acceptance gaps. The card was not reflashed during inspection.
