# Audio recovery revision 1: returned-seed review

Owner confirms Bluetooth playback and feedback work as intended, internet time
synchronization works, and internal-speaker playback remains inaudible. This
establishes accessory playback on the tested earbud, not all Bluetooth devices
or every disconnection/recovery case.

## Preserved evidence

Read-only capture:
`E:\DGttG\private-recovery\audio1-return-20260925-075649\seed-used-region.img`.
SHA-256: `6049EB70655F23860F464F3507CDF0A2F78422E95FD92BC64263996F9AA8F4FB`.
Boot: `7063d274-18b4-4916-8da3-3e35278a4e4b`. No seed writes in this review.

## What the measurements establish

- The board gain change took effect: DAC 58 (-5.8 dB), line output 27 (-6 dB),
  DAC and line switches enabled, Speaker Switch enabled, no headphone detected.
  Saved mixer state agrees with the live samples, including samples around
  50, 60 and 76 seconds after boot.
- Playback progresses and finishes. Before Bluetooth connection, the output is
  present and unmuted. At about 60 seconds software volume is 75% and sink
  volume is 100%. The original severe attenuation is therefore not sufficient
  to explain continued silence. No decoder/worker failure was recorded for
  these attempts. These observations do not prove that PCM reaches the codec
  or that its amplifier/multiplexer produces audible output.
- Bluetooth inventory shows discovery, then one connected device at about
  118 seconds. Owner testimony establishes audible Bluetooth output.
- timesyncd reports initial synchronization at 163.636 seconds, to
  25 September 2026 at 07:54:57 EDT. Diagnostic duration measurements continue
  using monotonic time across the wall-clock correction.
- Audio services stopped normally. WirePlumber reported leaked proxies during
  teardown; this does not establish the cause of earlier speaker silence.

## Evidence gap and next isolation boundary

The journal contains only the end of this boot, beginning near synchronization.
The previous clock was in April; the configured seven-day journal retention
limit is a strong explanation for deletion after the September correction.
The separately size-rotated diagnostic log survived. Early kernel messages are
therefore unavailable in this capture, and the speaker cause remains unproven.

The next speaker test should separate direct ALSA playback from the PipeWire
path, capture the codec's PCM activity and DAPM/amp routing while playing, and
retain the early kernel log. The board description routes speakers and jack
through an analog multiplexer and uses PI5 for amplifier control. A logical
Speaker Switch value alone does not establish the physical pin/path state.
Do not raise gain again or alter Bluetooth based on the speaker symptom.

Source corrections queued for the next candidate (not installed): journal
retention is now size-based instead of age-based, preserving its existing size
limits; the HCI controller count now excludes connection entries such as
`hci0:...`, which previously inflated the count during a connection.
