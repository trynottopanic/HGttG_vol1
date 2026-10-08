# Dynamic globe prototype 0

## Pending update: larger stars and visible world words

The owner requested doubled star size and the three original selection words
above the globe. All twelve stars are now 4 by 4 pixels (twice the pending 2 by
2 size). Stars that would cross the enlarged caption band move to clear
sky margins. Brightness and twinkle timing retain the pending visibility change.

The generator composes a 600 by 24 mask from the exact selected terrain, clouds
and lights words, separated by spaces in that order. It uses a small ASCII glyph
strip rasterized with the existing caption's OCR A Extended, 16-pixel bold font, 11-pixel letter advance and
single-bit settings; the renderer uses the same blue-white color and opacity as
Don't Panic. The line is centered 30 pixels from the top, above the globe. No
font runtime or text parsing is added to the native renderer. The generator's
seed algorithm is unchanged; generator output version is atlas-world-v4 because
it now includes caption-world-words.r8. The glyph asset hash is recorded with the
world metadata. The preparation wrapper verifies the new mask length before
selecting generated assets. Fixed fallback has a blank word line, avoiding false
seed labels. All current vocabulary combinations fit without shrinking type.

This update and the prior external-card retry correction are not installed.
Validation artifacts are in build/boot-words-bold; the earlier preview remains in build/boot-words. Source/image tests do not establish
physical star visibility. Earlier installation and physical evidence follows.


Physical follow-up, 26 September 2026: changed and improved landmasses confirmed by the owner after the ten-second preparation update. Stars still not visible. A visibility adjustment is prepared separately and is not installed; see [follow-up](CARD_STAR_FOLLOWUP_0.md).

Installation update, 26 September 2026: readability and boot-preparation correction written and fully readback-verified. Boot/data unchanged. Physical retest pending. See [latest handoff](RELEASE_0_3_7_HANDOFF.md). Earlier evidence follows.

Returned-seed investigation: the dynamic wrapper ran on both installed boots,
then selected fixed assets after 3066/3079 ms. The candidate expands preparation
from 3 to 10 seconds and reports timeout separately from generator exit failure.
See [correction evidence](READABILITY_CORRECTION_0.md). Physical retest is pending.

Physical result, 26 September 2026: the owner observed the old prebaked landmass and no stars after the combined write. Dynamic boot acceptance failed. Live diagnostics confirm successful playback (481 frames, 16.676 ms mean, no late frames), but the installed report does not expose generator selection or the effective launch command. Source/image validation is not physical acceptance.

Installation update, 26 September 2026: included in the combined Field Theme seed
write and fully readback-verified. Physical acceptance remains pending. See
[installation evidence](FIELD_THEME_IMPLEMENTATION_1.md). Earlier staging evidence follows.

Status: staged and validated in ARM64 emulation, 26 September 2026. Not installed.

## Requirement and boundary

The owner accepted terrain-atlas-draft-v1 on 26 September 2026 for a working
dynamic-globe prototype. This resumes the previously deferred boot-world work.
The existing boot service continues to own the display before the shell; it does
not handle input or Power. Systemd remains PID 1. No Envelope or broker contract
is introduced or changed.

The observable goal is that different boot selections produce different terrain,
cloud and settlement maps, while the same selection and generator version reproduce
the same assets; the native globe rotates and scrolls those maps, then releases
the display. Failure must retain the fixed globe or allow normal shell boot.

## Implemented generation

`apps/boot_animation/guide_boot_world.py` loads the approved atlas, normalizes it
to an 8 by 4 working grid, thresholds its alpha for construction, and removes
obvious fluorescent edge artifacts. The original artwork remains unchanged.
Three broad regions combine the enclosed land stamps in the middle rows, with
seeded selection, reflection, scale and placement. The prototype deliberately
uses enclosed stamps while the open coastline pieces still lack compatible
connectors; it does not claim that the complete 32-cell sheet is a validated
interchangeable tile library. Top and bottom source strips provide continuous
polar caps with 32-64-pixel depths and permanent ice at the outer edges.

The generated terrain is 1024 by 512 RGB565. The 2048 by 512 cloud opacity map
uses the eight stamps in the accepted cloud atlas and retains the existing
20-second traversal. The source alpha and neutral brightness yield opacity;
saturated color fringes, isolated speckles and cell-edge bleed are filtered
before seeded placement, reflection, scale and density variation. Thirty stamps
are composited with maximum opacity, preventing stacked opaque rectangles.
The original artwork stays unchanged; color comes from the existing shader.

Ocean generation adds low-contrast blue bands and 950 small curved wave crests,
wrapped at the longitude seam. Water is painted before land, keeping wave marks
off land and ice. These are static texture details carried by globe rotation,
not a separate animated ocean simulation. Generation runs once per boot.
Generator version is now `atlas-world-v2`; the `atlas-world-v1` seed derivation
is retained so existing landforms, word selections and settlements stay stable.
The cloud atlas hash is included in generated metadata.

Settlement generation is unchanged. Settlement clusters and three road intensities are generated on land;
every hub has a small local street and nearby settlement lights. Longer links
are accepted only when their complete straight path stays on land. This is a
first prototype, not a complete terrain-cost road-routing algorithm. Cloud and
light generation use separate seeds. Coastline edges are periodic; no city
lights or road pixels are placed in the ocean. Source row zero is north, with
the renderer's latitude sampling corrected to match.

