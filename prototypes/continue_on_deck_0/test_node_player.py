# SPDX-License-Identifier: AGPL-3.0-or-later
import unittest
from node_player import PAGE, byte_range


class NodePlayerTests(unittest.TestCase):
    def test_video_ranges(self):
        self.assertEqual(byte_range("bytes=10-19", 100), (10, 19))
        self.assertEqual(byte_range("bytes=90-", 100), (90, 99))
        self.assertEqual(byte_range("bytes=-5", 100), (95, 99))
        self.assertIsNone(byte_range(None, 100))

    def test_bad_range_is_rejected(self):
        with self.assertRaises(ValueError):
            byte_range("bytes=100-101", 100)

    def test_page_has_no_remote_content(self):
        self.assertNotIn("http://", PAGE)
        self.assertNotIn("https://", PAGE)


if __name__ == "__main__":
    unittest.main()
