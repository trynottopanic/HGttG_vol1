# UI flow audit — 0.4.1 working source

## Scope and evidence

This audit is based on the current working source under `board/rg35xxh/debian/shell0` and project version `0.4.1`. It does not use the r16 candidate as the basis for findings. It is a static control-flow audit; no tests were run and no input was sent to the Deck.

## Initial findings

The findings below record the baseline audit before the source corrections in the follow-up section.

### 1. Media view Back behavior still carries the old AudioPanel navigation — medium priority

The 0.4.1 source correctly maps A in the player to pause/resume and intercepts B in the player to return through `navigation_stack` (`guide_media_panel.py:137-149`, `guide_shell.py:236-245`). However, the Media wheel route deliberately opens `MediaPanel.view='library'` (`guide_shell.py:135-138`). For every non-player view, inherited `AudioPanel.key(B)` sets `view='player'` instead of leaving Media (`guide_audio_panel.py:94-105`). The same inherited rule applies to the `music`, `video`, `outputs`, and `bluetooth` views. This is stale behavior from the old audio screen: B from Media Library lands on a player view, and B from a nested list/output view does not return to the prior Media view. A view-history/back-stack policy is missing.

### 2. Settings → Audio label still points to the speaker-test page — confirmed mismatch

Settings describes Audio as “Volume, output and Bluetooth audio” (`guide_v3_ui.py:15`), but `open_v3_setting('audio')` selects `audio-test` (`guide_shell.py:154-167`), which renders only “Test speakers” (`guide_field_ui.py:192-195`). The control link is reachable but does not fulfill its label. Either route it to Media/audio controls or rename the setting to Speaker test.

### 3. About and Diagnostics still share a status destination — confirmed mismatch

Both settings identities map to `status` (`guide_shell.py:154-157`), rendered as “System / Deck status” (`guide_field_ui.py:181-188`). About has no distinct build/hardware identity view from this route, and Diagnostics has no distinct diagnostics view. These entries should lead to separate destinations or be removed/renamed until those views exist.

### 4. Optional Home destinations are visible even when their feature is unavailable — conditional dead links

The Home wheel always declares File browser, Applications, Settings, Web browser, Storage, and Media (`guide_v3_ui.py:11-13`). Dispatch silently returns `False` when File operations, browser support, storage, or media is unavailable (`guide_shell.py:135-152`). Thus any build with one of those providers omitted can display a selectable wheel item that does nothing. The Settings list is also unconditional (`guide_v3_ui.py:15-22`), while its dispatcher returns `False` for missing Wi-Fi, storage, audio, or operations providers (`guide_shell.py:154-167`). Confirm the actual 0.4.1 build profile; then hide/disable absent destinations or show an explicit unavailable state.

### 5. The reported “A returns to player” behavior in Media Library is not reproduced by the current source path

The working source opens Media in `library` view. Its rows include Music, Video, audio output, Bluetooth and volume (`guide_media_panel.py:38-53`); the Home/menu input maps an audio row to `MediaPanel.activate()` (`guide_menu_input.py:286-288`), which handles Music and Video (`guide_media_panel.py:67-70`). Static tracing therefore predicts that A on those rows enters the selected view. The owner's reported bounce back to the player remains a runtime/source-identity discrepancy to resolve on the next built image; it should not be marked fixed based only on this source inspection.

## Confirmed improvements in this working source

- A in the native audio player toggles pause/resume without switching views (`guide_media_panel.py:137-149`).
- B in the native audio player returns to the page that opened it (`guide_shell.py:236-245`).
- Media is now a Home wheel destination and routes to the library (`guide_v3_ui.py:11-13`, `guide_shell.py:135-138`).

These are source-level findings, not compiled-image or physical acceptance evidence. File Explorer Select behavior and browser interaction remain unverified.

## Suggested acceptance on the next image

1. From a file-opened track, verify A toggles playback and B returns to the same File browser location.
2. Open Media from Home. Verify B returns directly to Home; from Music, Video, Output and Bluetooth views, verify B returns one step to the prior Media view.
3. Open every Settings row; confirm each destination matches its label and offers a visible return path. Build without optional providers and check unavailable wheel/settings entries.
4. On the Deck, verify the reported Library A behavior, File Explorer Select tray and browser launch/navigation/recovery/return.
5. Compare the installed shell-file hashes to the built release sources before interpreting any source/runtime discrepancy.

## Source follow-up

The current working source now addresses the baseline findings:

- `guide_media_panel.py` maintains a view stack for Media library, Music, Video, output, Bluetooth and player navigation. `guide_shell.py` handles B through that stack and returns to the prior calling page when no in-Media parent remains. A in the player remains play/pause.
- Settings Audio opens Media controls. Settings About and Settings Diagnostics have separate screens. The diagnostics screen shows Wi-Fi state, the Deck IPv4 address when connected, paired SSH port 2222, and bounded `Guide-Link.ps1` Report/Watch instructions. The existing PC-initiated paired connection is reused; no Deck listener or remote-command facility was added.
- Wi-Fi provider status now includes the selected IPv4 address, including an explicit null when no adapter/address is available.
- Optional Home and Settings routes show an Unavailable screen with Back/Home actions when a provider is absent, instead of silently doing nothing.

These are working-source changes only. They have not been compiled, installed, or accepted on the Deck. The reported Library A bounce still needs to be compared against the next installed build identity. File Explorer Select and browser interaction remain physically unverified.

## Next acceptance

1. Build 0.4.1 and compare installed shell/provider hashes with this source before interpreting behavior.
2. On the Deck, verify A/B player controls; B through Media subviews; launching from File browser and returning to its prior location; and Settings Back/Home.
3. Connect Deck Wi-Fi and confirm Diagnostics displays the usable IPv4 address; run Guide-Link Report and Watch from the paired PC.
4. Verify File Explorer Select and browser launch, navigation, recovery and return.
