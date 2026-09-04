# SPDX-License-Identifier: AGPL-3.0-or-later
import unittest
from pathlib import PurePosixPath

from deck_runtime import player_command


class DeckRuntimeTests(unittest.TestCase):
    def test_player_starts_at_manifest_time(self):
        command = player_command({"position_ms": 372_450}, PurePosixPath("/data/guide-media/movie.mp4"))
        self.assertIn("--start=372.450", command)
        self.assertEqual(command[-1], "/data/guide-media/movie.mp4")
        self.assertIn("--", command)


if __name__ == "__main__":
    unittest.main()
