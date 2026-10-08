# File Browser locations UI 0

Status: adopted presentation direction, 27 September 2026. This specifies the
File Browser landing page only. It is a design contract and does not establish a
Node provider, remote browsing, transfer, or installed Deck behavior.

## Purpose

The landing page answers one question before the browser opens any folder:
where does the user want to browse? It presents available storage, servers and
connected devices as a small set of large, readable destination cards. It must
not reduce non-web locations to an address field or imply that every location
is a website.

The page uses the shared Guide status strip, deep midnight-blue work field,
near-black matte cards, pale-blue OCR-style metadata and clean mixed-case
labels. It has no persistent bottom instruction bar, Home wheel or Shortcut
Tray.

## First-release card layout

Use a two-column grid with no more than four large cards per page at the
accepted Deck text size. A card contains one location only:

1. `External card`
2. `Guide Node`
3. `Saved servers`
4. `Transfers`

`External card` represents the storage provider's dedicated external location.
`Guide Node` is a first-class selection for media and files a Node may expose to
the Deck. It is not hidden inside `Saved servers`, and it is not represented as
a generic web destination. `Saved servers` is the route for saved FTP/SFTP and
other supported remote connections. `Transfers` returns to independent active,
attention-needed and recently completed work without making transfer controls
permanent global chrome.

A later connected device becomes its own card only when its provider exposes a
valid location. It must not be invented as a disabled placeholder. Additional
locations paginate rather than shrinking cards below the accepted readable size.

## Card states

The title names the location. A short secondary line communicates its last
confirmed state. The state is written and never conveyed by color alone.

| State | Card presentation | Primary result |
| --- | --- | --- |
| Available | Crisp icon and label; brief confirmed availability or bounded content summary | Enter the location |
| Disconnected | Retained, subdued card with `Disconnected` state | Connect, if supported |
| Connecting | Written progress state; no false folder contents | Wait or cancel, if supported |
| Authentication required | `Sign-in required`; no credential fields on the card | Open the connection service flow |
| Unavailable | Written unavailable reason when known | Show recovery/help only when supported |
| Error | Short current error and retry availability | Retry or inspect the bounded error detail |

The card never uses a folder-empty illustration for disconnection, failure or
authentication. An actual empty-folder message belongs only after a successful,
complete folder listing.

## Guide Node card

The Node card is designed for the near-future case where a trusted Node exposes
media or other files to the Deck. Its idle wording is deliberately factual:

- available: `Node available` plus a bounded exposed-library summary when the
  provider supplies one;
- disconnected: `Node not connected` with the supported connection route;
- connecting: `Connecting to Node`;
- authentication or trust required: the provider's precise state, not a claim
  that trust has been established; and
- unavailable: a clear unavailable state rather than a hidden or empty card.

Selecting an available Node enters its exposed root location. It does not launch
media playback directly, mount a filesystem, expose a network address or merge
Node media into the Deck's local external-card listing. Once inside, Node media
uses the same folder, entry, open and download rules as any other location.

No Node discovery, trust management, pairing or media-sharing capability is
claimed by this page. The Guide Node card remains persistently visible even when
a usable provider or connection is unavailable; its written state explains that
condition and it offers only the recovery path actually supported.

## Focus and navigation

The selected card becomes crisp, gains a restrained pale-blue edge and exposes
only the relevant primary outcome (`Open`, `Connect`, `Retry`, or `View
transfers`). Idle cards remain legible but low-emphasis. D-pad and pointer reach
every card. Primary selection invokes the displayed outcome.

Back returns to Home. Entering a location opens its root folder. Returning from
a folder restores the focused card. A location's own folder history, selected
entry and scroll position remain owned by the browser and are restored only
while its generation remains valid. Replaced storage or a reconnected remote
location is a new generation and must not inherit stale entry identity.

Contextual guidance appears only when a relevant outcome first becomes
available or changes. The full control mapping remains in Help/Controls; this
page does not reserve a bottom legend.

## Boundaries and first-release scope

The first implementation may expose External card and Transfers before remote
providers exist. `Guide Node` and `Saved servers` require their accountable
location providers before appearing as live cards. Browsing, opening and
copying/downloading are the initial File Browser actions; rename, move, delete,
upload and folder creation are not promised here.

The GUI never interprets location identifiers as paths, stores credentials,
mounts storage, begins a transfer without a chosen destination, or treats a
card's displayed capability as authority. Provider capabilities remain
authoritative at operation time.
