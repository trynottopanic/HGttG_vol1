# Guide View 1 Draft

Status: exploratory contract; names and limits may change after prototype tests  
Depends on: Cartridge Format 1, the Guide shell, and a future capability broker

## Ordinary-language definition

A Guide View is a small description of information and choices. It says what
each thing *means*—title, paragraph, link, picture, choice, warning—without
dictating exactly where every pixel goes. GuideOS arranges it for the person's
screen and controls.

This gives an application enough vocabulary for an article, message list,
settings screen, simple utility, or Recipe interface. It does not give the
application a web browser, a command line, or permission to run downloaded
code.

The first uses are:

- structured Wikipedia articles;
- communication cards from a trusted Node;
- Node and provider status;
- Cartridge Workshop demonstrations;
- simple creator-made tools.

## Design rules

1. Meaning before coordinates. Applications describe content and actions;
   GuideOS owns layout, focus, typography, scrolling, and global controls.
2. Small enough to inspect. A view is bounded text and metadata, not an
   application binary.
3. Safe when unfamiliar. Unknown optional content can be omitted; unknown
   required behavior makes the view incompatible rather than half-executable.
4. Same meaning on different hardware. A 640×480 Deck, e-paper interface,
   phone, and desktop may lay out the same view differently.
5. Current state wins. Newer replaceable state supersedes older queued state;
   user input is never replayed after it becomes stale.
6. No implied success. Remote actions remain pending until acknowledged and
   failures remain visible.
7. User authority remains outside the document. A view can offer an action but
   cannot grant itself the capability needed to perform it.

## Non-goals

Guide View 1 is not:

- HTML, CSS, JavaScript, WebAssembly, or a browser document;
- a pixel-perfect design interchange format;
- a general programming language;
- a remote desktop protocol;
- a way to install fonts, codecs, drivers, or native libraries;
- permission to read files, contact a service, or change system state;
- a replacement for the Media Surface or Remote Application Surface.

## Document envelope

The first wire form is bounded UTF-8 JSON. The friendly Workshop will create it
without requiring a person to write JSON. An expert can still open and audit it.

Illustrative shape:

```json
{
  "format": "guide-view-1-draft",
  "id": "wikipedia:page:3850:1187742034",
  "title": "Douglas Adams",
  "source": {
    "provider": "wikipedia-online",
    "label": "English Wikipedia",
    "retrieved": "2026-09-09T12:00:00Z",
    "revision": "1187742034"
  },
  "state": "current",
  "blocks": [
    {"id": "lead", "type": "heading", "level": 1,
     "text": "Douglas Adams"},
    {"id": "p1", "type": "paragraph",
     "runs": [{"text": "Douglas Noel Adams was an English author."}]},
    {"id": "works", "type": "link", "label": "Works",
     "action": "open-works"}
  ],
  "actions": {
    "open-works": {
      "type": "provider.open",
      "provider": "wikipedia-online",
      "resource": "Douglas_Adams_bibliography"
    }
  }
}
```

This is a design example, not permission to call Wikipedia. The installed
application must already possess the relevant bounded provider capability.

### Required envelope fields

- `format` — exact protocol identifier;
- `id` — stable identifier within the provider and revision;
- `title` — short human-facing title;
- `source` — provider identity and human label;
- `state` — `current`, `stale`, `offline-copy`, `partial`, or `error`;
- `blocks` — ordered content elements;
- `actions` — action definitions referenced by interactive blocks.

### Optional envelope fields

- `subtitle` — one short contextual line;
- `revision` — provider revision independent of the source object;
- `continuation` — opaque provider cursor for another bounded page;
- `language` — BCP 47 language tag;
- `direction` — `ltr` or `rtl` when known;
- `license` — label and destination for source/license information;
- `notice` — visible source-supplied status, never hidden metadata;
- `expires` — time after which the view must be marked stale.

An opaque continuation cursor is data for the named provider only. It is never
executed, opened as a URL, or passed to another provider.

## Block vocabulary

Every block has a unique `id` within the document and one `type`. Text is UTF-8,
normalized for display, and prohibited from containing control characters other
than documented line separators.

### Structural blocks

