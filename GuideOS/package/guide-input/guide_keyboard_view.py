# SPDX-License-Identifier: AGPL-3.0-or-later
"""Portable PIL keyboard view using the earlier Guide prototype's design.

This module owns no input devices, framebuffer, timers, logging or persistence.
The caller supplies a keyboard model and presents the returned RGB image. Text
is never changed to fit the design: ASCII uses the original 5 x 7 bitmap font;
other text uses the optional Pango/Noto provider for shaping and font fallback.
Logical editing still counts code points; visual bidi navigation and input-method
composition remain future work.
"""

from __future__ import annotations

from math import ceil
import os
FIELD = True

from PIL import Image, ImageDraw, ImageFont

from prototype_font import GLYPHS
from guide_unicode import ImageCanvas, UnicodeText


PAPER = (239, 237, 225)
INK = (58, 59, 48)
MUTED = (68, 100, 112)
ACCENT = (157, 78, 34)
SELECTED = (219, 216, 201)
NEIGHBOR = (225, 231, 220)
BORDER = (104, 108, 96)
ERROR = (151, 57, 48)
if FIELD:
    PAPER=(206,226,239); INK=(33,58,73); MUTED=(60,89,105)
    ACCENT=(235,165,46); SELECTED=(83,124,150); NEIGHBOR=(99,124,141); BORDER=(136,163,181)
KEY_SCALE = 0.90
KEY_HEIGHT = 27
ROW_GAP = 9
KEY_TOP = 151
CAPTION_TOP = KEY_TOP + 4 * (KEY_HEIGHT + ROW_GAP) + KEY_HEIGHT + 2
EDIT_TOP = CAPTION_TOP + 7 + 3
EDIT_HEIGHT = 22
FOOTER_TOP = EDIT_TOP + EDIT_HEIGHT + 12
# Seven-pixel footer glyphs sit on a 15-pixel pitch: eight empty pixels between
# lines. Move all content below the header divider down until the bottom has
# the same eight-pixel margin, transferring that space beneath the divider.
BODY_OFFSET = 480 - (FOOTER_TOP + 40 + 7) - (15 - 7)
# Center the label/metadata/field block (base y=76..145) between the header
# divider at y=66 and the fixed first key row. Round to whole screen pixels.
ENTRY_OFFSET = (67 + KEY_TOP + BODY_OFFSET - 70) // 2 - 76

if FIELD:
    KEY_HEIGHT=31; ROW_GAP=4; KEY_TOP=178; BODY_OFFSET=0
    CAPTION_TOP=350; EDIT_TOP=379; EDIT_HEIGHT=31; FOOTER_TOP=417; ENTRY_OFFSET=0

def font_pixels(scale):
    return (24 if scale>=2 else 20) if FIELD else 8*scale

class PrototypeText:
    """Pixel text with a Unicode fallback, without retaining rendered strings."""

    def __init__(self, fallback_font: str | None = None):
        self._font_path = fallback_font
        self._fallbacks = {}
        self.unicode = UnicodeText()

    def _fallback(self, scale):
        if scale not in self._fallbacks:
            candidates = ([self._font_path] if self._font_path else []) + [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "C:/Windows/Fonts/segoeui.ttf",
                "DejaVuSans.ttf",
            ]
            for path in candidates:
                try:
                    font = ImageFont.truetype(
                        path, font_pixels(scale), layout_engine=ImageFont.Layout.BASIC)
                    break
                except OSError:
                    continue
            else:
                # Pillow's own fallback still gives a visible missing-glyph mark.
                font = ImageFont.load_default()
            self._fallbacks[scale] = font
        return self._fallbacks[scale]

    @staticmethod
    def _pixel_text(text):
        return not FIELD and all(character in GLYPHS for character in text)

    def width(self, text, scale=1, *, unicode_line=False):
        if not text:
            return 0
        if not unicode_line and self._pixel_text(text):
            return (len(text) * 6 - 1) * scale
        if self.unicode.available:
            return self.unicode.measure(text, font_pixels(scale))[0]
        return ceil(self._fallback(scale).getlength(text))

    def draw(self, canvas, position, text, scale=1, fill=INK,
             *, unicode_line=False):
        if not unicode_line and self._pixel_text(text):
            x, y = position
            for character in text:
                for row, bits in enumerate(GLYPHS[character]):
                    for column in range(5):
                        if bits & (1 << (4 - column)):
                            left, top = x + column * scale, y + row * scale
                            canvas.rectangle((left, top, left + scale - 1,
                                              top + scale - 1), fill=fill)
                x += 6 * scale
        elif self.unicode.available:
            self.unicode.draw(canvas, position, text, font_pixels(scale), fill)
        else:
            canvas.text(position, text, font=self._fallback(scale), fill=fill,
                        anchor="lt")

    def clipped(self, text, width, scale=1, *, unicode_line=False):
        """Clip a label at a character boundary and visibly mark truncation."""
        text = str(text).replace("\n", " ").replace("\r", " ")
        if self.width(text, scale, unicode_line=unicode_line) <= width:
            return text
        marker = "..."
        if self.width(marker, scale, unicode_line=unicode_line) > width:
            return ""
        low, high = 0, len(text)
        while low < high:
            middle = (low + high + 1) // 2
            if self.width(text[:middle] + marker, scale,
                          unicode_line=unicode_line) <= width:
                low = middle
            else:
                high = middle - 1
        return text[:low] + marker


