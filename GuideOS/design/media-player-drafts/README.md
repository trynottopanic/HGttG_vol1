# Media player interface drafts

These 640 by 480 images are design fixtures for Audio and Video Player 1. They
are not installed assets and do not establish physical framebuffer acceptance.

- `audio-player-concept-0.png` and `video-player-concept-0.png` are generative
  visual-direction studies using the accepted Paper Theme 0 palette.
- `render_audio_player_draft.py` composes Audio Player 1 from the same shared
  schema as the video screen.
- `render_video_player_draft.py` is a deterministic example renderer composed
  from [Design Schema 0](../../DESIGN_SCHEMA_0.md).
- `audio-player-renderer-draft-0.png` and
  `video-player-renderer-draft-0.png` are the renderer fixtures' current output.

The reusable manifests and shared drawing components live in `../schema/`. The
video fixture supplies semantic example state; the shared tokens and components
supply typography, colors, common geometry, header, footer, badges and panels.
Changing fixture content does not require changing those shared definitions.

Run the renderer with a Python environment containing Pillow. Its semantic font
roles follow [Typography 0](../../TYPOGRAPHY_0.md): Noto Serif for the masthead,
Noto Sans for interface language, and Noto Sans Mono for changing numeric
values. DejaVu is the reduced-profile fallback. Georgia and Segoe UI are allowed
only as development-host preview proxies when the portable faces are absent.
The finished Guide renderer must use the project's Unicode shaping contract.

The fixture's title, time, battery level, routes and tracks are fixed sample
state. Button labels remain candidates pending reconciliation with the shared
input contract. Production playback must receive acknowledged engine state and
must not infer successful pause, seek or output selection from this drawing.
