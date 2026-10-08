# WebKitGTK prototype: 0.4.0 integration handoff

Status: source ready for frontend integration. Host rendering and real Weston
session tests passed. ARM64 package resolution passed against the Debian trixie
build baseline. No image or Seed was changed; physical acceptance remains open.

## Scope

Single fullscreen page, HTTP/HTTPS address entry, Back/Forward/Reload, basic
Original/Adapted CSS toggle, pointer-operated keyboard using existing Guide
character layers, a private frontend command channel, and an unprivileged
packaged Weston/WebKitGTK session. The existing Home renderer stays unchanged.
Website state is ephemeral in this first prototype. Browser restart loses it.

HTTP/HTTPS GET downloads now enter the Guide transfer service with scoped cookies,
a destination picker, progress/history, cancellation and explicit collision
choices. WebKit does not select a privileged default destination. POST/blob
requests, uploads, device permissions and FTP remain unsupported. GET requests
are refetched; one-use URLs may require reopening the download. Read
[operations integration](../../../docs/DOWNLOADS_UPDATES_0_4_0.md) for the service
bootstrap, native panels, signed updates and bounded limitations. Tabs, saved
credentials, personal customization and Node rendering remain deferred.

## Frontend integration

Import `guide_browser_frontend.BrowserSession` from `/usr/lib/guideos/browser`.
Construct with `pause_display` and `resume_display` callbacks. Call `start()` or
`start('https://...')` when Browser is selected, then continue calling `poll()`.
The GUI is deliberately not patched here because its replacement is in progress.

The display lease callbacks are mandatory:

1. Reject/defer entry while video owns the display, a text editor/confirmation
   would lose work, shutdown or an update is underway. Preserve music playback.
2. On successful pause, suppress ALL framebuffer drawing and ordinary shell
   navigation. Keep the shell's exclusive gamepad grab, global power/volume
   handling and lifecycle polling alive. Do not close the shell or its media
   panel. Mark the updater as not safe to restart during the lease.
3. Feed ordinary gamepad key events with `session.input(code=code,value=value)`.
   Feed completed normalized stick snapshots with `session.input(sticks=sample)`
   on frames and steady-held ticks. Keep volume/power with the shell.
4. Starting/stopping states consume ordinary input without forwarding it. Running
   state forwards through a shell-owned virtual mouse/keyboard. Call `close()`
   on shell teardown. Unit BindsTo stops the session if the shell stops.
5. Restore only when `poll()` observes the service inactive/failed. Invalidate the
   framebuffer, reset held/armed inputs, redraw the owning page and show `detail`.
   Do not paint Home while the compositor is still stopping. A service-manager
   error must keep the lease held and offer recovery, not resume blindly.

Private local request API: `request('open',uri=...)`, `back`, `forward`, `reload`,
`stop`, `adapted` with boolean `enabled`, `address`, `keyboard`, `status`, `close`.
Status contains readiness/loading/mode/keyboard/history flags, not page contents,
credentials or browsing addresses. Packets are bounded at 8192 bytes. This is a
prototype host adapter, not a newly frozen cross-platform Guide protocol.

## Provisional controller mapping

- Left stick: pointer (existing Guide pointer movement model).
- A: pointer click; B: dismiss keyboard or browser Back.
- X/code 307: address keyboard; Y/code 308: page keyboard.
- D-pad: ordinary arrow keys; L1: Tab focus; R1: activate focused control.
- L2/R2: Page Up/Page Down. Menu: exit to the owning Guide page.
- Start, Power and Reset are not mapped by this adapter.

The keyboard is explicitly opened with Keys or the mapped button. Select a page
field first, type a chunk, then Done inserts it using WebKit's editing API. Page
text drafts are masked because a selected field may be a password. Address
entry is visible. Cancel inserts nothing. Controller typing is initially via
pointer clicks or Tab/activate; full shared stick keyboard behavior is deferred.
These browser-local mappings need a brief physical check; do not change Home's
adopted controls to match them.

## Image integration

Resolve the complete ARM64 set from the target Debian repositories:
`gir1.2-webkit-6.0 python3-gi python3-evdev weston dbus-user-session libpam-systemd`.
Include `dbus-run-session`, `chvt`, uinput support and the existing
`/usr/lib/guideos/input` modules. Check the actual target's dependencies and free
space; the old baseline resolution is compatibility evidence only. Do not
install this runtime through the existing shell-only Wi-Fi update path.

Use `package/guide-deploy/stage_operations.py` for the combined browser, transfer
and signed-update bootstrap. The older `stage.py OFFLINE_ROOT` copies browser
files only and is insufficient for the complete operations flow.
Create the service account using the staged sysusers file (or the image builder's
equivalent). Do NOT enable the unit at boot; the GUI starts it on demand. The
shell's trusted adapter must have /dev/uinput access. Browser itself does not.
The staged service uses tty2 and restores tty1, matching this board's shell.
Review that mapping if the frontend changes terminal ownership. Logind/PAM must
provide a usable seat; keep the WebKit sandbox enabled. No root browser process.

The 0.4.3.02 image candidate replaces launcher-only limits with actual Browser
UID/session containment: 320 MiB soft threshold, 384 MiB resident ceiling and
64 MiB swap maximum. See [memory and recovery policy](../../../docs/BROWSER_MEMORY_AND_RECOVERY_0.md).
These remain provisional RG35XX H settings rather than a universal hardware budget.

## Shared native text entry

Address and Page keys now open the shared Guide text-entry core, keyboard model,
640×480 renderer and stick adapter. Normal Browser X opens Address and Y toggles
page entry. Once editing, the ordinary Guide controls apply: LS/D-pad moves,
A/R3 selects, B cancels, L3 changes case, L1/R1 changes character layer, X inserts
space and Y deletes. RS uses the shared hold-to-highlight/release-to-select
behavior. Menu closes Browser through its normal display-release path;
Start + Select and Power retain their global owners.

Address commits navigate after URL validation. Page commits use WebKit's native
InsertText command for the selected field, without an HTML/script text bridge.
The page draft starts empty and inserts at the current selection; it does not
read or replace existing field contents. Page drafts are masked because the
field may contain a password, and support newlines for a textarea. WebKit and
the webpage still enforce their field constraints. Select a field first, then
open Page keys; automatic opening on arbitrary web-field focus is not implemented.

Drafts are bounded (4096 Unicode code points / 16384 UTF-8 bytes), remain in memory,
and are cleared on submit, cancel, replacement, navigation or shutdown. Status
and input packets contain no draft text. Bounded semantic controller packets
carry the private focus token so old events cannot edit a newly opened field.
Service waits remain on the background observer; stick frames do not spawn a
systemctl process each time.

## Verification and acceptance

Host: real WebKit original/adapted/form preservation; keyboard insertion into a
page field, password and multiline textarea; address cancellation; intercepted GET download completed through the transfer/storage owner; real Weston headless
startup, private commands, keyboard visibility and child cleanup. Separate
simulated lease tests cover refusal, startup timeout and delayed safe restoration.

Still physical: ARM64 rendering/GPU/seat, virtual pointer classification, all
controller keys, 640x480 readability, return Home after normal exit or failure,
video handover and music continuity. Run these on the consolidated 0.4.0 candidate.
Capture returned Seed and preserve owner data before that write. Do not claim
physical readiness from the host tests.
