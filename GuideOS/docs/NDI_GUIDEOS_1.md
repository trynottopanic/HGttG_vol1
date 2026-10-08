# GuideOS NDI 1.0

## Current build: 1.0.4

On 6 October 2026 the 0.4.4.01 combined release rebuilt the companion as
`E:\DGttG\GuideOS-NDI\GuideOS-NDI-1.0.4.exe` and updated the default
`GuideOS-NDI.exe`. The retained build receipt records executable SHA-256
`2257a422dad4a3f731f3bf637a64b298a09891b65f051ec707d87eaf523304ea`.
Automatic FFmpeg preparation preserves multiple audio tracks and supported text
subtitles; [video options](VIDEO_OPTIONS_TRACKS_0.md) records its limits.
The native Deck player still lacks the NDI stream-source provider. A successful
NDI conversion/build does not establish native end-to-end streaming playback.

The original 1.0 implementation and delivery evidence follow as historical
context. [0.4.4.01 release evidence](BUILD_0_4_4_01.md) is the current build record.

This implementation follows the owner's September 30 direction: a new NDI
designed around the working Debian GuideOS implementation, without using the
prototype UI or historical documentation as its design reference.

## Normal connection

1. Open `E:\DGttG\GuideOS-NDI\GuideOS-NDI.exe` on the computer.
2. Open Nodes on the Deck. It searches in the background.
3. Select the computer and enter the code displayed by NDI.
4. Choose **Remember this computer** on the Deck for future connections.

The code exchange accepts the session. Remembering it requires no additional
PC-side trust-arm checkbox. Future searches reconnect remembered computers
automatically. Forgetting a computer ends its remembered access and its current
Node sessions. The new NDI preserves the existing computer identity and remembered
relationships in the runtime's owner configuration.

## Interface

- **Deck:** pairing, session and remembered status, diagnostics, installed version,
  and signed update delivery. When multiple Decks have sessions, select the Deck
  explicitly. A Node session and a verified diagnostic connection have separate
  visible states.
- **Shared media:** add or remove computer folders and refresh their catalog.
  Removal unshares a folder; it does not delete its contents. Media preparation
  remains with the existing provider and the Deck uses its own Media application.
- **Connection details:** manual address recovery, remembered Deck removal,
  connection policy, and the current GuideOS source folder. These controls stay
  outside the ordinary connection path.

NDI obtains the Deck's address from its authenticated Node session and checks
the existing pinned developer connection before enabling diagnostics or update
delivery. It remembers a verified address for later diagnostic reconnection.
An open TCP port alone is never presented as an identified Deck.

**Run diagnostics** performs one bounded current-boot capture, using the installed
Guide-Link helper. It reports progress, failure, cancellation, and the saved path
inline. It does not run the repository's test suites or perform playback probes.

**Send update** stages a signed `.guide-release` through the existing developer
transport. Signature, device identity, compatible base release, and rollback
checks stay inside that transport. The installed Deck still requires its local
Settings → Updates installation action because it restarts the shell. NDI neither
claims an update installed after upload nor bypasses the installed activation
policy.

## Ownership and integration

The new frontend is `node/desktop/guide_ndi.py`. It uses the currently implemented
Node HTTP/discovery service, media provider, and pinned deployment transport.
The transport implementations remain replaceable; the UI does not introduce a
remote shell, a new discovery daemon, or another credential store. PC UI settings
contain only the source folder and remembered address. Existing credentials stay
in their existing private owner locations.

Pairing code renewal and all network, capture, update, startup and media indexing
jobs run outside the UI thread. The UI changes existing controls when state
changes. It does not recreate pages or initiate a service change during resize.

The Deck's connection UI now starts discovery when opened, opens code entry
directly after selection, and offers one relevant remember/forget action.
Its requests run in a worker while navigation remains responsive. A pending Node
request prevents replacing its owning release mid-request. Remembered addresses
are retained by the connection helper, supporting reconnection when the computer
does not advertise. Old trust records acquire the address after a successful
reconnection.

The r21 signed shell release includes its own Node bridge/client modules beside
the shell. The panel uses these release-owned helpers, retaining the previous
system helper only as a compatibility fallback when no local helper is packaged.
This uses the existing signed shell module profile and does not write arbitrary
root filesystem paths. Trust records and sessions keep their existing private
paths. The Deck's Diagnostics screen obtains its Wi-Fi IPv4 address from the
wireless interface in a background worker; it no longer reads a nonexistent
service field or tells an already connected owner to connect first.

## Original delivery and evidence

Build the Windows executable with `node/desktop/BUILD_NDI.ps1`. This build does
not invoke test suites. The canonical executable location is
`E:\DGttG\GuideOS-NDI\GuideOS-NDI.exe`; earlier prototype artifacts remain
separate. Close an already running NDI before starting it because both expose
the Deck-facing port 4365.

The companion Deck release is
`build/release-0.4.1/wifi-r21/GuideOS-0.4.1-home-v3-r21.guide-release`, sequence 56,
compatible with installed sequence 55 (r20). The assembly validates Python
syntax, the release signature, manifest identity, and every payload's size/hash.
Source verification and delivery receipts live beside the bundle. A signed
bundle and a built executable do not establish physical acceptance. No test
suites or physical acceptance exercises were run for this work.

A copy of the companion release is also placed beside the new Windows
executable. **Send update** opens that folder so it can be selected directly.

At preparation time the Deck did not answer at its last verified address,
192.168.4.70, and no port-2222 candidates answered on the computer's local
192.168.4.0/24 network. Delivery is pending; the old installed Deck behavior
continues until r21 is staged and installed. In the new NDI, use **Send update**
once the saved diagnostic connection is available, then install it on the Deck.
This Windows integration currently uses the existing Ubuntu WSL developer
profile and the current GuideOS helper files on the computer.
