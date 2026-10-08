# Legacy UI refresh 0

Status: first-pass design direction, 27 September 2026. These are replacement
references for later implementation and remain revisable. They do not modify the
current Seed.

The legacy Media, cartridge installer, Wi-Fi detail, power confirmation, running
application surfaces inherit the approved flat near-black status/chrome,
midnight-blue work field, matte panels, pale-blue selected state and absence of a
persistent bottom control legend.

References:

- `../handoffs/guide-ui-home-settings-20260927/media-landing-v1.png`
- `../handoffs/guide-ui-home-settings-20260927/cartridges-landing-v1.png`
- `../handoffs/guide-ui-home-settings-20260927/wifi-detail-v1.png`
- `../handoffs/guide-ui-home-settings-20260927/power-confirmation-v1.png`
- `../handoffs/guide-ui-home-settings-20260927/notepad-running-v1.png`

The current boot animation is retained unchanged and is explicitly excluded from this refresh.

System Status migrates into Settings through Diagnostics and About rather than
remaining a separate top-level destination. Volume, Help/control and text-entry
overlays retain their existing ownership and become compact modal layers using
the same visual tokens; their detailed layouts remain to be designed. Cartridge
agreement, permissions, integrity, progress and recovery states retain their
current explicit semantics and require later state-specific surfaces.
