# GuideOS Typography 0

Typography 0 fixes the reusable type choices for Paper Theme 0 on the current
640 x 480 Deck display. Sizes below are device pixels, not typographic points.
Applications may omit roles they do not need, but must not substitute another
family or invent an intermediate size merely to make content fit.

## Fixed families

| Family token | Required face | Use |
| --- | --- | --- |
| `guide-serif` | Noto Serif | Guide identity, mastheads and rare editorial display text |
| `guide-sans` | Noto Sans | Navigation, body text, status, controls and application labels |
| `guide-mono` | Noto Sans Mono | Times, counters, addresses, codes and aligned technical values |

These families are covered by the existing optional `fonts-noto-core` Deck
profile. Noto Sans remains the shaping provider's default face. Noto Serif is a
limited display accent; it must not be used for paragraphs or dense menus.

Reduced profiles that do not install Noto use DejaVu Serif, DejaVu Sans and
DejaVu Sans Mono respectively. This is a compatibility fallback, not an
alternative visual theme. Development-host previews may use Georgia for
`guide-serif` and Segoe UI for `guide-sans` when neither Noto nor DejaVu is
available, but those host proxies are not production font choices.

## 640 x 480 role scale

| Role token | Face | Weight | Size | Typical use |
| --- | --- | --- | ---: | --- |
| `masthead` | `guide-serif` | Bold | 19 px | Persistent “The Guide” identity |
| `screen-title` | `guide-sans` | Bold | 15 px | Current application, page or media title |
| `section-title` | `guide-sans` | Bold | 15 px | Panel headings and selected primary actions |
| `body` | `guide-sans` | Regular | 15 px | Main labels, prose and menu items |
| `body-strong` | `guide-sans` | Bold | 15 px | Emphasis and active settings |
| `control` | `guide-sans` | Regular | 12 px | Footer actions and compact secondary labels |
| `control-strong` | `guide-sans` | Bold | 12 px | Button badges and compact selected actions |
| `metadata` | `guide-sans` | Regular | 12 px | Routes, track details and noncritical status |
| `numeric` | `guide-mono` | Regular | 12 px | Elapsed time, duration, counts and percentages |
| `display-value` | `guide-mono` | Bold | 22 px | Pairing codes or a single prominent reading |

The 19/15/12 scale is the default application scale. The 22 px role is reserved
for one short focal value; it is not a fourth general-purpose heading level.
Text is clipped, wrapped, paginated or scrolled according to the owning view's
contract. It is never silently reduced below its role size to fit.

## Usage rules

- Mixed case is the default. All capitals are limited to literal abbreviations,
  codes, and source text.
- Bold communicates hierarchy or active state, not decoration. Italic and light
  weights are outside Typography 0.
- Numeric values that update in place use `guide-mono` so neighboring layout
  does not move as digits change.
- Button letters inside circular badges use `control-strong`; their action names
  use `control`.
- User and network text is rendered through the Unicode shaping and fallback
  contract in `UNICODE_RENDERING_0.md`. A missing display glyph is not a reason
  to replace the fixed Latin interface family globally.
- A local preview establishes layout intent only. Physical readability, glyph
  coverage and performance remain hardware acceptance questions.

## Video Player 1 mapping

The current renderer draft uses `masthead` for “The Guide / Video”,
`screen-title` for the media title, `section-title` for route and track values,
`numeric` for playback times and battery percentage, and the two control roles
for the footer and transport action. This mapping is the reference example for
future Paper Theme application screens.
