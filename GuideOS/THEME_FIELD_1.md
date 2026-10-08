# GuideOS Field Theme 1

Status: accepted visual-direction schema for future GuideOS screen work. This is a presentation contract only. It does not change the currently installed Debian shell, its Paper Theme 0 renderer, or any application, permission, lifecycle, or hardware behavior.

## Purpose

Field Theme 1 replaces Paper Theme 0 as the direction for new visual concepts. It is a compact, text-first handheld interface: a quiet field terminal with a pale work surface, dense but readable operational text, and a single warm focus accent. It is an original GuideOS visual language, not a reproduction of any existing game interface.

## Screen regions

The 640 x 480 reference display is divided into four persistent regions:

1. **Status strip:** dark blue-black across the top. It holds `GuideOS` at left and compact device/network status at right.
2. **Context band:** full-width light neutral gray immediately below the status strip. It holds the current location or task heading. It has no decorative underline.
3. **Work field:** pale cool blue-gray. It holds application content and has no gratuitous texture or ornament.
4. **Control strip:** dark blue-black across the bottom. It uses short plaintext control hints, such as `A Select` and `B Back`.

## Color roles

Exact production values remain an implementation task, but roles are fixed:

- **status/control ground:** deep desaturated blue-black.
- **context band:** light, nearly neutral cool gray; deliberately contrasts with the warm focus marker.
- **work field:** very pale cool blue-gray.
- **inactive panel:** muted blue-gray, approximately 70% visually opaque against the work field.
- **selected panel:** soft ice blue, approximately 85% visually opaque.
- **focus marker:** saturated amber/orange vertical bar at the selected panel's left outer edge. It is the sole warm navigation accent.
- **primary text:** near-white on panels, deep blue-black on light regions.
- **secondary metadata and rules:** pale cyan-blue.
- **success/warning/error:** semantic states only; they must not compete with focus.

## Typography and information hierarchy

- Use clean modern sans text for names, instructions, and ordinary labels.
- Use monospace sparingly for counts, dynamic values, addresses, compact state, and technical metadata.
- Keep labels mixed case. All caps are limited to short route/state markers where compact scanning benefits.
- Each selectable panel has reserved empty upper space, then a thin internal rule, a primary label, and an optional single metadata line. Removing an icon never collapses that reserved upper space.
- Text establishes hierarchy; large illustration, texture, and decorative brand treatment do not.

## Home navigation pattern

The current home concept uses a centered, flush five-column by two-row navigation grid positioned immediately above the control strip with a thin work-field gap.

- The grid may include intentionally blank, unassigned cells. Empty cells do not imply a hidden feature or automatic destination.
- Panels share edges with only subtle seams; they do not use individual outer card borders.
- The focused panel uses the selected-panel fill and amber outer-left marker. Inactive panels remain lower-contrast.
- The current six named entries are `Library`, `Media`, `Connections`, `Notes`, `Recipes`, and `System`. Their arrangement is a concept fixture, not a permanent information architecture.

## System-screen application

System uses the same persistent status strip, context band, work field, control strip, type roles, and focus treatment. Its content should privilege readable state over decoration: power, battery, storage, wireless status, current build identity, and safe system actions. Critical actions remain clearly named and require their existing behavioral safeguards; a visual focus marker does not authorize an action.

## Boundaries and next work

- Field Theme 1 is an accepted design direction, not a physical Deck acceptance result or a production renderer.
- Existing Paper Theme 0 documents and running shell remain historical/current implementation evidence until a separately tested migration occurs.
- Customization, dynamic layouts, final tokens, scaling rules, and an application-level rendering component remain future work. They must preserve text readability, focus clarity, semantic status indicators, and a low-complexity fallback layout.
