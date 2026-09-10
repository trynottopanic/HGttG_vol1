# Guide Companion APK — first concrete build

Guide Companion is the phone-side interface for offering narrow Android
capabilities to a paired Deck. Version 0.1 observes new Discord notifications,
turns them into small Guide events, and keeps them in temporary memory. It does
not yet transmit them because authenticated Deck pairing must be connected
first.

## What a person can do

1. Install and open **Guide Companion**.
2. Tap **Choose notification access** and explicitly allow the app.
3. Choose whether Discord forwarding is on.
4. Choose sender-only, short-preview, or full-notification visibility.
5. Revoke notification access or clear waiting events at any time.

Android's notification-access switch is broad: the operating system lets a
listener see notifications from many applications. The service therefore
checks for Discord's package name before reading any notification fields. No
other application's content is normalized, queued, logged, or transmitted.

## Present limit

Discord controls what appears in its Android notification. Muted messages,
suppressed notifications, old message history, attachments, and content omitted
by Discord are unavailable. This APK does not sign into Discord and does not
store a Discord token.

The queue contains at most 50 events, each expires after ten minutes, and the
queue disappears when Android ends the app process. This is deliberately less
convenient than persistent storage while the encrypted pairing path is absent.

## Build or open in Android Studio

Open this folder in a current Android Studio release:

```text
GuideOS/android/guide-companion
```

The project uses Android Gradle Plugin 9.4.0, its built-in Kotlin support,
Gradle 9.6.0, JDK 17, and Android SDK 36. The official Gradle wrapper is
included, so a developer can build from this folder without installing Gradle
separately. From Windows, `gradlew.bat lintDebug testDebugUnitTest assembleDebug`
checks the source, runs the tests, and makes a development APK.

## Very short dictionary

- **APK:** the installable Android application file.
- **Notification listener:** an Android service the user may permit to observe
  new notification cards.
- **Capability:** one specifically named ability; this build uses
  `phone.notifications.discord.observe`.
- **Normalize:** convert Discord's notification fields into one small,
  predictable Guide event.
- **Queue:** a short waiting line for events while a Deck is unavailable.
- **Transport:** the future authenticated and encrypted path to a paired Deck.

## Next build boundary

The next step is not a raw IP-address box. It is an authenticated pairing flow:

1. The Deck displays a short-lived pairing code and a public-key fingerprint.
2. The phone discovers the Deck on local Wi-Fi or accepts a QR code.
3. Both screens show the same human-readable words for confirmation.
4. Each side stores a revocable companion identity in protected storage.
5. Events are encrypted, signed, freshness-checked, deduplicated, and rate
   limited before the Deck displays them.

Only after that succeeds should `DisabledDeckTransport` be replaced with a live
transport.
