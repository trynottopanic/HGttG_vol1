# Finalized corona design 2

Owner-approved spacing adjustment, 2 October 2026: move S slightly farther from
O so its clearance matches G/O. S moves from x=418 to x=432 (14 pixels right).
The smallest clear horizontal scanline gap is now 12 pixels on both sides,
including the pale outer border of the final O. The renderer asserts equality.

[Current animation](GuideOS-Eclipse-Boot-Animation.gif) ·
[Final frame](guideos-boot-eclipse-final-2-final.png) ·
[Verification](guideos-boot-eclipse-final-2-verification.json)

Render with `render_boot_eclipse_final_2.py`. Only S placement changes from
[revision 1](FINAL_CORONA_1.md); corona, G, background, planet, fades and timing
remain unchanged. The historical renderer's new optional S coordinate defaults
to its original value, preserving old draft reproduction.

The current preview alias and working asset
`apps/boot_animation/assets/boot-eclipse-v1.rgb565a` use revision 2, still 75
frames at 10 fps, 640x480, 7.5 seconds. Every RGB565 frame is verified against
the exported GIF. Named final-1 outputs remain intact. The pre-spacing working
native asset and preview were additionally preserved under
`build/boot-corona-final-2-preserved/`.

No native player, service, GPU renderer, release image or Seed is changed.
Physical acceptance remains separate. Revision 1's documented pre-existing
service-order validator mismatch is unchanged; this bake verifies asset content
and timing, not that separate source/service contract.
