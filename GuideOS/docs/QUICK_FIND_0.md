# Quick Find 0

Owner-approved first release: offline filename and installed-application search
from Home, using the native text-entry keyboard. Note-content search is deferred.

Quick Find is a Home-wheel destination with a magnifying-glass icon. Opening it
starts the shared keyboard; Find submits a name, B cancels text entry, and B on
the result screen returns Home. The query row reopens the keyboard. Search in
cycles through Files and applications, Internal files, External card and
Applications. The selected result shows its full name and source/location.

Installed applications launch through the existing application host. Supported
external media opens through the existing player. Other files open in File
Browser's details view, which supplies its current available actions; this
release does not introduce image/text handlers. Returning restores the query
and results. A file identity is revalidated before opening, and a changed file
or removed card requires another search.

## Ownership and bounds

Search uses the owner-facing storage locations and installed catalog. It accepts
opaque provider identities, never raw paths; it does not read file contents,
follow symlinks, crawl system folders, index private application data or create
a persistent index. Private Notepad draft names are not exposed by the current
storage provider, so they are not searchable in this release. A later Notepad
integration requires a mediated, application-owned document listing.

Queries are limited to 64 Unicode code points / 256 UTF-8 bytes, compared using
NFC normalization and case folding. A search retains at most 64 results and
examines at most 4,096 entries, 128 folders and 12 nested levels, with a 20-second
worker deadline and individual provider calls capped at half a second. Provider
directory scanning retains its own existing bounds. Partial searches are marked
explicitly; a missing card is not reported as a complete empty search.

A single worker owns search I/O. Cancel, Home and leaving the view revoke the
current generation; late replies are ignored. Replacing a running query retains
only the newest pending query. The shell keeps display, input, global controls
and update ownership. Search queries and filenames are not emitted to telemetry.

## Evidence

`build/release-0.4.3.06/source-tests.json` records 29 passing focused checks:
14 Quick Find/provider tests, seven Home-state tests, four Browser-paused checks
and four application-editor recovery checks. Search tests use the production
Linux storage owner for Unicode matching, multiple listing pages, excluded
symlinks/content, result caps, changed files and card removal. Additional checks
cover pagination revision changes, deadlines, keyboard ownership, cancelled and
replaced queries, rendered targets and Home/Back navigation.

Two existing Home test fixtures now explicitly start with a closed tray rather
than assuming that obsolete default. Their R3 reservation and animation
assertions remain intact. This is not a pass of the broader legacy shell suite.

GuideOS 0.4.3.06 / signed sequence 70 accepts installed sequence 69. The candidate
preserves the .05 paused Browser, native input, Planegotchi payload/assets,
resident-repair inventory and rolling single-rollback policy. Signature and
unchanged-file hashes are checked during packaging. The package is
`build/release-0.4.3.06/GuideOS-0.4.3.06-quick-find.guide-release`.

Source/provider checks and rendered previews are verified. No .06 Seed write or
Deck activation has occurred. The paired endpoint at its last known address was
unreachable during the delivery check; physical usability remains pending.
