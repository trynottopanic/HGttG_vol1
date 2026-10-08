# GuideOS Deck text accommodation direction

Status: owner-approved direction for implementation. Saved 1 October 2026.

This guideline carries the approved text accommodation changes into the next
GuideOS Deck update. It addresses recurring overflow, hidden names and unreadable
messages across Media, Files, Settings, connections, applications and system
screens. Implement against the newest working source and the existing Seed's
verified installed release. This document is not evidence of implementation,
image validation, installation or physical acceptance.

The owner approved all changes in the review and requested their practical
implementation specification. The dimensions and timing choices below are
starting proposals within that approved direction, adjustable through layout
verification and physical readability checks.

## Shared text layout

Every text element receives a defined rectangle, typography role and overflow
policy. Measure with the same font and shaping provider used to draw it.

Support four policies:

- Single line: fit within the rectangle and add an ellipsis when necessary.
- Wrapped: fill a fixed number of lines, adding an ellipsis if content remains.
- Filename: preserve the extension and distinguishing text, using middle
  ellipsis where appropriate.
- Scrollable: preserve complete text in a bounded viewport.

Clip drawing to the rectangle, including glyph overhangs. Remove arbitrary
character-count truncation from screen renderers. Keep complete values in the
screen model; visual truncation must never change identity or action values.

Use the existing Unicode provider for shaping and wrapping. Truncation respects
grapheme boundaries, preserving combining marks and joined emoji. The reduced
rendering path must also measure and clip correctly. Treat user text literally,
without interpreting markup.

## Readable typography

Use the earlier physically accepted readability correction as the initial scale:

| Role | Starting size |
| --- | ---: |
| Screen heading | 28 px |
| Primary names and values | 24 px |
| Metadata, instructions and controls | 20 px |
| Status strip | Existing size |

Apply roles consistently. Adjust space, visible row count and pagination instead
of shrinking text to fit. Verify these sizes in the new renderer on the Deck;
the earlier acceptance does not establish acceptance of this new layout.

See [readability correction](READABILITY_CORRECTION_0.md). Reconcile historical
[Typography 0](../TYPOGRAPHY_0.md) with the later owner feedback rather than
silently restoring its smaller role sizes.

## Media and File lists

Use full-width rows for filenames regardless of item count. Choose layout
explicitly in the screen model; remove the automatic two-column grid for short
lists. Keep grids for short, fixed categories.

Starting geometry on 640 by 480:

- Four rows, approximately 58 px high.
- Primary name line plus optional metadata line.
- Fixed selected-item area below the list, approximately 88 px high.
- Separate bottom control strip.

Resolve the complete vertical budget with the header, notices and controls before
adopting these values; they are not independent additive requirements. Screens
with larger messages may show fewer rows.

The selected-item area displays the complete name across up to three lines.
Longer content scrolls vertically within that area after a short reading delay,
with a continuation indicator and pauses at the beginning and end. Only selected
text scrolls. Rows and hit areas stay stationary. Reset scrolling on selection
change; stop animation while the screen is hidden. The complete text remains
available without a session deadline.

Compact rows retain useful distinctions and file extensions, for example
`Interview with … — Part 02.flac`. Folder/source metadata distinguishes duplicate
names. Preserve existing A activation, B return and Menu behavior.

## Player title and metadata

Give the title a full-width two-line area. Put source and output below it and
reduce decorative artwork where necessary. Longer titles use the same scrolling
policy while transport controls and elapsed time remain stationary.

Use short output names such as “Deck speakers”; retain complete device identities
in Audio details. Separate source, output and playback messages instead of
combining them into one long line.

## Headers and navigation

Reserve the Back button rectangle before measuring heading width. Allow two
heading lines within a fixed-height header so wrapping does not move controls.
Long location paths use compact breadcrumbs with complete values in details.

Rendered geometry also defines pointer targets. Preserve focus and existing
semantic controls; text accommodation must not add a new global gesture.

## Instructions, notices and errors

Reserve two or three wrapped message lines and separate brief status from longer
explanation. For example:

> No computers found.
>
> Open NDI on the same network, then scan again.

