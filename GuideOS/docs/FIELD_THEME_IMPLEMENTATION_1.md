# Field Theme 1 implementation and combined seed update

Installation update, 26 September 2026: readability and boot-preparation correction written and fully readback-verified. Boot/data unchanged. Physical retest pending. See [latest handoff](RELEASE_0_3_7_HANDOFF.md). Earlier evidence follows.

Owner verification, 26 September 2026: boot and external-card recognition succeeded. Field text is too small except the status strip; readability acceptance failed. The owner also reports the old fixed landmass and no stars. Dynamic animation remains unaccepted. See [readability correction](READABILITY_CORRECTION_0.md).

Status: root partition written and fully readback-verified on 26 September 2026.
Physical Deck boot/readability acceptance is pending. Visible release: 0.3.7.

## Source and scope

The owner requested the handoff from **Musings**, integration with the dynamic
boot sequence and all changes not yet on the card, and a seed write. The handoff
at `design/handoff/field-theme-1/README.md` was approved visual direction, not
compiled code. This change implements that direction in the existing supervised
Python/Pillow shell. Existing semantic controls and provider requests remain.

The shared `guide_field_ui.py` renderer loads the new root-owned `field-1` token
variant. Four screen regions use dark status/control strips, a neutral context
band, a pale work field and muted blue-gray panels. Ice-blue selection has one
amber left marker. Text uses existing Unicode shaping and bounded clipping at
fixed role sizes. Home has five active cells and five unassigned blank cells.
System Status includes the flat blue/white capsule and actual storage, memory
and acknowledged Wi-Fi state. Host previews show emulation-host measurements;
they are not Deck hardware observations. Unavailable values remain explicit.

Home, System Status, Wi-Fi list/detail/forget/working views, Media views,
External Card and Power use shared visual/hit geometry. The shared keyboard
retains its editing model, masks and control meanings with modern sans text and
Field colors. Private editor mode returns no shell menu targets and preserves
the theme across background pointer refreshes. Pointer-only repaint keeps the
existing bounded frame cache; credentials never enter that cache.

The existing Paper Theme manifests and compiled recovery presentation remain.
`50-field-theme.conf` selects Field mode; removing that drop-in restores the
Paper presentation on restart. UI drawing does not own devices, mounts, audio,
connections or shutdown. No mockup SSID, file title, queue or invented action is
installed. The older migration plan's list fixture yields to the newer approved
Home grid; available destinations and D-pad order are unchanged.

## Combined contents

- Field Theme 1 and its seven visual surface families.
- Dynamic seeded terrain, cloud-atlas weather, detailed ocean and 12 faint stars.
- Read-only TF2 Guide recognition with matching exFAT/UTF-8 kernel modules.
- Transient left volume display, outlined circular pointer and Wi-Fi link/strength indicator.
- Previously working speaker corrections and five-second System Status Audio test preserved.

Future Planning's shared Envelope/Supervisor/broker work was not pulled into this
visual/card update. External Card continues recognition only; it does not install
or write cartridges.

## Evidence and installation

All 415 regression tests passed on the freshly rebased image, plus 14 boot tests.
Integration checks rendered all seven surface families and four Wi-Fi states,
checked exact visual/hit rectangles, dispatched a Home target, verified blank
cells have no actions, checked password masking and editor target isolation,
and rechecked volume fading and Wi-Fi status states. The globe executable is
byte-identical to the previously validated native starfield renderer. Every
final payload entry was verified before writing. Physical GPU timing, display
readability and real TF2 recognition remain separate pending observations.

A fresh 3,490,709,504-byte read-only capture precedes the update. The root image
was rebased onto that capture, preserving 23,483 existing files and links
outside the payload, including owner state, credentials and audio settings.
The shell bundle was repackaged against the actual installed release; that
release is retained as `previous.json`. There was no repeat volume migration.

Installed root SHA256: `9C0785BD2808BED4FB0A9662FC1E30B6693966F075EE269C88033A606D0FD942`.
Active shell: `c0a260703aa22378fc5db547c979a76e2f5f61f8ec69939e3a548d3cf21eac20`.
Records: `build/field-theme-install/install/installation.json`, `candidate.json`,
`prewrite.json`, `final-audit.json` and `seed-install.txt`.
Recovery: `E:/DGttG/private-recovery/field-theme-return-20260926-030058/seed-used-region.img`.

The writer verified card identity, layout and current region hashes, wrote only
the root partition, closed/reopened the device and verified the complete root
readback. Boot and data partition hashes remained unchanged. Prior candidates
and captures remain intact. No physical boot result is implied by readback.
