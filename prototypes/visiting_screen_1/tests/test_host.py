# SPDX-License-Identifier: AGPL-3.0-or-later

import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import thirdway_host as host
import thirdway_deck as deck


class HostTests(unittest.TestCase):
    def test_ssdp_headers_are_case_insensitive(self):
        headers = host.parse_ssdp_headers(
            b"HTTP/1.1 200 OK\r\nLOCATION: http://192.168.1.2/device.xml\r\nST: test\r\n\r\n"
        )
        self.assertEqual(headers["location"], "http://192.168.1.2/device.xml")

    def test_renderer_description_resolves_relative_control_url(self):
        body = b"""<root xmlns='urn:schemas-upnp-org:device-1-0'>
        <device><friendlyName>Test TV</friendlyName><manufacturer>Example</manufacturer>
        <modelName>Screen 1</modelName><serviceList><service>
        <serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType>
        <controlURL>/upnp/control/transport</controlURL>
        </service></serviceList></device></root>"""
        renderer = host.parse_renderer_description("http://192.168.1.2:8000/device.xml", body)
        self.assertIsNotNone(renderer)
        self.assertEqual(renderer.name, "Test TV")
        self.assertEqual(renderer.control_url, "http://192.168.1.2:8000/upnp/control/transport")

    def test_range_parsing(self):
        self.assertEqual(host.parse_byte_range("bytes=10-19", 100), (10, 19))
        self.assertEqual(host.parse_byte_range("bytes=90-", 100), (90, 99))
        self.assertEqual(host.parse_byte_range("bytes=-10", 100), (90, 99))
        self.assertIsNone(host.parse_byte_range("bytes=100-101", 100))

    def test_pairing_expires_and_rotates(self):
        with tempfile.TemporaryDirectory() as temp:
            state = host.HostState(Path(temp))
            original = state.pair_code
            self.assertTrue(state.pairing_is_valid(original))
            state.rotate_pairing_code()
            self.assertFalse(state.pairing_is_valid(original))

    def test_safe_filename_removes_directories(self):
        self.assertEqual(host.safe_filename("../../movie.mp4"), "movie.mp4")

    def test_upload_range_stream_and_revoke(self):
        payload = b"0123456789abcdef"
        with tempfile.TemporaryDirectory() as temp:
            state = host.HostState(Path(temp), pair_code="12345678")
            server = host.ThirdWayServer(("127.0.0.1", 0), state, 1024)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
            try:
                connection.request(
                    "POST",
                    "/api/upload?code=12345678&filename=test.mp4",
                    body=payload,
                    headers={"Content-Type": "video/mp4", "Content-Length": str(len(payload))},
                )
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 201)
                self.assertIsNotNone(state.movie)
                movie_path = state.movie.path
                media_path = f"/media/{state.movie.media_token}/test.mp4"

                connection.request("GET", media_path, headers={"Range": "bytes=4-9"})
                response = connection.getresponse()
                self.assertEqual(response.status, 206)
                self.assertEqual(response.read(), b"456789")

                connection.request(
                    "POST",
                    f"/api/revoke?owner={state.owner_token}",
                    body=b"",
                    headers={"Content-Length": "0"},
                )
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 303)
                self.assertIsNone(state.movie)
                self.assertFalse(movie_path.exists())
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_mock_tv_receives_set_uri_then_play(self):
        requests = []

        class MockTV(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                length = int(self.headers["Content-Length"])
                requests.append((self.headers["SOAPAction"], self.rfile.read(length)))
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

        server = ThreadingHTTPServer(("127.0.0.1", 0), MockTV)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        renderer = host.Renderer(
            name="Mock TV",
            location=f"http://127.0.0.1:{server.server_port}/device.xml",
            control_url=f"http://127.0.0.1:{server.server_port}/transport",
            service_type=host.AVTRANSPORT,
        )
        try:
            host.set_and_play(renderer, "http://192.168.1.5:8765/media/token/movie.mp4", "video/mp4")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(len(requests), 2)
        self.assertTrue(requests[0][0].endswith("#SetAVTransportURI\""))
        self.assertIn(b"movie.mp4", requests[0][1])
        self.assertTrue(requests[1][0].endswith("#Play\""))

    def test_deck_offers_direct_stream_and_owner_can_revoke_it(self):
        with tempfile.TemporaryDirectory() as temp:
            movie_path = Path(temp) / "deck-movie.mp4"
            movie_path.write_bytes(b"abcdefghijklmnop")
            host_state = host.HostState(Path(temp), pair_code="87654321")
            host_server = host.ThirdWayServer(("127.0.0.1", 0), host_state, 1024)
            host_thread = threading.Thread(target=host_server.serve_forever, daemon=True)
            host_thread.start()
            deck_state = deck.DeckState(movie_path, movie_path.name, "video/mp4")
            deck_server = deck.DeckServer(("0.0.0.0", 0), deck_state)
            deck_thread = threading.Thread(target=deck_server.serve_forever, daemon=True)
            deck_thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", host_server.server_port)
            try:
                offer_token = deck.send_offer(
                    f"http://127.0.0.1:{host_server.server_port}", "87654321", deck_server
                )
                self.assertTrue(offer_token)
                self.assertIsNone(host_state.movie.path)
                self.assertEqual(host_state.movie.source_url, deck_server.stream_url)

                with urllib.request.urlopen(deck_server.stream_url, timeout=2) as response:
                    self.assertEqual(response.read(), b"abcdefghijklmnop")

                range_request = urllib.request.Request(
                    deck_server.stream_url, headers={"Range": "bytes=4-9"}
                )
                with urllib.request.urlopen(range_request, timeout=2) as response:
                    self.assertEqual(response.status, 206)
                    self.assertEqual(response.headers["Content-Range"], "bytes 4-9/16")
                    self.assertEqual(response.read(), b"efghij")

                connection.request(
                    "POST",
                    f"/api/revoke?owner={host_state.owner_token}",
                    body=b"",
                    headers={"Content-Length": "0"},
                )
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 303)
                self.assertFalse(deck_state.active.is_set())
                self.assertIsNone(host_state.movie)
                with self.assertRaises(urllib.error.HTTPError) as rejected:
                    urllib.request.urlopen(deck_server.stream_url, timeout=2)
                self.assertEqual(rejected.exception.code, 403)
            finally:
                connection.close()
                deck_server.shutdown()
                deck_server.server_close()
                deck_thread.join(timeout=2)
                host_server.shutdown()
                host_server.server_close()
                host_thread.join(timeout=2)

    def test_deck_stream_expires(self):
        with tempfile.TemporaryDirectory() as temp:
            movie_path = Path(temp) / "movie.mp4"
            movie_path.write_bytes(b"movie")
            state = deck.DeckState(movie_path, movie_path.name, "video/mp4")
            state.started_at = time.time() - deck.MEDIA_LIFETIME - 1
            self.assertFalse(state.available())
            self.assertFalse(state.active.is_set())


if __name__ == "__main__":
    unittest.main()
