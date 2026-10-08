# Deck video options and track preparation

Date: 6 October 2026. Status: included in 0.4.4.01, written to the Seed.
Deck rendering and physical control acceptance are pending.

## Owner requirement and component mapping

Select while viewing video opens Video options with exactly two entries:
Subtitle track and Audio track. Subtitle track includes None and the tracks
actually offered by the playing source. Audio track lists available audio tracks,
including the selected track and alternatives. No audio-off choice was requested.

The shell owns input and global navigation. Its MediaPanel forwards semantic menu
actions to the existing native media control service. The service renders the
menu through its display-owning mpv process, keeping the display lease and common
audio/video clock. The adapter translates bounded decoder track inventories to
opaque session identities. Track writes use the existing revision-checked Media
Session methods and are verified against the decoder's selected-track property.
The install and install-validation lists include the menu module.

This implements the track-selection requirement in MEDIA_ENGINE_ADAPTER_1.md and
preserves FUTURE_FRAMEWORK_0.md's shell-owned input, navigation and display model.
The JSON command prefix used for literal titles follows the
[mpv 0.40 command parser](https://github.com/mpv-player/mpv/blob/v0.40.0/input/cmd.c).

## Interaction

- Select opens or closes the options menu without changing play/pause state.
- Up/Down moves focus; A opens a track list or applies a choice.
- B returns from a track list to Video options; B there closes options.
- D-pad and A/B are consumed by options, including while a menu close is
  awaiting acknowledgement or the command queue is full. A/B cannot also
  pause/resume or leave the video. Button release and kernel repeat are ignored.
  Failed menu requests retain this input capture until close is acknowledged.
- Outside options, A, seeking and B retain their playback behavior.
- Menu and Power retain the shell's global exit behavior while options are open.
- Subtitles start at None. Language/title labels and selected markers are shown.
- A source with no subtitles offers None. A source with no audio reports that
  no audio tracks are available. Unavailable selections leave the session active.
- Track selection does not reopen the video, seek, or request a new output lease.

## NDI preparation

Automatic FFmpeg preparation now retains up to eight audio tracks, converting
each to AAC and preserving language/title metadata. The first remains the default.
The cache revision changes so previously prepared single-audio copies are not
mistaken for the new multi-track output. Existing cached files are not deleted.
Supported embedded text subtitle preservation remains in place, with its existing
retry without subtitles if conversion fails. Bitmap subtitles remain unsupported
by that preparation path. VLC fallback and the separate manual HandBrake preset
do not establish preservation of alternative audio tracks.

## Validation and remaining evidence

Focused Linux checks exercise service/menu/session/adapter behavior, stale and
unconfirmed selections, subtitle None, alternate audio, literal track labels,
global exits, rapid menu close, failed menu requests, decoder notifications,
session lifecycle and source loss. A real FFmpeg fixture with two audio tracks
and a text subtitle verifies that the prepared MP4 contains both audio languages
and the mov_text subtitle. This is host conversion evidence, not Deck rendering.

The native player currently opens card media through its descriptor source
provider. Native NDI/Node source integration is still absent; these changes
prepare the native track controls and Node-side media preservation, but do not
connect Node streaming to that provider. The retained older FFmpeg Node player
and framebuffer UI are not modified or promoted to the current native design.

The combined release rebuilt NDI 1.0.4 and signed/verified the 0.4.4.01 player
image. [Release evidence](BUILD_0_4_4_01.md) records card-write status separately.
Next acceptance requires the native Node source path, actual subtitle rendering
and readability on the Deck, alternative audio switching with synchronized
playback, paused/running menu behavior and global exit while options are open.
