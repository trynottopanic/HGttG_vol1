# Notepad draft 1

The owner approved this draft on 3 October 2026. Production implementation and
its separate evidence are recorded in
`docs/NOTEPAD_UI_IMPLEMENTATION_2026_10_03.md`; these images remain the approved
concept references rather than screenshots of an installed Deck.

Two 640 x 480 concept screens requested by the owner on 3 October 2026.
These use the existing Deck Field/native-keyboard palette and synthetic notes.
They do not modify or install the application.

- `notepad-launch.png`: normal launch to Internal drafts; New note is initially
  selected. Existing notes have a name and short text preview. A selects,
  directional input chooses a row, B returns to the launching screen, Menu goes
  Home through the existing checkpoint path.
- `notepad-document.png`: a clean saved note with persistent title, destination
  and save status, a wrapped/scrollable document viewport and direct controls.
  A Edit opens native multiline text entry; Y Save saves the current draft;
  X Actions offers Save As and Close; B returns to the notes list with the
  existing unsaved-change guard. Menu remains Home. These local control mappings
  are draft choices rather than new global gestures.

Unsaved changes would replace Saved in the same status area. Error and recovery
messages remain conditional. The normal launch examples omit an interruption
dialog for a clean saved note. Filename entry needs a separate single-line
native-keyboard request in the later implementation.

Render source: `render_draft.py`. The draft imports palette constants from
`guide_deck_layouts.py`; there is no new renderer or application API in production.
