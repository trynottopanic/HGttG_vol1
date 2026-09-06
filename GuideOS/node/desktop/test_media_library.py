from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call
import urllib.error
import urllib.request

from guide_node_core import NodeState
from guide_node_server import (
    GuideHTTPServer,
    GuideRequestHandler,
    MEDIA_STREAM_TIMEOUT_SECONDS,
    parse_byte_range,
)
from media_library import MediaLibrary
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


if __name__ == "__main__":
    unittest.main()
