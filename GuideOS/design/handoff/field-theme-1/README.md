# Field Theme 1 — compilation handoff

Status: approved visual direction and draft set. This package is ready for a separate implementation chat to turn into a staged Debian-shell migration. It is **not** an instruction to flash, install, or replace the current Deck image.

## Goal

Migrate the current Python/Pillow shell toward the approved Field Theme 1 look while preserving its existing behavioral boundaries: system-owned power, provider-owned Wi-Fi and audio operations, shared secret-safe keyboard behavior, and the current low-complexity recovery path.

The active code target is `board/rg35xxh/debian/shell0/`. The reusable production presentation module is `package/guide-ui/`. The current installed renderer remains Paper Theme 0; do not claim Field Theme 1 is live until an explicit candidate is built, tested, and physically checked.

## Approved visual contract

Read `THEME_FIELD_1.md` in this package before implementation. In summary:

- 640x480 four-region frame: dark status strip, light neutral-gray context band, pale cool blue-gray work field, dark control strip.
- Dark translucent content panels on the pale field.
- Inactive panels are muted blue-gray; selection is soft ice blue.
- One amber/orange vertical marker at the selected panel's outer-left edge is the sole warm navigation accent.
- Clean modern sans for ordinary text; monospace only for compact live/technical values.
- No paper texture, illustration, retro ornament, excessive linework, or UI decoration that does not convey state or hierarchy.
- Text must remain readable and clipped/wrapped by the production layout system rather than scaled down to fit.

## Draft assets

The PNGs are visual references, not pixel-perfect specifications or runtime assets:

| File | Screen / state |
| --- | --- |
| `guideos-field-theme-home.png` | Home / Functions, current five active destinations and five intentionally blank grid cells. |
| `guideos-system-field-theme-1-draft-4-dark-stat-panels.png` | System Status. Shows flat blue/white capsule, storage used/available, and connected SSID. |
| `guideos-field-theme-media-library.png` | Media library browsing pattern. Example titles/metadata are placeholders only. |
| `guideos-field-theme-wifi-networks.png` | Wi-Fi network list. SSIDs and signal values are sample data only. |
| `guideos-field-theme-external-card.png` | External-card recognition and Guide folder view. This reflects recognition/browsing only; it does not authorize installation or writing. |
| `guideos-field-theme-power.png` | Safe shutdown confirmation. It must preserve existing independent power and confirmation behavior. |
| `guideos-field-theme-text-keyboard.png` | Shared QWERTY password-entry keyboard. Its literal footer labels are a design fixture only; actual semantic control rules remain in the existing input/keyboard contract. |

## Implementation sequence

1. Read `AGENTS.md`, `THEME_FIELD_1.md`, and `SHELL_UI_SCHEMA_MIGRATION_0.md`.
2. Add Field Theme tokens as a new root-owned validated theme variant; retain Paper Theme 0 and the compiled fallback/recovery presentation.
3. Convert only shared chrome plus Home and System Status first. Derive visible focus geometry and pointer hit rectangles from the same layout result.
4. Produce deterministic 640x480 renders and run the existing shell, keyboard, Wi-Fi, audio, and pointer tests without changing their semantics.
5. Then migrate Wi-Fi, External Card, Power, Media, and the shared keyboard one surface at a time. Do not turn draft values, sample SSIDs, sample media metadata, or unimplemented screens into runtime claims.
6. Build a recoverable candidate only after source/image validation. Physical Deck testing remains separate evidence.

## Critical preservation rules

- A visual state never proves Wi-Fi, storage, audio, or media success without provider acknowledgement.
- Wi-Fi discovery does not grant connection; credential text must not reach snapshots, logs, telemetry, or persistent UI state.
- The external-card page must not mount, install, eject, or write independently; it consumes its brokered status.
- Power confirmation is deliberate and separate from merely opening the Power screen; physical power recovery remains independent.
- Audio/media values must be provider-acknowledged. Do not fabricate queue, duration, output, or playback state from the mockup.
- Empty Home cells remain unassigned; they do not imply hidden features.
- Keep all existing global navigation and control semantics unless a separately approved input change is made.

## Acceptance evidence

Report separately:

1. source and automated test results;
2. host-rendered image verification at 640x480;
3. candidate image/recovery verification;
4. physical Deck observations.

Do not state that the theme is deployed based only on mockups or host rendering.