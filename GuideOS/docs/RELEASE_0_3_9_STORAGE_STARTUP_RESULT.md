# 0.3.9 external-card service startup repair

Installed and fully readback-verified at 11:29:50 UTC on 27 September 2026.
Boot and data partitions match the fresh returned capture exactly. Physical
startup is confirmed: the storage service runs with zero restarts. The owner
confirmed card recognition and media playback after one external-card reinsertion.
A separate boot-time TF2 clock timeout still prevents reliable initial detection.

27 September 2026. The owner reported "External card service unavailable" on
physical 0.3.9. Wi-Fi inspection confirmed active release
`971dd342b7de44c874c23cb70d18e5ce98526be421f7676c6ffd2ddce02e5e1b` and kernel
recognition of the external SDXC card. This failure is separate from the earlier
repeated-insertion TF2 clock-timeout investigation.

## Cause and correction

The installed storage entry point imported `storage_media_runtime` before
`serve()` added `/usr/lib/guideos/ipc` to Python's module search path. That import
failed with `ModuleNotFoundError: No module named 'guide_ipc'`, before card status
could be published. The returned physical boot journal confirms that exact
failure, including repeated service restarts. Earlier media fixtures established
the import path themselves and therefore did not test this startup boundary.

The storage owner now adds its media and IPC dependencies before importing the
media runtime. No service privileges, card mounting policy, or owner data change.
The existing fixed, read-only Wi-Fi inspection now also reports storage/library
and native-player service status and bounded journals. It does not add remote
shell access or expand the shell/input updater's deployment scope.

## Preservation and evidence

- New read-only returned Seed capture:
  `E:/DGttG/private-recovery/release-0.3.9-media-return-20260927-072233/seed-used-region.img`.
  SHA256 `4B24F3D71EF410D0638F147615DF8797D1B9CE096E02AEF47F4B3D92732EB83B`.
- Repair image: `build/release-0.3.9-media/storage-fix/guide-0.3.9-storage-fixed-root.ext4`.
  SHA256 `68DD63934E196F2883B3C9F30E4B1A8900C77D78CAF8F85B955D3A26092F5D19`.
- Whole-filesystem inventory: exactly two existing system files changed;
  28,512 other entries preserved. Notepad remains committed; all owner state
  from the newly returned Seed is preserved. The active shell release is unchanged.
- Source checks: 23 storage tests and 22 diagnostic/link tests passed.
- Installed-image check: actual ARM64 storage entry point starts through systemd
  with production process restrictions and inherited library socket; publishes
  absent-card status and creates cartridge/source sockets. Final test uses the
  repaired image without source overlays or preloaded Python paths. Temporary
  state, host group resolution, and module-loading omissions are fixture setup;
  this test does not prove physical card mounting or playback.
- Filesystem check passed. Physical correction acceptance and Music/Video
  playback remain pending the next Deck boot.

Evidence directory: `build/release-0.3.9-media/storage-fix/`, including
`returned-storage-journal.txt`, `preservation.json`, `service-start.log`,
`filesystem-check.log`, and the guarded writer's installation record.
Regression script: `build/release-0.3.9-media/test-storage-service-start.py`.
Do not use the older image-v7 as a corrected candidate.

## Physical follow-up

Wi-Fi inspection after the repaired boot (`inspect-20260927-073316.json`)
confirms storage/library and player services active, with no automatic restarts.
The kernel timed out updating the TF2 clock before storage started. One external
card reinsertion recovered enumeration; the owner confirmed recognition and
media playback. Follow-up `inspect-20260927-073438.json` records that enumeration.
The owner then explicitly confirmed both Music and Video playback. This is
physical acceptance of basic playback for both players. Seeking, pause/resume,
output switching, removal during playback, and repeated lifecycle behavior are
not inferred from that confirmation. TF2 reliability remains open.
