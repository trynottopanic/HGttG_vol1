# Notepad notes and document views, 3 October 2026

The owner approved the two screens in
`design/notepad-drafts/2026-10-03-v1` and their documented controls. Working source
now implements that direction in Notepad `0.1.0-preview.2`. The shell renders
semantic notes, document and action-menu surfaces through the shared application
interface; the cartridge owns neither display devices nor physical input.

## Behavior

- Normal launch shows New note and up to sixteen saved internal drafts with
  display-only text previews. Directional input moves through the complete list;
  the visible rows follow selection. New note opens the native multiline keyboard.
- Opening a note shows its name, Internal draft/Unsaved destination and
  Saved/Unsaved changes state. The full bounded body is wrapped into a viewport;
  Up/Down scroll by line. Reading no longer slices the document every 90 characters.
- A edits, Y saves, X opens Actions, and B returns to Notes through the existing
  unsaved-change guard. Actions contains Save As, Close and Back. Save As uses
  the native single-line Note name field. Local actions work through controller
  shortcuts and pointer regions. Menu checkpoints the application and goes Home;
  B from the notes list stops it and returns to the launching screen.
- Text submissions and interrupted Home transitions carry the codepoint caret
  into the recovery checkpoint. Cancelling changed keyboard contents still
  requires discard confirmation and preserves the original field constraints.
- A clean checkpoint is skipped on launch only when the indexed saved object
  matches its name, slot and text. Dirty buffers, changed/missing saved objects,
  and invalid recovery data retain the recovery/retention safeguards. Launch
  does not rewrite existing private objects.
- Save-and-close waits for successful saving. Cancellation, replacement refusal,
  failed publication or failed checkpoint retain the current document. Failed
  storage is shown as an actionable notice without claiming Saved. Existing
  atomic object writes, quota, explicit replacement and discard guards remain.

## Shared interface extension

The integer-keyed application-host interface adds optional presentation metadata
to Present (operation 4, argument 4); old requests still work. The metadata
contains a bounded view kind (`notes`, `document`, `menu`), labels, save status,
previews and bindings from semantic local actions to action indices. Notes may
have seventeen actions (New plus sixteen drafts); other views retain eight.
Document views require all four local action bindings. Invalid metadata is
rejected before replacing the previous presentation.

Text (operation 6, argument 3) optionally supplies label, multiline purpose,
initial caret and submit label. The shell's text result optionally supplies
caret at argument 2, delivered as event field 3. Interrupted result field 2 is
retained. Legacy text requests/results keep their previous shape. Revocation
clears extended presentation and text exactly as it clears legacy presentation.

Body limits remain 5,120 codepoints and 20,480 UTF-8 bytes. No capability,
private storage format, data schema or sandbox syscall privilege is added.
Display substitutions for legacy control characters do not rewrite stored text.
External-document open/export and private-draft search remain separate work.

## Evidence and delivery boundary

`build/notepad-ui-2026-10-03/source-tests.json` records 120 passing focused Linux
checks: Notepad retention/recovery, shared runtime validation and real packet
round trips, controller/pointer routing, scrolling, text entry, keyboard,
Quick Find, Home state and Browser pause. `sandboxed-app.json` additionally
records an actual Notepad worker under kernel seccomp using SDK packets through
ready, save, interrupted text/caret and durable checkpoint acknowledgement.
These are development-host checks, not physical Deck acceptance.

Production-rendered launch, document, bottom scroll position, unsaved, error,
Actions and native keyboard examples are in that same folder. They use synthetic
notes. The deterministic cartridge and index are under its `cartridges` folder.

The application-host extension is a root-resident dependency outside the normal
shell-only update. The cartridge must be installed together with that host
extension. The separate `.07` offline root candidate stages them together, along
with the existing Quick Find and Planegotchi work. Its signed image payload is
not a substitute for installing the root components through a system image.
No Seed write or physical boot/interaction acceptance is claimed for this pass.
Any later Seed write must start from a fresh capture so current owner data and
the current rollback release can be preserved.

The independent `.07` image verification passed: 110 signed payload files and
54 system/application files match their inventories; the filesystem check is
clean. The image's ARM64 Python loads the installed Notepad policy/source and
exercises notes/document metadata, saving, native single-line keyboard caret
delivery, rendering and the retained Planegotchi rotation behavior. It also
confirms Browser remains paused and the rollback is `.05`. This is an emulated
ARM64 check, not an on-Deck Supervisor/service or physical performance check.

Candidate: `build/release-0.4.3.07`, signed release ID
`9b1bd0b17b085692e5d5d226224a658e95fdf607ae50b45055ee7f25745b0e9c`,
sequence 71, base 69. The development-only `.06` candidate was never installed.
Cartridge SHA-256:
`4889f909610cd91187ddccf43ab1073d6a8e4066b1f79041017c404f93c9a8bf`.
The `.07` image starts from the verified offline `.05` image; rebase its system
changes onto a fresh current Seed capture before writing, preserving any private
notes/settings created since that earlier capture as well as the owner partition.
