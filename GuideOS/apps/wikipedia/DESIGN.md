# Native Wikipedia reader design

## First usable path

1. Choose **Wikipedia** from the Deck menu.
2. Enter a search with a controller-friendly on-screen keyboard.
3. See up to eight article titles with their approximate article length.
4. Open one and read plain text sized for the 640×480 display.
5. Page through the text and return to results.
6. Save an article for later offline reading.

## Controls

- D-pad: move keys, results, links, or text.
- A: choose a key or open the selected item.
- B: erase while typing; otherwise go back.
- Start: submit the search or open the action menu.
- Select: switch between article text and its table of contents when present.
- Power: the existing safe-shutdown confirmation remains global.

Every necessary operation will also be reachable with only D-pad, A, and B so
unusual interface devices are not excluded.

## Reading presentation

The screen favors title, text, section position, and connection state. It does
not reproduce Wikipedia's desktop layout, advertisements do not exist, images
are not downloaded automatically, and links are visibly distinguished from
ordinary text. Article license/source information remains reachable from the
article menu and is stored with offline copies.

## Network and privacy boundary

- Requests go only to the user-selected Wikimedia language host over verified
  HTTPS.
- The client supplies the descriptive User-Agent required by Wikimedia.
- Search text and requested article titles necessarily reach Wikimedia; the UI
  explains this the first time network search is used.
- There is no background prefetch, telemetry, advertising identifier, Deck
  identity, location transmission, or third-party content request.
- One foreground request runs at a time, with a timeout and strict response
  size limit.
- HTTP retry/rate-limit instructions are respected rather than bypassed.

## Offline behavior

Previously saved articles remain readable without Wi-Fi. Search clearly says
**Offline — saved articles only**, and failed connections never erase cached
content. Cached records include article title, stable page id when available,
retrieval time, source URL, language, text, and Wikimedia licensing notice.

## Technical boundary

The data client returns UTF-8 JSON containing only the fields the view needs.
The view never renders remote HTML or executes JavaScript. This sharply
reduces memory use and prevents webpages from acquiring a general execution
surface on the Deck.

The 0.2 cartridge packages the missing Python TLS modules, OpenSSL libraries,
and certificate-authority bundle in an application-private runtime. The Deck
installs it only after exact package and file verification. A later GuideOS
image may instead enable `guide-wikipedia-core` to build those facilities into
the platform itself.
