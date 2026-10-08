# Boot animation: successful rendering and startup timing

The owner reports that the corrected animation played as expected. Read-only
inspection of the returned seed confirms XRGB8888 configuration selection and
subsequent shell startup. Visual playback is accepted by owner observation;
normal animation completion is not yet accepted because the service timed out.

Capture record: `build/boot-animation-1/capture-return.json`.
Evidence directory:
`E:\DGttG\private-recovery\boot-animation1-return-20260925-012953`.
Capture SHA-256:
`CDC76B1989F66ADDFFC59ADFBFAE2D4E8BB9410AE889040DB6FDC05DAD8BCED2`.
Boot ID: `184d2f7508134d35830307c29d8cc4ec`.

## Observed timeline

Times below are journal monotonic timestamps in seconds, not power-button
timings. Bootloader time is not measured. Kernel messages may be ingested after
their original emission; use these milestones without claiming precise driver
execution costs.

| Time | Event |
| --- | --- |
| 6.519 | local filesystems ready |
| 8.025 | framebuffer registration message |
| 8.029 | global udev-settle wait completes |
| 8.386 | animation service starts |
| 9.644 | renderer logs connected 640x480 display on card1 |
| 13.808 | renderer logs matching XRGB8888 EGL configuration |
| 21.554 | systemd start timeout; renderer receives termination and logs handoff=signal |
| 22.090 | animation service marked failed due to timeout |
| 22.184 | shell service started |
| 59.963 | shell stopped cleanly |

The first visible frame is not timestamped by this revision. It comes after
configuration selection, context/surface setup, shaders and texture loading.
Do not label 13.808 seconds as measured time to first frame.

## Interpretation and proposed next work

1. Instrument native startup stages: GBM device/surface, EGL display setup,
   initialization, config selection, context/surface activation, shader setup,
   each asset read/upload and first successful presentation. Separate elapsed
   time from CPU cost where practical. These measurements would run on the Deck.
2. Investigate the 4.164-second display-open to configuration-selection interval
   first. The current logs cannot divide it among GBM initialization, driver
   library loading, EGL and scheduling/storage contention. It precedes texture
   file loading, so repacking the two small assets does not address this interval.
3. Measure the 1.258-second service-start to display-open interval. It includes
   the Python console helper, process and library startup, and DRM discovery.
   A small native console helper is a candidate if measurements justify it; it
   must preserve independent cleanup after renderer termination.
4. Replace global hardware settling with targeted display readiness when doing
   the boot-order work. Do not remove the wait without providing readiness
   handling. On this boot the service started only 0.361 seconds after the
   framebuffer message, so this dependency change alone is not evidence of a
   multi-second improvement. The systemd documentation also discourages waiting
   for unrelated devices:
   https://manpages.debian.org/trixie/systemd/systemd-udev-settle.service.8.en.html
5. If earlier visible feedback is wanted, a static globe on the framebuffer
   while GPU setup proceeds is an optional product choice. That reduces blank
   time but does not make the moving animation start sooner, and still needs
   explicit display ownership and a clean transition.

The twelve-second service timeout includes setup and playback. The successful
visual test still hit it. A follow-up must define bounded initialization and
playback budgets coherently and verify normal handoff rather than merely raising
the timeout and calling that a startup optimization. No runtime or seed changes
were made during this analysis.
