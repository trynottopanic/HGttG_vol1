# CONTINUE-ON-DECK-0

This is the first end-to-end GuideOS acceptance test.

## Human action

The user pauses an authorized local video on their desktop Node, connects the
Anbernic Deck by USB, and chooses **Continue on Deck**. When the Node reports
that the handoff is complete, the user disconnects the Deck and continues
watching on it.

## Data that moves

- The original video file, without conversion in the first prototype.
- A small UTF-8 JSON resume record containing a format version, display name,
  byte size, SHA-256 content hash, playback position in milliseconds, and the
  time the record was created.

The resume record uses milliseconds so it is exact to describe. A player may
start on the nearest decodable video keyframe and then seek forward. The
acceptance tolerance is two seconds from the Node's reported position.

## Safe transfer rule

The Node first asks the Deck for its identity, available storage, and supported
formats. The user confirms the named Deck. The Node writes the video and resume
record under temporary names, verifies the final size and SHA-256 hash, and
only then asks the Deck to publish the handoff. Loss of power or removal of the
cable must leave either the previous valid copy or an explicitly incomplete
temporary copy, never a falsely complete movie.

The USB design target is a small private network connection carried by the USB
cable. The Deck remains in charge of its own filesystem; Windows never mounts
the live GuideOS system partition for direct writes. This avoids filesystem
damage from two computers writing the same storage.

## Success criteria

- No internet connection, cloud account, or Semiotic Engine is required.
- The UI names both the sending Node and receiving Deck before confirmation.
- The Node checks free space before sending and shows byte and time progress.
- Cancellation and cable removal are safe and plainly reported.
- The Deck verifies the received content before offering **Resume**.
- Playback begins within two seconds of the saved position.
- Repeating the handoff does not create ambiguous partial copies.
- Logs contain operational facts, not video contents or unrelated personal data.

## Deliberate limits

The first test accepts a local, unencrypted media file the user is permitted to
copy. It does not bypass DRM, copy a protected streaming-service cache, or
promise transcoding. A format the Deck cannot decode must be rejected before
transfer with a useful explanation.
