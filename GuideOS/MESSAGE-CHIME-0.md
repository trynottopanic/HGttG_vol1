# MESSAGE-CHIME-0

This is the secondary GuideOS event-routing acceptance test.

## Human rule

The user creates this Guide Recipe:

```text
WHEN my phone receives a text from Dad
THEN play "Dad message sound" on my Deck once
```

The friendly words map to two narrow permissions:

- `messages.observe-sender`: the phone may report that a message from one
  selected contact arrived. It does not grant access to every message body.
- `audio.play`: the Deck may play one selected local sound.

## Route

1. A cellular network delivers the SMS to the user's phone in the ordinary way.
2. An authorized phone adapter receives the operating system's message event.
3. The adapter maps the selected contact to a paired Guide person identifier.
4. It creates a signed event with a unique ID, creation time, and event type.
5. The phone finds the paired Deck on the shared Wi-Fi and sends the event.
6. The Deck verifies the sender, freshness, uniqueness, Recipe, and rate limit.
7. The Deck plays the selected sound once and records a minimal success or
   failure result.

The sender's and recipient's cell carriers do not participate after step 1 and
do not need to be the same.

## Privacy and non-aggression rules

- Do not include the text body by default.
- Do not reveal the sender's telephone number on the local network; use a
  pair-specific identifier.
- Do not accept unauthenticated broadcast triggers.
- Reject replayed and stale events.
- Rate-limit repeated playback so message floods cannot make the Deck
  continuously disruptive.
- Let the user disable the Recipe or revoke the phone at either device.

## Android prototype path

Both phones are Android devices. Only the receiving phone needs the Guide phone
adapter; Dad's phone sends an ordinary SMS and requires no project software.

The adapter listens for Android's `SMS_RECEIVED_ACTION` notification and asks
the user for the `RECEIVE_SMS` permission. It extracts only enough sender
information to compare against the person selected by the user, emits the
minimal Guide event, and discards the message body. It does not read historical
messages. Network delivery must be queued as short follow-up work because an
Android broadcast receiver is expected to return quickly.

The first APK will be built from source and installed directly for a controlled
test. Google Play restricts SMS permissions and requires review or a qualifying
core use; direct prototype installation does not remove Android's permission
prompt or our duty to explain and minimize access. Any later store release must
follow the store policy in force at that time.

## Success criteria

- Both phones may use arbitrary cellular providers.
- The user's phone and Deck share Wi-Fi; internet access is not required for
  the phone-to-Deck step.
- A message from the selected person causes exactly one playback.
- A message from another sender does not.
- A replayed event does not.
- Removing either permission stops the behavior.
- The Deck reports a useful failure if it was offline or the event expired.
