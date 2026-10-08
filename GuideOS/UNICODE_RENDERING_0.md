# Unicode rendering foundation

The inspected Debian build root contained DejaVu fonts, but no Pango provider or
Noto core/CJK/emoji packages. The local build environment now includes those
dependencies; the seed and previously released images have not been changed.

[guide_unicode.py](package/guide-input/guide_unicode.py) provides literal text
measurement, shaping, font fallback, bidirectional display, color emoji and
rendering onto an existing image. It owns no display, input device, text session,
network connection or persistent text history. Layout objects are per-call.
Rendering dimensions and input length are bounded. ASCII keyboard labels retain
the earlier prototype's pixel font; Unicode fields and Wi-Fi labels use the new
provider when present.

The [Debian profile installer](build/install-guide-unicode.sh) adds Pango/Cairo,
Fontconfig and Noto core, CJK and color-emoji fonts to an explicitly supplied
build root. The inspected installation added approximately 160 MB of storage.
The RG35XX H shell and Wi-Fi image preparation paths invoke this profile. It is
an optional display capability for other ports, not a universal minimum; without
it the current renderer retains its narrower DejaVu fallback.

The [ARM64 tests](build/keyboard-0/arm64-validation.json) require the provider and
check representative Latin, Greek, Cyrillic, Arabic, Hebrew, Indic, Thai,
Georgian, Armenian, Chinese, Japanese, Korean, combining-mark and emoji samples.
[Coverage evidence](build/keyboard-0/unicode-coverage.json) records missing-glyph
counts for the rendered sample sheet. Installed versions are recorded in
[unicode-packages.tsv](build/keyboard-0/unicode-packages.tsv). These samples do
not establish coverage of every Unicode character or language.

This is rendering groundwork for later text entry. The shared text core already
preserves Unicode strings and UTF-8 limits. The controller screens still offer
letters, digits and ASCII punctuation. International layouts, composition/input
methods, grapheme-cluster editing and visual bidirectional navigation remain to
be implemented. A sequence of combining characters or emoji is not yet guaranteed
to behave as one editing unit. No physical font readability or runtime memory
acceptance is claimed by the local previews.
