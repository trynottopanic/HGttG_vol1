# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pointer and radial context presentation for the 640 x 480 Guide shell.

The shell owns hit testing and actions. This view draws on the caller's existing
PIL canvas and never opens devices, routes input, or draws over the keyboard.
"""

import os
from math import isfinite, cos, sin, degrees
from PIL import Image, ImageColor, ImageDraw
from guide_pointer_input import CONTEXT_RADIUS


BACKGROUND = '#101c2c'
PANEL = '#203047'
INK = '#f1f5fa'
MUTED = '#9cacbf'
GOLD = '#ffd166'
EDGE = '#53657c'
FOCUS = '#8fd3ff'
FOCUS_GLOW = '#244d69'
MAX_RADIUS = round(CONTEXT_RADIUS)
SURFACE_ALPHA = 77  # nearest 8-bit value to 30%
CURSOR_ALPHA = 179  # dark-blue center: 30% transparent, 70% opaque
CURSOR_RADIUS = 6
_DOT_LARGE = Image.new('RGBA', (52, 52))
ImageDraw.Draw(_DOT_LARGE).ellipse((2, 2, 49, 49), fill=(8, 38, 63, CURSOR_ALPHA),
                                   outline=(255, 255, 255, 255), width=8)
_DOT = _DOT_LARGE.resize((13, 13), Image.Resampling.LANCZOS)
VIEWPORT = (640, 480)
SECTORS = {
    'up': (225, 315, 0, -1),
    'right': (315, 405, 1, 0),
    'down': (45, 135, 0, 1),
    'left': (135, 225, -1, 0),
}


def _width(draw, text, font):
    bounds = draw.textbbox((0, 0), text, font=font)
    return bounds[2] - bounds[0]


def _clip(draw, text, font, width):
    if _width(draw, text, font) <= width:
        return text
    marker = '...'
    if _width(draw, marker, font) > width:
        return ''
    while text and _width(draw, text + marker, font) > width:
        text = text[:-1]
    return text + marker


def _lines(draw, label, font, width):
    """At most two short lines, including an explicit truncation marker."""
    words = str(label).split()
    if not words:
        return ['']
    first = words.pop(0)
    while words and _width(draw, first + ' ' + words[0], font) <= width:
        first += ' ' + words.pop(0)
    if not words:
        return [_clip(draw, first, font, width)]
    return [_clip(draw, first, font, width),
            _clip(draw, ' '.join(words), font, width)]


def _label(draw, center, lines, font, color, background):
    """Opaque text over the 30% context surface; no opaque backing stroke."""
    heights = []
    boxes = []
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        boxes.append(box)
        heights.append(box[3] - box[1])
    height = sum(heights) + max(0, len(lines) - 1) * 4
    top = round(center[1] - height / 2)
    for line, box, line_height in zip(lines, boxes, heights):
        width = box[2] - box[0]
        left = round(center[0] - width / 2)
        if line:
            draw.text((left - box[0], top - box[1]), line, font=font, fill=color)
        top += line_height + 4


def _dot(image, position):
    """One cached outlined circle; its center is the click hotspot."""
    x = max(0, min(VIEWPORT[0] - 1, round(position[0])))
    y = max(0, min(VIEWPORT[1] - 1, round(position[1])))
    image.paste(_DOT, (x - CURSOR_RADIUS, y - CURSOR_RADIUS), _DOT)


def draw_pointer(image, pointer, fonts, hover=None):
    """Overlay the model's cursor and optional fixed-center cardinal menu.

    ``hover`` is an optional (left, top, right, bottom) shell hitbox. The model
    supplies a clamped context center, options keyed by cardinal direction, an
    optional highlight, and optional radius/inner_radius geometry. Mouse motion
    does not alter that center. The held RS choice is the strongest highlight.
    """
    draw = ImageDraw.Draw(image)
    context = pointer.context
    if context is None:
        if not pointer.visible:
            return
        _dot(image, pointer.position)
        return

    radius = float(getattr(context, 'radius', MAX_RADIUS))
    if not isfinite(radius):
        radius = MAX_RADIUS
    radius = max(1, min(MAX_RADIUS, round(radius)))
    inner = max(1, min(radius, round(getattr(context, 'inner_radius', 25))))
    x, y = (round(value) for value in context.center)
    options = context.options
    sectors = context.sectors()
    highlighted = context.highlight if context.highlight in options else None
    # Draw one compact RGBA surface, then blend once. Overlapping sectors and
    # the center must not compound opacity over the underlying page.
    surface = Image.new('RGBA', (radius * 2 + 1, radius * 2 + 1))
    layer = ImageDraw.Draw(surface)
    bounds = (0, 0, radius * 2, radius * 2)
    def translucent(color):
        return ImageColor.getrgb(color) + (SURFACE_ALPHA,)
    layer.ellipse(bounds, fill=translucent(BACKGROUND))
    for direction, option in options.items():
        angle, half_width = sectors[direction]
        start, end = degrees(angle - half_width), degrees(angle + half_width)
        layer.pieslice(bounds, start, end,
                      fill=translucent(GOLD if direction == highlighted else PANEL),
                      outline=EDGE, width=1)
    layer.ellipse(bounds, outline=MUTED, width=2)
    layer.ellipse((radius - inner, radius - inner, radius + inner, radius + inner),
                  fill=translucent(BACKGROUND), outline=MUTED, width=1)
    image.paste(surface, (x - radius, y - radius), surface)
    # Put the dot above menu surfaces, then keep option text above the dot.
    if pointer.visible:
        _dot(image, pointer.position)

    font = fonts[14].font_variant(size=20)
    for direction, option in options.items():
        angle, _ = sectors[direction]
        dx, dy = cos(angle), sin(angle)
        width = max(1, radius * (.80 if context.items else 1.05 if abs(dy) > .9 else .68))
        lines = _lines(draw, option['label'], font, width)
        center = (x + dx * radius * .66, y + dy * radius * .66)
        selected = direction == highlighted
        _label(draw, center, lines, font, INK,
               GOLD if selected else PANEL)
    if not options:
        message = _clip(draw, 'No actions', fonts[16], max(1, radius * 1.05))
        _label(draw, (x, y - radius * .64), [message], fonts[16], MUTED, BACKGROUND)
    if inner >= 20:
        # B closes the menu. Returning RS to neutral instead confirms a held
        # selection; the center must never imply that release means cancel.
        _label(draw, (x, y - 8), ['B'], fonts[14], INK, BACKGROUND)
        close = _clip(draw, 'close', fonts[14], inner * 1.75)
        _label(draw, (x, y + 7), [close], fonts[14], MUTED, BACKGROUND)
    elif inner >= 12:
        _label(draw, (x, y), ['B'], fonts[14], INK, BACKGROUND)