The approved vocabulary is stored as a versioned local asset with 200 terrain
adjectives/adverbs, 310 cloud nouns and 150 light verbs. Each category uses
`((count - 1) % category_size) + 1`, including recurring entry 1. A versioned
SHA-256 seed drives each layer. The complete selection repeats after 18,600
boots. Words are seed material, not semantic terrain commands. World metadata
records the words, indices, generator version, atlas/vocabulary hashes and
output hashes for reproduction.

## Distant stars

The native renderer scatters exactly 12 fixed stars outside the globe and caption:
eight single pixels and four 2-by-2 points at the 640-by-480 target resolution.
Their cool white brightness stays between 8.5% and 18%, with smooth occasional
pulses and staggered phases over 5.5-8.7-second periods. There is no motion,
flashing, added asset load or additional boot preparation. The existing display
owner and animation deadlines remain unchanged.

The actual GLES shader test checks all expected star pixels across three times,
verifies changing brightness within the faint range, and requires the rest of
the sky to remain black. Both generated worlds passed. Visibility on the Deck
and frame timing with its GPU still need physical confirmation.

## State, limits and recovery

`guide_boot_dynamic.py` persists a counter under `/var/lib/guideos-boot-world`.
The first dynamic boot is count 1; it does not invent a historical lifetime boot
count. A lock, atomic replacement and fsync protect the state. The kernel boot
ID prevents retries in the same boot from consuming another count. Corrupt
state is preserved and triggers the fixed-world fallback rather than silently
resetting the sequence.

Only generated assets live under `/run/guideos-boot-animation`; no full atlas
processing occurs per frame. The worker has a three-second preparation deadline,
and all six output sizes must match before the native renderer uses them. A
failed or timed-out worker selects the unchanged fixed assets. Termination
kills and reaps the worker. The existing first-frame readiness pipe survives
execution of the wrapper into the native renderer.

The dynamic service drop-in allows 15 seconds for preparation plus graphics
initialization (the existing 12 seconds plus a three-second generation budget),
retains the ten-second playback watchdog around the eight-second visual, and
uses a 29-second outer bound. Existing console cleanup, display release and
shell ordering remain intact. Actual hardware initialization and timing still
need measurement; emulated results are not those measurements.

The installer retains the accepted renderer as
`guide-boot-animation-fixed-backup`, leaves its fixed assets intact, and enables
the dynamic mode through `40-dynamic.conf`. Removing that drop-in restores the
fixed-asset execution path; the original binary also remains available for
recovery. This requires a seed/root update, not the shell-only network updater.

## Evidence and remaining work

The cloud/ocean candidate passed all 14 animation/console/runner Python tests,
the native runtime checks, and actual GLES shader rendering for two worlds
across multiple rotation/cloud phases. Cloud/ocean generation previously took 1.308 and 1.239 seconds
in ARM64 emulation; Deck preparation time remains unmeasured. Boot 1 selects
`ever / length / moved`; boot 2 selects `well / point / said`.

Candidate: `build/dynamic-globe-v3/guide-dynamic-globe-root.ext4`.
SHA256: `9D7A911883E675F656A1F97F9F28A3AF3863F95E2DEFE1ABF21C53A1327FF759`.
The file comparison against the cumulative base preserved 23,585 existing files
and symlinks; only the native globe executable changed, with an exact backup of
its predecessor. Seven expected files were added. Existing fixed maps, audio,
external-card support, owner state and interface changes remain preserved.
The base's 415 regression results are inherited evidence, not a new full-suite run.
See `build/dynamic-globe-v3/candidate.json` and `preservation.json` for records.

Rendered previews: [boot 1](../build/dynamic-globe-v3/globe-boot-1.png),
[boot 2](../build/dynamic-globe-v3/globe-boot-2.png), and
[assembled terrain](../build/dynamic-globe-v3/terrain-boot-1.png).

Prior validated images and previews remain under `build/dynamic-globe` and
`build/dynamic-globe-v2`.
Cloud tests also check opacity range, sparse coverage, seam continuity and
rejection of an entirely colored/noise atlas. Ocean tests check reproducibility
and visible longitude detail.

Validation covers RGB565 byte order, exact map sizes, repeatability, changing
boots, independent category wrap, recurring entry 1, longitude edges, polar
continuity, no lights/roads in ocean, counter retries/corruption, failed workers
and preparation timeout. The ARM64 native graphics runtime and actual GLES
shader are exercised separately; shader images show multiple rotation/cloud
phases. The initial visible tile joins were rejected and their previews retained
under build/dynamic-globe/first-preview.

The candidate is based on the latest external-card, volume, pointer and Wi-Fi
indicator candidate. It has not been written to a physical seed. A fresh capture
and state-preserving rebase remain necessary before installation. Physical
acceptance must check two boots, changed/reproducible worlds, animation timing,
clean shell handoff. Preserve the standing exclusion of physical Start, Power
and Reset exercises; independent shutdown remains a system requirement.

Still deferred: full compatible coastline-tile assembly, geographic relief and
moisture masks, more sophisticated road routing, courier ship animation,
and a favorite-world selection UI. These are not needed to exercise the first
dynamic-world path, and are not represented as finished.
