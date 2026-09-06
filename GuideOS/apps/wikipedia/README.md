# Guide Wikipedia

Guide Wikipedia is a native, reading-first Wikipedia client for Decks. It is
not a general web browser: it asks Wikipedia's documented API for search
results and plain article text, then renders that information in the GuideOS
interface.

The first implementation is split in two so hardware work can proceed safely:

- `guide_wikipedia_client.py` is the small network/data client. It already
  performs bounded, certificate-verified HTTPS requests and returns plain
  structured data.
- `guide_wikipedia_model.py` implements controller-driven text entry and
  bounded article wrapping/pagination without depending on a desktop toolkit.
- `guide_wikipedia_app.py` is the small application state machine joining
  search, results, article paging, visible errors, and offline saves without
  depending on a particular display library.
- `guide_wikipedia_store.py` keeps up to 32 explicitly saved articles in a
  bounded, owner-only, atomic offline store.
- `guide_wikipedia_bridge.py` exposes one bounded, line-oriented request for
  the framebuffer shell without parsing or rendering remote HTML.
- the remaining Deck view will own the framebuffer and controls,
  scrolling, history, saved articles, and visible error states.

The installable 0.3 prototype cartridge first presents up to eight selectable
search results and retrieves the full article only after selection. Wikimedia
parses its own wiki markup; the client then accepts only readable text blocks
and internal page-link targets from that response. Remote HTML and scripts are
never rendered on the Deck.

Paragraph breaks, list items, and bracketed section headings remain visible in
the framebuffer reader. Links are numbered in the article. Pressing `A` opens
the link list at the first link visible on the current page; up/down moves one,
left/right moves seven, `A` opens the selected Wikipedia page, and `B` returns.
The prototype keeps at most 500 links per article to bound memory and response
size.
It carries its HTTPS libraries and
trusted certificate bundle in an application-private runtime. The Deck shell
verifies every file before installation and does not overwrite global copies.

The optional Buildroot package `guide-wikipedia-core` remains the path for
building the same facilities directly into later GuideOS images.

## Host demonstration

```text
python guide_wikipedia_client.py search "Douglas Adams"
python guide_wikipedia_client.py article "Douglas Adams"
```

No request is sent before the user performs a search or opens an article. The
client identifies itself to Wikimedia, uses one request at a time, honors HTTP
errors, limits response size, and does not send Deck identity or location.
