# SPDX-License-Identifier: AGPL-3.0-or-later
"""Opt-in integration tests: real systemd user units, never system services.

All numbers are test fixtures, not deployment defaults. Cleanup force-kills only
the uniquely named, disposable workers created by this test process.
"""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host"))
from guide_systemd import HostError, InstalledAgreement, SystemdUserHost, UnloadAuthorization


WORKER = """
import json, os, pathlib, signal, subprocess, sys, time
if sys.argv[2] == 'stubborn':
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
child = subprocess.Popen(['/usr/bin/sleep', '120'])
pathlib.Path(sys.argv[1]).write_text(json.dumps([os.getpid(), child.pid, sys.argv[3]]))
while True:
    time.sleep(0.1)
"""


class SystemdIntegration(unittest.TestCase):
    def setUp(self):
        self.host = SystemdUserHost(command_timeout=5, max_instances=4)
        self.temp = tempfile.TemporaryDirectory(prefix="guide-host-test-")
        self.units = []
        self.agreement = InstalledAgreement("00000001", 7, 3, 37, 64 * 1024**2,
                                            16, 200, True)

    def tearDown(self):
        for unit in self.units:
            # Only test-created units; this is not Guide's production stop path.
            for args in (["kill", "--signal=SIGKILL", unit],
                         ["stop", unit], ["reset-failed", unit]):
                subprocess.run(["/usr/bin/systemctl", "--user", *args],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=5, check=False)
        self.temp.cleanup()

    def until(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(0.02)
        self.fail("timed out waiting for host evidence")

    def launch(self, *, stubborn=False, agreement=None):
        ready = Path(self.temp.name) / (str(len(self.units)) + ".json")
        instance = self.host.reserve(agreement or self.agreement,
            [sys.executable, "-c", WORKER, str(ready),
             "stubborn" if stubborn else "normal", "$HOME; literal argument"])
        self.units.append(self.host._instances[instance].unit)
        self.host.start(instance)
        self.until(lambda: ready.exists() and ready.stat().st_size > 0)
        return instance, json.loads(ready.read_text())

    def auth(self, handle, **changes):
        return replace(UnloadAuthorization(handle, 7, 1, 4, True, True), **changes)

    def test_whole_application_controls_checkpoint_and_release(self):
        instance, worker = self.launch()
        observation = self.host.observe(instance)
        self.assertTrue(observation.controls_verified)
        self.assertTrue(observation.populated)
        self.assertGreaterEqual(observation.tasks, 2)
        self.assertGreater(observation.memory_bytes, 0)
        self.assertIsNotNone(observation.cpu_usage_usec)
        self.assertEqual(worker[2], "$HOME; literal argument")
        group = self.host._instances[instance].cgroup
        pids = {int(p) for p in (group / "cgroup.procs").read_text().split()}
        self.assertTrue(set(worker[:2]).issubset(pids))
        for changes in ({"revision": 6}, {"checkpoint_durable": False},
                        {"quiescent": False}, {"instance": "unknown"}):
            with self.assertRaises(HostError):
                self.host.unload(self.auth(instance, **changes))
        self.assertTrue(self.host.observe(instance).populated)
        with self.assertRaises(HostError):
            self.host.retire(instance)
        self.assertTrue(self.host.unload(self.auth(instance)))
        self.assertFalse(self.host.unload(self.auth(instance)))
        self.until(lambda: self.host.observe(instance).populated is False)
        self.assertFalse((group / "cgroup.procs").exists() and
                         (group / "cgroup.procs").read_text().strip())
        self.host.retire(instance)
        with self.assertRaises(HostError):
            self.host.observe(instance)

    def test_refused_stop_does_not_auto_kill_or_claim_release(self):
        instance, _ = self.launch(stubborn=True)
        self.host.unload(self.auth(instance))
        self.until(lambda: self.host.observe(instance).active == "failed")
        observation = self.host.observe(instance)
        self.assertTrue(observation.populated)
        self.assertEqual(observation.result, "timeout")
        with self.assertRaises(HostError):
            self.host.retire(instance)
        self.assertFalse(self.host.unload(self.auth(instance)))

    def test_replacement_invocation_rejected(self):
        instance, _ = self.launch(agreement=replace(self.agreement, needs_checkpoint=False))
        unit = self.host._instances[instance].unit
        subprocess.run(["/usr/bin/systemctl", "--user", "restart", unit],
                       check=True, timeout=5)
        with self.assertRaisesRegex(HostError, "invocation changed"):
            self.host.unload(self.auth(instance))

    def test_validation_bounds_and_fresh_identity(self):
        with self.assertRaises(ValueError):
            self.host.reserve(replace(self.agreement, cpu_weight=10001), ["/usr/bin/true"])
        with self.assertRaises(ValueError):
            self.host.reserve(self.agreement, ["relative-command"])
        handles = [self.host.reserve(self.agreement, ["/usr/bin/true"]) for _ in range(4)]
        self.assertEqual(len(set(handles)), 4)
        with self.assertRaises(HostError):
            self.host.reserve(self.agreement, ["/usr/bin/true"])
        for handle in handles:
            self.host.retire(handle)


if __name__ == "__main__":
    if "--run-systemd-integration" not in sys.argv:
        raise SystemExit("Explicit opt-in required: --run-systemd-integration")
    sys.argv.remove("--run-systemd-integration")
    unittest.main(verbosity=2)
