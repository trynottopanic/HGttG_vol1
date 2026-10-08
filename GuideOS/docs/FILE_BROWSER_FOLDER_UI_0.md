# File Browser folder UI 0

Status: adopted presentation direction, 27 September 2026. This specifies the
first folder-browsing page. It is a GUI design contract, not evidence of a file
provider, transfer service, installed image, or physical Deck behavior.

## Structure

A folder uses a focused full-width list as its default state. The persistent
status strip is followed by the folder name and a compact location breadcrumb.
The list places folders before other entries when the active provider supports
that ordering. A row has a name and only the directly useful, confirmed metadata:
file type, size, item count or unknown. Optional metadata remains out of the
main view.

The selected row is crisp and visibly distinct without relying on color alone.
Idle rows stay quiet. Folder selection and scroll position are restored when
returning from an entry or child folder only while the location generation and
entry identity remain valid.

## Select details pane

`Select` opens a temporary details pane for the current entry. It overlays the
list rather than reserving permanent width for a second panel. The pane states
its entry name, kind and confirmed metadata, then exposes only currently
available actions. It closes with Back or its written close control, returning
focus to the same list row and leaving the folder position unchanged.

For a folder, the primary pane action is `Open folder`. For a file, it is
`Open file` only when an application handler is available. Copy/download and
other actions appear only when the entry and destination capabilities support
them. A missing handler is explained rather than made to look like corruption.

Select never opens a folder, starts a transfer, executes a file or treats the
displayed details as fresh authority. Providers revalidate the entry when an
operation begins.

## Navigation

Back returns to the parent folder when one exists; at a location root, it
returns to the location cards. A separate Up affordance may be shown in the
breadcrumb when relevant, but it does not replace Back history. The GUI retains
Back/Forward history, breadcrumbs, selection and scroll position. A late result
from an older folder request cannot replace the newer folder currently shown.

Loading identifies the requested folder and permits cancellation/navigation as
supported. A successful complete empty listing is explicitly shown as empty.
Disconnection, authentication required, provider error and a failed refresh are
distinct written states. A failed refresh may retain the prior listing only when
it is marked stale and entry actions are revalidated.

## Scope

This page governs local external-card, Guide Node, saved-server and connected-
device locations with the same neutral language. It does not add web-view modes,
URL editing, mount authority, credentials, multi-selection, rename, move,
delete, upload or recursive-operation policy.