class KeyboardRenderer:
    """Render a keyboard model at 640 x 480, optionally fitted to another size.

    The prototype's staggered rows use 90% key boxes and horizontal pitch, with
    half the empty vertical spacing. Text keeps its original readable size.
    The sixth row contains explicit text-caret editing controls.
    Sizes other than 640 x 480 use a centred, aspect-preserving nearest-neighbour
    fit. Smaller images are previews, not a claim of readable small-screen UX.
    """

    def __init__(self, application_label="", fallback_font=None):
        self.application_label = application_label
        self.text = PrototypeText(fallback_font)

    def _center(self, draw, y, text, scale=1, fill=INK, width=584, *, offset=BODY_OFFSET):
        label = self.text.clipped(text, width, scale)
        self.text.draw(draw, ((640 - self.text.width(label, scale)) // 2, y + offset),
                       label, scale, fill)

    def _field(self, draw, session):
        # Obtain only the model's display form, so a secret cannot accidentally
        # enter the visible text path. One display character per codepoint is
        # part of the session contract, including when the text is masked.
        visible = session.display_text()
        if session.request.secret:
            # The historical keyboard used asterisks. Translate the model's
            # mask to that visual form without reading its secret characters.
            visible = "*" * len(visible)
        else:
            # Keep each displayed marker one codepoint wide for logical cursor
            # indexing; tabs remain in the result but are visible while editing.
            visible = visible.replace("\t", "\u2192").replace("\u2028", "\n").replace("\u2029", "\n")
        cursor = min(max(0, session.cursor), len(visible))
        line_index = visible.count("\n", 0, cursor)
        line_start = visible.rfind("\n", 0, cursor) + 1
        caret_column = cursor - line_start
        lines = visible.split("\n")
        first_line = max(0, line_index - 1)
        draw.rectangle((28, 106 + ENTRY_OFFSET, 612, (170 if FIELD else 145) + ENTRY_OFFSET), outline=BORDER)
        top = (110 if len(lines)>1 else 120 if FIELD else 118) + ENTRY_OFFSET
        for index, line in enumerate(lines[first_line:first_line + 2]):
            current = first_line + index == line_index
            unicode_line = not self.text._pixel_text(line)
            position = caret_column if current else 0
            start, end = self._window(line, position, 552, unicode_line)
            display = line[start:end]
            y = top + index * (28 if FIELD else 17)
            self.text.draw(draw, (42, y), display, 2, INK,
                           unicode_line=unicode_line)
            if start:
                draw.polygon(((32, y + 6), (37, y + 2), (37, y + 10)), fill=MUTED)
            if end < len(line):
                draw.polygon(((607, y + 6), (602, y + 2), (602, y + 10)), fill=MUTED)
            if current:
                before = line[start:position]
                x = 42 + (self.text.unicode.cursor_x(display, position - start, 24 if FIELD else 16)
                          if unicode_line and self.text.unicode.available else
                          self.text.width(before, 2, unicode_line=unicode_line))
                # Preserve the pixel font's two-pixel gap after the previous
                # glyph. Fallback advances already include their spacing.
                if before and not unicode_line:
                    x += 2
                draw.line((x, y - 1, x, y + (26 if FIELD else 14)), fill=ACCENT, width=2)
        if first_line:
            draw.polygon(((614, 108 + ENTRY_OFFSET), (619, 108 + ENTRY_OFFSET),
                          (616, 105 + ENTRY_OFFSET)), fill=MUTED)
        if first_line + 2 < len(lines):
            draw.polygon(((614, 141 + ENTRY_OFFSET), (619, 141 + ENTRY_OFFSET),
                          (616, 144 + ENTRY_OFFSET)), fill=MUTED)

    def _window(self, line, cursor, width, unicode_line=False):
        """Return a bounded horizontal slice whose insertion caret stays visible."""
        low, high = 0, cursor
        while low < high:
            middle = (low + high) // 2
            if self.text.width(line[middle:cursor], 2,
                               unicode_line=unicode_line) + 4 > width:
                low = middle + 1
            else:
                high = middle
        start = low
        low, high = max(start, cursor), len(line)
        while low < high:
            middle = (low + high + 1) // 2
            if self.text.width(line[start:middle], 2,
                               unicode_line=unicode_line) <= width:
                low = middle
            else:
                high = middle - 1
        return start, low

    @staticmethod
    def _direction_hint(draw, center, direction):
        """Small pixel arrow showing the RS flick for this secondary target."""
        x, y = center
        dx, dy = direction
        tip = (x + dx * 3, y + dy * 3)
        draw.line((x - dx * 3, y - dy * 3, *tip), fill=MUTED)
        base = (tip[0] - dx * 3, tip[1] - dy * 3)
        draw.line((base[0] - dy * 2, base[1] + dx * 2, *tip,
                   base[0] + dy * 2, base[1] - dx * 2), fill=MUTED)

    def render(self, keyboard, size=(640, 480), *, application_label=None):
        """Return a new image; neither the model nor its text is mutated."""
        if (not isinstance(size, (tuple, list)) or len(size) != 2 or
                any(type(value) is not int or value <= 0 for value in size)):
            raise ValueError("Keyboard render size must contain two positive integers")
        image = Image.new("RGB", (640, 480), PAPER)
        draw = ImageCanvas(image)
        session, request = keyboard.session, keyboard.session.request
        application_label = (self.application_label if application_label is None
                             else application_label)
        if FIELD:
            draw.rectangle((0,0,639,27),fill=(20,41,54))
            draw.rectangle((0,28,639,77),fill=(213,221,227))
        if FIELD:
            title='Password' if request.secret else 'Text entry'
            self.text.draw(draw,(20,34),title,2,INK)
            context=self.text.clipped(application_label,290,1)
            self.text.draw(draw,(610-self.text.width(context),39),context,1,MUTED)
            count=f'{len(session.text)} / {request.max_length}'
            self.text.draw(draw,(610-self.text.width(count),78),count,1,INK)
            label=self.text.clipped(request.label,420,1)
            self.text.draw(draw,(28,78),label,1,MUTED)
        else:
            self.text.draw(draw, (28, 34), "Text entry" if FIELD else "The Guide", 2, INK)
            self.text.draw(draw, (30, 54), "" if FIELD else "Don't Panic.", 1, MUTED)
            context = self.text.clipped(application_label, 265, 1)
            self.text.draw(draw, (610 - self.text.width(context), 54), context, 1, MUTED)
            title = "Password" if request.secret else "Text entry"
            self.text.draw(draw, (420, 36), title, 2, INK)
            draw.line((20, 66, 619, 66), fill=BORDER)
            self._center(draw, 76, request.label, 2, MUTED, offset=ENTRY_OFFSET)
            page_name = ("LETTERS abc  1/2", "LETTERS ABC  1/2", "NUMBERS / PUNCT  2/2")[keyboard.page % 3]
            mode = "MASKED" if request.secret else ("MULTILINE" if request.multiline else "TEXT")
            self.text.draw(draw, (30, 95 + ENTRY_OFFSET), f"{mode} / {page_name}", 1, MUTED)
            count = f"{len(session.text)} OF {request.max_length}"
            self.text.draw(draw, (610 - self.text.width(count), 95 + ENTRY_OFFSET), count, 1, INK)
        self._field(draw, session)

        neighbors = {target: direction for direction, target in keyboard.neighbors.items()}
        for row_index, row in enumerate(keyboard.rows):
            pitch, columns = keyboard.row_geometry(row_index, len(row))
            start = (640 - columns * pitch) / 2 - 5
            top = KEY_TOP + row_index * (KEY_HEIGHT + ROW_GAP) if row_index < 5 else EDIT_TOP
            top += BODY_OFFSET
            height = KEY_HEIGHT if row_index < 5 else EDIT_HEIGHT
            scale = 2 if row_index < 4 else 1
            for column, key in enumerate(row):
                # Scale pitch and box width together before pixel rounding. This
                # preserves column-gap proportions and the model's neighbor geometry.
                original_left = start + column * pitch
                left = round(320 + (original_left - 320) * KEY_SCALE)
                right = round(320 + (original_left + pitch - 4 - 320) * KEY_SCALE) - 1
                focused = keyboard.focus == (row_index, column)
                held = keyboard.stick_highlight == (row_index, column)
                direction = neighbors.get((row_index, column))
                disabled = not getattr(key, "enabled", True) or key.action in (None, "disabled")
                if disabled and not key.label:
                    continue
                draw.rectangle((left, top, right, top + height - 1),
                               fill=SELECTED if focused or held else NEIGHBOR if direction else (78,101,117) if FIELD else PAPER,
                               outline=MUTED if direction else BORDER)
                label = self.text.clipped(key.label.title() if FIELD and len(key.label)>1 else key.label, right - left + 1 - (10 if FIELD else 18) - (8 if FIELD and direction else 13 if direction else 0), scale)
                self.text.draw(draw, (left + (5 if FIELD else 9), top + (0 if FIELD else (height - 7 * scale) // 2)),
                               label, scale, (242,247,250) if FIELD and not disabled else MUTED if disabled else (ACCENT if focused else INK))
                if focused or held:
                    # The outline/fill identify key focus; the thin orange line
                    # in the text field separately identifies insertion position.
                    draw.rectangle((left, top, right, top + height - 1),
                                   outline=SELECTED if FIELD else ACCENT if focused else INK, width=2)
                    if FIELD:draw.rectangle((left,top,left+2,top+height-1),fill=ACCENT)
                elif direction:
                    self._direction_hint(draw, (right - 9, top + height // 2), direction)

        error = getattr(session, "error", "")
        if error:
            self._center(draw, CAPTION_TOP, error, 1, ERROR)
        else:
            self._center(draw, CAPTION_TOP, "Edit position" if FIELD else "EDIT TEXT POSITION", 1, MUTED)
        if FIELD:draw.rectangle((0,FOOTER_TOP+BODY_OFFSET,639,479),fill=(20,41,54))
        draw.line((20, FOOTER_TOP + BODY_OFFSET, 619, FOOTER_TOP + BODY_OFFSET), fill=BORDER)
        if FIELD:
            self._center(draw,FOOTER_TOP+1,'LS / D-pad Move · A / R3 Select · B Cancel',1,(242,247,250))
            self._center(draw,FOOTER_TOP+30,'RS Hold/release · L1/R1 Page · Menu Home',1,(196,230,237))
        else:
            self._center(draw, FOOTER_TOP + 10, "LEFT STICK / D-PAD: MOVE   L3: CASE   A / R3: SELECT", 1, (196,230,237) if FIELD else MUTED)
            self._center(draw, FOOTER_TOP + 25, "RIGHT STICK: HOLD TO HIGHLIGHT / RELEASE TO SELECT", 1, (242,247,250) if FIELD else INK)
            self._center(draw, FOOTER_TOP + 40, "L1/R1 SCREEN   B CANCEL   MENU HOME   X SPACE   Y BACKSPACE", 1, (196,230,237) if FIELD else MUTED)
        if tuple(size) == (640, 480):
            return image
        ratio = min(size[0] / 640, size[1] / 480)
        fitted = (max(1, round(640 * ratio)), max(1, round(480 * ratio)))
        canvas = Image.new("RGB", size, PAPER)
        canvas.paste(image.resize(fitted, Image.Resampling.NEAREST),
                     ((size[0] - fitted[0]) // 2, (size[1] - fitted[1]) // 2))
        return canvas