- `heading` — levels 1 through 4; also becomes a section-jump target;
- `paragraph` — readable text split into bounded semantic runs;
- `list` — ordered or unordered items, with at most two nesting levels;
- `quote` — quoted text plus optional source label;
- `facts` — short label/value pairs;
- `table` — bounded columns and rows with a mandatory narrow-screen fallback;
- `divider` — semantic section break, not arbitrary line art;
- `spacer` — one small theme-defined separation, never a pixel count.

### Interactive blocks

- `link` — named action with a visible destination class;
- `button` — named action described with a verb;
- `choice` — one selection from a bounded list;
- `text-input` — single or multiline text with a purpose and length limit;
- `toggle` — explicit on/off preference;
- `media` — reference opened by the supervised Media Controller;
- `remote-application` — reference opened by the Remote Session Controller.

### Informational blocks

- `image` — bounded asset reference, alt text, caption, and attribution;
- `status` — neutral current condition;
- `progress` — determinate or indeterminate work with cancellation state;
- `warning` — risk or partial result;
- `error` — failure plus safe recovery actions;
- `code` — literal fixed-width text for documentation, never executable;
- `attribution` — source, author, revision, license, and retrieval information.

Rich paragraph text is represented by runs with a limited role: ordinary,
emphasis, strong, code, citation, or an action reference. Colors, font names,
font sizes, animation, absolute coordinates, hidden text, and overlapping
content are not author-controlled properties.

## Action vocabulary

Actions describe an intention. The shell validates the action, looks up the
calling package and provider, checks the capability grant, and then asks the
appropriate controller to perform it.

Guide View 1 should begin with:

- `view.back` — return through local navigation history;
- `view.replace` — ask the same provider for another view;
- `provider.open` — open a typed resource from the named provider;
- `provider.search` — submit explicit user text to the named provider;
- `store.save` and `store.remove` — change the package's private store;
- `media.open` — give a validated reference to the Media Controller;
- `application.session.request` — request an approved remote session;
- `application.session.close` — end the calling package's session;
- `external.open` — show and confirm an external destination before handing it
  to a separately available handler;
- `form.submit` — send the visible bounded fields to the named provider;
- `event.dismiss` — acknowledge or hide one event according to provider rules.

There is deliberately no `execute`, `shell`, `eval`, arbitrary HTTP request,
arbitrary filesystem path, or arbitrary window-input action.

An action contains typed parameters with individual length and count limits.
Text entered by the user is not silently reused for another action. A sensitive
action shows its service, account, destination, and effect at confirmation.

## Focus and controls

The renderer creates a single predictable focus order from the block order.
Layout cannot reorder meaning behind the user's back.

- Up/down moves to the previous or next focusable item or scroll step.
- Left/right changes a bounded choice, moves within a horizontal fallback, or
  pages only when the current component declares that behavior.
- A activates the focused choice.
- B goes back or closes a temporary overlay.
- Start opens the local action menu.
- Select opens local document navigation when sections exist.
- Home and Power remain global and cannot be intercepted.

Every action must be reachable by D-pad, A, and B. Analog input maps to the same
semantic movement and uses the established held-input governor. Pointer,
touchscreen, keyboard, switch, voice, or e-paper implementations may produce the
same actions without changing application logic.

Focus survives a view refresh when a stable block identifier still exists. If
it does not, focus moves to the nearest preceding stable block rather than the
top or an unrelated destructive action.

## Rendering rules

The Deck renderer, not the provider, decides:

- typeface, scale, colors, and theme;
- line wrap, page size, and scroll behavior;
- focus ring and selection color;
- image downscaling and placeholder behavior;
- table fallback;
- status-bar placement;
- accessibility transformations.

The renderer must display the provider and stale/offline/partial state without
requiring the user to open a hidden details screen. Source attribution and
license may live in the local action menu when they do not fit continuously.

### Narrow-screen table fallback

A table must name its key column or provide a `record` fallback. On a narrow
screen, each row becomes a small facts card:

```text
Planet: Earth
Mass: 5.972 × 10^24 kg
Moons: 1
```

If no understandable fallback exists, the validator rejects the table and the
provider must offer a download or source-link action instead.

### Images

An image block contains an asset identifier, media type, declared pixel size,
byte size, digest, alt text, caption, and attribution. The asset controller:

