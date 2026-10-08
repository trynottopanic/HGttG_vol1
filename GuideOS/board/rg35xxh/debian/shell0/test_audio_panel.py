import tempfile
import unittest
from unittest.mock import patch
from guide_audio_panel import AudioPanel, A, B, DOWN, MENU


class AudioPanelTests(unittest.TestCase):
    def test_missing_provider_and_navigation(self):
        with tempfile.TemporaryDirectory() as folder:
            panel = AudioPanel(folder)
            self.assertTrue(panel.poll())
            self.assertIn('unavailable', panel.status['message'])
            panel.activate('view:bluetooth')
            self.assertEqual(panel.key(B), 'changed')
            self.assertEqual(panel.view, 'player')
            self.assertEqual(panel.key(MENU), 'home')

    def test_stale_output_cannot_activate(self):
        panel = AudioPanel()
        panel.view = 'outputs'
        self.assertFalse(panel.activate('output:vanished'))

    def test_volume_available_on_every_audio_view(self):
        panel = AudioPanel()
        panel.view = 'bluetooth'
        with patch('guide_audio_panel.socket.socket') as constructor:
            panel.activate('quieter')
            raw = constructor.return_value.__enter__.return_value.sendto.call_args[0][0]
            self.assertIn(b'"value": 15', raw)

    def test_shell_audio_focus_context_and_global_volume(self):
        import guide_shell
        with patch.object(guide_shell, 'AUDIO_ENABLED', True):
            state = guide_shell.ShellState()
        state.page = 'media'
        state.menu_input.sync_focus()
        state.key(DOWN, 1)
        self.assertEqual(state.menu_input.focus_target().identity, 'audio:view:outputs')
        state.key(A, 1)
        self.assertEqual(state.audio_panel.view, 'outputs')
        options = state.menu_input.options_for(None)
        self.assertEqual(options['right']['id'], 'back')
        self.assertEqual(options['down']['id'], 'home')
        state.page = 'home'
        with patch.object(state.audio_panel, 'activate') as activate:
            state.key(115, 1)
            activate.assert_called_once_with('louder')


if __name__ == '__main__':
    unittest.main()
