from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch
import urllib.error
import urllib.request

from guide_node_core import NodeState
from guide_node_server import (
    GuideHTTPServer,
    GuideRequestHandler,
    MEDIA_STREAM_TIMEOUT_SECONDS,
    parse_byte_range,
)
from media_library import MediaLibrary, MediaRecord
from media_preparer import DeckMediaPreparer


class MediaLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.media = self.root / "Media"
        (self.media / "Albums").mkdir(parents=True)
        (self.media / "movie.mp4").write_bytes(b"0123456789")
        (self.media / "Albums" / "song.mp3").write_bytes(b"music")
        (self.media / "private.txt").write_text("not media", encoding="utf-8")
        self.library = MediaLibrary(self.root / "settings" / "config.json")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_only_recognized_media_is_indexed_without_absolute_paths(self) -> None:
        self.assertEqual(self.library.set_folder(self.media), 2)
        listing = self.library.listing()
        self.assertEqual({item["name"] for item in listing}, {"movie.mp4", "song.mp3"})
        encoded = json.dumps(listing)
        self.assertNotIn(str(self.root), encoded)
        self.assertNotIn("private.txt", encoded)
        self.assertEqual(next(item for item in listing if item["name"] == "movie.mp4")["subtitles"], [])

    def test_changed_file_is_not_served_until_rescan(self) -> None:
        self.library.set_folder(self.media)
        record = next(item for item in self.library.listing() if item["name"] == "movie.mp4")
        (self.media / "movie.mp4").write_bytes(b"changed")
        self.assertIsNone(self.library.get(record["id"]))

    def test_folder_choice_is_remembered_and_can_be_revoked(self) -> None:
        self.library.set_folder(self.media)
        restored = MediaLibrary(self.library.config_path)
        self.assertEqual(restored.folder, self.media.resolve())
        restored.set_folder(None)
        self.assertIsNone(restored.folder)

    def test_multiple_folders_preserve_library_and_directory_structure(self) -> None:
        second = self.root / "Other" / "Media"
        (second / "Shows" / "Season 1").mkdir(parents=True)
        (second / "Shows" / "Season 1" / "episode.mkv").write_bytes(b"episode")
        self.assertEqual(self.library.set_folders((self.media, second)), 3)
        listing = self.library.listing()
        episode = next(item for item in listing if item["name"] == "episode.mkv")
        self.assertEqual(episode["library"], "Media (2)")
        self.assertEqual(episode["folder"], "Shows/Season 1")
        self.assertEqual(self.library.folders, (self.media.resolve(), second.resolve()))
        restored = MediaLibrary(self.library.config_path)
        self.assertEqual(restored.folders, self.library.folders)

    def test_old_single_folder_setting_is_migrated(self) -> None:
        self.library.config_path.parent.mkdir(parents=True)
        self.library.config_path.write_text(
            json.dumps({"media_folder": str(self.media)}), encoding="utf-8")
        restored = MediaLibrary(self.library.config_path)
        self.assertEqual(restored.folders, (self.media.resolve(),))
        restored.add_folder(self.root / "settings")
        saved = json.loads(self.library.config_path.read_text(encoding="utf-8"))
        self.assertNotIn("media_folder", saved)
        self.assertEqual(len(saved["media_folders"]), 2)


class ByteRangeTests(unittest.TestCase):
    def test_common_ranges(self) -> None:
        self.assertEqual(parse_byte_range("bytes=2-5", 10), (2, 5))
        self.assertEqual(parse_byte_range("bytes=8-", 10), (8, 9))
        self.assertEqual(parse_byte_range("bytes=-3", 10), (7, 9))
        self.assertIsNone(parse_byte_range("bytes=10-12", 10))
        self.assertIsNone(parse_byte_range("bytes=1-2,4-5", 10))

    def test_media_stream_temporarily_uses_playback_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "clip.mp4"
            path.write_bytes(b"video")
            handler = object.__new__(GuideRequestHandler)
            handler.headers = {}
            handler.connection = Mock()
            handler.connection.gettimeout.return_value = 5
            handler.wfile = Mock()
            handler.send_response = Mock()
            handler.send_header = Mock()
            handler.end_headers = Mock()
            record = SimpleNamespace(
                size=5, path=path, content_type="video/mp4"
            )
            handler._send_media_record(record, send_body=True)
        self.assertEqual(
            handler.connection.settimeout.call_args_list,
            [call(MEDIA_STREAM_TIMEOUT_SECONDS), call(5)],
        )
        handler.wfile.write.assert_called_once_with(b"video")


