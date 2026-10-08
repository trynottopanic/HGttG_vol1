# System settings first-release scope 0

Status: implementation-facing design audit, 27 September 2026. This document
defines settings that can be exposed by reusing current GuideOS providers or by
adding a small bounded adapter around an existing operating-system facility. It
does not claim that the new Settings interface is implemented or installed.

## Approved visual references

Approved 27 September 2026 for implementation-facing design work. These are
presentation references only; they do not establish installed behavior:

- `../handoffs/guide-ui-home-settings-20260927/system-settings-landing-v2.png`
- `../handoffs/guide-ui-home-settings-20260927/settings-audio-v1.png`
- `../handoffs/guide-ui-home-settings-20260927/settings-connections-v1.png`
- `../handoffs/guide-ui-home-settings-20260927/settings-storage-v2.png`
- `../handoffs/guide-ui-home-settings-20260927/settings-power-v1.png`
- `../handoffs/guide-ui-home-settings-20260927/settings-diagnostics-v1.png`
- `../handoffs/guide-ui-home-settings-20260927/settings-about-v1.png`

## Decision

The first Settings landing page should expose six useful destinations:

1. `Audio`
2. `Connections`
3. `Storage`
4. `Power`
5. `Diagnostics`
6. `About`

`Display`, `Accessibility`, broad `Device` preferences, Pocket Mode and system
updates remain future destinations until their setting owners and persistence
contracts exist. The interface should not present inactive switches merely to
look complete.

## Available through current providers

### Audio

The current audio service already owns persistent volume and output selection,
output discovery, a bounded audio test, playback state and Bluetooth-audio
discovery and connection.

| Setting or action | Initial presentation | Existing authority |
| --- | --- | --- |
| Master volume | Adjustable value from 0 to 100 in existing five-point steps | Audio service `volume` request |
| Current output | Selected output plus available output list | Audio service `output` request |
| Test selected output | Start/stop test with current volume and route visible | Existing audio test |
| Bluetooth audio devices | Scan, pair/connect, disconnect and cancel | Existing audio Bluetooth actions |
| Playback state | Read-only track, playing/paused/stopped, position | Audio status snapshot |

The settings surface must reuse the audio service rather than invoke PipeWire,
WirePlumber, ALSA or Bluetooth tools directly. An output that disappears stays
visible long enough to explain the loss, and the current pause-on-output-loss
behavior remains authoritative.

### Connections

The current Wi-Fi service already supports bounded discovery, saved and active
state, connection, switching, explicit disconnection, cancellation and removal
of saved credentials.

| Setting or action | Initial presentation | Existing authority |
| --- | --- | --- |
| Current Wi-Fi link | State, network name and cached signal | Wi-Fi status snapshot |
| Nearby networks | Rescan and bounded network list | Wi-Fi `scan` request |
| Join or switch | Open/saved/password-protected connection flows | Wi-Fi `connect` request and existing secret editor |
| Disconnect | Disconnect and pause automatic reconnection | Wi-Fi `disconnect` request |
| Forget saved network | Consequential confirmation, then remove credentials | Wi-Fi `forget` request |
| Bluetooth audio | Link to the same device owner shown under Audio | Audio Bluetooth provider |

The page must preserve the current distinctions between available, saved,
active, unsupported, busy and cleanup-unconfirmed states. It must not imply
that general Bluetooth peripherals or Guide Node discovery already exist.

### Storage

The current storage owner recognizes the dedicated external slot without giving
the shell mount authority. It reports presence, recognition state, filesystem,
capacity, Guide folders and a bounded cartridge count.

The adopted first-release presentation is specified in
[`STORAGE_SETTINGS_UI_0.md`](STORAGE_SETTINGS_UI_0.md). File browsing is a
separate top-level Guide destination and does not grant the Settings renderer
mount or filesystem-navigation authority.

| Setting or action | Initial presentation | Existing authority |
| --- | --- | --- |
| External-card state | Absent, checking, Guide layout, incomplete, ordinary, invalid or unsupported | Storage status snapshot |
| Filesystem and capacity | Read-only filesystem and formatted capacity | Storage status snapshot |
| Guide folders | Read-only recognized top-level folders | Storage status snapshot |
| Cartridge inventory | Read-only bounded unverified count | Storage status snapshot |
| Rescan | Not initially exposed; insertion/removal already drives recognition | Storage owner |
| Safe eject | Deferred until the storage owner has an acknowledged detach operation | Not implemented |

