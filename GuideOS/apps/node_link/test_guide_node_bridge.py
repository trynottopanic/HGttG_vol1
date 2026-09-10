from __future__ import annotations

import contextlib
import io
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, call, patch

import guide_node_bridge as bridge


class BridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.candidates = patch.object(bridge, "CANDIDATES_FILE", root / "candidates.json")
        self.session = patch.object(bridge, "SESSION_FILE", root / "session.json")
        self.media = patch.object(bridge, "MEDIA_FILE", root / "media.json")
        self.local_media = patch.object(bridge, "LOCAL_MEDIA_FILE", root / "local-media.json")
        self.resume = patch.object(bridge, "MEDIA_RESUME_FILE", root / "resume.json")
        self.media_status = patch.object(bridge, "MEDIA_STATUS_FILE", root / "media-status.json")
        self.media_owner = patch.object(bridge, "MEDIA_OWNER_FILE", root / "media-player.owner")
        self.deck_id = patch.object(bridge, "DECK_ID_FILE", root / "deck-id")
        self.trusted = patch.object(bridge, "TRUSTED_FILE", root / "trusted.json")
        self.candidates.start()
        self.session.start()
        self.media.start()
        self.local_media.start()
        self.resume.start()
        self.media_status.start()
        self.media_owner.start()
        self.deck_id.start()
        self.trusted.start()

    def tearDown(self) -> None:
        self.trusted.stop()
        self.deck_id.stop()
        self.media.stop()
        self.resume.stop()
        self.media_status.stop()
        self.media_owner.stop()
        self.local_media.stop()
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
                    "size": 1234, "library": "Films", "folder": "Comedy",
                    "private_path": "C:/Private/Movie.mp4",
                }]}
        output = io.StringIO()
        with patch.object(bridge, "_session_client", return_value=Client()), \
             contextlib.redirect_stdout(output):
            self.assertEqual(bridge.media(), 0)
        self.assertTrue(output.getvalue().startswith("GUIDE-MEDIA-2\n"))
        self.assertIn("MEDIA=0\tvideo\t1234\tFilms\tComedy\tMovie.mp4", output.getvalue())
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
        self.assertNotIn("-readrate_initial_burst", arguments)
        self.assertEqual(arguments[arguments.index("-thread_queue_size") + 1], "1024")
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

    def test_local_media_scan_preserves_folders_and_hides_paths(self) -> None:
        root = Path(self.temp.name) / "card"
        movies = root / "Movies" / "Comedy"
        movies.mkdir(parents=True)
        video = movies / "Film.mkv"
        video.write_bytes(b"video")
        (movies / "Film.English.srt").write_text("subtitle", encoding="utf-8")
        (root / "private.txt").write_text("ignore", encoding="utf-8")
        output = io.StringIO()
        with patch.object(bridge, "LOCAL_MEDIA_ROOTS", ((root, "Cartridge"),)), \
             contextlib.redirect_stdout(output):
            self.assertEqual(bridge.local_media(), 0)
        lines = output.getvalue()
        self.assertIn("GUIDE-LOCAL-MEDIA-1\n", lines)
        self.assertIn("MEDIA=0\tvideo\t5\tCartridge\tMovies/Comedy\tFilm.mkv", lines)
        self.assertIn("SUBTITLE=0\t0\tEnglish", lines)
        self.assertNotIn(str(root), lines)
        saved = bridge._load(bridge.LOCAL_MEDIA_FILE)
        self.assertEqual(saved[0]["path"], str(video.resolve()))

    def test_local_media_is_rechecked_before_playback(self) -> None:
        root = Path(self.temp.name) / "deck"
        root.mkdir()
        song = root / "Song.mp3"
        song.write_bytes(b"first")
        with patch.object(bridge, "LOCAL_MEDIA_ROOTS", ((root, "This Deck"),)):
            bridge.local_media()
        self.assertEqual(bridge._local_media_record("0")["name"], "Song.mp3")
        song.write_bytes(b"changed")
        with self.assertRaisesRegex(Exception, "CHANGED"):
            bridge._local_media_record("0")

    def test_local_player_uses_file_input_without_network_options(self) -> None:
        arguments = bridge._player_arguments(
            "/media/guide-card/Movies/Film.mp4", "video", network=False,
            subtitle=0, subtitle_path="/media/guide-card/Movies/Film.srt")
        self.assertNotIn("-reconnect", arguments)
        self.assertNotIn("-rw_timeout", arguments)
        self.assertIn("/media/guide-card/Movies/Film.mp4", arguments)
        subtitle_filter = arguments[arguments.index("-vf") + 1]
        self.assertIn("Film.srt", subtitle_filter)
        self.assertNotIn(":si=0", subtitle_filter)

    def test_bluetooth_video_holds_first_frame_for_private_earbud_buffer(self) -> None:
        arguments = bridge._player_arguments(
            "http://node/ticket", "video",
            "bluealsa:DEV=AA:BB:CC:DD:EE:FF,PROFILE=a2dp")
        filters = arguments[arguments.index("-vf") + 1]
        self.assertIn("tpad=start_mode=clone:start_duration=2.200", filters)
        self.assertEqual(arguments[arguments.index("-threads") + 1], "4")

    def test_player_control_state_is_small_and_rejects_unknown_values(self) -> None:
        state = Path(self.temp.name) / "player.state"
        bridge._write_player_control_state(state, "paused")
        self.assertEqual(state.read_text(encoding="ascii"), "paused\n")
        bridge._write_player_control_state(state, "invented")
        self.assertEqual(state.read_text(encoding="ascii"), "paused\n")

    def test_resume_positions_are_private_bounded_and_removable(self) -> None:
        key = "a" * 32
        bridge._store_resume_position(key, 42.26)
        self.assertEqual(bridge._resume_positions()[key], 42.3)
        bridge._store_resume_position(key, None)
        self.assertNotIn(key, bridge._resume_positions())

    def test_connected_bluetooth_is_preferred_without_losing_speaker_fallback(self) -> None:
        root = Path(self.temp.name)
        status = root / "bluetooth-status"
        plugin = root / "alsa-lib"
        config = root / "alsa-media.conf"
        status.touch()
        plugin.mkdir()
        config.touch()
        connected = types.SimpleNamespace(
            returncode=0,
            stdout="READY=YES\nCONNECTED=YES\n"
                   "ALSA=bluealsa:DEV=AA:BB:CC:DD:EE:FF,PROFILE=a2dp\n",
        )
        environment = {}
        with patch.object(bridge, "BLUETOOTH_STATUS", status), \
             patch.object(bridge, "BLUETOOTH_PLUGIN_DIRECTORY", plugin), \
             patch.object(bridge, "BLUETOOTH_ALSA_CONFIG", config), \
             patch.object(bridge.subprocess, "run", return_value=connected):
            output, bluetooth = bridge._audio_output(environment)
        self.assertTrue(bluetooth)
        self.assertEqual(output, "bluealsa:DEV=AA:BB:CC:DD:EE:FF,PROFILE=a2dp")
        self.assertEqual(environment["ALSA_PLUGIN_DIR"], str(plugin))
        self.assertEqual(environment["ALSA_CONFIG_PATH"], str(config))

        with patch.object(bridge, "BLUETOOTH_STATUS", root / "missing"):
            self.assertEqual(bridge._audio_output({}), ("default", False))

    def test_media_commands_are_consumed_once_and_new_commands_remain_readable(self) -> None:
        control = Path(self.temp.name) / "control"
        control.write_text("seek:10\npause\n", encoding="ascii")
        commands, offset = bridge._read_control_commands(control, 0)
        self.assertEqual(commands, ["seek:10", "pause"])
        self.assertEqual(bridge._read_control_commands(control, offset), ([], offset))
        with control.open("a", encoding="ascii") as target:
            target.write("rate:2\n")
        commands, next_offset = bridge._read_control_commands(control, offset)
        self.assertEqual(commands, ["rate:2"])
        self.assertGreater(next_offset, offset)

    def test_stopping_player_discards_audio_instead_of_draining_it(self) -> None:
        player = Mock()
        player.poll.return_value = None
        bridge._stop_player(player)
        player.kill.assert_called_once_with()
        player.terminate.assert_not_called()
        player.wait.assert_called_once_with(timeout=1)

    def test_player_ownership_is_exclusive_and_cleared_after_use(self) -> None:
        with bridge._player_ownership():
            self.assertEqual(
                bridge.MEDIA_OWNER_FILE.read_text(encoding="ascii").strip(),
                str(bridge.os.getpid()),
            )
            with self.assertRaisesRegex(Exception, "ALREADY ACTIVE"):
                with bridge._player_ownership():
                    self.fail("a second player acquired the output lock")
        self.assertEqual(bridge.MEDIA_OWNER_FILE.read_text(encoding="ascii"), "")

    def test_only_playback_commands_receive_process_isolation(self) -> None:
        self.assertTrue(bridge._is_media_command(["play", "3"]))
        self.assertTrue(bridge._is_media_command(["local-play", "0"]))
        self.assertFalse(bridge._is_media_command(["media"]))

    def test_pause_closes_player_and_resume_reopens_without_signal_backlog(self) -> None:
        class Player:
            pid = 123

            @staticmethod
            def poll():
                return None

        first, resumed = Player(), Player()
        command_sets = [(["pause"], 1), (["pause"], 2), (["stop"], 3)]
        with patch.object(bridge, "MEDIA_CONTROL_DIRECTORY", Path(self.temp.name)), \
             patch.object(bridge, "_audio_output", return_value=("default", False)), \
             patch.object(bridge, "_read_control_commands", side_effect=command_sets), \
             patch.object(bridge.subprocess, "Popen", side_effect=[first, resumed]) as popen, \
             patch.object(bridge, "_stop_player") as stop, \
             patch.object(bridge.os, "kill") as signal_player, \
             patch.object(bridge.time, "monotonic", side_effect=range(20)), \
             patch.object(bridge.time, "sleep"):
            result = bridge._run_player_controller(
                "http://node/ticket", {"kind": "audio"}, {})
        self.assertEqual(result, 0)
        self.assertEqual(popen.call_count, 2)
        self.assertIn(call(first), stop.call_args_list)
        signal_player.assert_not_called()

    def test_subtitle_selection_resumes_with_only_one_new_decoder(self) -> None:
        class Player:
            pid = 123

            @staticmethod
            def poll():
                return None

        first, restarted = Player(), Player()
        command_sets = [(["pause"], 1), (["subtitle:0", "pause"], 2),
                        (["stop"], 3)]
        client = types.SimpleNamespace(base="http://node",
            media_subtitle_ticket=lambda media_id, track: "http://node/subtitle-ticket")
        with patch.object(bridge, "MEDIA_CONTROL_DIRECTORY", Path(self.temp.name)), \
             patch.object(bridge, "_audio_output", return_value=("default", False)), \
             patch.object(bridge, "_session_client", return_value=client), \
             patch.object(bridge, "_cache_node_subtitle",
                          return_value="/run/guide-subtitle.srt") as cache, \
             patch.object(bridge, "_read_control_commands", side_effect=command_sets), \
             patch.object(bridge.subprocess, "Popen",
                          side_effect=[first, restarted]) as popen, \
             patch.object(bridge, "_stop_player"), \
             patch.object(bridge.time, "monotonic", side_effect=range(30)), \
             patch.object(bridge.time, "sleep"):
            result = bridge._run_player_controller(
                "http://node/ticket", {"kind": "video", "id": "a" * 32}, {})
        self.assertEqual(result, 0)
        self.assertEqual(popen.call_count, 2)
        restarted_arguments = popen.call_args_list[1].args[0]
        self.assertIn("/run/guide-subtitle.srt", restarted_arguments[
            restarted_arguments.index("-vf") + 1])
        cache.assert_called_once_with("http://node/subtitle-ticket", "http://node", 0)

    def test_subtitle_cache_is_bounded_private_and_rejects_foreign_tickets(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *arguments):
                return False

            @staticmethod
            def read(limit):
                if limit != bridge.MAX_SUBTITLE_BYTES + 1:
                    raise AssertionError("subtitle download is not bounded")
                return b"1\n00:00:01,000 --> 00:00:02,000\nHello\n"

        with patch.object(bridge, "MEDIA_CONTROL_DIRECTORY", Path(self.temp.name)), \
             patch.object(bridge.urllib.request, "urlopen", return_value=Response()):
            path = bridge._cache_node_subtitle(
                "http://node/guide/v1/play/ticket", "http://node", 2)
        cached = Path(path)
        self.assertEqual(cached.read_bytes()[-6:], b"Hello\n")
        self.assertEqual(cached.stat().st_mode & 0o777, 0o600)
        cached.unlink()
        with self.assertRaisesRegex(Exception, "INVALID SUBTITLE ADDRESS"):
            bridge._cache_node_subtitle(
                "http://other/guide/v1/play/ticket", "http://node", 0)

    def test_bluetooth_startup_delay_is_not_counted_as_played_media(self) -> None:
        played, remaining = bridge._played_interval(1.0, 2.2)
        self.assertEqual(played, 0.0)
        self.assertAlmostEqual(remaining, 1.2)
        played, remaining = bridge._played_interval(2.0, 1.2)
        self.assertAlmostEqual(played, 0.8)
        self.assertEqual(remaining, 0.0)


if __name__ == "__main__":
    unittest.main()
