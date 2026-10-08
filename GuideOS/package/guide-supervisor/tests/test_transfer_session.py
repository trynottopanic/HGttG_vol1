"""Exercise the shipped session runner and its saved evidence against real HTTP."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from serve_transfer_fixture import FixtureHandler, manifest


class SessionTests(unittest.TestCase):
    def test_session_records_pause_recovery_and_verified_completion(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix="guide-session-test-") as folder:
                root = Path(folder)
                config = manifest(f"http://127.0.0.1:{server.server_port}")
                config["agreement"]["interval_seconds"] = 0.1
                config_path = root / "manifest.json"
                config_path.write_text(json.dumps(config))
                runner = Path(__file__).resolve().parents[1] / "host/run_transfer_session.py"
                args = [sys.executable, str(runner), "--planner", os.environ["GUIDE_NETWORK_PLANNER"],
                        "--manifest", str(config_path), "--output", str(root / "output")]
                result = subprocess.run(args, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                summary = json.loads(result.stdout)
                self.assertTrue(summary["all_content_verified"])
                rows = [json.loads(line) for line in next((root / "output").glob("events-*.jsonl")).read_text().splitlines()]
                paused = [r for r in rows if r["download"]["state"] == "paused"]
                self.assertGreater(len(paused), 2)
                self.assertEqual(len({r["download"]["bytes"] for r in paused}), 1)
                self.assertTrue(any(r["download"]["bytes"] > paused[-1]["download"]["bytes"]
                                    for r in rows if r["tick"] > paused[-1]["tick"]))
                # Rerunning already completed work must not overwrite or redownload it.
                config["capacity_schedule"] = [{"intervals": 1, "capacity_bytes": 24576}]
                config_path.write_text(json.dumps(config))
                restarted = subprocess.run(args, capture_output=True, text=True, timeout=5)
                self.assertEqual(restarted.returncode, 0, restarted.stdout + restarted.stderr)
                self.assertNotEqual(json.loads(restarted.stdout)["instance"], summary["instance"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main(verbosity=2)