1. checks the declaration before fetch;
2. enforces source, byte, dimension, redirect, and time limits;
3. decodes outside the shell's critical input/power path;
4. scales to a bounded surface;
5. caches only according to the view's permission and retention state;
6. substitutes alt text on any failure.

Animated images are shown as a still image in revision 1.

## Limits proposed for the first prototype

These limits must be measured on the RG35XX H and may be lowered:

| Item | Initial ceiling |
| --- | ---: |
| Encoded view document | 512 KiB |
| Blocks in one view | 512 |
| Interactive blocks | 128 |
| Actions | 128 |
| Total decoded text | 256 KiB |
| One text field | 8 KiB |
| List nesting | 2 levels |
| Table columns | 12 |
| Table rows in one view | 100 |
| Images referenced | 16 |
| Decoded image surface | 640×480 |
| Continuation requests in flight | 1 per provider |

Providers should normally send much less. A long Wikipedia article is a series
of section-aware chunks with stable reading positions, not one maximum-sized
document. Limits apply after decompression as well as before it.

## Refresh, continuation, and events

A view may be:

- **static** — changes only after a visible action;
- **replaceable** — the provider may supply a newer complete revision;
- **event-backed** — named blocks may be replaced by acknowledged events.

Revision 1 does not permit arbitrary document mutation instructions. A provider
can replace the full bounded view or replace one explicitly replaceable block by
stable identifier. The Deck rejects an older sequence number. High-frequency
progress or presence state is coalesced. Messages and other durable events use
acknowledged ordered delivery.

Continuation requests state the user's operation—next chunk, previous chunk,
open section, or more results. A provider cursor alone never determines a
surprising action.

## Failure behavior

- Invalid encoding or JSON: reject the view and retain the last valid view.
- Unsupported required feature: show **This needs a newer Guide runtime**.
- Oversize content: cancel parsing and identify the exceeded limit.
- Provider timeout: keep usable cached content and label it stale.
- Missing asset: show alt text; do not fail the whole document.
- Invalid action: disable only that action and show the reason in details.
- Lost capability: close sensitive overlays and show that access was revoked.
- Lost Node: retain permitted cached information; end remote surfaces safely.
- Low memory: abandon the incoming view before evicting the current usable one.

Errors never include credentials, private local paths, session tokens, or a raw
remote response body in the ordinary interface. A bounded diagnostic record may
include provider, stage, category, sizes, timings, and safe identifiers.

## Accessibility contract

Each block exposes a role, human label, value, state, action, and position in its
group. Images require alt text. Controls cannot depend on color alone. Timeouts
for reading or responding are absent unless the outside service truly requires
one, in which case the remaining time and consequence are visible.

The semantic document can later be spoken, enlarged, translated into an e-paper
page, or operated by switch input without reverse-engineering a picture. Voice
is another input/output adapter; it receives no additional application powers.

## Validation and conformance fixtures

The first validator and renderer are not complete until the repository contains
fixtures for:

- article with headings, paragraphs, lists, citations, and links;
- long article continued by section;
- message inbox with stale and unread cards;
- provider-offline status and retry;
- form with text, choice, cancel, and confirmation;
- simple media catalogue;
- remote-application request and rejection;
- narrow table fallback;
- missing and malicious image metadata;
- unknown optional and unknown required elements;
- duplicate identifiers and dangling actions;
- deeply nested, oversized, compressed, and malformed inputs;
- out-of-order refresh events and reconnection;
- focus preservation after refresh;
- cancellation during parse, fetch, and render;
- Power and Home response while a provider is stalled.

Every fixture should have a screenshot or text-layout expectation for 640×480,
an accessibility-tree expectation, a focus traversal, a memory ceiling, and an
expected user-facing failure. The desktop Deck Simulator runs the same fixtures
before any image is installed to physical hardware.

## Questions intentionally left open

- Whether the final wire encoding remains JSON or adds a compact equivalent;
- exact block/action identifiers and whether they use dotted names;
- whether revisions permit one-block replacement or only complete views;
- how application signatures and author identity enter a later cartridge
  format;
- the smallest safe image decoder set;
- localization ownership between provider, application, and shell;
- the appropriate per-application storage quotas;
- how much styling an authored game or expressive document may request without
  breaking accessibility and portability.

These should be answered by conformance fixtures and physical measurements, not
by freezing an attractive schema before the renderer exists.
