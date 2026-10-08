# GuideOS 0.4.2

Owner-authorized consolidation of the boot, browser, and media repairs. Signed release sequence 59, based on the freshly returned r23 Seed at sequence 58. Later revisions use `0.4.2.01`, `0.4.2.02`, and sequential two-digit suffixes; the manifest, visible System Info, and source `VERSION` must agree.

## Behavior changes

- Home initializes and composes its first frame while the approved boot animation plays. The animation presents alone until its process releases DRM. Home then opens the framebuffer and writes its prepared frame while the console stays in graphics mode. Home inherits the pre-boot terminal mode for cleanup; failed handoff restores the console after a bounded wait. Older shells retain the serial startup path when selected for rollback.
- Browser service startup claims its dedicated tty2 immediately, bounds each terminal switch to three seconds, and bounds service startup to fifteen seconds. The unprivileged browser account, PAM/logind seat setup, sandbox, and return to tty1 remain.
- B from video stops playback and returns to the originating selection list or file folder. File Explorer retains its folder, pagination, and focus; its details tray closes when playback opens. Menu retains its explicit Home behavior. B from music restores its originating list or page while preserving the existing music playback behavior.
- Media removes textual volume controls and repeated volume metadata. Physical volume buttons and the volume overlay remain available. A failed or completed video uses a Video status screen rather than a Music player screen.
- Video prefers GPU presentation for conversion and scaling with simple bilinear filters, while retaining the software DRM renderer as a fallback. Software codec decoding remains; this release makes no hardware-decoder claim. Decoder threads are bounded to three on the four-core Deck.
- Decoder IPC startup allows eight seconds, within the frontend's twelve-second request budget. Guide's bounded buffering policy now owns pause/resume thresholds, avoiding a second independent cache-pause controller. Media refresh runs at four times per second, and pause commands are sent only on changes.
- Media startup failures record their phase and exception class without source paths. Periodic playback records renderer, dropped frames, A/V offset, and buffer underruns. Full diagnostics include service pre-start/stop-post commands, control PID, and startup timeout.

## Diagnosis and evidence

The supplied full capture and fresh Seed journal show r23 loaded uinput and created the virtual browser controls. The browser then stalled in service pre-start setup for 25 seconds without launching Weston or WebKit. Terminal ownership blocking is the leading inference; the older capture omitted the pre-start process state. See `BOOT_HANDOFF_BROWSER_STARTUP_FIXES.md` for the precise timestamps and source reference.

The returned Seed's installed player used software DRM scaling, independent mpv and Guide cache-pause logic, and a two-second IPC startup budget. A recovery restart is recorded at approximately 327 seconds; later playback consumes 191.1 MiB at peak. The older backend discarded decoder stderr and did not record its open exception, so the initial video's exact failure and physical frame rate cannot be established from those logs.

The installed mpv was queried for supported outputs and option names without playing media. It supports GPU and DRM outputs and all selected configuration options. The mpv manual documents DRM's software scaling and the GPU output/context options: https://mpv.io/manual/stable/. Support does not prove the optimized path renders smoothly on this Deck.

## Verification and installation evidence

Evidence is in `build/release-0.4.2/seed-current-audit` and `build/release-0.4.2/candidate`.

The candidate was built from the fresh connected Seed capture. Owner state, home directories, network credentials, Guide configuration, SSH identities, and retained root logs were compared before and after and match. The data partition is separately captured and excluded from the write. The existing uinput module, kernel, boot assets, and boot partition are unchanged.

Signature and payload checks, Python source compilation, ARM runtime imports, target systemd configuration verification, filesystem integrity, and independent bounded root-file inventory passed. No test suites or physical playback experiments were run. The installer requires the connected Seed's root, boot, data, and checked tail hashes to match this capture before writing only the 2 GiB root partition. Its receipt records the complete readback and post-write preservation hashes.

Physical acceptance remains pending: boot without the terminal flash, open Browser, start video on the first attempt, return to the same selection folder with B, and assess frame pacing. Installation readback is distinct from those checks.

## Verified Seed write

The root-only installation completed with status `GUIDE_0_4_2_ROOT_READBACK_VERIFIED`. The complete 2 GiB readback matches `6CCE18A7B574DA11B12595E173B8C01BD22A8F1EB1B2ED2316BD29042A2FAE7F`. The partition table/boot region, data partition, and checked tail were rehashed after installation and remain unchanged. Receipt: `build/release-0.4.2/candidate/installation.json`. The installed version is `0.4.2`; physical acceptance remains pending.
