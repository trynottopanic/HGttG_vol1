# Notepad and media image handoff 0

26 September 2026. Based on the freshly returned Seed, not an older candidate.
Status: installed on the Seed and fully readback-verified at 22:48 EDT.
Boot and data regions verified unchanged.
Physical acceptance: pending.

## Included

- Internal-draft Notepad cartridge preview and its shared application-host/editor
  support. The cartridge is available as `build/notepad-0/Notepad-cartridge.zip`.
  It is also retained under `/usr/share/guideos/cartridges/` in the image without
  automatically installing it or granting capabilities.
- Geometric Home D-pad navigation and working power-confirm selection.
- Faster pointer engagement, smoothing and changed-region framebuffer updates.
- Single three-state Wi-Fi bars icon.
- L2/R2 previous/next Home pages with a 200 ms horizontal slide; ten icons per
  page, no wrapping. A single page remains stationary.
- Future Planning Media Engine steps 1–4 source handoff: provider grant socket,
  storage-owned media catalog lifecycle, audio/video adapter modules, bounded
  GStreamer buffering and pinned mpv 0.40.0-3+deb13u1 for ARM64.

The dynamic boot animation and other already accepted returned-Seed changes are
preserved. The immutable shell release and installed files match the tested
source: `21894f4a9310ff577eb7ebe8ca5cde69f9e5f058487122a3513936d4c7842fab`.

## Integration fixes and evidence

The capability broker now identifies inherited listeners by their actual socket
paths; systemd does not promise the assumed order across the two socket units.
The live fixture starts all three control/health/provider listeners.
The media installer now includes its shared grant and generated-interface imports.
mpv replies use request IDs and a bounded persistent buffer, so unsolicited events
and combined/fragmented reads cannot be mistaken for a command response.

Passed:

- 321 UI/input/shell/IPC/storage/installer tests, 320 passing and one existing skip.
- Eleven Notepad tests and four shared editor interruption tests on ARM64.
- Actual installed GStreamer buffer/drain fixture and five audio-buffer tests.
- Actual installed ARM64 mpv JSON IPC, pause/seek and bounded stop fixture, using
  null video/audio outputs; this does not test the Deck display or audible output.
- Twenty-two media tests; Foundation C, sanitizer, codec and systemd adapter
  checks plus nine application-runtime tests and generated-registry validation.
- Live systemd application, installer, unhealthy-update rollback, removal,
  retained-data/reinstall and explicit deletion tests. Actual Notepad installation
  then cartridge removal, internal save/relaunch, keyboard/Home recovery and
  uninstall-retained-draft checks all passed.
- Installed layout/source hashes, service verification and a clean filesystem check.

Root image SHA256:
`2937DB8AD22E4FBD2CD5D69F1C2A5CA384182A4266019BFA1C00280B9874E581`.

The fresh recovery capture and region hashes are recorded in
`build/notepad-media-0/install/prewrite.json`. The full file/metadata audit is
`preservation.json`: current owner data, deployment credentials, network/audio
settings, Bluetooth state, SSH identity, machine identity and fstab are retained.
Only cached package archives were removed; all 167 have matching external
recovery copies and hashes. Boot and data partitions are not write targets.
Available application space is 414 MiB with the existing 118 MiB reserve intact.
mpv adds 155,929 KiB of package contents; versions and complete dependency hashes
are retained in `build/notepad-media-0/`.

## Remaining boundaries

Notepad currently implements internal drafts, not external document open/export
or the complete document presentation. See `NOTEPAD_INTERNAL_DRAFT_0.md`.
The external cartridge card was not connected to the PC; no unidentified drive
was written. Extract the delivery ZIP onto the existing Guide external card.

The media handoff contains engines, contracts and broker modules, not a finished
Media Library/Media Session service deployment or player UI. The storage owner
constructs its catalog; a public media endpoint and media-session daemon are not
yet wired. The existing audio service uses the updated buffering. A video player
cannot be opened from the shell just because mpv and its adapter are present.
Provider group access is given to the existing trusted audio account only, not
to installed applications. The application SDK still needs the media-specific
capability integration before a cartridge can use the new session interfaces.

Deck acceptance still requires boot; physical cartridge install and removal;
Notepad typing/save/relaunch and interrupted-edit recovery; pointer response;
Home/power D-pad; Wi-Fi states; and paging when enough icons exist. Audio needs an
audible start/seek/underrun check. Future video acceptance needs DRM acquisition
and restoration, startup buffering, dropped frames, A/V offset, Power response,
memory/CPU and temperature measurements. None is inferred from the image tests.

## Physical follow-up

The owner confirmed boot and package preview, but repeated external-card
reinsertion and Notepad installation failed. See
[CARD_INSTALL_PHYSICAL_FOLLOWUP_0.md](CARD_INSTALL_PHYSICAL_FOLLOWUP_0.md) for
returned-Seed logs, the Supervisor authentication correction and the separate
MMC controller clock-timeout evidence. Notepad installation is not physically
accepted; the original host/image tests did not cover an idle first launch.

## Subsequent physical result

The owner confirmed installation and the first-note test succeeded. Returned
logs confirm a committed release, successful health check, normal launch and
durable checkpoint. An additional cold-service startup failure and misleading
uninstalled-record display remain; see
[Notepad physical result](NOTEPAD_PHYSICAL_RESULT_0.md). The latest returned Seed
was read only. Repeated external-card reinsertion remains unresolved.
