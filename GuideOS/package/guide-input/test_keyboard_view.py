# SPDX-License-Identifier: AGPL-3.0-or-later
"""Renderer acceptance checks at the real shared-model boundary."""

import unittest
from unittest.mock import patch

from guide_keyboard import Keyboard
from guide_keyboard_view import ACCENT, MUTED, NEIGHBOR, PAPER, SELECTED, KeyboardRenderer
from guide_text_entry import TextEntryManager, TextRequest


def keyboard(**overrides):
    values = dict(owner_id="example:instance-1", field_id="query", label="Search")
    values.update(overrides)
    return Keyboard(TextEntryManager(), TextRequest(**values))


class KeyboardViewTests(unittest.TestCase):
    def test_compact_geometry_and_focused_key_are_preserved(self):
        model = keyboard()
        view = KeyboardRenderer("Reader")
        image = view.render(model)
        self.assertEqual(image.size, (640, 480))
        self.assertEqual(image.mode, "RGB")
        self.assertEqual(image.getpixel((0, 0)), PAPER)
        self.assertEqual(image.getpixel((64, 208)), ACCENT)
        self.assertEqual(image.getpixel((65, 209)), ACCENT)
        self.assertEqual(image.getpixel((66, 210)), SELECTED)
        # A aligns directly below Q; the unused tenth column stays empty.
        self.assertEqual(image.getpixel((64, 244)), MUTED)
        self.assertEqual(image.getpixel((65, 245)), NEIGHBOR)
        self.assertEqual(image.getpixel((519, 245)), PAPER)
        occupied = [y for y in range(445, 480)
                    if any(image.getpixel((x, y)) != PAPER for x in range(640))]
        self.assertEqual(max(occupied), 471)
        self.assertEqual(min(y for y in occupied if y > 456) - 456 - 1,
                         479 - max(occupied))

    def test_secret_characters_never_reach_draw_text(self):
        secret = "zQ-Private-value-7"
        model = keyboard(secret=True, initial=secret)
        view = KeyboardRenderer()
        with patch.object(view.text, "draw", wraps=view.text.draw) as draw:
            view.render(model)
        rendered = [call.args[2] for call in draw.call_args_list]
        self.assertNotIn(secret, rendered)
        self.assertIn("*" * len(secret), rendered)
        self.assertEqual(model.session.text, secret)

    def test_case_unicode_and_model_state_are_preserved(self):
        value = "MiXeD caf\u00e9 \u03b1\u03b2"
        model = keyboard(initial=value)
        view = KeyboardRenderer()
        before = (model.session.text, model.session.cursor, model.focus, model.page)
        with patch.object(view.text, "draw", wraps=view.text.draw) as draw:
            view.render(model)
        rendered = [call.args[2] for call in draw.call_args_list]
        self.assertIn(value, rendered)
        self.assertEqual((model.session.text, model.session.cursor, model.focus, model.page), before)

    def test_long_text_scroll_keeps_caret_inside_field(self):
        model = keyboard(initial="abcdefghij" * 100)
        view = KeyboardRenderer()
        image = view.render(model)
        start, end = view._window(model.session.text, model.session.cursor, 552)
        self.assertGreater(start, 0)
        self.assertEqual(end, len(model.session.text))
        caret = [(x, y) for x in range(29, 612) for y in range(133, 171)
                 if image.getpixel((x, y)) == ACCENT]
        self.assertTrue(caret)
        self.assertLess(max(x for x, _ in caret), 600)

    def test_multiline_scroll_renders_current_and_preceding_lines(self):
        model = keyboard(initial="first\nsecond\nthird\nfourth", multiline=True)
        view = KeyboardRenderer()
        with patch.object(view.text, "draw", wraps=view.text.draw) as draw:
            view.render(model)
        rendered = [call.args[2] for call in draw.call_args_list]
        self.assertIn("third", rendered)
        self.assertIn("fourth", rendered)
        self.assertNotIn("first", rendered)
        self.assertNotIn("second", rendered)

    def test_error_and_long_submit_label_fit_their_regions(self):
        model = keyboard(initial="", min_length=5,
                         submit_label="Submit this unusually long search")
        model.session.submit()
        view = KeyboardRenderer()
        with patch.object(view.text, "draw", wraps=view.text.draw) as draw:
            view.render(model)
        rendered = [call.args[2] for call in draw.call_args_list]
        self.assertIn(model.session.error, rendered)
        self.assertNotIn(model.session.request.submit_label, rendered)
        self.assertTrue(any(text.endswith("...") for text in rendered))

    def test_render_size_is_aspect_fitted_without_mutating_model(self):
        view = KeyboardRenderer()
        image = view.render(keyboard(), (800, 480))
        self.assertEqual(image.size, (800, 480))
        self.assertEqual(image.getpixel((0, 150)), PAPER)
        self.assertEqual(image.getpixel((144, 208)), ACCENT)
        for size in [(0, 480), (640, -1), (True, 480), (640.0, 480)]:
            with self.assertRaises(ValueError):
                view.render(keyboard(), size)

    def test_eight_secondary_targets_have_distinct_styling_and_flick_arrows(self):
        model = keyboard()
        model.focus = (1, 4)
        view = KeyboardRenderer()
        with patch.object(view, '_direction_hint', wraps=view._direction_hint) as arrows:
            image = view.render(model)
        self.assertEqual(arrows.call_count, 8)
        self.assertEqual({call.args[2] for call in arrows.call_args_list}, set(model.neighbors))
        # T is the northern secondary target; G remains the strong primary focus.
        self.assertEqual(image.getpixel((265, 208)), MUTED)
        self.assertEqual(image.getpixel((266, 209)), NEIGHBOR)
        self.assertEqual(image.getpixel((265, 244)), ACCENT)
        self.assertEqual(image.getpixel((267, 246)), SELECTED)

    def test_edge_targets_show_only_available_direction_hints(self):
        model = keyboard(allowed_characters='qs')
        view = KeyboardRenderer()
        with patch.object(view, '_direction_hint', wraps=view._direction_hint) as arrows:
            view.render(model)
        self.assertEqual([call.args[2] for call in arrows.call_args_list], [(1, 1)])


if __name__ == "__main__":
    unittest.main()
