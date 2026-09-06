# Guide Payload Format 0

Payload Format 0 is the first removable-card discovery experiment. It proves
that a Deck can recognize a human-readable Guide package on its external
microSD slot without allowing the card to execute software or silently alter
the Deck.

## Card layout

Use a FAT32 card for the first physical test. Create this file:

```text
GUIDE/PAYLOAD.GDE
```

Its contents are plain UTF-8-compatible ASCII text:

```text
GUIDE-PAYLOAD-0
NAME=HELLO CARD
TYPE=DEMO
SUMMARY=FIRST EXTERNAL GUIDE PAYLOAD
```

`NAME` and `TYPE` are required. `SUMMARY` is optional. For this small-screen
prototype, displayed values are safely shortened to 22, 16, and 44 characters
respectively. The manifest is limited to 4 KiB so it remains easy to inspect
and cannot consume unbounded memory.

## Format 0 security boundary

- GuideOS examines only the second microSD device; it never treats the boot
  card as an external payload.
- The card is mounted read-only with `nodev`, `nosuid`, and `noexec`.
- The manifest must be a regular file and symbolic-link following is denied.
- Format 0 recognizes and displays metadata only. It cannot execute, install,
  copy, or modify payload content.
- The user explicitly opens **Payloads** and presses A to scan. Recognition is
  not consent to perform another action.
- Leaving the Payloads screen unmounts the card. Safe shutdown also unmounts it
  before the root filesystem is made read-only.

Later formats may add content hashes, signatures, declared capabilities,
portable resources, and atomic import. Those features must preserve the rule
that removable media receives no authority merely by being inserted.
