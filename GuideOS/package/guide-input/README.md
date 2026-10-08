# Shared Guide text input

This is the first local implementation of [Text Entry 0](../../TEXT_ENTRY_0.md).
It separates field editing, controller navigation, and rendering so new trusted
shell consumers can share them. It is not yet an application IPC service.

The core uses only Python's standard library. The current renderer needs Pillow
and targets 640x480, using the earlier prototype's glyphs, paper palette and key
layout. The optional [Unicode provider](../../UNICODE_RENDERING_0.md) uses Pango,
Cairo and Noto for font fallback, shaping and color emoji. Without that profile,
rendering falls back to DejaVu. Editing positions still count code points.
The controller layout offers printable ASCII and optional newline.

## A caller supplies field meaning and receives a result

~~~python
from guide_text_entry import TextEntryManager, TextRequest
from guide_keyboard import Keyboard
from guide_keyboard_view import KeyboardRenderer

manager = TextEntryManager()  # normally shared by the shell's foreground owner
keyboard = Keyboard(manager, TextRequest(
    owner_id='app.notes', field_id='title', label='Note title',
    initial='Untitled', max_length=120, max_bytes=480, submit_label='SAVE'))
renderer = KeyboardRenderer(application_label='NOTES')

# The shell maps a fresh device press into an action such as:
keyboard.handle('activate')
# Its existing display owner presents this image:
image = renderer.render(keyboard)

# After explicit submit/cancel, the owner consumes the result exactly once.
if keyboard.session.state != 'editing':
    result = keyboard.take_result()
    if result.state == 'submitted':
        title = result.text  # commit to the application here
# On application exit or loss of ownership:
keyboard.close()
~~~

Direction actions move the selected key; visible LEFT/RIGHT/HOME/END keys move
the text caret. All editing and submit/cancel actions are reachable with the
D-pad and A. The RG35XX H adapter also maps B to cancel, X to space, Y to
backspace and right-stick click to change letter case. This shortcut changes
the available keys, leaving entered text unchanged; the visible CASE key remains
available. The shell owns Menu/Home and physical Power.

L1/R1 map to previous-layer/next-layer, switching between letters and
numbers/punctuation while preserving entered text, caret and remembered letter
case. MORE provides the same operation without shoulder buttons. The host resets
stick state after a shoulder press, requiring neutral before input on the new
screen. Both screens retain submit/cancel and text-editing actions.

Callers explicitly set secret=True for password fields. Purpose describes field
meaning; it does not grant permission, save credentials or automatically mask
text. Wi-Fi declares both purpose='password' and secret=True, with its byte and
character restrictions. Use multiline=True for a notes body. Restrictions reject
an entire invalid insertion and leave the draft intact.

Results and requests retain strings only as needed by their owner; do not log
them, key positions or editing histories. Consuming/cancelling a session clears
its retained draft/result references. Callers must release their own copies.
Python reference clearing is not guaranteed memory erasure.

## Experimental analog-stick adapter

`StickController` receives normalized positions from the existing input owner;
it does not read devices. Keep one controller per active keyboard:

~~~python
import time
from guide_stick_input import StickController

sticks = StickController(keyboard)
changed = sticks.update(left=(0.0, 0.0), right=(0.0, 0.0),
                        generation=0, now=time.monotonic())
~~~

Supply each complete sample in order, then keep supplying the latest snapshot
while visible to support held movement. Coordinates range from -1 to 1, with
positive x right and positive y down. `None` means a missing stick, not neutral.
Change `generation` after an input discontinuity. Both new sessions and missing
or reset inputs require an observed neutral position before acting. Right-stick
click calls `keyboard.handle('case')` and `sticks.reset_right()`; while it is held,
pass `right=None` so a case change cannot also activate a neighbor.

The left stick moves selection in eight directions, beginning hold repetition
after `INITIAL_REPEAT_DELAY=0.350` seconds with `REPEAT_INTERVAL=0.125` seconds.
The right stick calls `activate_neighbor(dx, dy)` once per flick without moving
primary focus. `Keyboard.neighbors` is the shared source for target highlighting
and activation; it omits missing/disabled neighbors and does not wrap. Engagement
uses radius `ENGAGE_THRESHOLD=0.55`, neutral uses `RELEASE_THRESHOLD=0.30`, and
left-stick sector changes use `ANGULAR_HYSTERESIS_DEGREES=7.5`. These are current
experimental defaults, not measured hardware calibration or a frozen public API.

The board adapter buffers ABS_X/Y and ABS_RX/RY until SYN_REPORT and attaches a
complete `sticks` snapshot to each frame event. The host must process all such
events in order, including unavailable samples after SYN_DROPPED or disconnect,
then use `DeckInputs.stick_snapshot()` for idle updates. Do not log these samples,
coordinates, activated neighbors or secret drafts. Closing the editor also releases
its controller. Ordinary D-pad and button text entry remain available.

## Menu pointer

The separate [menu pointer contract](../../MENU_POINTER_0.md) describes the
left-stick cursor, primary/secondary buttons and adaptive context menu.
The shell supplies semantic targets to guide_pointer_input.py and presents
guide_pointer_view.py on its existing canvas. Keyboard sessions bypass this
menu adapter so text shortcuts and right-stick neighbor activation retain their
meaning.

PointerController.open_context accepts a cardinal dictionary for small menus or
an ordered list of action dictionaries for expanded menus. Each action supplies
id and label. Expanded pages contain up to eight sectors; longer lists use
Previous/More without discarding actions. D-pad stepping uses step_choice and A
confirms its highlight. The same sector geometry drives drawing, pointer hit
testing and right-stick release selection. draw_pointer takes the caller's RGB
image so the menu surface can be composited once at approximately 50% opacity.

## Validation and packaging

The [isolated ARM64 validator](../../build/validate-keyboard0-arm64.sh) tests
the production sibling layout used by the shell and compares staged source bytes
with the working tree. The common installer copies the modules into
/usr/lib/guideos/input and the board adapter into /usr/lib/guideos/shell0.

The [current result](../../build/keyboard-0/arm64-validation.json) records the
validated source hashes, suite counts and evidence for its particular snapshot.
Ordinary and multiline callers are exercised without Wi-Fi dependencies.
Physical controller/display acceptance remains pending.
