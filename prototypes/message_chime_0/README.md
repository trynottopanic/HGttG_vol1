# MESSAGE-CHIME-0 protocol core

This folder contains the platform-independent safety gate for the Android
phone-to-Deck event test. It verifies that an event came from the paired phone,
rejects old or repeated events, matches only the selected person, and limits
how often the sound may play.

The first prototype uses a shared secret created during local pairing and an
HMAC-SHA-256 signature. HMAC is a standard way for two paired devices to prove
that a short message has not been forged or altered. The message body is not
part of the event.

The Android adapter and Deck audio output are still separate components. This
module deliberately returns a yes/no decision rather than gaining unrestricted
access to speakers or messages.
