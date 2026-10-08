# NetSurf integration for Guide Wikipedia

## Decision

GuideOS will use NetSurf's SDL framebuffer frontend as the first rich Wikipedia
renderer. NetSurf is a rendering component, not the authority for networking,
identity, permissions, or application navigation.

The existing plain-text Wikipedia reader remains available until controller,
framebuffer, memory, and shutdown behavior pass on the RG35XX H.

## First-stage architecture

```text
Deck controls
     |
Guide Wikipedia view
     |
NetSurf framebuffer process
     |
http://127.0.0.1:8765 only
     |
Guide loopback gateway
     |
bounded MediaWiki API client
     |
English Wikipedia
```

The gateway generates the home and search pages. For an article, it requests
MediaWiki's parsed HTML and serializes only a documented passive subset. It
keeps headings, paragraphs, lists, tables, figures, internal article links, and
HTTPS images from `upload.wikimedia.org`. Approved images pass through the
gateway, which limits their type, redirect destination, and size. It discards scripts, styles supplied
by the article, forms, media players, frames, embedded objects, event handlers,
external links, and arbitrary attributes.

The service binds to `127.0.0.1`; it is not a Node service and is not reachable
from another device. Responses carry a restrictive content-security policy,
never set cookies, and instruct the browser not to retain them in a shared
cache. NetSurf itself only contacts the loopback gateway.

## Process and ownership contract

Only one process may own the Deck framebuffer and input devices at a time.
The shell must:

1. save its current screen and navigation state;
2. start the loopback gateway and confirm its health endpoint;
3. release framebuffer and input handles;
4. start NetSurf at the local gateway home page;
5. translate Deck controls into a small browser action set;
6. stop NetSurf and the gateway on exit, failure, sleep, or shutdown;
7. reacquire the devices and restore the shell;
8. fall back to the text reader if any handoff step fails.

The first action set is deliberately small: move focus, open, back, forward,
page up, page down, search, and exit. No address bar or arbitrary URL entry is
required for the Wikipedia mode.

## Acceptance gates

### Host gate

- all client, sanitizer, gateway, and existing reader tests pass;
- hostile fixture HTML cannot create active content or leave the gateway;
- searches and article pages contain only local links plus approved images;
- failures produce a readable local page rather than an empty screen.

### Build gate

- Buildroot resolves NetSurf's framebuffer frontend with HTTPS, FreeType, WebP,
  PNG, and JPEG support;
- the installed ARM64 executable is `/usr/bin/netsurf-fb`;
- the image contains the gateway and its Python modules;
- NetSurf starts without a desktop GUI toolkit.

Buildroot compiler caching is enabled in the Deck configuration. A matching
existing Buildroot output directory may be reused as a whole; individual
compiler or sysroot directories must not be copied between outputs. NetSurf
3.10's generated lexer sub-build is serialized by a GuideOS source patch to
avoid a clean-build race while the rest of the build remains parallel.

### Deck gate

- the shell can enter and leave the reader repeatedly without a hard reset;
- every required action is usable from the Deck controls;
- memory remains bounded on long and image-heavy articles;
- network loss, server delay, and malformed responses remain escapable;
- safe shutdown works while the gateway is fetching and while NetSurf is open.

## Later work

After the Deck gate passes, the same NetSurf component may support a separate
general Guide browser. That browser must have its own capability policy,
downloads boundary, history/storage rules, and visible origin controls. The
Wikipedia client should not silently expand into that larger trust domain.
