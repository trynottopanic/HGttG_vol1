# Text entry 0 — shared internal keyboard

Status: revised local Python integration, 24 September 2026. The owner requested
an internal keyboard reusable by future applications while testing the existing
Wi-Fi seed. This work does not modify that seed or establish physical acceptance.
The existing Wi-Fi-specific password keyboard is the first integration to replace;
an ordinary-text fixture exercises the same editor without Wi-Fi assumptions.

## Source and responsibility

This implements the system-owned focus and controls described in
[Future framework](FUTURE_FRAMEWORK_0.md#runtime-and-package-architecture) and
[Guide View](GUIDE_VIEW_1_DRAFT.md#focus-and-controls), within the portable-component
direction of [Modern foundation](MODERN_FOUNDATION_0.md). It preserves the password
handling and connection boundary in [Wi-Fi connections 2](WIFI_CONNECTIONS_2.md).
The shared lifecycle and capability interfaces remain unfinished, as recorded in
[Design alignment](docs/DESIGN_ALIGNMENT_0.md#active-architectural-risks).

| Component | Responsibility |
| --- | --- |
| Calling application or system panel | Explain the field's purpose, supply an initial value and appropriate limits, choose ordinary or secret entry, validate meaning, and decide what an explicitly committed value does. |
| GuideOS shell | Own focus, route ordinary controls exclusively to the active editor, retain global navigation and Power behavior, and end the editor when its presentation is dismissed. |
| Shared text-entry core | Maintain the bounded draft and editing position, apply edits and validation, and distinguish editing, committed and cancelled outcomes. It does not know Wi-Fi, Linux input devices or screen dimensions. |
| Keyboard presentation and input adapter | Show the field, draft or masking, focus, actions and errors; translate the current device's controls into editing actions. It does not store credentials or open network connections. |

The implementation is divided between the core/session manager
[`guide_text_entry.py`](package/guide-input/guide_text_entry.py), controller model
[`guide_keyboard.py`](package/guide-input/guide_keyboard.py), and renderer
[`guide_keyboard_view.py`](package/guide-input/guide_keyboard_view.py), with callers
in the Debian shell. None of these shared modules opens hardware devices. The
shell supplies one shared session manager to its panels, and the owning caller
consumes its committed result directly. These are internal Python integration
points. This document
does not freeze a cartridge API, grant schema, callback protocol or cross-process
text service. Reuse now means one shared editing implementation and presentation,
rather than each new application copying the Wi-Fi keyboard.

The 0.4.3.02 Browser candidate also reuses that core, model, renderer and stick
adapter for Address and selected page-field entry. Its GTK adapter presents the
shared image in the existing Browser surface. The shell routes bounded controller
events over the private Browser channel, bound to the current editor's token.
Page entry uses WebKit's native editing command; this is not a webpage-to-host
text service. See [Browser integration](apps/browser/gtk/INTEGRATION.md#shared-native-text-entry).

## Session behavior

1. The caller opens one text-entry session with a visible purpose and explicit
   constraints. Its initial value becomes a separate working draft. Opening the
   session must not consume the same button press again as a character or submit.
2. While editing, navigation, insertion and deletion affect that draft. Reading
   and typing have no countdown. Refreshing another service must not move keyboard
   focus, change the field being edited or submit the draft.
3. The visible submit action checks the field's constraints. Failure leaves the
   editor open with an understandable error. Success produces one committed value
   for the caller; further input cannot submit the closed session again.
4. Cancellation produces no replacement value. The caller's previously committed
   value remains its own state. Submission means the caller received a value; it
   does not imply a file was durably saved, a connection succeeded or another
   service accepted it.
5. Dismissal, replacement or shutdown releases the session's draft references and
   focus. Returning later starts an explicit new session. Automatic persistence of
   editor drafts is outside this first implementation.

The application chooses constraints appropriate to its field. Wi-Fi's current
8–63 printable ASCII password rule belongs to that caller and its provider;
it must not become the universal editor's length or character policy. Validation
must also remain at the provider boundary when that provider has its own rules.
An ordinary search term or title must not inherit Wi-Fi's minimum length or
connection side effect. Reaching a configured limit should be visible; an insertion
must not silently turn into a different value through truncation.
The core can maintain single-line or multiline drafts, as chosen by the caller,
with insertion, backward/forward deletion and explicit cursor movement. A
multiline core option does not imply a finished document editor or uniform
multiline support in every current caller.

## Controls and presentation

The initial RG35XX H presentation uses the D-pad to choose keys and A to activate
the selected key or action. Character entry, case/symbol changes, space, deletion
and submission have visible targets. B cancels the temporary editor. Menu retains
the shell's global return-home behavior and cancels an unsubmitted draft first.
The physical Power key remains under systemd-logind; the editor does not claim or
intercept it. No new Start, Power or Reset gesture is introduced.
The footer shows shortcuts for X to insert a space, Y to delete the preceding
character, left-stick click (L3) to change letter case, and right-stick click (R3)
to activate the main selected key like A. Changing case leaves existing text intact. The same
operations remain available through the on-screen actions, including CASE.

The owner confirmed the earlier prototype as the visual reference:
[`guide-hello-fb.c`](package/guide-hello-fb/src/guide-hello-fb.c), including its
`font[]`, paper/ink palette and `draw_keyboard_keys` presentation. The shared
renderer retains that visual identity. Character rows preserve the 10/9/10/10
QWERTY order in a uniform ten-column grid: Q/A/Z/1 share a column, with the
unused position after L left empty. Uppercase uses the same grid. The punctuation
page similarly aligns all its character rows to its widest row, without adding
selectable blank keys. Shared geometry drives both rendering and neighbor
selection; a missing grid neighbor has no right-stick action. The character
grid is followed by six wider actions: CASE, MORE, SPACE, DEL,
the caller's submit label, and CANCEL. A compact editing row adds HOME, LEFT,
RIGHT, END and DELETE; NEWLINE is available for multiline fields. Here HOME
means the start of the draft, not the shell's global Menu/Home action. DEL removes
the preceding character, and DELETE removes the character after the caret.
These explicit editing actions avoid requiring new hidden button combinations.

The compact revision reduces key boxes and horizontal pitch to 90% of the
prototype dimensions, preserving the proportions of the column gaps. Character
and action rows use 27-pixel boxes with 9-pixel empty gaps (previously 30 and 18).
The final editing row uses 22-pixel boxes, and the empty margins around its
caption are halved. Text sizes remain unchanged for readability.
The footer's bottom margin matches its eight-pixel interline gap. The keys and
instructions are shifted down by 57 pixels. The label, metadata and entry field
are centered as a group between the header divider and the fixed first key row,
leaving 35 pixels above the group and 36 below at native resolution.

L1 and R1 switch between the letters screen and a numbers/punctuation screen.
The second screen starts with digits and includes printable ASCII punctuation;
both retain submit, cancel and editing controls. The visible MORE key also
switches screens. Letter case is remembered when returning from numbers. Switching
screens preserves the draft and text caret, and resets held stick gestures until
neutral so a new screen cannot receive an unintended character.

Selection is visible and predictable. Activating case or symbols changes the
available characters without changing the field or submitting it. Submission
requires the explicit submit action, not reaching a length limit, moving past the
last key, an application refresh or a held activation button. The caller can give
submission a meaningful label such as Connect; the shared editor does not perform
that action itself.

The first controller layout offers printable ASCII characters. The core uses
Unicode strings so other input adapters and later layouts need not replace its
basic session model. This is not a claim of a complete international keyboard:
input methods, composition, visual bidirectional navigation, grapheme-aware
cursor/deletion and locale-specific validation remain future work. The optional
[Unicode display provider](UNICODE_RENDERING_0.md) now supplies font fallback,
script shaping and bidirectional rendering. Initial editing counts code points;
a combining sequence or emoji
sequence is not guaranteed to behave as one displayed character. Limits must state
their unit; a provider's byte limit and an editor's character limit are distinct.

The first renderer targets the existing 640×480 Deck interface. Physical keyboard,
touch, accessibility and headless entry are future adapters, not available just
because the core accepts text. Applications should provide field meaning and
constraints rather than board button numbers or pixel positions.

## Experimental stick entry

The current extension adds a device-neutral
[`StickController`](package/guide-input/guide_stick_input.py) above the keyboard
model. The shell supplies complete normalized samples through its board adapter;
the controller neither opens input devices nor stores text or input history.
This is an experimental control option, with physical ergonomics and timing
acceptance still pending. The values below are configured defaults, not measured
calibration or a universal GuideOS control specification.

- The left stick moves primary key selection in eight directions. A held direction
  repeats after 350 ms, then no faster than one movement per 125 ms observation.
  Delayed observations produce at most one repeat rather than replaying a burst.
- The right stick highlights one of the marked neighboring keys while held.
  Sweeping changes the preview; returning to neutral activates it exactly once.
  Primary selection stays in place, and holding never types repeatedly. Moving
  the primary selection during a preview cancels it until neutral recovery.
- Neighbors are immediate enabled keys around the selected key. Horizontal
  neighbors stay in the same row; character-row neighbors use exact grid offsets.
  At the wider action rows, vertical neighbors use the nearest physical key
  center, with a tie going left; diagonal neighbors are immediately beside it.
  They do not wrap across edges
  or skip disabled targets. The displayed marks and activated targets share the
  same model. Submit and Cancel obey their existing explicit action semantics when
  reached this way.
- Left-stick click changes letter case; right-stick click activates the primary
  key. Both discard a pending neighbor preview. A, editing controls and layer
  switches likewise discard it, preventing a second action on release.
- Each stick must first report neutral after editor entry, missing input, a new
  input generation or loss of focus. The engage radius is 0.55 and the release
  radius is 0.30 on the normalized range. Both sticks' direction changes include
  7.5 degrees of angular hysteresis beyond the sector boundary to resist noise.
  These thresholds govern control gestures, not a deadline for reading or typing.

The RG35XX H adapter uses the verified evdev pairs ABS_X/ABS_Y (0/1) and
ABS_RX/ABS_RY (3/4). It reads current position, minimum, maximum and flat metadata
on open and after dropped-event recovery. Normalization uses the declared midpoint
and full range, clamped to -1 through 1, with positive x right and positive y down.
The kernel already applies the board's orientation; the adapter does not invert
again or mistake the opening held position for center. Missing or invalid pairs
are unavailable, not fabricated neutral samples.

Axis changes are buffered until SYN_REPORT, so a keyboard never sees half of an
x/y frame. Every complete frame retains its own sample and order among button
events; a quick deflection and return within one read therefore remains visible.
An idle snapshot supports hold repetition. Dropped events or disconnection change
the generation and deliver unavailable samples before recovery. These samples,
coordinates and neighboring-key activations remain excluded from shell reports.

Menu returns home and tears down the editor and its stick controller. Power retains
the system-owned path. The D-pad and visible actions remain available; this
extension does not make analog sticks a requirement for applications or text entry.

## Privacy and interruptions

Secret fields are masked. Their contents must not enter shell reports, diagnostic
snapshots, filenames, command-line arguments or generic object representations.
Logging selected key positions or edit actions can reconstruct a password even
when characters are masked, so editor input and cursor details are excluded from
ordinary shell event reports. Ordinary user text is not automatically diagnostic
data either. Errors describe the invalid condition without echoing a secret.

The editor has no credential store, clipboard history, network access or automatic
draft persistence. Explicit submission passes the value to the owning caller;
Wi-Fi then uses its existing local provider path and NetworkManager credential
storage. Cancelling the keyboard must not initiate a connection. Cancelling an
already submitted connection attempt is a separate Wi-Fi lifecycle action.

Ending a session clears its retained draft/result references when consumed or
discarded. Python strings may have copies in process memory; reference clearing
does not guarantee secure erasure. The editor must not claim that masking protects
against physical memory access or that it encrypts the application's saved data.

Focus loss does not grant another application access to the draft or keys. The
current shell integrates one foreground editor at a time. A local session owner
token guards routing and result delivery; it is an internal
focus check, not a capability grant or a security boundary for arbitrary callers.
A general application pause/resume protocol, restoration of non-secret drafts and
concurrent text-entry requests remain future shared-lifecycle work, not an implicit
new service API.

## Acceptance examples and evidence boundary

| Example | Observable result |
| --- | --- |
| Enter an ordinary short title, then submit. | The ordinary-text fixture receives that exact value once through the shared session; no Wi-Fi action occurs. |
| Edit an existing title, then press B. | No replacement value is committed; the existing title remains unchanged. |
| Edit an ordinary multiline draft with the same core and renderer. | A newline is inserted only for a multiline field; cursor movement and deletion edit that draft without a Wi-Fi dependency. |
| Open password entry with A. | The opening press does not type the first keyboard key or submit an empty field. |
| Enter letters, numbers, spaces and symbols. | Every supported character is reachable with the declared controls, and edits preserve exact case and spacing. |
| Submit an invalid Wi-Fi password or insert beyond a field limit. | The error is visible, editing remains available and no connection request is sent. |
| Hold or repeat activation at Submit. | There is at most one committed result and one caller action. |
| A Wi-Fi status update arrives while typing. | The draft, selected key and chosen network identity remain stable. |
| Press Menu while entering a password, then open an ordinary field. | Home is reached; no secret or previous editor state appears in the new session or shell report. |
| Power or shell termination interrupts entry. | Existing system shutdown ownership is retained; an unsubmitted draft does not become an application action. |
| Insert supported Unicode directly into the core. | The core preserves the supplied string within declared limits, without claiming controller-layout, font or grapheme support. |
| Open a field while either stick is held. | No movement or text activation occurs until that stick has returned to neutral. |
| Hold a right-stick neighbor, sweep, then recenter. | The last highlighted neighbor activates once on release; holding does not type or move primary selection. |
| Receive deflection and neutral frames together, or lose an input frame. | Complete frames retain order; loss disarms affected input until actual neutral recovery. |

Source/model tests can establish draft transitions, limits, keyboard reachability,
call-site behavior and report exclusion. Rendered fixtures can check clipping and
focus visibility. Neither establishes actual controller repeat behavior, readable
on-device output, exclusive hardware ownership or independent Power response.
Keep those physical checks separate from Wi-Fi association and saved-network
acceptance.

The local ARM64 tests cover the core, controllers, renderers, Wi-Fi panel, shell,
board sampling and full input routing. They include ordinary/multiline callers,
one-shot submission, stale focus, complete key reachability, limits, masked
rendering, live Wi-Fi refresh during typing, local credential delivery, and
secret-bearing exception suppression, stick timing, dropped-input recovery,
menu/keyboard mode changes and context target identity. The
[validation record](build/keyboard-0/arm64-validation.json) includes source and
test-log hashes. The [package guide](package/guide-input/README.md) shows caller
usage. No seed installation or physical keyboard acceptance is claimed.
