# UI flow audit — Seed candidate 0.4.0 r16

## Scope and evidence boundary

Audited the `release-source` bundled with candidate `candidate-v20-home-v3-r16` (release sequence 51, root SHA-256 `2EC705DF2AF250E1E4C9CABBDE9602DA311B14CA229B500F3A0717A236F8B859`). This is the newest Seed candidate currently recorded. Working-tree version 0.4.1 contains newer media/navigation edits, but those edits are not represented by this candidate and have not been compiled into a replacement image. This was a static route audit; no input was sent to the Deck and no tests were run.

## Findings

### 1. Media player has no working B exit — confirmed, high priority

In the candidate, `MediaPanel.player_key()` maps A to stop-and-switch-to-library and B to pause/resume (`release-source/shell0/guide_media_panel.py:137-151`). `ShellState.key()` dispatches to that handler before generic page navigation (`release-source/shell0/guide_shell.py:233-237`); because the handler consumes B, it never reaches the `go_back()` branch. This matches the owner's reported player trap. The current 0.4.1 working source changes A to playback toggle and routes B through page history, but needs image build and Deck acceptance.

The owner also reported that A in “Media: Library” returns to the player. The candidate's static library model exposes Music, Video, output and volume rows, and its action handler accepts those rows (`guide_media_panel.py:38-53, 67-77`). That reported bounce is not explained by this source path. Check the installed runtime/source identity and actual rendered focus/activation after the next image is built.

### 2. Settings → Audio opens a speaker test, not the described audio controls — confirmed, medium priority

The Settings item promises “Volume, output and Bluetooth audio” (`guide_v3_ui.py:14-16`), but `open_v3_setting('audio')` routes to `audio-test` (`guide_shell.py:151-164`). That screen contains only “Test speakers” (`guide_field_ui.py:192-195`). This is a stale route to the earlier diagnostic page; it should either open the actual Media/audio controls or be relabeled to describe the speaker test.

### 3. Settings → About and Diagnostics collapse into the same status page — confirmed, medium priority

Both settings identities map to `status` (`guide_shell.py:151-154`). The rendered destination is “System / Deck status” (`guide_field_ui.py:181-188`). About therefore does not reach the advertised build/hardware identity view, and Diagnostics has no distinct diagnostic view from this entry. These are mislabeled links, not separate completed destinations.

### 4. Media is absent from the r16 Home wheel — confirmed in candidate; fixed only in working source

The candidate wheel has only File browser, Applications, Settings, Web browser and Storage (`guide_v3_ui.py:11-13`). The current 0.4.1 source adds Media and routes it to the media library; this remains a source change until compiled into a new candidate.

### 5. Embedded source manifest carries 0.3.9 metadata — verify intent before release

The r16 candidate metadata identifies release `0.4.0-home-v3-r16`, while its bundled `release-source/manifest.json` says version `0.3.9`. This may identify the base source bundle rather than the system release, so it is not classified as a user-facing route failure. Confirm which consumer reads this manifest and whether the value is intentionally the base version before producing the 0.4.1 bundle.

## Explicitly unverified

The file-explorer Select behavior and Web browser interaction remain physically untested, as reported by the owner. The browser has a static B/MENU return path in the candidate shell, but that does not establish device behavior. Settings entries whose handlers depend on optional providers should also be checked against the candidate's installed feature flags; the static list is unconditional while some handlers return without navigating when a provider is absent.

## Suggested acceptance pass for the next image

1. From a track opened in File browser, press A once and confirm playback toggles without leaving the player; press B and confirm return to the same File browser location.
2. From Home, open Media from the wheel; enter Music and Video; return with B.
3. Open every Settings row and confirm the screen matches its label and has a visible return path. For unavailable features, show an unavailable state instead of silently ignoring activation.
4. Test the File browser Select tray and browser launch, normal navigation, recovery and B return on the Deck.
5. Confirm actual installed shell files match the built release sources before interpreting any runtime/source disagreement.
