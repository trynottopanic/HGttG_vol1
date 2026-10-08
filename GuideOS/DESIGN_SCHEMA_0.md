# GuideOS Design Schema 0

Design Schema 0 is the renderer-neutral presentation contract for Paper Theme 0.
It lets current and future applications reuse one visual language without giving
the theme control over application behavior, resources, files, or devices.

The initial implementation is a deterministic design fixture under
`design/schema/`. It proves schema composition and image output on a development
host. It is not yet the production framebuffer renderer and does not establish
physical Deck acceptance.

The staged plan for promoting this work into the current Debian shell is recorded
in `SHELL_UI_SCHEMA_MIGRATION_0.md`.

Field Theme 1 is the accepted visual direction for new concept work, recorded in `THEME_FIELD_1.md`. It is not yet a replacement renderer or a claim that Paper Theme 0 has been migrated on the Deck.

## Ownership layers

1. `tokens.toml` owns display profiles, colors, type roles, spacing, strokes and
   fixed shape dimensions.
2. `components.toml` owns reusable arrangements such as the application header,
   footer, panel, button badge and video transport overlay.
3. A screen fixture owns semantic content and selected component variants. It
   may refer only to declared tokens and components.
4. A renderer owns measurement, clipping, drawing and output conversion. It does
   not infer application success or alter application state.
5. A future application adapter will translate acknowledged application state
   into the same bounded screen model and translate user actions back into the
   application's semantic control contract.

This division follows Guide View's rule that GuideOS owns presentation and
global interaction while applications provide meaning and state.

## Current files

- `design/schema/tokens.toml`: Paper Theme 0 and Typography 0 tokens for the
  `deck-640x480` display profile.
- `design/schema/components.toml`: shared component geometry.
- `design/schema/fixtures/video-player.toml`: fixed Video Player 1 example state.
- `design/schema/fixtures/audio-player.toml`: fixed Audio Player 1 example state.
- `design/schema/guide_design.py`: bounded loader, validation and shared drawing
  components for deterministic Pillow fixtures.
- `design/media-player-drafts/render_video_player_draft.py`: the example screen
  renderer, now composed from the schema.
- `design/media-player-drafts/render_audio_player_draft.py`: a second screen
  proving reuse of the same foundation and accessory variants.

## Rules for extension

- Add a token when a value should be consistent across unrelated components.
- Add a component when an arrangement and its states recur across screens.
- Add a screen pattern when the central information hierarchy recurs, not merely
  because two screens share the same background.
- Keep content, labels and live values out of tokens and components.
- Keep permissions, playback, networking, persistence and lifecycle state out of
  the design schema. The schema may display those states but never produce them.
- Use named color and typography references. Fixtures must not introduce raw
  colors, font families or arbitrary sizes.
- Preserve the fixed 640 x 480 geometry in this profile. A later display size
  receives another explicit profile rather than silently scaling this one.
- Reject missing references, invalid bounds and unsupported component variants.
  Do not silently substitute an invented style.

## Video Player 1 example

The example fixture supplies the media title, playback values, route indicators,
footer actions and availability message. The renderer combines those values with
the shared `application_header`, `status_panel`, `application_footer`,
`button_badge` and `video_transport` definitions. Its landscape is explicitly a
fixture placeholder for a decoded video frame, not a reusable theme component.

Changing the title or progress in the fixture therefore changes content without
changing layout. Changing a shared token or component changes every screen that
uses it. That distinction is the principal acceptance condition for Schema 0.

Audio Player 1 reuses the same theme, typography, header, footer, buttons and
battery component. It adds an audio-specific main panel and queue pattern. It
also exercises a text header accessory and footer battery accessory, while the
video example uses the inverse arrangement.

## Evidence and remaining work

The local reference renderer must produce a 640 x 480 RGB image and reject
invalid references. Source checks and the rendered fixture validate the draft
composition only. Before production adoption, the same roles must be integrated
with the Unicode/Pango provider, framebuffer-safe primitives, input focus and
Guide View state model, then inspected on physical hardware.
