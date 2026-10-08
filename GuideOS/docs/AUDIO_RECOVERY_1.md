# Audio recovery revision 1

GuideOS 0.3.2 follow-up to the returned-seed audio/earbud failure. The shared
media provider owns playback and pairing; the board profile owns analog gain;
the shell retains all display/input and global controls. This does not promote
the trusted-shell socket into a public cartridge capability interface.

## Changes

- Bluetooth command failures appear on the Bluetooth page. Missing controllers,
  empty discovery results, unavailable services, permission errors and pairing
  failures receive distinct feedback. Synchronous pairing failures release the
  busy state. Cancel invalidates late callbacks. Connecting stops active discovery.
- The diagnostic collector retains fixed operation/backend error names and
  adapter/power/discovery/connection counts. It never retains device addresses,
  aliases or raw backend messages. Cached BlueZ inventory is still explicitly
  described as known/found devices, not proof that every cached device is nearby.
- Playback records selected-route presence, mute and volume every fifteen
  seconds. Board mixer and radio-blocking/controller counts are sampled once a
  minute and on playback start. The hardware query has a one-second deadline.
  The bar itself does not trigger these hardware queries or radio scans.
- RG35XX H speaker activation sets DAC 58 (-5.8 dB) and line output 27 (-6 dB),
  explicitly enables playback and selects stereo routing. Previously observed
  values were 45 and 16 (combined attenuation 43.38 dB). This is a conservative
  initial board calibration, not a measured sound-pressure guarantee.
- WirePlumber uses software mixing for this codec only. Explicit playback clears
  this selected onboard sink's mute/additional attenuation. Application volume
  remains separate. Headphone activation disables the speaker and uses the
  previous lower analog gains. Other outputs and the default route are not changed.
- Introducing the gain profile lowers saved software volume to at most 20%
  once, preserving zero. Later boots preserve user adjustments. No playback
  starts automatically. Earbud loss still pauses instead of falling back to speakers.
- The revision includes the shared status bar and internet time synchronization
  described in STATUS_BAR_0.md.

## Physical test

1. Boot, check the top bar, and connect Wi-Fi. The time asterisk should disappear
   after internet synchronization; time/date should match Eastern local time.
2. Open Audio > Audio output and select Internal Speaker. Open Music files and
   play Guide-audio-test. Start at the installed volume (at most 20%) and adjust
   gradually. The six-second sample plays left, right, then both channels.
3. Check pause/resume and navigation, then Start+Select to open/close diagnostics.
4. Put the earbud in pairing mode. Select Bluetooth earbuds > Find earbuds.
   A scan ends after twenty seconds; record the exact visible result. If found,
   select the earbud, then select its Audio output before playing.
5. If earbud playback works, disconnect it during playback and confirm playback
   pauses without switching to speakers. Reconnect, select its output and Resume.
6. Shut down normally and return the seed for logs.

Software validation cannot establish audible output, successful board radio
initialization or earbud compatibility. Firmware and the kernel transport support
are present, but a functioning controller was not established in the previous
test. The animation delay/vertical-strip defect remains outside this revision;
its existing review is AUDIO_CONTROL_PHYSICAL_REVIEW_0.md.

Configuration reference: [WirePlumber ALSA device properties](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/alsa.html).

## Software evidence

The candidate passed 258 tests (90 shell, 135 input, 17 audio, 7 diagnostics,
9 control), installed UCM syntax validation, systemd unit verification and
filesystem/payload checks. Two virtual boots exercised actual Debian audio
services. The targeted boot began with an explicitly muted, 1% PipeWire output
using the board sink identity; explicit playback restored an unmuted unity sink
while application volume remained independently controlled. Playback, pause,
resume, output removal/replacement, Bluetooth-absence feedback, overlay crash
recovery and shutdown with the foreground frozen passed. Display/input and
the audio sink were virtual fixtures; the guest has no Bluetooth radio or
internet connection. Evidence is under `build/debian-audio-1`.

## Installation

Written on 25 September 2026 to the identified Transcend seed, physical Disk 4,
partition 2 (offset 135266304, length 2147483648 bytes). Full root readback matched
SHA-256 `A359E2060E3104991618B7B3DEE8F3694DB78EBC8E1CD4C064EF943AD445557A`.
The boot region and data partition matched their prewrite hashes. The installer
exited and closed its disk handles. Installation evidence is
`build/debian-audio-1/installation.json`; physical acceptance remains pending.

Returned-test update: the owner confirms Bluetooth playback/feedback and time
synchronization; internal speakers remain silent. See
[the physical review](AUDIO_RECOVERY_1_PHYSICAL_REVIEW.md) for measurements,
the clock-related logging gap and the next speaker isolation boundary.
