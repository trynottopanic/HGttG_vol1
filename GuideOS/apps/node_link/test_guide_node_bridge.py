from __future__ import annotations

import contextlib
import io
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import guide_node_bridge as bridge


class BridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.candidates = patch.object(bridge, "CANDIDATES_FILE", root / "candidates.json")
        self.session = patch.object(bridge, "SESSION_FILE", root / "session.json")
        self.media = patch.object(bridge, "MEDIA_FILE", root / "media.json")
        self.deck_id = patch.object(bridge, "DECK_ID_FILE", root / "deck-id")
        self.trusted = patch.object(bridge, "TRUSTED_FILE", root / "trusted.json")
        self.candidates.start()
        self.session.start()
        self.media.start()
        self.deck_id.start()
        self.trusted.start()

    def tearDown(self) -> None:
        self.trusted.stop()
        self.deck_id.stop()
        self.media.stop()
        self.session.stop()
        self.candidates.stop()
        self.temp.cleanup()

    def test_discovery_writes_bounded_index_without_addresses(self) -> None:
        nodes = [{
            "protocol": "guide-node/1",
            "node_id": f"{index:032x}",
            "name": "Node\tName",
            "address": f"http://192.168.1.{index + 1}:4365",
            "pairing_required": True,
            "transport_security": "development-local-http",
        } for index in range(10)]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(bridge.discover(lambda: nodes), 0)
        lines = output.getvalue().splitlines()
        self.assertEqual(lines[0], "GUIDE-NODES-1")
        self.assertEqual(len(lines), 9)
        self.assertNotIn("192.168", output.getvalue())
        self.assertIn("Node Name", output.getvalue())

    def test_bad_pairing_arguments_fail_cleanly(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(bridge.main(["pair", "9", "password"]), 1)
        self.assertTrue(output.getvalue().startswith("ERROR="))

    def test_media_protocol_omits_token_and_path(self) -> None:
        class Client:
            def media_library(self, offset, limit):
                return {"count": 1, "items": [{
                    "id": "a" * 32, "kind": "video", "name": "Movie.mp4",
                    "size": 1234, "private_path": "C:/Private/Movie.mp4",
                }]}
        output = io.StringIO()
        with patch.object(bridge, "_session_client", return_value=Client()), \
             contextlib.redirect_stdout(output):
            self.assertEqual(bridge.media(), 0)
        self.assertIn("MEDIA=0\tvideo\t1234\tMovie.mp4", output.getvalue())
        self.assertNotIn("Private", output.getvalue())

    def test_play_initializes_speaker_before_running_bounded_controller(self) -> None:
        root = Path(self.temp.name)
        runtime = root / "media"
        (runtime / "bin").mkdir(parents=True)
        (runtime / "lib").mkdir()
        loader = runtime / "lib" / "ld-linux-aarch64.so.1"
        ffmpeg = runtime / "bin" / "ffmpeg"
        control = runtime / "bin" / "guide-audio-control"
        for executable in (loader, ffmpeg, control):
            executable.touch()
        bridge._atomic_private_json(bridge.MEDIA_FILE, [{
            "id": "b" * 32, "kind": "video", "name": "Movie.mp4", "size": 42,
        }])
        client = types.SimpleNamespace(media_ticket=lambda media_id: "http://node/ticket")
        completed = types.SimpleNamespace(returncode=0)
        with patch.object(bridge, "MEDIA_RUNTIME", runtime), \
             patch.object(bridge, "MEDIA_LOADER", loader), \
             patch.object(bridge, "MEDIA_FFMPEG", ffmpeg), \
             patch.object(bridge, "MEDIA_AUDIO_CONTROL", control), \
             patch.object(bridge, "_session_client", return_value=client), \
             patch.object(bridge.subprocess, "run", return_value=completed) as initialize, \
             patch.object(bridge, "_run_player_controller", return_value=0) as controller:
            self.assertEqual(bridge.play("0"), 0)
        self.assertEqual(initialize.call_args.args[0][-1], "--initialize-speaker")
        arguments = bridge._player_arguments("http://node/ticket", "video")
        self.assertIn("fast_bilinear", arguments)
        self.assertIn("-stats_period", arguments)
        self.assertEqual(arguments[arguments.index("-readrate_initial_burst") + 1], "5")
        self.assertEqual(arguments[-2:], ["alsa", "default"])
        controller.assert_called_once()

    def test_media_protocol_includes_bounded_subtitle_labels(self) -> None:
        class Client:
            def media_library(self, offset, limit):
                return {"count": 1, "items": [{
                    "id": "a" * 32, "kind": "video", "name": "Movie.mp4",
                    "size": 1234, "subtitles": ["English", "Commentary"],
                }]}
        output = io.StringIO()
        with patch.object(bridge, "_session_client", return_value=Client()), \
             contextlib.redirect_stdout(output):
            self.assertEqual(bridge.media(), 0)
        self.assertIn("SUBTITLE=0\t0\tEnglish", output.getvalue())
        self.assertIn("SUBTITLE=0\t1\tCommentary", output.getvalue())


if __name__ == "__main__":
    unittest.main()
