# WebKitGTK decision and first runtime evidence

Status: owner-selected browser direction for 0.4.0; development-host prototype
verified. No Seed, installed release, owner data or release version was changed.

The owner selected WebKitGTK to reuse established components and spend work time
on Guide integration. This supersedes the earlier WPE-first recommendation.
Home remains the existing shell. GTK does not become a universal GUI requirement.

Implementation: [prototype and limitations](../apps/browser/gtk/README.md).
Use packaged GTK 4, WebKitGTK 6.0 APIs and Python GI. Prefer a packaged minimal
Wayland compositor for the eventual Deck display session; do not build a custom
compositor or rewrite the shell. Exact Debian ARM64 dependency selection remains
pending, rather than adopting the development host's package set blindly.

Verified on the Ubuntu WSL development host using WebKitGTK 2.52.6, GTK 4.22.4,
a virtual X display and an ordinary user, without disabling the WebKit sandbox:

- Real WebKit process loads a local HTTP fixture.
- Adapted CSS changes layout without reloading the page.
- Returning to Original restores its original styling and preserves form text.
- A real download is intercepted and cancelled with no destination selected.

The fixture tests actual WebKit integration, not a mocked renderer. The virtual
display emitted graphics-driver warnings; these checks do not establish GPU
acceleration, ARM64 compatibility, Deck performance or physical acceptance.

Immediate remaining integration: ARM64 packages/image space; display and input
handover; existing Guide keyboard; supervised lifecycle and private website
state; shared transfer/storage bridge; useful load/TLS/permission recovery UI.
The later transfer integration below supersedes the original unavailable-download state; uploads remain unavailable.
Original/Adapted presently covers a small CSS adaptation, not arbitrary layout
simplification. No full browser-completion claim is made.

Download integration must preserve the engine's authenticated request context
where needed rather than pass only a URL and assume cookies/POST requests survive.
Keep browser code updates separate from the engine dependency set. Complete
runtime upgrades must respect the existing network delivery size boundary.

Physical acceptance: navigation and text entry at 640x480; readable adaptation;
completed download through Guide storage; return Home and video handover; bounded
memory and preserved music playback. Capture the returned Seed before eventual
0.4.0 integration and preserve all owner state.


## Frontend-ready prototype handoff

The source now includes a packaged Weston session runner, unprivileged on-demand
systemd unit, private bounded frontend command channel, trusted shell controller
adapter using the existing pointer model, and GTK text entry using the existing
Guide character layers. Home source was not changed.

[Integration instructions](../apps/browser/gtk/INTEGRATION.md) specify the display
lease callbacks and image staging. The handoff package is
`build/handoffs/webkitgtk-browser-0.4.0/START_HERE.md`.

Additional host evidence: real WebKit page-field text insertion; real packaged
Weston headless session launch, commands, keyboard open/close and complete exit;
four simulated lifecycle tests covering lease refusal, existing-session refusal,
input startup failure and timeout recovery. Packaged ARM64 dependencies resolved
against the existing Debian trixie build root (not the returned Seed image).

The first prototype is ready to wire into the new GUI, not physically accepted.
GET downloads now use the implemented transfer/storage bridge and GTK destination/history screens; see [current operations handoff](DOWNLOADS_UPDATES_0_4_0.md).
ARM64 package installation/space, DRM/logind/VT and virtual controller behavior
remain consolidated-image/Deck checks. Do not restart exact-cause investigations
unless a bounded functional fix fails or preservation is at risk.

## Downloads and update installation continuation

[DOWNLOADS_UPDATES_0_4_0.md](DOWNLOADS_UPDATES_0_4_0.md) supersedes the earlier pending-transfer notes. Real WebKit GET downloads now complete through Guide-owned transfer/storage, and the trusted native Updates panel supports signed Wi-Fi receipt and selected-file import. These remain source/host evidence until the consolidated image is installed and tested on Deck.
