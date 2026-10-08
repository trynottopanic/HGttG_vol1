# Boot animation: first physical failure and format correction

Owner observation: no visible animation during the first Deck test after the
0.3.2 boot-animation installation. The returned seed was captured read-only;
no card changes were made during diagnosis.

## Evidence

Capture: `E:\DGttG\private-recovery\boot-animation0-return-20260925-011127\seed-used-region.img`

SHA-256: `BDA505170C2246ACEF6FC4A9C50767EA73CDF3011326430578617AB66969044D`.
The adjacent `animation-summary.json`, `journal.jsonl` and reports preserve the
diagnostics. Use boot ID and monotonic time: the Deck's calendar clock is stale.

Boot ID: `a19db85e9e1945f59d27532fdb19164a`.

| Seconds after kernel start | Observation |
| --- | --- |
| 8.438 | systemd starts the animation service |
| 13.493 | renderer reports `error=egl-context code=0x3009` |
| 13.643 | buffered output identifies card1, 640x480, connector 51, CRTC 49 |
| 13.991 | animation service fails with exit code 1 |
| 14.037 | shell startup begins |
| 14.400 | shell service has started |
| 51.827 | shell stops cleanly |

The installed native binary, console helper and unit match the intended payload.
The animation was neither missing nor skipped. Graphics initialization failed
before drawing. The old combined error check covers context creation, surface
creation and making the context current; it cannot isolate which call failed.
No console-helper failure appears in this boot's journal.

## Defect and bounded correction

The code creates a GBM surface with `GBM_FORMAT_XRGB8888`, but previously accepted
the first EGL configuration returned without checking `EGL_NATIVE_VISUAL_ID`.
Those formats must match. The
[Khronos GBM platform specification](https://registry.khronos.org/EGL/extensions/KHR/EGL_KHR_platform_gbm.txt)
specifies `EGL_BAD_MATCH` for mismatched formats and illustrates selecting a
configuration with an exact native visual match.

That defect is confirmed in the source and is consistent with the device error.
The precise failed call and the device's chosen old format remain unproven.
The correction enumerates configurations and chooses XRGB8888 explicitly,
fails cleanly when none is compatible, logs the selected format, and reports
context creation, surface creation and activation failures separately. Standard
output is line-buffered so journal order reflects execution order.

The graphics setup API, assets, service ordering, console helper, shell and all
user controls remain unchanged. This is a correction within the bounded boot
probe, not a migration of the shell to GPU rendering.

## Validation and next physical test

The corrected image was installed with owner approval on 2026-09-25 at
05:24:34 UTC. Full root readback matched SHA-256
`239F704DC1EE614258FBFD600DBD92C1C0CFAD5D9C4F1E68F7F96B740F60A0E5`;
boot and data were verified unchanged against the returned-seed capture.
Evidence is in `build/boot-animation-1/installation.json` and `seed-install.txt`.
The pre-installation validation record remains a snapshot of that earlier stage.

The ARM64 build passes. Wrapped-library tests exercise a nonmatching first
configuration followed by a matching one, no match, zero configurations, failed
enumeration, and failed attribute lookup. Existing page-flip timeout,
interruption and argument tests also pass. These tests do not emulate the GPU.

`build/boot-animation-1/validation.json` records the offline image checks. The
candidate is based on the latest returned root, preserving current state; a
full filesystem content/type/ownership/mode comparison must show only the
animator binary changed. The original failed image and captured logs are kept.

The owner subsequently confirmed visible playback on the Deck. The returned
logs show the format error is gone, but the service still ends on its outer
timeout. Visual playback is accepted; normal completion remains unresolved.
See [successful boot timing](BOOT_ANIMATION_TIMING_1.md) for measurements and
the next optimization priorities.
