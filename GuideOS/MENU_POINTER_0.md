# Experimental menu pointer and context menu

Local source revision, 24 September 2026. The owner requested a stick-controlled
mouse-style cursor outside the keyboard, plus circular context menus. The owner
subsequently approved more than four options and removing irrelevant actions.
Contextual defaults remain Open/Select, Back, Home, and Close where applicable.

This extends the shell's existing input/display ownership in
[Guide View](GUIDE_VIEW_1_DRAFT.md) and [Future framework](FUTURE_FRAMEWORK_0.md).
It does not send mouse events to arbitrary applications or create a general
windowing system. The current shell supplies semantic hit targets for its own
menus and Wi-Fi panel. Future applications can use the shared pointer model and
renderer through a shell-owned presentation adapter.

## Controls

| Context | Control | Result |
| --- | --- | --- |
| Menus | Left stick | Move the pointer continuously; deflection controls speed. |
| Menus | A or left-stick click | Primary click on the visible target under the pointer. |
| Menus | Y or right-stick click | Open the circular context menu; another secondary click closes it. |
| Small context menu | D-pad cardinal press | Choose that direction's available action immediately. |
| Expanded context menu | D-pad up/left or down/right | Step backward or forward through choices; A confirms. |
| Context menu | Right-stick direction | Highlight the sector in that direction while held. |
| Context menu | Return right stick to center | Confirm the highlighted action once. |
| Context menu | Left stick, then A/left-stick click | Move the mouse pointer and click an available wedge. |
| Context menu | B | Close the popup without activating the underlying page. |
| Any menu | Menu button | Close the popup and return Home. |

The popup's center stays fixed when the cursor moves. Its radius is 84 pixels
(reduced from 110), and its background and selected wedge use approximately 30%
opacity. Labels and outlines stay opaque for readability; labels have no opaque
backing stroke. The pointer is a white circular dot at 40% opacity with its
click hotspot at the center. The circle is kept
inside the screen above the control hints. Unavailable directions have no action. Releasing the stick
without first choosing a direction does nothing. There is no reading timeout.
D-pad navigation outside the popup keeps the existing menu behavior and moves
the pointer to the focused item so A remains predictable.

The [keyboard](TEXT_ENTRY_0.md) has its own controls: left-stick flick/repeat
navigation, right-stick neighbor hold/release selection, Y backspace, left-stick
click for case and right-stick click for the primary key. No pointer or radial
menu appears there. Switching between the two
modes requires neutral stick input before a held direction can act again.
Physical Power remains independently owned by systemd-logind.

## Defaults and lifecycle

The top context slot offers the action of the target under the pointer when
applicable. In small menus, Right prefers Back, Down Home, and Left Close. Free
slots can hold other relevant actions. Duplicate destinations are omitted.
Larger menus distribute their actions around the circle. At most eight sectors
appear on one page; longer action lists use six actions plus Previous/More page
controls, preserving access to every action without shrinking labels further.
Power-off still requires a separate confirmation.

Wi-Fi context menus can offer Open, Connect/Disconnect and Forget according to
the selected network. Connect is omitted for unavailable or unsupported networks;
Forget requires saved credentials. Busy operations suppress incompatible new
requests. Forget opens its existing confirmation screen. Menu actions are checked
again before execution. If availability changes while a menu is open, the menu
closes; reopening shows current choices. A held direction cannot silently acquire
a different action because options moved beneath it.

Context actions retain the selected target's identity and page. A Wi-Fi list
refresh cannot redirect an open context menu to a different network. If its
target disappears or the page changes, the stale action does not run.
Connectivity operations retain their existing provider lifetime; closing a
popup alone does not cancel networking.

Missing input, dropped events, device loss and focus changes clear pending
right-stick confirmations. They are not interpreted as a deliberate release.
Holding right-stick click while opening a menu cannot also choose a direction.
Shell reports do not record stick coordinates or keyboard neighbor selections.

The portable model lives in
[guide_pointer_input.py](package/guide-input/guide_pointer_input.py); its
[renderer](package/guide-input/guide_pointer_view.py) takes no hardware ownership.
The shell's [menu adapter](board/rg35xxh/debian/shell0/guide_menu_input.py)
supplies current hit targets and routes their actions.

Experimental tuning starts movement above 24% deflection and stops at 20%,
with a nonlinear precision curve up to 400 pixels/second. A 40 ms exponential
velocity filter reduces angular jitter; centering stops immediately without
coasting. A 50 ms cap on each motion time step avoids jumping after a stalled
frame. Fractional movement accumulates without redrawing identical pixels.
Radial selection engages at 55%, releases at 30%, and uses
7.5 degrees of angular hysteresis. These are configurable implementation values,
not physically calibrated performance claims.

Rendering is capped at 30 frames/second and occurs only for dirty state. The
input loop still preserves complete input-frame order. Pointer-only rendering
reuses one 640 by 480 RGB menu image (921,600 bytes of pixel data, plus library
allocation overhead); it keeps no screen history and clears the cache on text
entry. The dot is a single cached 11 by 11 image. The ordinary idle poll remains
50 ms; active pointer motion or a pending frame uses a shorter bounded wait.
The [cost measurement](build/keyboard-0/input-cost.json) compares full and cached
rendering under ARM64 emulation and checks retained pointer-model allocations.
It excludes framebuffer writes and does not establish hardware CPU/battery use.

## Evidence

The [ARM64 validation record](build/keyboard-0/arm64-validation.json) records the
exact tested source hashes and suites. Tests cover temporal controls, pointer
and keyboard integration, completed input frames, dropped-input recovery, stale
targets and report privacy. Rendered previews establish layout only. Physical
stick orientation, comfort, drift, repeat cadence, release selection, and display
response still require an installed Deck test. This local revision does not
write the seed.
