# Build 0.4.1 media navigation fixes

## Requirements and implementation

- In the native audio player, **A** toggles playback between resume and pause while keeping the player open. `board/rg35xxh/debian/shell0/guide_media_panel.py` owns player input.
- In the native audio player, **B** returns to the page that opened it. `board/rg35xxh/debian/shell0/guide_shell.py` owns page history and routes B through `go_back()`.
- The Home control wheel includes **Media**, opening the media library when the audio/media service is available. `board/rg35xxh/debian/shell0/guide_v3_ui.py` owns wheel destinations and presentation; `guide_shell.py` owns destination routing.
- The system reports release version **0.4.1** in `guide_shell.py`.

## Acceptance and evidence

Source acceptance: A toggles playback without changing views; B restores the prior page; Home wheel selection reaches Media; the displayed release version is 0.4.1.

Physical acceptance remains pending. On the Deck, confirm A pause/resume, B return from a file-opened track to the file explorer, direct Home wheel access to Media, and playback continuity after returning. The file explorer Select tray behavior and Web browser remain untested. The connected Deck has not been written to by this change.