If essential instructions exceed this area, provide a visible Details action
opening a scrollable explanation. B returns to the same screen and selection.
Routine message updates should not unexpectedly move selectable rows.

Confirmations show the complete consequence and affected item. Use a scrollable
body when necessary, keeping confirm/cancel controls fixed and visible. Preserve
existing confirmation safeguards.

## Details and system values

Stack labels above long names, paths, output identities and diagnostic values so
the value can use the full width. Side-by-side fields remain suitable for short
values such as battery percentage, duration and file size.

The file-details drawer may remain a summary. Provide a full-width detail view
for complete names and paths, with vertical scrolling through all facts. Do not
truncate underlying values. Return to the original item and selection.

## Other screen families

| Screen | Implementation |
| --- | --- |
| Settings | Fixed category layouts; separate category labels from descriptions. |
| Wi-Fi and Bluetooth | Full-width name rows; security/connection metadata below. |
| Nodes and applications | Full-width variable-name rows and selected-name expansion. |
| Transfers and updates | Separate filename, progress and explanation; fixed progress geometry. |
| Keyboard and text entry | Preserve caret-following viewports and masking; readable prompt/error roles. |
| Context menus | Measure and wrap labels in bounded menus; derive hit regions from layout. |
| Status strip | Compact states/indicators; long explanations in their system screens. |

Browser-owned controls require the same review. Website content has a separate
browser zoom/scrolling contract and is not validated by shell rendering checks.

## Implementation ownership

The current shell uses [V3UI](../board/rg35xxh/debian/shell0/guide_v3_ui.py) through
[Screen](../board/rg35xxh/debian/shell0/guide_shell.py).
[field_model](../board/rg35xxh/debian/shell0/guide_field_ui.py) supplies semantic
models; changing the older FieldUI drawing path alone will not fix current V3
screens. Reverify that routing against the newest source before editing.

Extend the [shared screen model](../package/guide-ui/guide_ui_model.py) with
explicit list presentation, item metadata, selected full text and message detail.
Keep presentation separate from action identities and values. Implement shared
measurement, wrapping, ellipsis and clipping using
[UnicodeText](../package/guide-input/guide_unicode.py), then connect the component
to the active renderer and migrate screen families through it.

Maintain bounded caches keyed by text, font role, available dimensions and
overflow policy. During scrolling repaint only the affected viewport. Clear
transient text on screen/editor closure and preserve private editor masking.
Align packaged and board-local copies through the existing release assembly
process; inspect which copies actually enter the candidate.

## Validation and rollout

Migrate Media and Files first, then headers/messages, then remaining families.
Use fixtures covering:

- Long spaced and unbroken names.
- Identical prefixes with different endings/extensions.
- Multilingual/right-to-left text, combining marks and emoji.
- Missing metadata, long errors and maximum supported values.
- Selection changes, provider/list updates and navigation during scrolling.

Check clipping, access to complete information, visible focus and matching pointer
targets. Check pagination/scrolling reaches every item and fact, not just the
initial visible subset. Render with production fonts and inspect representative
screens. Run appropriate navigation, Unicode and renderer regressions. Perform
physical readability checks on the Deck after installation.

## Existing Seed integration

Continue the current release workflow and sequential `0.4.2.xx` naming. Coordinate
with the conversation building the newest update so source and candidate changes
do not race. Identify the current installed release and candidate baseline from
fresh evidence; the review observed working VERSION `0.4.2.02`, which is not a
claim about the connected Seed or the latest release.

Before writing, identify the actual connected Seed, verify its match to the
expected capture, preserve owner data and recovery material, validate the complete
candidate, and use the established bounded update/write and readback procedure.
Never assume a drive number or overwrite boot/data for a presentation change.
Honor any newer owner deployment instructions. This save operation changes only
this guideline and does not itself perform a Seed installation.

Report working-source checks, simulated integration, candidate/image validation,
Seed readback and physical acceptance separately. Installation/readback alone
does not establish readable text, correct display ownership or navigation on
hardware. Retain a recoverable previous release through the existing workflow.
