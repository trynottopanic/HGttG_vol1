# Combined Wi-Fi and input revision

Build `wifi3-20260924` was installed on 24 September 2026 at 23:29 EDT
(25 September 03:29:54 UTC). Full root readback passed and boot/data remained
unchanged. See [installation.json](../build/debian-wifi-3/installation.json).
At installation, physical acceptance was pending. The owner subsequently reported
that the seed works as intended; see the [physical result](WIFI3_PHYSICAL_RESULT_2026-09-24.md).
Original machine-readable validation and installation records retain their
at-installation status.

Candidate and full readback SHA-256:
`6F3C05A19262A6FC361A1CA6FDB0195FF6F43F1B345B5CF3BEACFCB6034A70CB`.

## Contents

This revision combines the Wi-Fi delayed-reply correction, the reusable prototype
keyboard, left-stick keyboard navigation/repeat, right-stick eight-neighbor
entry, R3 case switching, and L1/R1 letters/numbers-and-punctuation layers.
It includes the approved compact layout and centered entry field.

Menus have the left-stick pointer, A/L3 primary click, Y/R3 context click,
relevant context actions, compact 50%-opacity surfaces, expanded action menus,
and right-stick highlight/release selection. Keyboard stick behavior remains
distinct from menu pointer behavior.

Pango/Cairo and Noto provide broad Unicode rendering and script shaping.
International input methods and additional language keyboard layouts remain
future work. Fonts add a platform profile; they are not a mandatory hardware
floor for every GuideOS installation.

The existing kernel, boot partition, data partition, systemd PID 1, independent
Power handling and exclusive shell input/display ownership are preserved.

## Evidence and installation safeguards

The [validation record](../build/debian-wifi-3/validation.json) binds the image
hash to installed source, 258 ARM64 tests, two disposable virtual boots,
NetworkManager profile storage, persistent disconnect hold and clean shutdown.
The delayed D-Bus reply regression record is also checked against current source.
Virtual tests do not establish radio authentication, real display/input behavior,
battery savings, or successful five-second switching between access points.

The guarded writer checks the Transcend TS-RDF5 reader, serial `00000000TS38`,
Windows Disk 4, 62,239,277,056-byte size, and all partition boundaries. It verifies
the private recovery capture and compares the current card's boot-prefix, root
and data hashes before writing anything. A changed card causes an abort.

Only partition 2 is replaced: offset 135,266,304, length 2,147,483,648 bytes.
The complete root is read back and hashed; boot-prefix and data hashes must
remain unchanged. The recovery capture is kept outside the active build root.

## Next physical run

1. Boot and open Wi-Fi. Select **the wifi**, choose Connect, and enter the password
   on the Deck. Check the revised keyboard layout, both layers and stick controls.
2. Confirm the network becomes connected and saved. Disconnect, then reconnect
   from its saved entry without entering the password again.
3. Try the menu cursor and context menu. Check that releasing the right stick
   chooses the highlighted action and that irrelevant actions are absent.
4. If convenient, leave a deliberate Disconnect in effect for over five minutes;
   it must remain disconnected. Test saved credentials across reboot separately.
5. Shut down normally and return the seed for log inspection. Record any visible
   failure message and the action immediately preceding it.

Two-network switching is deferred until a second access point is available.

## Repeatable build path

Run `prepare-wifi3-image.sh`, then `validate-wifi3-guest.sh`, then
`record-wifi3-validation.py`. The first two refuse to overwrite existing working
images. Preserve the previous evidence and use a new revision directory for
later releases. `install-wifi3-seed.ps1` accepts the validated image hash and
refuses an existing installation transcript. It must run as a Windows
administrator; it does not bypass the identity or recovery checks.
