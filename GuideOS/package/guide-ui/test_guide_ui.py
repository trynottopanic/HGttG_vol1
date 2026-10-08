from dataclasses import replace
from pathlib import Path
import unittest

from guide_shell_schema_adapter import home_model, status_model
from guide_field_ui import FieldUI
from guide_ui_model import ActionHint, ScreenModel, UIError


HERE = Path(__file__).resolve().parent


class FieldUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = FieldUI(HERE)

    def test_home_returns_drawn_hit_regions(self):
        model = home_model(("media", "status", "power"),
                           ("Audio", "System Status", "Power Off"), 1, 78)
        result = self.ui.render(model)
        self.assertEqual(result.image.size, (640, 480))
        self.assertEqual(result.image.mode, "RGB")
        self.assertEqual([row.identity for row in result.regions],
                         ["home:media", "home:status", "home:power"])
        self.assertEqual(result.regions[1].value, 1)
        self.assertEqual(result.visible_ids[1], "home:status")

    def test_visible_window_is_bounded_and_contains_focus(self):
        pages = tuple("page" + str(i) for i in range(8))
        model = home_model(pages, pages, 7)
        result = self.ui.render(model)
        self.assertEqual(len(result.regions), 4)
        self.assertIn("home:page7", result.visible_ids)

    def test_identity_does_not_depend_on_label(self):
        first = home_model(("status",), ("System Status",), 0)
        renamed = home_model(("status",), ("État du système",), 0)
        self.assertEqual(self.ui.render(first).regions[0].identity,
                         self.ui.render(renamed).regions[0].identity)

    def test_absent_focus_is_rejected(self):
        model = home_model(("status",), ("System Status",), 0)
        with self.assertRaisesRegex(UIError, "focused"):
            self.ui.render(replace(model, focus_id="home:missing"))

    def test_status_is_bounded(self):
        model = status_model(tuple("Row " + str(i) for i in range(20)))
        self.assertEqual(len(model.facts), 9)
        self.assertEqual(self.ui.render(model).image.size, (640, 480))

    def test_unsupported_pattern_is_rejected(self):
        with self.assertRaisesRegex(UIError, "Unknown Field screen"):
            self.ui.render(ScreenModel(pattern="unknown", title="No"))

    def test_unknown_footer_color_is_rejected(self):
        model = ScreenModel(pattern="facts-status", title="Status",
                            actions=(ActionHint("A", "Open", "missing"),))
        with self.assertRaisesRegex(UIError, "unknown color"):
            self.ui.render(model)


if __name__ == "__main__":
    unittest.main()
