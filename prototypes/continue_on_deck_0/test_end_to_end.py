# SPDX-License-Identifier: AGPL-3.0-or-later
import tempfile
import threading
import unittest
from pathlib import Path

from deck_receiver import DeckServer, HandoffStore
from node_sender import parse_timecode, transfer


class EndToEndTests(unittest.TestCase):
    def test_node_sends_verified_video_and_timecode(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as deck_dir:
            video = Path(source_dir) / "walk.mp4"
            video.write_bytes(b"prototype video" * 4096)
            server = DeckServer(("127.0.0.1", 0), HandoffStore(Path(deck_dir)), "246810")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = transfer(video, parse_timecode("06:12.450"),
                                  f"http://127.0.0.1:{server.server_port}", "246810")
            finally:
                server.shutdown()
                server.server_close()
            resume = result["resume"]
            self.assertEqual(resume["position_ms"], 372_450)
            self.assertEqual((Path(deck_dir) / "library" / resume["media_file"]).read_bytes(), video.read_bytes())

    def test_timecode_formats(self):
        self.assertEqual(parse_timecode("72.5"), 72_500)
        self.assertEqual(parse_timecode("01:12.5"), 72_500)
        self.assertEqual(parse_timecode("1:02:03.250"), 3_723_250)


if __name__ == "__main__":
    unittest.main()
