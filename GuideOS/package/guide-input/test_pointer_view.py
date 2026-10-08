# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rendering acceptance for shell pointer and radial context overlays."""

import unittest
from unittest.mock import patch

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFont

import guide_pointer_view as view
from guide_pointer_input import PointerController


def fonts():
    for path in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                 'C:/Windows/Fonts/segoeui.ttf', 'DejaVuSans.ttf'):
        try:
            return {size: ImageFont.truetype(path, size) for size in (14, 16)}
        except OSError:
            continue
    return {size: ImageFont.load_default() for size in (14, 16)}


def pointer(options=None, highlight=None, center=(320, 240), visible=True,
            position=(320, 240)):
    model = PointerController()
    model.move_to(*position)
    if options is not None:
        model.open_context(options, center)
        model.context.highlight = highlight
    model.visible = visible
    return model


class PointerViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fonts = fonts()

    def render(self, model, hover=None):
        image = Image.new('RGB', (640, 480), view.BACKGROUND)
        view.draw_pointer(image, model, self.fonts, hover)
        return image

    def test_hidden_pointer_leaves_menu_content_unchanged(self):
        image = self.render(pointer(visible=False), (20, 120, 620, 176))
        self.assertIsNone(ImageChops.difference(image, Image.new('RGB', image.size, view.BACKGROUND)).getbbox())

    def test_visible_cursor_has_no_hover_box_and_remains_inside_viewport(self):
        for position in ((0, 0), (639, 0), (0, 479), (639, 479), (320, 240)):
            image = self.render(pointer(position=position), (-20, -20, 680, 520))
            colors = {color for count, color in image.getcolors(image.width * image.height)}
            # Bold opaque white ring remains visible even at clipped edges.
            self.assertIn((255, 255, 255), colors)
            self.assertNotIn(ImageColor.getrgb(view.FOCUS), colors)
            self.assertNotIn(ImageColor.getrgb(view.FOCUS_GLOW), colors)
            self.assertEqual(image.getpixel((20, 20)), ImageColor.getrgb(view.BACKGROUND))
            self.assertEqual(image.size, (640, 480))
            if position == (320, 240):
                center=image.getpixel(position)
                self.assertGreater(center[2], center[0])
                self.assertEqual(view._DOT.size, (13, 13))

    def test_zero_to_four_options_render_only_supplied_labels(self):
        supplied = {'up': {'id': 'open', 'label': 'Open'},
                    'right': {'id': 'details', 'label': 'Details'},
                    'down': {'id': 'disconnect', 'label': 'Disconnect'},
                    'left': {'id': 'refresh', 'label': 'Refresh'}}
        for count in range(5):
            model = pointer(dict(list(supplied.items())[:count]), visible=False)
            with patch.object(view, '_label', wraps=view._label) as labels:
                self.render(model)
            rendered = [line for call in labels.call_args_list for line in call.args[2]]
            for option in list(supplied.values())[:count]:
                self.assertTrue(any(line.startswith(option['label'][:3]) for line in rendered))
            for option in list(supplied.values())[count:]:
                self.assertNotIn(option['label'], rendered)
            self.assertEqual('No actions' in rendered, count == 0)

    def test_popup_stays_in_its_84_pixel_radius_at_viewport_edges(self):
        options = {direction: {'id': direction, 'label': 'Select'} for direction in view.SECTORS}
        for center in ((86, 86), (553, 86), (86, 393), (553, 393)):
            model = pointer(options, center=center, visible=False)
            image = self.render(model)
            changed = ImageChops.difference(image, Image.new('RGB', image.size, view.BACKGROUND)).getbbox()
            self.assertIsNotNone(changed)
            left, top, right, bottom = changed
            self.assertGreaterEqual(left, center[0] - 84)
            self.assertGreaterEqual(top, center[1] - 84)
            self.assertLessEqual(right, center[0] + 85)
            self.assertLessEqual(bottom, center[1] + 85)

    def test_held_direction_has_distinct_fill_from_other_options(self):
        options = {direction: {'id': direction, 'label': direction} for direction in view.SECTORS}
        model = pointer(options, highlight='right', visible=False)
        image = self.render(model)
        for point, color in (((370, 260), view.GOLD), ((270, 260), view.PANEL)):
            expected = tuple(round((foreground * 77 + background * 178) / 255)
                             for foreground, background in zip(ImageColor.getrgb(color),
                                                               ImageColor.getrgb(view.BACKGROUND)))
            self.assertEqual(image.getpixel(point), expected)
        self.assertEqual(model.context.highlight, 'right')

    def test_cursor_is_drawn_before_labels_and_long_labels_are_bounded(self):
        model = pointer({'right': {'id': 'details', 'label': 'A very long contextual action label'}},
                        highlight='right', position=(393, 240))
        events = []
        original_arrow, original_label = view._dot, view._label
        def arrow(*args):
            events.append('arrow')
            return original_arrow(*args)
        def label(*args):
            events.append('label')
            return original_label(*args)
        with patch.object(view, '_dot', side_effect=arrow), patch.object(view, '_label', side_effect=label):
            image = self.render(model)
        self.assertEqual(events[0], 'arrow')
        lines = view._lines(ImageDraw.Draw(image), model.context.options['right']['label'], self.fonts[14], 74.8)
        self.assertLessEqual(len(lines), 2)
        self.assertTrue(all(view._width(ImageDraw.Draw(image), line, self.fonts[14]) <= 74.8 for line in lines))
        self.assertTrue(lines[-1].endswith('...'))


if __name__ == '__main__':
    unittest.main()
