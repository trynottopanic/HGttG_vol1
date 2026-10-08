"""Real HTTP integration with synthetic payloads and synthetic capacity inputs.

Tests transfer delivery, not video decoding, Wi-Fi or playback continuity.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host"))
from guide_transfers import RangeTransfer, Source, TransferAgreement, TransferScheduler


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        payload = self.server.payloads.get(self.path)
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", self.headers.get("Range", ""))
        if payload is None or not match:
            self.send_error(404)
            return
        start, end = map(int, match.groups())
        self.server.requests.append((self.path, start, end))
        if self.path == "/slow":
            self.server.started.set()
            self.server.release.wait(2)
        if not 0 <= start <= end < len(payload):
            self.send_error(416)
            return
        self.send_response(200 if self.path == "/ignored-range" else 206)
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Content-Range", f"bytes {start}-{end}/{len(payload)}")
        self.end_headers()
        try:
            self.wfile.write(payload[start:end + 1])
        except (OSError, ConnectionError):
            pass


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="guide-transfer-test-")
        self.root = Path(self.temp.name)
        self.workers = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.payloads = {
            "/stream": bytes(range(256)) * 512,
            "/download": bytes(reversed(range(256))) * 1024,
            "/slow": b"slow" * 4096,
            "/ignored-range": b"range" * 4096,
        }
        self.server.requests = []
        self.server.started, self.server.release = threading.Event(), threading.Event()
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.agreement = TransferAgreement(7, 0.1, 8192, 6144, 16384, 2048, (8, 4, 2, 1))

    def tearDown(self):
        self.server.release.set()
        for worker in self.workers:
            worker.close()
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join()
        self.temp.cleanup()

    def transfer(self, route, filename, *, digest=None):
        payload = self.server.payloads[route]
        source = Source(f"http://127.0.0.1:{self.server.server_port}{route}",
                        len(payload), digest or hashlib.sha256(payload).hexdigest())
        worker = RangeTransfer(source, self.root / filename, chunk_bytes=2048, request_timeout=1)
        self.workers.append(worker)
        return worker

    def until(self, predicate, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if value := predicate():
                return value
            time.sleep(0.005)
        self.fail("expected transfer evidence did not arrive")

    def scheduler(self, stream, download):
        return TransferScheduler(Path(os.environ["GUIDE_NETWORK_PLANNER"]), self.agreement,
                                 stream, download)

    def tick(self, scheduler, capacity):
        delay = scheduler._next - time.monotonic()
        if delay > 0:
            time.sleep(delay + 0.001)
        return scheduler.tick(capacity, reserve_bytes=1024)

    def test_real_transfer_pause_recovery_and_completed_checksums(self):
        stream, download = self.transfer("/stream", "stream"), self.transfer("/download", "download")
        scheduler = self.scheduler(stream, download)
        for _ in range(3):
            self.tick(scheduler, 24576)
        self.until(lambda: download.snapshot()["bytes"] > 0)
        plan = self.tick(scheduler, 7168)
        self.assertTrue(plan["plan"]["pause_download"])
        self.until(lambda: download.snapshot()["state"] == "paused")
        paused_bytes = download.snapshot()["bytes"]
        stream_before = stream.snapshot()["bytes"]
        for _ in range(4):
            self.tick(scheduler, 7168)
        self.assertEqual(download.snapshot()["bytes"], paused_bytes)
        self.assertGreater(stream.snapshot()["bytes"], stream_before)
        self.assertEqual(download.part.stat().st_size, paused_bytes)
        self.tick(scheduler, 24576)
        self.until(lambda: download.snapshot()["bytes"] > paused_bytes)
        for _ in range(40):
            self.tick(scheduler, 24576)
            if all(w.snapshot()["state"] == "complete" for w in (stream, download)):
                break
        self.assertEqual(stream.snapshot()["state"], "complete")
        self.assertEqual(download.snapshot()["state"], "complete")
        for worker, route in ((stream, "/stream"), (download, "/download")):
            self.assertEqual(worker.destination.read_bytes(), self.server.payloads[route])
        ranges = [(start, end) for route, start, end in self.server.requests if route == "/download"]
        self.assertEqual(ranges[0][0], 0)
        self.assertTrue(all(b[0] == a[1] + 1 for a, b in zip(ranges, ranges[1:])))
        self.assertEqual(scheduler.agreement, self.agreement)

    def test_slow_download_does_not_block_stream_and_pause_waits_for_request(self):
        stream, slow = self.transfer("/stream", "stream"), self.transfer("/slow", "slow")
        scheduler = self.scheduler(stream, slow)
        self.tick(scheduler, 24576)
        self.assertTrue(self.server.started.wait(1))
        before = stream.snapshot()["bytes"]
        self.tick(scheduler, 7168)
        self.assertEqual(slow.snapshot()["state"], "pausing")
        self.until(lambda: stream.snapshot()["bytes"] > before)
        self.server.release.set()
        self.until(lambda: slow.snapshot()["state"] == "paused")
        self.assertEqual(slow.snapshot()["bytes"], 2048)
        self.assertFalse(slow.snapshot()["in_flight"])

    def test_provider_restart_resumes_saved_partial_content(self):
        first = self.transfer("/download", "recovered")
        first.grant(4096, valid_until=time.monotonic() + 1)
        self.until(lambda: first.snapshot()["bytes"] == 4096)
        first.close()
        resumed = self.transfer("/download", "recovered")
        self.assertEqual(resumed.snapshot()["bytes"], 4096)
        resumed.grant(resumed.source.size, valid_until=time.monotonic() + 2)
        self.until(lambda: resumed.snapshot()["state"] == "complete")
        self.assertEqual(resumed.destination.read_bytes(), self.server.payloads["/download"])

    def test_invalid_range_and_wrong_checksum_never_publish_complete_file(self):
        bad_range = self.transfer("/ignored-range", "bad-range")
        bad_hash = self.transfer("/slow", "bad-hash", digest="0" * 64)
        self.server.release.set()
        for worker in (bad_range, bad_hash):
            worker.grant(worker.source.size, valid_until=time.monotonic() + 2)
            self.until(lambda: worker.snapshot()["state"] == "failed")
            self.assertFalse(worker.destination.exists())

    def test_shortfall_does_not_grant_false_capacity_or_allow_catchup(self):
        stream, download = self.transfer("/stream", "stream"), self.transfer("/download", "download")
        scheduler = self.scheduler(stream, download)
        report = self.tick(scheduler, 6144)
        self.assertEqual(report["plan"]["status"], "shortfall")
        self.assertEqual(stream.snapshot()["bytes"], 0)
        self.assertEqual(download.snapshot()["bytes"], 0)
        with self.assertRaises(ValueError):
            scheduler.tick(24576)
        self.assertEqual(self.server.requests, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
