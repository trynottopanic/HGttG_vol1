# Storage settings UI 0

Status: adopted presentation contract, 27 September 2026. This solidifies the
approved Storage-page draft for the first Settings release. It does not
implement the page, change provider authority, or establish installed behavior.

Reference mock-up: `../design/ui-theme-drafts/guideos-storage-settings-0.png`.

## Structure

The page keeps the shared Guide status strip and uses the established deep
midnight-blue work field, near-black charcoal controls, pale blue OCR metadata,
clean mixed-case sans labels, flat matte surfaces and low-opacity idle icons.
It has no persistent bottom control bar, Home wheel or Shortcut Tray.

The header is `Storage` with route label `SYSTEM / STORAGE`.

The left selection column contains:

1. `Internal storage`
2. `External memory`
3. `Application storage`

The selected row becomes crisp and slightly brighter; idle rows and their seams
remain subdued. The right region contains the selected source's status and
available actions. Complete rows paginate with L2/R2 only when required at the
accepted text size.

## External-memory view

The initial external-memory view shows only provider-confirmed information:

- recognition state;
- filesystem and access mode;
- physical/logical slot identity;
- formatted capacity, without presenting it as used or available space;
- recognized Guide-folder count and names; and
- bounded cartridge-file count with explicit verification state.

The capacity graphic identifies total capacity. It must not use a filled
fraction that implies measured use until the storage owner reports used and
available bytes. Values in the mock-up are fixtures and must be replaced by
live bounded provider data.

Recognized folders are displayed as quiet non-interactive labels. They do not
become buttons merely because they resemble compact panels.

## Boundaries

- The Settings page reads the storage owner's snapshot; it never opens, mounts,
  formats, repairs or detaches a filesystem itself.
- `File browser` is a separate top-level Guide destination for navigating
  user-visible files and folders. `Storage` remains responsible for volume
  status, health and storage policy.
- Formatting, repair, safe eject, file deletion, browsing and package
  installation are absent until their accountable owners expose acknowledged
  operations.
- Unavailable, stale, ambiguous and unsupported states remain visible and
  written. The page does not retain stale successful values as current state.
- Consequential controls added later require explicit confirmation and distinct
  completed, cancelled, uncertain and failed outcomes.

## First implementation acceptance

1. Every displayed value comes from a validated current storage snapshot or is
   explicitly shown as unavailable.
2. Capacity is labeled as total capacity unless used/free values are actually
   reported.
3. The shell cannot gain mount or raw-path authority through this page.
4. External-card removal replaces the prior detail with the confirmed absent
   state rather than leaving stale content.
5. Text remains legible on the 640 by 480 Deck display and no control depends on
   color alone.