class MediaPreparationTests(unittest.TestCase):
    def test_selected_text_subtitle_is_extracted_to_small_cached_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cache = root / "cache"
            cache.mkdir()
            video = cache / "prepared.mp4"
            video.write_bytes(b"prepared-video" * 100)
            record = MediaRecord("a" * 32, root / "source.mkv", "Episode.mkv",
                                 "Episode.mkv", "video", "video/x-matroska",
                                 14, 1)
            preparer = DeckMediaPreparer(cache)
            preparer._states[record.media_id] = ("ready", "")
            preparer._outputs[record.media_id] = video
            preparer._subtitles[record.media_id] = ("English",)

            def extract(arguments, **kwargs):
                del kwargs
                Path(arguments[-1]).write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n",
                                               encoding="utf-8")
                return SimpleNamespace(returncode=0)

            try:
                with patch("media_preparer._winget_program", return_value="ffmpeg.exe"), \
                     patch("media_preparer.subprocess.run", side_effect=extract) as run:
                    subtitle = preparer.subtitle(record, 0)
                self.assertIsNotNone(subtitle)
                self.assertEqual(subtitle.kind if subtitle else "", "subtitle")
                self.assertEqual(subtitle.content_type if subtitle else "",
                                 "application/x-subrip")
                self.assertTrue(subtitle.path.name.endswith(".subtitle-0.srt") if subtitle else False)
                self.assertIn("0:s:0", run.call_args.args[0])
            finally:
                preparer.close()

    def test_ffmpeg_conversion_is_bounded_and_lower_priority_on_windows(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            preparer = DeckMediaPreparer(root / "cache")
            process = Mock()
            process.communicate.return_value = ("", "")
            process.returncode = 0
            try:
                with patch("media_preparer._winget_program", return_value="ffmpeg.exe"), \
                     patch("media_preparer._hardware_encoders", return_value=()), \
                     patch.object(preparer, "_probe", return_value=None), \
                     patch("media_preparer.sys.platform", "win32"), \
                     patch("media_preparer.subprocess.Popen", return_value=process) as launch:
                    okay, detail = preparer._convert(root / "source.mkv", root / "output.mp4")
                self.assertTrue(okay, detail)
                arguments = launch.call_args.args[0]
                expected_threads = str(min(8, max(2, (__import__("os").cpu_count() or 4) // 2)))
                self.assertEqual(arguments[arguments.index("-threads") + 1], expected_threads)
                self.assertEqual(arguments[arguments.index("-filter_threads") + 1], "2")
                flags = launch.call_args.kwargs["creationflags"]
                self.assertTrue(flags & getattr(__import__("subprocess"),
                                                    "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000))
            finally:
                preparer.close()

    def test_amd_hardware_path_uses_compatible_nv12_frames(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            preparer = DeckMediaPreparer(Path(folder) / "cache")
            try:
                arguments = preparer._ffmpeg_arguments(
                    "ffmpeg.exe", Path(folder) / "source.mkv",
                    Path(folder) / "output.mp4", None, False, encoder="h264_amf")
                self.assertEqual(arguments[arguments.index("-c:v") + 1], "h264_amf")
                self.assertIn("format=nv12", arguments[arguments.index("-vf") + 1])
                self.assertIn("speed", arguments)
            finally:
                preparer.close()

    def test_conversion_preserves_bounded_audio_alternatives_and_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            preparer=DeckMediaPreparer(Path(folder)/'cache')
            try:
                probe={'streams':[{'index':0,'codec_type':'video'},
                    *[{'index':i,'codec_type':'audio','tags':{'language':'eng','title':f'Track {i}'}} for i in range(1,11)]]}
                args=preparer._ffmpeg_arguments('ffmpeg',Path('input.mkv'),Path('output.mp4'),probe,True)
                mappings=[args[i+1] for i,value in enumerate(args) if value=='-map']
                self.assertEqual(mappings,['0:'+str(i) for i in range(9)])
                self.assertIn('title=Track 2',args);self.assertIn('-metadata:s:a:1',args)
                self.assertIn('-disposition:a:7',args)
            finally:preparer.close()

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg tools required')
    def test_real_conversion_keeps_two_audio_tracks_and_text_subtitles(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);subtitle=root/'captions.srt';source=root/'source.mkv';output=root/'prepared.mp4'
            subtitle.write_text('1\n00:00:00,000 --> 00:00:01,000\nCaption fixture\n')
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=black:s=160x90:r=10:d=1',
                '-f','lavfi','-i','sine=frequency=440:duration=1','-f','lavfi','-i','sine=frequency=880:duration=1',
                '-i',str(subtitle),'-map','0:v','-map','1:a','-map','2:a','-map','3:s',
                '-c:v','libx264','-c:a','aac','-c:s','srt','-metadata:s:a:0','language=eng',
                '-metadata:s:a:1','language=fra','-metadata:s:a:1','title=French',str(source)],check=True,timeout=30)
            preparer=DeckMediaPreparer(root/'cache')
            try:
                args=preparer._ffmpeg_arguments('ffmpeg',source,output,preparer._probe(source),True)
                subprocess.run(args,check=True,timeout=30,capture_output=True)
                result=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(output)],timeout=10))
                audio=[s for s in result['streams'] if s['codec_type']=='audio']
                subs=[s for s in result['streams'] if s['codec_type']=='subtitle']
                self.assertEqual(len(audio),2);self.assertEqual(len(subs),1)
                self.assertEqual([s['tags']['language'] for s in audio],['eng','fra'])
                self.assertEqual(subs[0]['codec_name'],'mov_text')
            finally:preparer.close()

    def test_converter_retries_without_subtitles_and_reports_real_errors(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            preparer = DeckMediaPreparer(root / "cache")
            probe = {"streams": [
                {"index": 0, "codec_type": "video", "codec_name": "h264",
                 "disposition": {"attached_pic": 0}},
                {"index": 1, "codec_type": "audio", "codec_name": "flac"},
                {"index": 2, "codec_type": "subtitle", "codec_name": "subrip"},
                {"index": 3, "codec_type": "subtitle", "codec_name": "hdmv_pgs_subtitle"},
            ]}
            try:
                with patch("media_preparer._winget_program", return_value="ffmpeg.exe"), \
                     patch("media_preparer._hardware_encoders", return_value=()), \
                     patch.object(preparer, "_probe", return_value=probe), \
                     patch.object(preparer, "_run_converter",
                                  side_effect=[(False, "bad subtitle timing"), (True, "")]) as run:
                    okay, detail = preparer._convert(root / "source.mkv", root / "output.mp4")
                self.assertTrue(okay, detail)
                self.assertEqual(run.call_count, 2)
                first, second = run.call_args_list[0].args[0], run.call_args_list[1].args[0]
                self.assertIn("0:2", first)
                self.assertNotIn("0:3", first)
                self.assertNotIn("0:2", second)
                self.assertIn("ignore_err", second)
            finally:
                preparer.close()

    def test_video_is_hidden_until_cached_deck_copy_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            media = root / "Media"
            media.mkdir()
            (media / "episode.mkv").write_bytes(b"original-video")
            library = MediaLibrary(root / "config.json")
            library.set_folder(media)
            record = library.records()[0]

            release = threading.Event()
            def backend(source: Path, destination: Path) -> tuple[bool, str]:
                self.assertEqual(source, record.path)
                release.wait(timeout=2)
                destination.write_bytes(b"prepared" * 200)
                return True, ""

            preparer = DeckMediaPreparer(root / "cache", backend)
            try:
                preparer.synchronize([record])
                self.assertIsNone(preparer.prepared(record))
                release.set()
                self.assertTrue(preparer.wait_for_idle())
                prepared = preparer.prepared(record)
                self.assertIsNotNone(prepared)
                self.assertEqual(prepared.content_type if prepared else "", "video/mp4")
                self.assertEqual(prepared.name if prepared else "", "episode.mkv")
                self.assertNotEqual(prepared.path if prepared else None, record.path)
                self.assertEqual(prepared.subtitle_tracks if prepared else None, ())
            finally:
                preparer.close()


class MediaHTTPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        media = root / "Media"
        media.mkdir()
        (media / "clip.mp4").write_bytes(b"0123456789")
        library = MediaLibrary(root / "config.json")
        library.set_folder(media)
        self.state = NodeState("Media Test Node")
        self.state.media = library
        self.server = GuideHTTPServer(("127.0.0.1", 0), self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        pair = urllib.request.Request(
            self.base + "/guide/v1/pair",
            data=json.dumps({"code": self.state.pairing_code, "client_name": "Deck"}).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(pair) as response:
            self.token = json.loads(response.read())["token"]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, path: str, byte_range: str = "", authorized: bool = True):
        headers = {}
        if authorized:
            headers["Authorization"] = "Bearer " + self.token
        if byte_range:
            headers["Range"] = byte_range
        return urllib.request.urlopen(urllib.request.Request(self.base + path, headers=headers))

    def post(self, path: str):
        return urllib.request.urlopen(urllib.request.Request(
            self.base + path, data=b"{}",
            headers={"Authorization": "Bearer " + self.token,
                     "Content-Type": "application/json"}, method="POST",
        ))

    def test_catalogue_and_range_stream_require_pairing(self) -> None:
        with self.request("/guide/v1/media") as response:
            item = json.loads(response.read())["items"][0]
        with self.request("/guide/v1/media/" + item["id"], "bytes=2-5") as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.headers["Content-Range"], "bytes 2-5/10")
            self.assertEqual(response.read(), b"2345")
        with self.assertRaises(urllib.error.HTTPError) as denied:
            self.request("/guide/v1/media/" + item["id"], authorized=False)
        self.assertEqual(denied.exception.code, 401)

    def test_catalogue_page_is_bounded(self) -> None:
        with self.request("/guide/v1/media?offset=0&limit=1") as response:
            payload = json.loads(response.read())
        self.assertEqual(payload["count"], 1)
        self.assertEqual(len(payload["items"]), 1)

    def test_file_specific_ticket_supports_ranges_and_is_revoked_on_unpair(self) -> None:
        with self.request("/guide/v1/media") as response:
            media_id = json.loads(response.read())["items"][0]["id"]
        with self.post(f"/guide/v1/media/{media_id}/ticket") as response:
            path = json.loads(response.read())["path"]
        with self.request(path, "bytes=7-", authorized=False) as response:
            self.assertEqual(response.read(), b"789")
        self.state.unpair(self.token)
        with self.assertRaises(urllib.error.HTTPError) as revoked:
            self.request(path, authorized=False)
        self.assertEqual(revoked.exception.code, 404)

    def test_subtitle_ticket_serves_only_the_prepared_text_track(self) -> None:
        with self.request("/guide/v1/media") as response:
            media_id = json.loads(response.read())["items"][0]["id"]
        subtitle_path = Path(self.temp.name) / "English.srt"
        subtitle_path.write_bytes(b"small subtitle")
        subtitle = SimpleNamespace(
            size=subtitle_path.stat().st_size, path=subtitle_path,
            content_type="application/x-subrip")
        with patch.object(self.state, "playback_subtitle", return_value=subtitle):
            with self.post(
                    f"/guide/v1/media/{media_id}/subtitles/0/ticket") as response:
                path = json.loads(response.read())["path"]
            with self.request(path, authorized=False) as response:
                self.assertEqual(response.read(), b"small subtitle")


if __name__ == "__main__":
    unittest.main()
