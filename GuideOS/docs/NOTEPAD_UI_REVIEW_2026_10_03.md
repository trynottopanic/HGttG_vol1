# Notepad UI review, 3 October 2026

Follow-up: the owner approved the two draft screens. The
[implementation record](NOTEPAD_UI_IMPLEMENTATION_2026_10_03.md) describes the
implemented source, shared host extension, checks and offline candidate. The
review below describes the earlier application and remains historical evidence.

Review of working source and production-rendered synthetic examples, following
Quick Find implementation. This is a proposed polish direction; no Notepad
application or shared application-presentation API change is included in .06.
On-device acceptance of this review has not been performed.

## Findings

1. There is no document viewport. New/open leads to a menu of Edit text, Read
   note, Save, Save As and Close rather than showing the document. The shared
   application host renders its entire presentation as a generic field list:
   title, notice text and action labels. Notepad cannot currently request a
   semantic document surface.
2. Read note slices text every 90 code points. Paragraphs and words can split;
   a maximum-length note requires 57 chunks. Previous/Next consume ordinary
   action rows. The chunk is rendered in the scrolling notice area rather than
   a readable text pane. Newlines make the visible area especially inadequate.
3. Text requests lack field metadata. The shell calls all fields Application
   text, uses field ID document and always enables multiline input. A Save As
   filename gets the same generic treatment as the note body, despite separate
   name-validation requirements. The round trip also lacks caret position.
4. A cleanly saved note still creates a non-null checkpoint. Every non-null
   checkpoint leads to the recovery screen on launch; Restore then marks it
   dirty, including when the saved note was clean. A synthetic save/relaunch
   probe reproduced this unnecessary recovery decision.
5. Repeated Internal draft/Unsaved/preview explanations compete with the note
   name and content. Reading and editing take extra menu transitions, and the
   document name, destination and save status have no stable visual hierarchy.
6. Storage scope remains the internal-draft preview: sixteen private drafts.
   Ordinary external-document open/export is still absent. Quick Find therefore
   cannot discover these draft names through its public-file provider. This
   requires a separate mediated document interface, not a private-directory scan.

## Recommended first polish pass

Use a notes list and a document view. Opening a saved note should show its text
with preserved paragraphs, wrapping and scrolling. New note should enter the
native keyboard directly. Keep the filename prominent, with a compact Internal
draft/Unsaved destination and Saved/Unsaved changes status; reserve long notices
for actionable errors.

Make Edit and Save direct actions, with Save As and Close in a secondary action
menu. B should return to the notes list through the existing unsaved-change
guard; Menu should keep the existing checkpoint-before-Home behavior. Cancellation,
replacement and failed save must continue to preserve the buffer and saved file.

Extend the portable application presentation contract with a bounded semantic
document view, and the text request with field label, single/multiline purpose
and caret position. Keep rendering, device input and global controls in the
shell; avoid a Notepad-specific privileged display/input path.

Reopen a verified clean saved note without an interruption dialog. Keep explicit
recovery for dirty/interrupted buffers, changed/missing saved objects and invalid
checkpoints. Any state migration must preserve existing private drafts and the
accepted UTF-8 limits. External-document support and Quick Find draft integration
should follow through the documented storage contract.

## Evidence and retained behavior

All eleven existing Notepad tests pass, including recovery, failed save,
failed index publication, full storage, explicit replacement, discard guards
and maximum Unicode checkpoint bounds. The four shared application-editor
recovery checks also pass with Quick Find. These checks support retaining the
save/recovery safeguards during a UI pass; they do not establish physical UX.

Synthetic production-rendered examples and the clean-relaunch probe are under
`build/release-0.4.3.06`: `notepad-note-menu.png`, `notepad-read.png`,
`notepad-clean-relaunch.png`, `notepad-existing-tests.log`, `notepad-review.json`.
