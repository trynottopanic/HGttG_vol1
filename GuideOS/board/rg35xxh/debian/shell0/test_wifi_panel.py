import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
import time
import traceback
import unittest
from unittest.mock import Mock, patch

import guide_wifi_panel as panel


LINUX_ONLY = unittest.skipUnless(os.name == 'posix', 'Linux shell/socket integration')


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ui = panel.WiFiPanel(self.tmp.name)
        self.addCleanup(self.ui.clear)
        self.row = dict(id='a'*24, ssid='Example', security='WPA2', saved=False, available=True, active=False, supported=True, signal=80)
        self.ui.status['networks'] = [self.row]
        self.ui.target = self.row['id']

    def open_password(self, text=''):
        self.ui.view = 'detail'
        self.ui.key(panel.A)
        self.assertEqual(self.ui.view, 'password')
        if text:
            self.ui.editor.handle('insert', text=text)
        return self.ui.editor

    def select_submit(self):
        for row, keys in enumerate(self.ui.editor.rows):
            for column, key in enumerate(keys):
                if key.action == 'submit':
                    self.ui.editor.focus = (row, column)
                    return
        self.fail('Submit action is missing')

    def write_status(self, **changes):
        values = dict(self.ui.status, observed=time.monotonic())
        values.update(changes)
        (Path(self.tmp.name) / 'status.json').write_text(json.dumps(values))

    def load_shell(self):
        spec = importlib.util.spec_from_file_location('keyboard_test_shell', Path(__file__).with_name('guide_shell.py'))
        shell = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {'GUIDE_WIFI_DISCOVERY':'1', 'GUIDE_WIFI_CONTROL':'1'}):
            spec.loader.exec_module(shell)
        return shell

    def fake_hardware(self):
        inputs = Mock()
        inputs.devices = []
        inputs.close.return_value = []
        framebuffer = Mock()
        framebuffer.close.return_value = []
        return inputs, framebuffer

    def test_opening_press_does_not_type_or_submit(self):
        with patch.object(self.ui, 'send') as send:
            editor = self.open_password()
            self.assertEqual(editor.session.text, '')
            self.assertEqual(editor.session.state, 'editing')
            send.assert_not_called()

    def test_cancel_and_menu_release_shared_focus_and_secret_references(self):
        for key in (panel.B, panel.MENU):
            with self.subTest(key=key), patch.object(self.ui, 'send') as send:
                editor = self.open_password('sensitive-password')
                outcome = self.ui.key(key)
                self.assertEqual(outcome, 'home' if key == panel.MENU else 'changed')
                self.assertIsNone(self.ui.editor)
                self.assertIsNone(self.ui.text_entries.active)
                self.assertEqual(editor.session.text, '')
                self.assertIsNone(editor.session.take_result(
                    editor.session.request.owner_id, editor.session.token))
                send.assert_not_called()

    def test_invalid_password_stays_editing_and_never_sends(self):
        editor = self.open_password('short')
        self.select_submit()
        with patch.object(self.ui, 'send') as send:
            self.ui.key(panel.A)
            send.assert_not_called()
        self.assertIs(self.ui.editor, editor)
        self.assertEqual(editor.session.state, 'editing')
        self.assertEqual(editor.session.text, 'short')
        self.assertIsNotNone(editor.session.error)

    def test_submission_delivers_exact_password_once_and_releases_editor(self):
        secret = 'MiXeD space!'
        editor = self.open_password(secret)
        self.select_submit()
        with patch.object(self.ui, 'send') as send:
            self.ui.key(panel.A)
            self.ui.key(panel.A)
            send.assert_called_once_with('connect', id=self.row['id'], password=secret)
        self.assertIsNone(self.ui.editor)
        self.assertIsNone(self.ui.text_entries.active)
        self.assertEqual(editor.session.text, '')
        self.assertIsNone(editor.session.take_result(
            editor.session.request.owner_id, editor.session.token))

    @LINUX_ONLY
    def test_local_socket_receives_password_without_argv_or_persisted_ui_file(self):
        endpoint = str(Path(self.tmp.name) / 'control.sock')
        editor = self.open_password('local-secret')
        self.select_submit()
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server:
            server.bind(endpoint)
            server.settimeout(1)
            self.ui.key(panel.A)
            received = json.loads(server.recv(4096))
            self.assertEqual(received['password'], 'local-secret')
            self.assertEqual(received['id'], self.row['id'])
        self.assertIsNone(self.ui.editor)
        self.assertEqual(editor.session.text, '')
        self.assertEqual(len(list(Path(self.tmp.name).iterdir())), 1)

    def test_failed_send_still_releases_secret_and_exposes_failure(self):
        editor = self.open_password('local-secret')
        self.select_submit()
        with patch.object(panel.socket, 'AF_UNIX', 1, create=True), patch.object(
                panel.socket, 'socket', side_effect=OSError('unavailable')):
            self.ui.key(panel.A)
        self.assertIsNone(self.ui.editor)
        self.assertIsNone(self.ui.text_entries.active)
        self.assertEqual(editor.session.text, '')
        self.assertIn('unavailable', self.ui.notice)
        self.assertNotIn('local-secret', repr(self.ui.__dict__))

    def test_refresh_preserves_selected_network_when_signal_order_changes(self):
        self.ui.cursor = 2
        other = dict(self.row, id='b'*24, ssid='Other')
        self.write_status(networks=[other, self.row])
        self.ui.poll()
        self.assertEqual(self.ui.rows()[self.ui.cursor][0], self.row['id'])

    def test_refresh_and_network_disappearance_preserve_active_draft_and_target(self):
        editor = self.open_password('not-yet-submitted')
        editor.handle('right')
        editor.handle('down')
        before = (editor.focus, editor.page, editor.session.cursor, editor.session.text)
        self.write_status(networks=[dict(self.row, id='b'*24, ssid='Other')])
        self.ui.poll()
        self.assertIs(self.ui.editor, editor)
        self.assertEqual(self.ui.target, self.row['id'])
        self.assertEqual((editor.focus, editor.page, editor.session.cursor, editor.session.text), before)

    def test_saved_network_connects_without_editor(self):
        self.row['saved'] = True
        self.ui.view = 'detail'
        with patch.object(self.ui, 'send') as send:
            self.ui.key(panel.A)
            send.assert_called_once_with('connect', id=self.row['id'])
        self.assertIsNone(self.ui.editor)

    def test_forget_requires_explicit_confirmation(self):
        self.ui.view = 'detail'
        self.row['saved'] = True
        self.ui.key(panel.DOWN)
        with patch.object(self.ui, 'send') as send:
            self.ui.key(panel.A)
            self.assertEqual(self.ui.view, 'forget')
            send.assert_not_called()
            self.ui.key(panel.A)
            send.assert_called_once_with('forget', id=self.row['id'])

    def test_leaving_screen_does_not_cancel_system_owned_connection(self):
        self.ui.view = 'working'
        with patch.object(self.ui, 'send') as send:
            self.assertEqual(self.ui.key(panel.MENU), 'home')
            send.assert_not_called()

    def test_back_after_completion_does_not_send_a_spurious_cancel(self):
        self.ui.view = 'working'
        self.ui.status['busy'] = False
        with patch.object(self.ui, 'send') as send:
            self.ui.key(panel.B)
            send.assert_not_called()
        self.assertEqual(self.ui.view, 'list')

    def test_unavailable_saved_network_never_prompts_for_password(self):
        self.row['available'] = False
        self.row['saved'] = True
        self.ui.view = 'detail'
        self.ui.key(panel.A)
        self.assertEqual(self.ui.view, 'detail')
        self.assertIsNone(self.ui.editor)
        self.assertIn('Unavailable', self.ui.notice)

    @LINUX_ONLY
    def test_shell_repeats_cannot_type_or_submit(self):
        shell = self.load_shell()
        state = shell.ShellState()
        state.wifi_panel = self.ui
        state.page = 'wifi'
        editor = self.open_password('ready-secret')
        self.assertFalse(state.key(panel.A, 2))
        self.assertFalse(state.key(panel.A, 0))
        self.assertEqual(editor.session.text, 'ready-secret')
        self.select_submit()
        with patch.object(self.ui, 'send') as send:
            self.assertFalse(state.key(panel.A, 2))
            send.assert_not_called()
            state.key(panel.A, 1)
            state.key(panel.A, 2)
            send.assert_called_once_with('connect', id=self.row['id'], password='ready-secret')

    @LINUX_ONLY
    def test_shell_excludes_wifi_keystrokes_from_reports_and_still_shuts_down(self):
        shell = self.load_shell()
        events = [panel.DOWN, panel.DOWN, panel.A, panel.DOWN, panel.DOWN, panel.A,
                  panel.A, panel.RIGHT, panel.A, panel.MENU, panel.DOWN, panel.A, panel.A]
        inputs, framebuffer = self.fake_hardware()
        inputs.poll.return_value = [('H700 Gamepad', 1, code, 1) for code in events]
        report = shell.Report(Path(self.tmp.name)/'data', Path(self.tmp.name)/'boot')
        with patch.object(shell, 'WiFiPanel', return_value=self.ui), patch.object(shell, 'Screen'), patch.object(self.ui, 'poll', return_value=False):
            power = Mock()
            shell.run(report, input_factory=lambda _cb: inputs, framebuffer_factory=lambda: framebuffer, poweroff=power)
        power.assert_called_once()
        self.assertFalse(any(e.get('code') == panel.RIGHT for e in report.events))
        self.assertIsNone(self.ui.editor)
        self.assertIsNone(self.ui.text_entries.active)

    @LINUX_ONLY
    def test_shell_exception_never_reports_or_prints_secret_payload(self):
        shell = self.load_shell()
        state = shell.ShellState()
        state.wifi_panel = self.ui
        state.page = 'wifi'
        editor = self.open_password('private-error-payload')
        inputs, framebuffer = self.fake_hardware()
        inputs.poll.side_effect = ValueError('private-error-payload')
        report = shell.Report(Path(self.tmp.name)/'data', Path(self.tmp.name)/'boot')
        with patch.object(shell, 'ShellState', return_value=state), patch.object(shell, 'Screen'), patch.object(self.ui, 'poll', return_value=False):
            try:
                shell.run(report, input_factory=lambda _cb: inputs, framebuffer_factory=lambda: framebuffer, poweroff=Mock())
            except RuntimeError:
                failure = traceback.format_exc()
            else:
                self.fail('The shell failure was not surfaced')
        self.assertNotIn('private-error-payload', failure)
        self.assertNotIn('private-error-payload', json.dumps(report.events))
        self.assertEqual(editor.session.text, '')
        self.assertIsNone(self.ui.editor)
        self.assertIsNone(self.ui.text_entries.active)
        self.assertTrue(any(e.get('error_type') == 'ValueError' for e in report.events))


if __name__ == '__main__':
    unittest.main()
