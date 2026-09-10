# Android Companion 0

## Purpose

The working name **Guide Companion** describes a small Android APK that lets a
person offer selected phone abilities to their Deck. It is an interface device,
not a Semiotic Engine, a remote-control back door, or a second identity system.

The first offered ability is:

```text
phone.notifications.discord.observe
```

It means: report selected facts from new Discord notification cards after the
phone owner enables both Android notification access and Discord forwarding.

## First screen

The first interface contains four understandable decisions:

- whether Android has granted notification access;
- whether Discord forwarding is enabled;
- whether the Deck sees sender only, a short preview, or the full notification;
- whether queued events should be forgotten.

It also states whether a Deck is paired. Pairing is visibly unavailable in build
0.1, so no captured event can leave the phone accidentally.

## Data contract

Every accepted notification becomes one bounded JSON object:

```json
{
  "protocol": "guide-event/1",
  "type": "message.received",
  "capability": "phone.notifications.discord.observe",
  "event_id": "64 lowercase hexadecimal characters",
  "occurred_at_ms": 0,
  "expires_at_ms": 0,
  "source": {
    "kind": "android.notification",
    "application": "discord"
  },
  "message": {
    "sender": "up to 80 characters",
    "conversation": "up to 120 characters or null",
    "preview": "up to 512 characters or null",
    "content_state": "hidden, unavailable, preview, or full"
  }
}
```

Control characters are removed. Sender, conversation, and preview lengths are
capped. The event identifier is derived from the Android notification key,
time, sender, and content, then represented only as a SHA-256 digest. A Deck
must reject expired or repeated identifiers.

## Processing architecture

```text
Android notification system
    -> Discord package gate
    -> user-enabled capability gate
    -> bounded field extraction and privacy reduction
    -> duplicate/expiry gate
    -> temporary queue
    -> authenticated Deck transport (deliberately disabled in build 0.1)
```

The Android callback performs only the two gates and schedules the remaining
work on one background worker. Future network delays therefore cannot freeze
Android's notification service or the APK interface.

## Security rules

- Never request a Discord password, account token, or message history.
- Test the package name before reading notification content.
- Never log raw notification text.
- Keep no more than 50 events; expire each after ten minutes.
- Keep the prototype queue in memory until encrypted local persistence exists.
- Do not enable cleartext network traffic.
- Do not send before mutually confirmed and revocable Deck pairing exists.
- Grant no reply, attachment, contact, microphone, camera, or file capability by
  implication.
- A notification that Discord does not produce cannot be observed by this path.

## Acceptance path

### Build 0.1: private capture boundary

- The APK installs and opens on an Android 8 or newer phone.
- The user can enter Android's notification-access screen.
- Turning forwarding off prevents all Discord extraction.
- Non-Discord notifications are discarded before their fields are read.
- Privacy choice changes the fields placed in the temporary event.
- Duplicates and expired events are rejected; queue capacity is enforced.
- No data leaves the phone.

### Build 0.2: trusted Deck delivery

- Phone and Deck pair with matching human-readable confirmation.
- A new Discord direct-message notification reaches a Deck Messages view on the
  same local network within five seconds under ordinary conditions.
- Muted or suppressed Discord messages are reported as unavailable rather than
  silently promised.
- Disabling forwarding or revoking either companion stops delivery immediately.
- Replayed, expired, malformed, oversized, or unauthenticated events are rejected.

### Later, separately granted capabilities

Replies, notification actions, attachments, other applications, and access to a
Node are separate contracts. None should be added by expanding the meaning of
the first capability.

## Concrete next tasks

1. Install a current Android Studio/JDK/SDK toolchain and generate the official
   Gradle 9.6 wrapper.
2. Compile build 0.1 and test extraction against real Discord notification
   shapes on the user's phone without transmitting them.
3. Add a privacy-safe diagnostic screen that shows field presence and lengths,
   never other applications or raw message content.
4. Define a transport adapter against the Deck's existing companion trust store.
5. Implement QR-assisted local pairing and encrypted event delivery.
6. Add a Deck Messages view and run the build 0.2 acceptance path.
