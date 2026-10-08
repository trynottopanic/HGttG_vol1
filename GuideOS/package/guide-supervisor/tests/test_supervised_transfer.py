"""Opt-in integration: C planner + HTTP provider inside a real systemd user unit."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host"))
from guide_systemd import InstalledAgreement, SystemdUserHost
from serve_transfer_fixture import FixtureHandler, manifest


class SupervisedTransfer(unittest.TestCase):
    def test_provider_application_completes_under_real_host_controls(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        unit = None
        try:
            with tempfile.TemporaryDirectory(prefix="guide-supervised-transfer-") as folder:
                root = Path(folder)
                config = manifest(f"http://127.0.0.1:{server.server_port}")
                config["agreement"]["interval_seconds"] = 0.1
                config_path = root / "manifest.json"
                config_path.write_text(json.dumps(config))
                runner = Path(__file__).resolve().parents[1] / "host/run_transfer_session.py"
                host = SystemdUserHost(command_timeout=5, max_instances=1)
                agreement = InstalledAgreement("00000002", 1, 1, 100, 64 * 1024**2, 16, 1000, True)
                instance = host.reserve(agreement, [sys.executable, str(runner), "--planner",
                    os.environ["GUIDE_NETWORK_PLANNER"], "--manifest", str(config_path),
                    "--output", str(root / "output")])
                unit = host._instances[instance].unit
                observation = host.start(instance)
                self.assertTrue(observation.controls_verified)
                self.assertTrue(observation.populated)
                deadline = time.monotonic() + 15
                results = []
                while time.monotonic() < deadline:
                    results = list((root / "output").glob("summary-*.json"))
                    if results and host.observe(instance).populated is False:
                        break
                    time.sleep(0.05)
                self.assertEqual(len(results), 1)
                summary = json.loads(results[0].read_text())
                self.assertTrue(summary["all_content_verified"])
                self.assertEqual(summary["outcome"], "schedule-finished")
                self.assertIs(host.observe(instance).populated, False)
                self.assertEqual(host.observe(instance).result, "success")
                host.retire(instance)
        finally:
            if unit:
                for args in (["kill", "--signal=SIGKILL", unit], ["stop", unit], ["reset-failed", unit]):
                    subprocess.run(["/usr/bin/systemctl", "--user", *args], timeout=5,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    if "--run-systemd-integration" not in sys.argv:
        raise SystemExit("Opt in with --run-systemd-integration")
    sys.argv.remove("--run-systemd-integration")
    unittest.main(verbosity=2)
