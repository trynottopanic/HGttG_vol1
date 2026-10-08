# Guide Wikipedia

The proposed [application contract](APPLICATION_CONTRACT_0.md) defines the
Wikipedia lifecycle, capabilities, saved state and Guide/systemd boundary for
the rework. The implementation notes below describe existing prototype work;
they do not establish conformance to that contract.

Guide Wikipedia is a reading-first Wikipedia client for Decks. It is not an
unrestricted web browser: GuideOS asks Wikipedia's documented API for search
results and articles, reduces the returned article HTML to a passive allow-list,
and gives that local document to NetSurf's lightweight framebuffer renderer.

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
  the original framebuffer shell and remains the plain-text fallback.
- `guide_wikipedia_html.py` keeps useful document structure, internal article
  links, and Wikimedia images while removing scripts, forms, embedded objects,
  arbitrary attributes, and external navigation.
- `guide_wikipedia_netsurf.py` is a loopback-only HTTP gateway. NetSurf opens
  its local pages; the gateway performs the bounded MediaWiki requests.
- the remaining Deck view will own the framebuffer and controls,
  scrolling, history, saved articles, and visible error states.

The installable 0.3 prototype cartridge still presents up to eight selectable
search results and retrieves the full article only after selection. Wikimedia
parses its own wiki markup; the client then accepts only readable text blocks
and internal page-link targets from that response. The new NetSurf path is the
next image-built version. Remote pages are never opened directly and remote
scripts are never accepted.

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

## NetSurf proof stage

The current implementation establishes the safe data/rendering boundary and
adds NetSurf plus its SDL framebuffer, HTTPS, image, and font dependencies to
the RG35XX H Buildroot image. It does not yet replace the working controller UI.
The next hardware step is a clean shell-to-NetSurf framebuffer handoff and an
RG35XX H input adapter. Until that passes, the existing text reader remains the
fallback rather than being removed.

## Host demonstration

```text
python guide_wikipedia_client.py search "Douglas Adams"
python guide_wikipedia_client.py article "Douglas Adams"
```

No request is sent before the user performs a search or opens an article. The
client identifies itself to Wikimedia, uses one request at a time, honors HTTP
errors, limits response size, and does not send Deck identity or location.
