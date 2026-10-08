"""Paused web browsing must not acquire a display or leave a Home launch target."""
import unittest
from unittest.mock import Mock, patch
import guide_shell as shell
from guide_menu_input import Target
from guide_v3_ui import DESTINATIONS, HomeState, V3UI
import guide_browser_session


class BrowserPausedTests(unittest.TestCase):
    def state(self):
        with patch.multiple(shell, AUDIO_ENABLED=False, STORAGE_ENABLED=False,
                            OPERATIONS_ENABLED=False, WIFI_CONTROL_ENABLED=False):
            state = shell.ShellState()
        self.addCleanup(state.text_entries.teardown)
        self.addCleanup(state.nodes_panel.worker.shutdown, wait=True)
        if state.wifi_panel:
            self.addCleanup(state.wifi_panel._address_worker.shutdown, wait=True)
        return state

    def test_bootstrap_environment_cannot_restore_browser_route(self):
        self.assertFalse(shell.BROWSER_ENABLED)
        self.assertNotIn('browser', shell.PAGES)
        self.assertNotIn('BROWSER', shell.CHOICES)
        state = self.state()
        state.open_v3_destination('browser')
        self.assertEqual(state.page, 'unavailable')
        self.assertIn('paused', state.unavailable_message)

    def test_all_home_wheel_positions_exclude_browser(self):
        home = HomeState()
        seen = set()
        for _ in DESTINATIONS:
            seen.update(home.visible)
            home.scroll(1)
        self.assertEqual(seen, set(DESTINATIONS))
        self.assertNotIn('browser', seen)
        V3UI(world_runtime='missing', world_module='missing')._tray_tile('C', True)

    def test_third_tray_shortcut_opens_installed_applications(self):
        state = self.state()
        target = Target('v3-tray:C', 'Shortcut C', (196,374,278,466), 'v3-shortcut', 2)
        state.menu_input.targets = Mock(return_value=[target])
        with patch.object(state, 'open_installer') as opened:
            self.assertTrue(state.menu_input.activate(target.identity))
        opened.assert_called_once_with('installed')
        self.assertEqual(state.page, 'installer')

    def test_service_entry_cannot_start_compositor_or_modify_runtime(self):
        with patch.object(guide_browser_session.subprocess, 'Popen') as launch, \
             patch.object(guide_browser_session.os, 'geteuid') as uid:
            with self.assertRaisesRegex(RuntimeError, 'paused'):
                guide_browser_session.run(runtime_path='/not-an-owned-runtime')
        launch.assert_not_called()
        uid.assert_not_called()
