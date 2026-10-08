# Guide shell UI schema migration 0

Status: working implementation plan requested 25 September 2026  
Target: the supervised minimal-Debian shell under
`board/rg35xxh/debian/shell0/`  
Foundation: `DESIGN_SCHEMA_0.md`, `TYPOGRAPHY_0.md`, Paper Theme 0, Guide View 1

## Objective

Apply the reusable Guide Design Schema to the existing shell menus without
changing their authority, input meanings, provider behavior, or lifecycle as a
side effect of visual migration. The result should make every shell surface look
like one system, derive drawing and hit geometry from one layout model, and make
future screens cheaper to add and easier to verify.

This plan targets the current Python/Pillow Debian shell. The older C/Buildroot
shell remains historical implementation evidence and is not the migration
target. No physical card or installed Deck is changed by this plan.

## Existing surfaces in scope

| Surface | Current variants | Migration pattern |
| --- | --- | --- |
| Home | Feature-dependent list | `standard-menu` with five-row window and proportional scrollbar |
| System Status | Bounded status rows | `facts-status` |
| Power | Confirm and cancel | `confirmation`, preserving separate deliberate confirmation |
| Wi-Fi discovery | Idle, scanning, ready, empty, failed | `service-list` plus visible state notice |
| Wi-Fi control | List, detail, forget, working | `service-list`, `details`, `confirmation`, `progress` |
| Wi-Fi editor | Shared keyboard | Existing keyboard pattern restyled through shared tokens separately |
| Audio | Player, files, outputs, Bluetooth | `media-player`, `standard-list`, and `service-list` |
| Pointer overlay | Pointer, hover, small/expanded context menu | Theme-aware overlay above the owning screen |
| Status bar | Battery and system notices | Shared shell chrome, never application-owned |
| Missing-provider and failure views | Media unavailable, radio unavailable and errors | `empty`, `unavailable`, `warning`, and `error` states |

## Runtime architecture

The design fixture under `design/schema/` must not be imported directly by the
installed shell. Promote its reusable subset into a small installed `guide-ui`
module with these responsibilities:

1. Load root-owned token and component manifests once at shell startup.
2. Validate schema version, display profile, references and geometry before the
   first frame is presented.
3. Resolve Typography 0 roles through the existing Unicode/Pango provider, with
   the documented DejaVu reduced-profile fallback.
4. Produce bounded layout objects containing draw instructions, focus order and
   hit rectangles.
5. Draw shared chrome and components onto a caller-owned Pillow surface.
6. Retain no application history, credentials, playback authority, network
   authority or device handles.

The shell continues to own the framebuffer, input, page history and global
controls. `AudioPanel` and `WiFiPanel` continue to own their local view state and
provider requests. They provide semantic rows and acknowledged status to
`guide-ui`; they do not choose fonts, colors, or coordinates.

The manifests remain inspectable TOML. They are parsed and validated once, not
once per frame. The installed copies are part of the signed/transactional system
release and are not application-writable theme files.

## Shared component set for the first migration

Promote and complete these components before converting individual pages:

- `application_header`: identity, page title, and text/battery accessory;
- `application_footer`: semantic action hints and text/battery accessory;
- `menu_list`: stable row identity, selected/disabled/busy states, bounded text,
  five-row viewport and proportional scrollbar;
- `button_badge`: physical or semantic button plus action label;
- `notice`: neutral, stale, offline, success, warning and error variants;
- `facts`: bounded label/value rows, with `numeric` typography where appropriate;
- `details`: title, metadata and bounded action list;
- `confirmation`: effect, consequence, confirm and cancel actions;
- `progress`: determinate/indeterminate state and optional cancellation;
- `empty_state`: explanation and available recovery action;
- `media_transport` and `media_queue`: the existing Audio Player 1 pattern;
- `scrollbar`: proportional thumb derived from total, first visible and visible
  count;
