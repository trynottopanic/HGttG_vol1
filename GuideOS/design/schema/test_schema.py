"""Source-level conformance checks for Guide Design Schema 0."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from guide_design import SchemaBundle, SchemaError


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "fixtures" / "video-player.toml"
AUDIO_FIXTURE = ROOT / "fixtures" / "audio-player.toml"


class SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = SchemaBundle.load(ROOT, FIXTURE)

    def test_video_fixture_uses_current_display_profile(self) -> None:
        self.assertEqual(self.bundle.tokens["display"]["profile"], "deck-640x480")
        self.assertEqual(self.bundle.tokens["display"]["width"], 640)
        self.assertEqual(self.bundle.tokens["display"]["height"], 480)

    def test_audio_fixture_reuses_current_display_profile(self) -> None:
        audio = SchemaBundle.load(ROOT, AUDIO_FIXTURE)
        self.assertEqual(audio.screen["screen"]["pattern"], "audio-player")
        self.assertEqual(audio.screen["screen"]["display_profile"],
                         self.bundle.tokens["display"]["profile"])

    def test_all_typography_roles_reference_declared_faces(self) -> None:
        faces = self.bundle.tokens["fonts"]
        for role in self.bundle.tokens["typography"].values():
            self.assertIn(role["family"], faces)
            self.assertIn(role["weight"], faces[role["family"]])

    def test_unknown_color_reference_is_rejected(self) -> None:
        screen = deepcopy(self.bundle.screen)
        screen["footer"]["actions"][0]["color"] = "undeclared"
        invalid = SchemaBundle(self.bundle.tokens, self.bundle.components, screen)
        with self.assertRaisesRegex(SchemaError, "unknown color tokens"):
            invalid.validate()

    def test_out_of_range_progress_is_rejected(self) -> None:
        screen = deepcopy(self.bundle.screen)
        screen["transport"]["progress"] = 1.1
        invalid = SchemaBundle(self.bundle.tokens, self.bundle.components, screen)
        with self.assertRaisesRegex(SchemaError, "progress"):
            invalid.validate()


if __name__ == "__main__":
    unittest.main()
