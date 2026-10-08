"""Optional shared Unicode display provider; no input, devices or text logging.

Pango supplies script shaping, bidirectional display and Fontconfig fallback.
Noto coverage is a Debian image profile, not a universal Guide hardware floor.
Rendering support does not imply an international keyboard or input method.
"""
from io import BytesIO
import math

from PIL import Image, ImageDraw


class ImageCanvas:
    """Pillow drawing facade with an explicit image for alpha compositing."""
    def __init__(self, image):
        self.image = image
        self.drawing = ImageDraw.Draw(image)

    def __getattr__(self, name):
        return getattr(self.drawing, name)


class UnicodeText:
    def __init__(self):
        self.available = False
        try:
            import gi
            gi.require_version('Pango', '1.0')
            gi.require_version('PangoCairo', '1.0')
            from gi.repository import Pango, PangoCairo
            import cairo
        except (ImportError, ValueError):
            return
        self.Pango, self.PangoCairo, self.cairo = Pango, PangoCairo, cairo
        self.available = True

    def _layout(self, text, size, width=None, bold=False):
        if not self.available:
            raise RuntimeError('Unicode display provider is unavailable.')
        if not isinstance(text, str) or len(text) > 16384 or '\0' in text:
            raise ValueError('Invalid or oversized display text.')
        if not isinstance(size, (int, float)) or not math.isfinite(size) or not 1 <= size <= 128:
            raise ValueError('Invalid display size.')
        # Reject invalid surrogate strings without retaining a failed payload.
        try:
            text.encode('utf-8')
        except UnicodeError:
            raise ValueError('Invalid Unicode display text.') from None
        surface = self.cairo.ImageSurface(self.cairo.FORMAT_ARGB32, 1, 1)
        context = self.cairo.Context(surface)
        # Offscreen RGBA glyphs must use grayscale coverage; LCD subpixel
        # masks create colored fringes when composited onto different panels.
        options = self.cairo.FontOptions()
        options.set_antialias(self.cairo.ANTIALIAS_GRAY)
        context.set_font_options(options)
        layout = self.PangoCairo.create_layout(context)
        self.PangoCairo.context_set_font_options(layout.get_context(), options)
        font = self.Pango.FontDescription('Noto Sans')
        font.set_absolute_size(round(size * self.Pango.SCALE))
        if bold:font.set_weight(self.Pango.Weight.BOLD)
        layout.set_font_description(font)
        layout.set_auto_dir(True)
        if width is not None:
            if type(width) is not int or not 1 <= width <= 4096:
                raise ValueError('Invalid display width.')
            layout.set_width(width * self.Pango.SCALE)
            layout.set_wrap(self.Pango.WrapMode.WORD_CHAR)
        layout.set_text(text, -1)  # Literal user text; never markup.
        return layout

    def measure(self, text, size=16, width=None, bold=False):
        return self._layout(text, size, width, bold).get_pixel_size()

    def unknown_glyphs(self, text, size=16):
        return self._layout(text, size).get_unknown_glyphs_count()

    def cursor_x(self, text, position, size=16):
        if type(position) is not int or not 0 <= position <= len(text):
            raise ValueError('Invalid cursor position.')
        layout = self._layout(text, size)
        strong, _weak = layout.get_cursor_pos(len(text[:position].encode('utf-8')))
        return round(strong.x / self.Pango.SCALE)

    def render(self, text, size=16, color=(58, 59, 48), width=None, bold=False):
        layout = self._layout(text, size, width, bold)
        ink, logical = layout.get_pixel_extents()
        left, top = min(0, ink.x), min(0, ink.y)
        w = max(1, max(logical.x + logical.width, ink.x + ink.width) - left)
        h = max(1, max(logical.y + logical.height, ink.y + ink.height) - top)
        if w > 4096 or h > 4096 or w * h > 4_194_304:
            raise ValueError('Rendered text exceeds the display budget.')
        surface = self.cairo.ImageSurface(self.cairo.FORMAT_ARGB32, w, h)
        context = self.cairo.Context(surface)
        context.set_source_rgb(*(component / 255 for component in color))
        context.move_to(-left, -top)
        self.PangoCairo.show_layout(context, layout)
        # PNG conversion preserves Cairo premultiplied alpha and color glyphs.
        buffer = BytesIO()
        surface.write_to_png(buffer)
        buffer.seek(0)
        with Image.open(buffer) as image:
            return image.convert('RGBA')

    def draw(self, canvas, position, text, size=16, color=(58, 59, 48)):
        rendered = self.render(text, size, color)
        position = tuple(round(value) for value in position)
        image = getattr(canvas, 'image', None)
        if image is not None:
            image.paste(rendered, position, rendered)
        else:
            # Compatibility for callers supplying only an ImageDraw surface.
            canvas.bitmap(position, rendered.getchannel('A'), fill=color)