- `focus_overlay`: visible focus/hover without changing the component's meaning.

Every interactive component returns its final hit rectangle and stable identity.
`MenuInput.targets()` must consume those rectangles instead of repeating a
second set of hand-written coordinates. This is the critical integration rule:
what the person sees and what the shell activates must be the same layout.

## Semantic screen model

Each shell page should create a bounded local model similar to:

```python
ScreenModel(
    pattern="standard-menu",
    title="Wi-Fi",
    state="current",
    items=[MenuItem(id="network:<stable-id>", label="Example", detail="72% WPA2")],
    focus_id="network:<stable-id>",
    actions=[Action(id="open", button="A", label="Open")],
    notice=Notice(kind="neutral", text="Nearby networks"),
)
```

This is an internal typed model, not Guide View wire JSON and not application
authority. Stable identities preserve focus across provider refreshes. The
renderer clips, wraps, paginates or scrolls according to the component contract;
it never shrinks Typography 0 roles to force content into a box.

## Migration sequence

### Stage 0 — freeze evidence

- Record current host-rendered images for every page and panel state.
- Record current focus identities, hit rectangles and button outcomes.
- Run the existing shell, Wi-Fi, audio, pointer and keyboard suites unchanged.
- Add fixture states for empty, loading, populated, stale, unavailable, warning
  and error cases before replacing their drawings.

Acceptance: the behavioral baseline is explicit, including known defects; image
fixtures are not represented as physical evidence.

### Stage 1 — install the runtime foundation

- Create the production `guide-ui` module and install the schema manifests with
  the Debian shell package.
- Move Paper Theme colors, Typography 0 roles, spacing and component metrics out
  of individual shell files.
- Adapt `Screen._text`, `text_width` and Unicode rendering behind one text API.
- Add a startup validation failure screen using compiled safe constants so a
  malformed theme cannot leave the Deck blank.

Acceptance: one validated theme instance is loaded per shell process; missing or
invalid manifests produce a readable recovery screen and leave Power recovery
independent.

### Stage 2 — shared chrome and passive pages

- Migrate header, footer, battery/status accessories and notice components.
- Convert System Status first, then missing-provider and empty/error screens.
- Convert Home to `standard-menu`, including the accepted five-row window,
  mixed-case labels and proportional scrollbar.

Acceptance: content and navigation results remain unchanged; the header/footer
and type roles match the deterministic Schema 0 fixtures at 640 by 480.

### Stage 3 — geometry-coupled input

- Have the layout result expose stable interactive regions.
- Replace duplicated rectangles in `guide_menu_input.py` with regions from the
  current rendered model.
- Preserve D-pad order as semantic item order, regardless of pointer position.
- Retheme pointer, hover and radial context-menu overlays without changing their
  timing, stale-target checks, privacy behavior or action filtering.

Acceptance: snapshot tests verify visible bounds equal hit bounds; every action
remains reachable through D-pad/A/B; provider refresh cannot redirect a pending
action to another stable identity.

### Stage 4 — power and Wi-Fi

- Convert Power to the shared confirmation pattern without weakening the second
  explicit confirmation or independent systemd-logind Power behavior.
- Convert Wi-Fi list, details, forget and working states one at a time.
- Keep credential text entry in the shared keyboard and never put entered or
  masked secrets into snapshots, telemetry, the schema, or persistent UI state.
- Preserve busy-state cancellation, saved/active distinctions and current
  connection acknowledgements.

Acceptance: existing provider and cancellation tests pass; destructive and
connection actions are visually distinct; focus survives list refresh by stable
network identity; a visual state never implies connection before acknowledgement.

### Stage 5 — audio

- First restyle the existing AudioPanel views without changing their current
  service contract or inventing unavailable metadata.
- Use the approved audio-player pattern only for fields the service actually
  acknowledges: state, position, duration, output, volume and current item.
