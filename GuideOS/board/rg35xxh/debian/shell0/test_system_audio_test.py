import unittest
from unittest.mock import patch
import guide_shell
from guide_shell_schema_adapter import status_model
from guide_field_ui import FieldUI
from pathlib import Path

class SystemAudioTestTests(unittest.TestCase):
    def test_controller_action_and_back_preserve_global_navigation(self):
        with patch.object(guide_shell,'AUDIO_ENABLED',True):state=guide_shell.ShellState()
        state.page='status';state.menu_input.sync_focus()
        self.assertEqual(state.menu_input.focus_target().identity,'status:audio-test')
        with patch.object(state.audio_panel,'activate') as activate:
            self.assertTrue(state.key(guide_shell.A,1));activate.assert_called_once_with('test')
        self.assertFalse(state.key(guide_shell.A,2))
        state.key(guide_shell.DOWN,1)
        self.assertEqual(state.menu_input.focus_target().identity,'back')
        state.key(guide_shell.A,1);self.assertEqual(state.page,'home')

    def test_schema_drawn_action_matches_hit_target(self):
        root=Path(__file__).resolve().parents[4]/'package/guide-ui'
        ui=FieldUI(root)
        for label in ('Audio test','Stop test'):
            result=ui.render(status_model(['GuideOS: 0.3.9'],audio_test_label=label))
            self.assertEqual([r.identity for r in result.regions],['status:audio-test','back','home'])
            self.assertEqual(result.regions[0].value,guide_shell.A)
            self.assertEqual(result.regions[0].label,label)
            for region in result.regions:
                x,y,right,bottom=region.rect.tuple();self.assertLessEqual(right,640);self.assertLessEqual(bottom,480)

    def test_option_absent_without_audio_provider(self):
        with patch.object(guide_shell,'AUDIO_ENABLED',False):state=guide_shell.ShellState()
        state.page='status'
        self.assertNotIn('status:audio-test',[t.identity for t in state.menu_input.targets()])

if __name__=='__main__':unittest.main()
