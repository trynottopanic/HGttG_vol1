# Finalized corona design 1

Superseded only for S placement by [final revision 2](FINAL_CORONA_2.md).
Named final-1 outputs preserve this revision; the current animation alias and
working-source native asset now use revision 2.

Owner-approved on 2 October 2026: corona draft 02, including irregular connected
filaments, white-ivory/pale-orange shading, expansion before outward flare, then
contraction to a stable bold O. The old corona is removed from the current full
animation and baked working-source asset; historical references remain available.

[Full animation](GuideOS-Eclipse-Boot-Animation.gif) ·
[Stage preview](guideos-boot-eclipse-final-1-stages.png) ·
[Verification](guideos-boot-eclipse-final-1-verification.json)

## Integration

`render_boot_eclipse_final_1.py` loads the original draft 5 sequence, replaces its
corona function with the approved draft 02 and renders all 75 frames at 10 fps.
The isolated draft's emergence-to-O interval maps to 1.5–5.8 seconds in the full
sequence. Its final O remains fixed through the end. Existing planet rotation,
planet fade (2.5–4.5 seconds), letters (5.5–5.8 seconds), background fade
(5.5–7.5 seconds), size and total duration are retained.

The unchanged nebula is cached offline and checked pixel-for-pixel against the
original background source. Every baked RGB565 frame is checked against its GIF
source. Offline NumPy/Pillow dependencies are not added to the target runtime.

Current output: `apps/boot_animation/assets/boot-eclipse-v1.rgb565a`, retaining
the native player's existing filename and format. No player, GPU, service,
deadline, display ownership or handoff logic is changed.

## Preservation and evidence boundary

The pre-change native asset and current-preview GIF were copied into
`build/boot-corona-final-1-preserved/` before replacement. The old native asset's
SHA-256 is `7f565548c3a5d0e37fff9424f03cf70ab4bca8dabc71d3229514de8df12556b1`.
Historical draft and handoff files are retained; they do not override this
subsequently approved corona treatment.

Design approval and offline bake verification do not establish physical
acceptance. No existing release candidate/image or Seed is modified. A future
candidate must include the revised working asset and pass boot/handoff and Deck
acceptance before deployment.

The existing `apps/boot_animation/validate.py` does not pass the current source:
it requires `Before=guide-shell.service`, which is absent from the unchanged
service unit using first-frame readiness/concurrent Home initialization. The
new stream passed the validator's header, timing and size checks before that
service-order assertion failed. No service or validator was altered to mask it;
release integration must reconcile this separate validation mismatch.

Linux-host runner tests (6) and console test (1) pass. An initial Windows run
could not exercise those POSIX-only tests (`fcntl`/`pass_fds`); the Linux rerun
is the relevant result. These tests are not physical display/handoff evidence.
