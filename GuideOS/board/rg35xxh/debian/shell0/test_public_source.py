"""The public shell remains usable without the optional private world app."""
import builtins
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import guide_shell as shell
from guide_v3_ui import V3UI


class PublicSourceTests(unittest.TestCase):
    def test_missing_application_has_visible_failure_and_back_returns_home(self):
        with patch.multiple(shell, AUDIO_ENABLED=False, STORAGE_ENABLED=False,
                            OPERATIONS_ENABLED=False, WIFI_CONTROL_ENABLED=False):
            state = shell.ShellState()
        self.addCleanup(state.text_entries.teardown)
        self.addCleanup(state.nodes_panel.worker.shutdown, wait=True)
        original = builtins.__import__

        def missing(name, *args, **kwargs):
            if name == 'guide_planegotchi':
                raise ModuleNotFoundError('Optional application omitted', name=name)
            return original(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=missing):
            self.assertTrue(state.open_v3_destination('planegotchi'))
        self.assertEqual(state.page, 'unavailable')
        self.assertIn('not installed', state.unavailable_message)
        self.assertIsNone(state.planegotchi)
        self.assertTrue(state.key(shell.B, 1))
        self.assertEqual(state.page, 'home')

    def test_home_renders_without_private_art_and_preserves_settings_navigation(self):
        ui = V3UI()
        ui.planet_assets_available = False
        ui.world_available = False
        ui._planet_tile = None
        with patch.multiple(shell, AUDIO_ENABLED=False, STORAGE_ENABLED=False,
                            OPERATIONS_ENABLED=False, WIFI_CONTROL_ENABLED=False):
            state = shell.ShellState()
        self.addCleanup(state.text_entries.teardown)
        self.addCleanup(state.nodes_panel.worker.shutdown, wait=True)
        with tempfile.TemporaryDirectory() as temporary:
            ui.design_assets = Path(temporary)
            for frame in (0, 35, 899):
                state.v3_home.planet_frame = frame
                result = ui.render_home(state)
                self.assertEqual(result.image.size, (640, 480))
                self.assertTrue(any(r.value == 'settings' for r in result.regions))
        state.open_v3_destination('settings')
        state.open_v3_setting('nearby')
        self.assertEqual(state.page, 'nearby')


if __name__ == '__main__':
    unittest.main()
