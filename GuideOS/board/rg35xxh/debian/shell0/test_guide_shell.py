#!/usr/bin/python3
"""Host-safe tests for the first Debian Guide Shell slice."""
import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path
import sys
import unittest
import tempfile
from unittest.mock import Mock, patch

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("shell", HERE / "guide_shell.py")
shell = importlib.util.module_from_spec(spec)
with patch.dict(os.environ, {"GUIDE_WIFI_DISCOVERY": "1"}):
    spec.loader.exec_module(shell)


class StateTests(unittest.TestCase):
    def test_baseline_profile_maps_third_choice_to_power(self):
        with patch.object(shell, 'PAGES', ('media', 'status', 'power')), patch.object(shell, 'CHOICES', ('MEDIA FOUNDATION', 'SYSTEM STATUS', 'POWER OFF')):
            state = shell.ShellState()
            state.key(shell.DOWN, 1)
            state.key(shell.DOWN, 1)
            state.key(shell.A, 1)
            self.assertEqual(state.page, 'power')
            self.assertFalse(state.shutdown_requested)
            state.key(shell.A, 1)
            self.assertTrue(state.shutdown_requested)

    def test_baseline_status_does_not_claim_discovery(self):
        with patch.object(shell, 'WIFI_DISCOVERY_ENABLED', False):
            self.assertIn('Wi-Fi: not enabled in this revision', shell.system_status())

    def test_menu_navigation_and_pages(self):
        state = shell.ShellState()
        self.assertTrue(state.key(shell.DOWN, 1))
        self.assertEqual(state.selection, 1)
        state.key(shell.A, 1)
        self.assertEqual(state.page, "status")
        state.key(shell.B, 1)
        self.assertEqual(state.page, "home")

    def test_repeat_and_release_do_not_replay(self):
        state = shell.ShellState()
        state.key(shell.DOWN, 1)
        self.assertFalse(state.key(shell.DOWN, 2))
        self.assertFalse(state.key(shell.DOWN, 0))
        self.assertEqual(state.selection, 1)

    def test_power_requires_separate_confirmation(self):
        state = shell.ShellState()
        state.selection = shell.CHOICES.index('POWER OFF')
        state.key(shell.A, 1)
        self.assertEqual(state.page, "power")
        self.assertFalse(state.shutdown_requested)
        state.key(shell.B, 1)
        self.assertEqual(state.page, "home")
        state.key(shell.A, 1)
        state.key(shell.A, 1)
        self.assertTrue(state.shutdown_requested)

    def test_global_menu_returns_home(self):
        state = shell.ShellState()
        state.page = "status"
        state.key(shell.MENU, 1)
        self.assertEqual(state.page, "home")

    def test_power_device_is_not_in_shell_input_allowlist(self):
        platform = __import__("guide_platform_rg35xxh")
        self.assertEqual(platform.ALLOWED_INPUTS, {"H700 Gamepad", "gpio-keys-volume"})

    def test_wifi_scan_is_cancellable_and_does_not_connect(self):
        state = shell.ShellState()
        state.selection = shell.CHOICES.index('WI-FI DISCOVERY')
        state.key(shell.A, 1)
        self.assertEqual(state.page, 'wifi')
        self.assertTrue(state.scan_requested)
        state.scan_requested = False
        state.wifi = dict(state='scanning', message='Scanning', networks=[])
        self.assertFalse(state.key(shell.A, 1))
        state.key(shell.B, 1)
        self.assertEqual(state.page, 'home')

    def test_wifi_scroll_is_bounded(self):
        state = shell.ShellState()
        state.page = 'wifi'
        state.wifi['networks'] = [{}] * 8
        for _ in range(20):
            state.key(shell.DOWN, 1)
        self.assertEqual(state.wifi_scroll, 3)
        state.key(shell.MENU, 1)
        self.assertEqual(state.page, 'home')

    def test_stalled_scan_is_killed_and_reported_as_timeout(self):
        job = shell.WiFiScan()
        child = Mock()
        child.poll.return_value = None
        child.communicate.return_value = (b'', None)
        job.process = child
        job.deadline = 1
        with patch.object(shell.time, 'monotonic', return_value=2):
            result = job.poll()
        self.assertEqual(result['state'], 'timeout')
        child.kill.assert_called_once()
        self.assertIsNone(job.process)


