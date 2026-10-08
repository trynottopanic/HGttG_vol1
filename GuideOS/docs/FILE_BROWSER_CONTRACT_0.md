# File Browser Contract 0

Status: owner-approved functional contract, 27 September 2026.
Approval: the owner accepted the proposed contract in full and requested this
handoff for Future Planning's GUI design. This is not implemented-backend evidence.
Field names below express agreed concepts; wire encoding, API signatures, enum
values and limits still need implementation specifications. Do not invent them
as established APIs while designing the GUI.

## Purpose and ownership

One browser presents locations and entries across external storage, servers and
connected devices. Storage/connection providers own access. A transfer service
owns copying/downloading. The application service owns opening files. The GUI
owns presentation, navigation history, selection and scroll position.

## 1. Locations

A location is a browsing destination, such as an external card, remote server or
exposed folder on a device.

| Field | Meaning |
| --- | --- |
| location_id | Opaque identifier; never interpreted by the GUI as a filesystem path. |
| label | User-facing name, such as External card or Home server. |
| kind | Local storage, remote server, or connected device. |
| state | Available, disconnected, connecting, authentication required, unavailable, or error. |
| root_entry_id | Entry used to begin browsing when available. |
| capabilities | Actions this location currently supports. |
| space | Available and total space when known. |
| generation | Changes when the underlying connection or storage instance is replaced. |

Saved connections remain visible while disconnected. The connection service
manages credentials; file/location records never contain them.

## 2. Entries

| Field | Meaning |
| --- | --- |
| entry_id | Opaque identifier scoped to its location and generation. |
| parent_id | Parent entry, where applicable. |
| name | Display name preserved as supplied by the provider. |
| kind | File, folder, link, or other. |
| content_type | Known or estimated file type; may be unknown. |
| size | File size in bytes when known. |
| modified | Modification time when known. |
| revision | Provider evidence for detecting replacement/modification. |
| actions | Actions currently available for this entry. |

Unknown information stays unknown. A folder size does not imply a recursive
scan. Providers resolve links within the allowed location; listings do not
follow links automatically.

## 3. Navigation and listings

Requests cover listing locations, connecting/disconnecting, listing a folder,
reading entry details, refreshing, and watching relevant changes while a view
is open. Each request has an identifier and can be cancelled. A late response
from an old folder request must not replace a newer view.

Listings are bounded and paginated, with a continuation token and listing
revision. Expired/changed listings request a refresh; pages from different
revisions are never silently combined. Exact page limits remain an engineering
detail, not a GUI constraint fixed by this contract.

Sorting applies to the whole listing, not just a visible page: name, size, type
or modification time; ascending/descending; folders first. Unsupported sorts
are reported explicitly.

The GUI owns Back/Forward history, breadcrumbs, selection and scroll position.
Providers supply valid parent relationships. Returning to a folder restores its
selection where that entry still exists. Initial selection is single-item;
the interface should permit later multi-selection without requiring it now.

## 4. Actions

| Action | Meaning |
| --- | --- |
| Browse | Enter/list a folder. |
| Open | Ask the application service to open a file. |
| Copy/download | Read an entry and transfer it to a chosen destination. |
| Create folder | Create a folder at a writable destination. |
| Rename | Change an entry's name. |
| Move | Move an entry where supported. |
| Delete | Remove an entry under the separately agreed deletion policy. |
| Upload | Transfer a local file to a writable remote location. |

Locations advertise capabilities; entries report currently available actions.
An unavailable action may remain visible with a useful reason, such as Card is
read-only. Availability helps the GUI; it does not grant permission. Providers
recheck access and identity when an operation begins. Unsupported operations
are not silently approximated.

First-release implementation may be limited to browsing, opening and copying/
downloading. Other actions belong to the contract but are not promises of first-
release availability. Deletion policy and move semantics are not yet specified.

## 5. Transfers

A request identifies a source entry or download resource, destination folder,
proposed filename and explicit collision policy. It returns a transfer_id
immediately. Transfers continue independently of the folder being viewed.

| State | Meaning |
| --- | --- |
| Queued | Waiting to start. |
| Preparing | Checking source, destination and requirements. |
| Transferring | Moving data. |
| Paused | Deliberately paused, where supported. |
| Needs attention | Requires a decision, credentials or reconnection. |
| Finalizing | Closing and publishing the completed destination file. |
| Completed | Destination is ready. |
| Failed | Stopped with a reported failure. |
| Cancelled | Cancelled, with cleanup status reported. |

Progress includes transferred bytes, total bytes when known, and optional speed
and estimated remaining time. Unknown totals use indeterminate progress, not a
fabricated percentage. Pause/resume appear only when supported. Retry distinguishes
safe resume from restarting from the beginning.

Existing files are never overwritten silently. Collision choices are keep both,
replace, skip or cancel, according to provider support. The GUI needs a destination
picker and a collision decision state; their visual form is not prescribed.

Incomplete data remains separate from the completed filename. Completion means
successful destination finalization. Checksum verification is reported separately
when available; the service must not imply stronger verification than it performed.
Low space, cancellation or removal must preserve existing destination files and
must not present partial data as a finished download. Cleanup/retention is reported.

## 6. Opening

Opening is separate from transfer and execution. The application service supplies
suitable handlers; the GUI opens the chosen handler or explains that none exists.
If a remote file needs a local copy, show the required download and its destination.
Do not silently create permanent copies. Downloading a cartridge does not install
it. Browsing a folder does not execute its contents.

## 7. Errors and change notifications

Errors contain a stable code, short display message, retry possibility and supported
next actions. Initial categories: disconnected location, authentication required,
permission denied, missing entry, changed entry, stale listing, unsupported operation,
insufficient space, name collision, invalid filename and I/O failure.

A failed refresh can retain the previous listing, clearly marked stale.
Disconnection must not appear as an empty folder. Notifications identify affected
locations, folders, entries or transfers. Missed notifications require a refresh.

## 8. Lifecycle and access

Providers own mounts, remote credentials and access permissions. The browser
neither mounts cards nor writes independently around the storage provider.
Card removal/disconnection invalidates access to that generation. Transfers stop
or need attention. Reconnection alone does not authorize resumption: the service
must verify the source and destination still match.

Closing the browser view does not cancel transfers. Explicit cancellation,
shutdown and provider loss follow the transfer service lifecycle and report
whether partial data was retained or removed.