Internal free space and per-application use may be added as a small read-only
adapter, but they should not be fabricated from external-card capacity. File
management, formatting and installation remain outside the first Settings page.

### Power

The Deck already exposes battery capacity and charging state through the status
bar, and both the physical Power key and the shell's confirmed Power Off path
reach orderly system shutdown.

| Setting or action | Initial presentation | Existing authority |
| --- | --- | --- |
| Battery state | Read-only percentage and charging/discharging state | Power-supply sysfs reader |
| Power off | Written confirmation followed by orderly shutdown | Existing shell/logind path |
| Restart | Small addition using the same confirmation and independent system owner | systemd/logind adapter to add |
| Screen timeout | Deferred | No accepted display/power owner |
| Pocket Mode | Deferred | No implemented policy owner |
| Performance profile | Deferred | No implemented resource-policy owner |

The physical Power key remains independently effective if the shell fails. The
new interface must not replace that path until it proves equal independence and
bounded response.

### Diagnostics

The existing diagnostics service and shell status sources can populate a useful
read-only page without granting Settings arbitrary command execution.

| Information | Initial presentation |
| --- | --- |
| Service health | Active/failed/unavailable summary for known Guide services |
| Resource summary | Current bounded CPU, memory and process information already collected by diagnostics |
| Connectivity and audio | Provider state and recent bounded error summary |
| Storage | External-card service state |
| Recent events | Small sanitized recent-event view; no unbounded journal browser |
| Controller test | Link to the existing bounded input diagnostic where present |

Exporting diagnostics to external storage is deferred until Storage exposes an
acknowledged write operation for this purpose.

### About

About is read-only and assembled from installed identity rather than example
values:

- GuideOS release/build identity;
- board and hardware profile;
- kernel version;
- boot-world generator and current three-word world name when available;
- licenses and source-information entry;
- installed component versions where bounded metadata exists.

The landing-page mock-up's `GuideOS 0.3.9` and capacity figures are visual
fixtures, not values to hard-code.

## Low-effort additions allowed in the first implementation

These additions use existing operating-system facilities but still require a
small accountable adapter, validation and tests:

1. Restart with the same confirmation/outcome handling as Power Off.
2. Internal filesystem total/free-space reporting through a bounded read-only
   system-status adapter.
3. Installed build, board profile and kernel identity through bounded reads.
4. A sanitized service-health summary restricted to an allowlist of Guide
   units; Settings must not become a general systemd controller.
5. The current boot-world words and generator version from validated world
   metadata, with `unavailable` when fixed fallback was used.

## Explicitly deferred

- Brightness adjustment and display blanking until the physical panel exposes a
  verified backlight/control path.
- UI scaling and text-size changes until the renderer supports reflow under a
  shared setting rather than per-screen constants.
- Reduced motion until every affected transition has a deterministic fallback.
- Pocket Mode, suspend and background-work policy until a power owner can
  coordinate audio, networking, display and applications.
- General Bluetooth input/peripheral management; the current provider owns
  Bluetooth audio only.
- Guide Node discovery and trust management until those services exist on Deck.
- Safe eject, formatting and repair until the storage owner exposes explicit,
  acknowledged operations.
- System-update controls until the signed-bundle consumer and recovery path are
  implemented and integrated.
- Language, locale, time-zone and clock mutation until text resources and a
  bounded time configuration owner exist.
- Theme and palette selection while the current visual system is still being
  established.

## Interaction contract

- A row always shows the last confirmed state, not merely the requested state.
- A pending action identifies what is pending and remains cancellable where the
  provider supports cancellation.
- An unavailable provider produces a useful unavailable state; its controls do
  not disappear or retain stale authority.
- Destructive or disruptive actions use an explicit confirmation surface and
  report completion, cancellation, uncertainty or failure separately.
- Settings consumes existing provider sockets and status snapshots. It does not
  duplicate Wi-Fi, audio, storage or power ownership inside the renderer.
- L2 and R2 paginate only when the active Settings page cannot fit complete
  semantic rows at the accepted text size.