class ScanProcessTests(unittest.TestCase):
    def launch(self, code):
        job = shell.WiFiScan()
        real_popen = subprocess.Popen
        def child(*_args, **_kwargs):
            return real_popen([sys.executable, '-c', code], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, pipesize=4096)
        with patch.object(shell.subprocess, 'Popen', side_effect=child):
            job.start()
        job.deadline = time.monotonic() + 5
        self.addCleanup(job.cancel)
        return job

    def finish(self, job):
        result = None
        while result is None:
            result = job.poll()
            time.sleep(0.005)
        return result

    def test_dense_response_larger_than_pipe_completes(self):
        payload = dict(state='ready', message='Nearby networks', networks=[
            dict(ssid='\ufffd' * 28 + f'{i:04d}', signal=60, security='WPA2') for i in range(64)])
        encoded = json.dumps(payload)
        self.assertGreater(len(encoded), 4096)
        job = self.launch('import sys; sys.stdout.write(' + repr(encoded) + ')')
        self.assertEqual(self.finish(job), payload)

    def test_oversized_output_is_bounded_and_child_reaped(self):
        job = self.launch("import sys; sys.stdout.write('x' * 200000)")
        child = job.process
        self.assertEqual(self.finish(job)['state'], 'failed')
        self.assertIsNotNone(child.poll())
        self.assertIsNone(job.process)
        self.assertEqual(len(job.output), 0)

    def test_cancel_while_pipe_full_reaps_child(self):
        job = self.launch("import sys,time; sys.stdout.write('x' * 200000); time.sleep(10)")
        child = job.process
        job.cancel()
        self.assertIsNotNone(child.poll())
        self.assertTrue(child.stdout.closed)

    def test_malformed_network_row_is_failure(self):
        payload = json.dumps(dict(state='ready', message='Nearby networks', networks=[dict(ssid='x')]))
        job = self.launch('print(' + repr(payload) + ')')
        self.assertEqual(self.finish(job)['state'], 'failed')

    def test_nonzero_child_cannot_report_success(self):
        payload = json.dumps(dict(state='ready', message='Nearby networks', networks=[]))
        job = self.launch('import sys; print(' + repr(payload) + '); sys.exit(1)')
        self.assertEqual(self.finish(job)['state'], 'failed')

    def test_timeout_reaps_live_child(self):
        job = self.launch('import time; time.sleep(10)')
        child = job.process
        job.deadline = 0
        self.assertEqual(job.poll()['state'], 'timeout')
        self.assertIsNotNone(child.poll())

class ReportFailureTests(unittest.TestCase):
    def test_unwritable_mirror_does_not_prevent_reporting_to_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            blocked = root / 'blocked'
            blocked.write_text('not a directory')
            report = shell.Report(root / 'data', blocked)
            errors = report.save(shell.ShellState(), 'running')
            self.assertEqual(len(errors), 1)
            self.assertEqual(len(list((root / 'data').rglob('guide-shell.json'))), 1)
            self.assertEqual(report.saved_destinations, 1)
            saved = json.loads(next((root / 'data').rglob('guide-shell.json')).read_text())
            self.assertEqual(saved['shell_sha256'], report.shell_sha256)
            self.assertEqual(len(saved['shell_sha256']), 64)

    def test_both_report_destinations_failing_do_not_raise(self):
        with tempfile.TemporaryDirectory() as temporary:
            blocked = Path(temporary) / 'blocked'
            blocked.write_text('not a directory')
            report = shell.Report(blocked, blocked)
            self.assertEqual(len(report.save(shell.ShellState(), 'shutdown_requested')), 2)
            self.assertEqual(report.saved_destinations, 0)

    def test_reporting_recovers_when_destination_becomes_available(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            blocked = root / 'mirror'
            blocked.write_text('not a directory')
            report = shell.Report(root / 'data', blocked)
            self.assertEqual(len(report.save(shell.ShellState(), 'running')), 1)
            blocked.unlink()
            blocked.mkdir()
            self.assertEqual(report.save(shell.ShellState(), 'stopped'), [])
            self.assertEqual(report.saved_destinations, 2)

    def test_report_failure_does_not_suppress_confirmed_power_request(self):
        class Inputs:
            devices = []
            def __init__(self, _logger): pass
            def poll(self, _delay):
                return [('fixture', shell.EV_KEY, code, 1) for code in
                        (shell.DOWN, shell.DOWN, shell.DOWN, shell.A, shell.A)]
            def close(self): return []
        class Surface:
            def close(self): return []
        with tempfile.TemporaryDirectory() as temporary:
            blocked = Path(temporary) / 'blocked'
            blocked.write_text('not a directory')
            report = shell.Report(blocked, blocked)
            power = Mock()
            with patch.object(shell, 'Screen'), patch.object(shell.signal, 'signal'):
                shell.run(report, input_factory=Inputs, framebuffer_factory=Surface, poweroff=power)
            power.assert_called_once()
            self.assertEqual(report.saved_destinations, 0)


if __name__ == "__main__":
    unittest.main()
