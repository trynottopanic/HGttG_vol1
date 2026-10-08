# GuideOS prebaked eclipse boot animation

This boot stage plays the approved 640x480 eclipse sequence from one validated,
fixed-rate RGB565 frame stream. It does not generate a world, import Pillow, or
run the authored design script on the Deck.

The stream contains 75 frames at 10 frames per second for an exact 7.5-second
sequence. The native DRM/KMS, GBM, EGL and OpenGL ES player uploads frames into
one texture, preserves the existing ready signal and timeout supervisor, and
starts the Guide Shell after its first frame is presented. Home initializes and
composes its first frame while the animation plays; its framebuffer adapter waits
for the native player to exit and restore DRM before opening the display.
The console remains in graphics mode until Home acknowledges its first write,
and Home inherits the original terminal mode for cleanup. If Home fails to take
over within ten seconds of animation exit, the console is restored for recovery.

## Current visual revision

On 2 October 2026 the owner approved corona draft 02 for integration. The working
asset now uses its irregular connected ivory/peach filaments instead of the old
red-orange flares and scattered pixels. It emerges at 1.5 seconds, expands,
flares, then contracts to the stable bold O by 5.8 seconds. Planet, background,
lettering and the total sequence remain unchanged.

The offline source is
`design/boot-eclipse-animation-0/render_boot_eclipse_final_2.py`; it imports the
approved draft 02 and preserves the historical draft 5. The full visual preview,
frame-conversion receipt and rollback location are recorded in
`design/boot-eclipse-animation-0/FINAL_CORONA_2.md`.
The owner-approved spacing revision moves S 14 pixels right to give both sides
of the final O a minimum horizontal clearance of 12 pixels.
The asset is selected for the pending 0.4.2.06 update; see
`docs/BUILD_0_4_2_06.md` for the consolidated candidate and verification record.
Source and image checks do not establish Seed installation or physical playback.

## Files

- `assets/boot-eclipse-v1.rgb565a`: installed, target-native frame stream.
- `build_prebaked_animation.py`: offline conversion and format validation.
- `guide-boot-animation.c`: bounded native player and DRM handoff.
- `guide_boot_runner.py`: independent initialization/playback deadline supervisor.
- `guide_boot_console.py`: console acquire/release helper.
- `guide-boot-animation.service`: first-frame startup notification and cleanup bounds.
- `install.sh`: installs the player and removes the superseded dynamic-world boot path.
- `validate.py`: source, stream and service contract checks.

## Stream format

The 32-byte little-endian header is `GOSANIM1` followed by six unsigned 32-bit
values: width, height, frame count, FPS numerator, FPS denominator, and bytes per
frame. Frames follow contiguously as top-to-bottom RGB565 pixels.

Rebuild the asset only from an approved 640x480, fixed-rate, exactly 7.5-second
GIF:

```sh
python3 build_prebaked_animation.py approved.gif assets/boot-eclipse-v1.rgb565a
```

Compile with `build-debian.sh`, then install into a staged root:

```sh
./install.sh --root /path/to/rootfs --binary ./guide-boot-animation
```

Physical acceptance still requires a Deck boot test for clean shell handoff,
the complete end hold, acceptable playback, and normal input/Power behavior.
