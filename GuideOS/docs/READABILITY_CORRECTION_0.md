# Deck readability correction 0

Physical acceptance, 26 September 2026: the owner confirmed the text is readable at the new size. The owner also confirmed changed, improved terrain. Star visibility and initial external-card detection remain unresolved; see [follow-up](CARD_STAR_FOLLOWUP_0.md).

Installation update, 26 September 2026: readability and boot-preparation correction written and fully readback-verified. Boot/data unchanged. Physical retest pending. See [latest handoff](RELEASE_0_3_7_HANDOFF.md). Earlier evidence follows.

Status: candidate validated; not installed. All 415 existing regressions pass, including reruns of the affected input/UI suites after final spacing changes. Integration renders cover seven surface families and four Wi-Fi states, matching hit regions and masked password entry. Home, Status, keyboard and forget-confirmation previews were visually checked. Physical readability remains pending.

The owner reported that Field Theme text was too small, except the status strip.
Anbernic specifies a 3.5-inch, 640 by 480 RG35XX H display:
https://win.anbernic.com/product/364.html
Its calculated density is 800 / 3.5 = 228.57 pixels per inch. PPI alone does not
establish readable type: the selected sizes are an engineering response to the
owner's physical feedback, pending another physical check.

The Field renderer owns this correction. Main text is 24 px, headings 28 px,
secondary text and controls 20 px. The status strip is unchanged. Menus show
four rows with room for details; System Status uses the full content width.
Home retains the ten-cell layout and five active destinations. The keyboard
and diagnostic pane use larger text with corresponding spacing. Transparent
text composition now applies glyph alpha once instead of twice, improving
stroke contrast. Truncation remains explicit at fixed role sizes.

No provider permissions, input gestures, device ownership or update scope
change. The next image also adds a fixed read-only boot journal, launch-command
and counter snapshot to the existing paired Inspect operation. The current
installed report lacks that evidence; it is insufficient to diagnose the old
landmass conclusively. The native starfield is present in the verified image,
so missing visible stars alone does not establish that an old executable ran.

The staged candidate derives from the fully verified installed Field image.
It must be rebased onto a fresh capture of the returned seed before writing,
preserving intervening owner state. The paired updater covers shell/input only;
shared UI modules and root diagnostics need the root-image update path.

## Returned-seed boot evidence

The fresh returned-seed capture on 26 September preserves both post-update boots.
Their journals record GUIDE_BOOT_WORLD generation-failed-or-timeout at 3066 and
3079 ms, followed by successful native playback. The counter is 2. This establishes
that the dynamic wrapper ran and selected fixed assets; the timing is consistent
with exhaustion of its three-second limit. It does not establish star visibility.
Preparation now has ten seconds, with the outer initialization budget increased
to 22 seconds and the service limit to 36 seconds. The generator reports timeout
separately from nonzero exit. This is a bounded correction requiring physical
verification, not proof that ten seconds is sufficient on the Deck.