- Keep files, outputs and Bluetooth devices as schema lists/details.
- Add queue rows only after queue identity and metadata exist in the audio
  provider; the current three-row design fixture is not evidence they exist.
- Preserve playback when leaving the screen and visibly distinguish pending,
  unavailable, paused, playing and failed states.

Acceptance: every displayed playback transition follows provider state; leaving
the page does not stop audio; output loss and service loss remain visible; no
schema renderer sends audio requests itself.

### Stage 6 — consolidation and installation candidate

- Remove obsolete per-page colors, fonts and geometry after each replacement has
  equivalent tests; do not perform a single large deletion before comparison.
- Produce deterministic reference images for all migrated states.
- Measure full redraw and pointer-only redraw cost under ARM64 emulation.
- Build a recoverable Debian candidate through the existing deployment path.
- Only then perform physical Deck testing.

Acceptance: no old page renderer remains on the normal shell path; startup,
navigation, text entry, audio, Wi-Fi and orderly shutdown survive repeated use;
performance and physical readability are reported separately from source/image
checks.

## Page-by-page behavior preservation

| Page | Must remain true during migration |
| --- | --- |
| Home | Feature flags determine available destinations; Menu returns here. |
| Status | Values remain bounded and do not claim unavailable providers. |
| Power | Entering the page does not shut down; confirmation is a separate input. |
| Wi-Fi | Discovery does not grant connection; busy operations and cancellation remain explicit. |
| Wi-Fi editor | Secret characters never reach ordinary drawing, logs or snapshots. |
| Audio | Requests remain tokened and acknowledged; UI state does not manufacture success. |
| Pointer/context | Stable target identity and stale-action rejection remain intact. |
| Global shell | Display/input ownership and independent Power recovery do not move into the schema. |

## Verification matrix

### Source and host-rendered evidence

- Manifest and model validation, including unknown tokens, invalid bounds and
  unsupported variants.
- Golden 640 x 480 images for every fixture state.
- Layout tests for clipping, long ASCII, shaped Unicode, right-to-left text,
  missing glyphs and maximal bounded lists.
- Equality tests between rendered interactive regions and MenuInput hit targets.
- Focus preservation across inserted, removed and reordered stable items.
- No secret text in captured draw calls, snapshots, reports or exceptions.
- Existing audio, Wi-Fi, shell, keyboard and pointer suites.
- Dirty-frame and pointer-cache measurements; no manifest parsing in the frame
  loop.

### Physical acceptance

- Native readability and contrast at several brightness levels.
- D-pad, stick pointer, radial menu and keyboard behavior across every page.
- No mismatch between visible focus and activation area.
- Audio playback and Bluetooth behavior while navigating away and returning.
- Wi-Fi refresh, connection, cancellation and credential flows.
- Repeated confirmation/cancellation and physical Power during each major state.
- Frame latency, CPU, memory and idle wakeups compared with the current shell.

## Principal risks

1. **Visible/hit geometry divergence.** Prevent it by deriving both from one
   layout result, not matching constants by convention.
2. **Visual migration accidentally changing behavior.** Keep panel state and
   provider requests intact until the page has visual parity and tests.
3. **Unicode regression.** Route all schema text through the existing shaping
   provider rather than Pillow's ASCII-oriented development proxies.
4. **A malformed external theme blanking the shell.** Install root-owned,
   validated manifests and retain a compiled recovery presentation.
5. **Audio mockup outrunning service data.** Render only acknowledged fields and
   defer queue behavior until the provider contract supplies it.
6. **Pointer overlays obscuring new footer controls.** Reserve overlay-safe bounds
   and rerun the accepted context-menu visibility and input tests.

## First implementation slice

The first code change should implement the production token loader, Typography 0
resolver, shared header/footer, `standard-menu`, scrollbar and a layout-result
hit-region API. Apply it only to Home and System Status. This gives useful visual
coverage and proves the renderer/input geometry boundary without first touching
credentials, shutdown, or live playback.
