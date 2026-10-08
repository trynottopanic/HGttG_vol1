# Card startup and star visibility follow-up

Status: source correction and ARM64 renderer validated; not installed. The storage lifecycle suite passed all 16 tests. Native runtime tests and shader readback across three phases passed; the preview was visually inspected. These are host/emulation checks, not Deck acceptance.

Owner evidence on 26 September 2026: the new text is readable; the landmasses
changed and improved. No stars were visible. The external card was missed at
first, then recognized on removal/reinsertion. The paired diagnostic connection
timed out, so no new runtime logs were collected in this follow-up.

The storage provider polls sysfs every second. A concrete lifecycle bug was
reproduced: the parent discovers a card, a separate probe briefly sees absence,
and the parent sees the same card afterward. It caches absent but previously
only retried error/busy/unsupported for an unchanged card. The new regression
fails before the correction (one probe) and passes after it (automatic second
probe recognizes Guide format without reinsertion). Absent results now join the
existing ten-second retry schedule when sysfs still identifies a card. Truly
absent cards remain on the existing one-second discovery loop. All 16 storage
tests pass. The provider retains its read-only mount and ownership constraints.
This is a confirmed software race, not a confirmed cause of the owner's boot
observation. Kernel-level failure to enumerate the card needs separate evidence.

The star change responds to physical visibility failure: all twelve stars are
now 2 by 2 pixels, with intensity 0.22 through 0.48 rather than 0.085 through
0.18. Positions remain in the same sky regions; twinkle periods and phases are
unchanged. A star remains much smaller than the globe and the rest of the sky
stays black. This is an engineering visibility adjustment, not proof that
brightness was the only hardware issue. Renderer tests check exactly 48 lit
sky pixels, twinkle variation and no other exterior light across three frames.

No device write was performed. Build artifacts are in build/card-star-followup;
physical confirmation of both corrections is still required after installation.
