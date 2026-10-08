# Notepad internal-draft preview 0

Status: supporting image installed and fully readback-verified on the Seed.
The Notepad cartridge awaits installation from the external card on the Deck.
Physical acceptance pending.

## Delivery and independence

`org.hhgtg.notepad` version `0.1.0-preview.1` is an installable Guide cartridge.
Delivery: `build/notepad-0/Notepad-cartridge.zip` contains the `GUIDE/CARTRIDGES`
layout. Copy its contents onto an already recognized Guide external card, then
use the Deck cartridge installer and review the requested permissions.
The cartridge is unsigned and the preview must say so. The image also holds a
recovery copy in `/usr/share/guideos/cartridges/`; it does not silently install
Notepad or approve permissions.

The installer copies application code and assets internally. Notepad stores
notes and recovery checkpoints in its application-private internal storage.
Removing the cartridge after successful installation does not remove Notepad,
its icon, its functionality, or its drafts. No cartridge path is used at runtime.
Uninstall preserves drafts unless the separate explicit data deletion is chosen.

## Implemented

- New, edit with the shared keyboard, read, internal save, Save As and close.
- Sixteen named drafts; case-insensitive name conflicts require explicit replace.
- Unsaved-close/discard confirmation and recoverable interrupted editing.
- Home captures text still in the keyboard before the Supervisor checkpoints and
  stops the application. Done immediately followed by Home retains the submission.
- Strict UTF-8 text limits: 5,120 code points / 20,480 bytes, LF normalization,
  normalized names of 1–32 characters and bounded private-storage objects.
- Corrupt recovery data is reported and not silently replaced. Failed saves do
  not claim success or discard the in-memory document.

## Evidence

- Eleven Notepad tests pass, including maximum Unicode checkpoint size, full
  storage, failed publication, failed save, recovery and explicit replacement.
- Four shared editor tests pass, including Done/Home ordering and cancel guards.
- Live systemd installation passed the production parser/publisher/health path.
  The fixture then removed all cartridge files and invalidated the card catalog,
  launched Notepad, saved a draft, stopped/relaunched it, recovered unsubmitted
  keyboard text on Home, and verified uninstall retained the saved draft.
- The installed ARM64 application and shared editor tests pass in the image.
- Logs: `build/notepad-0/live.log` and
  `build/notepad-media-0/image-validation.log`.

## Preview limits

This is the internal-draft milestone, not full external-document compliance.
External document open/export and a full document viewport remain to be built.
Read note currently uses compact text pages. The host does not yet transfer the
keyboard caret, so recovery records the end of committed text. The fixed host
memory profile is 48 MiB high / 64 MiB maximum; real Deck usage is unmeasured.
Physical cartridge install/removal, typing, power interruption and readability
must still be checked on the Deck.

## Subsequent physical result

The owner confirmed installation and the first-note test succeeded. Returned
logs confirm a committed release, successful health check, normal launch and
durable checkpoint. An additional cold-service startup failure and misleading
uninstalled-record display remain; see
[Notepad physical result](NOTEPAD_PHYSICAL_RESULT_0.md). The latest returned Seed
was read only. Repeated external-card reinsertion remains unresolved.
