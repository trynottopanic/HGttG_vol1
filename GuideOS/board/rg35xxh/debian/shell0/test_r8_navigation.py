import os
import unittest
from unittest.mock import Mock,patch

with patch.dict(os.environ, {
        'GUIDE_WIFI_DISCOVERY':'1', 'GUIDE_WIFI_CONTROL':'1',
        'GUIDE_AUDIO':'1', 'GUIDE_STORAGE':'1', 'GUIDE_OPERATIONS':'1'}):
    import guide_shell as shell
from guide_v3_ui import SETTINGS
from guide_v3_ui import V3UI


class SettingsRegressionTests(unittest.TestCase):
    def make_state(self):
        state=shell.ShellState()
        self.addCleanup(state.text_entries.teardown)
        self.addCleanup(state.operations.close)
        if state.audio_panel and hasattr(state.audio_panel,'close'):
            self.addCleanup(state.audio_panel.close)
        return state

    def test_every_settings_focus_has_a_valid_identity(self):
        state=self.make_state();state.page='settings'
        for index,(identity,_label,_detail) in enumerate(SETTINGS):
            state.settings_selection=index
            target=state.menu_input.focus_target()
            self.assertIsNotNone(target)

    def test_settings_down_reaches_about_without_exception(self):
        state=self.make_state();state.page='settings'
        for _ in range(3):
            state.menu_input.key(shell.DOWN)
        self.assertEqual(SETTINGS[state.settings_selection][0],'about')

    def test_settings_child_b_returns_to_settings_then_home(self):
        state=self.make_state();state.open_v3_destination('settings')
        self.assertTrue(state.open_v3_setting('updates'))
        self.assertEqual(state.page,'updates')
        state._key(shell.B,1)
        self.assertEqual(state.page,'settings')
        state._key(shell.B,1)
        self.assertEqual(state.page,'home')

    def test_every_available_settings_child_returns_to_settings(self):
        for setting in ('audio','connections','storage','power','updates','diagnostics','about'):
            with self.subTest(setting=setting):
                state=self.make_state();state.open_v3_destination('settings')
                self.assertTrue(state.open_v3_setting(setting))
                state._key(shell.B,1)
                self.assertEqual(state.page,'settings')

    def test_internal_wifi_back_precedes_parent_back(self):
        state=self.make_state();state.open_v3_destination('settings')
        state.open_v3_setting('connections');state.wifi_panel.view='detail'
        state._key(shell.B,1)
        self.assertEqual(state.page,'wifi')
        self.assertEqual(state.wifi_panel.view,'list')
        state._key(shell.B,1)
        self.assertEqual(state.page,'settings')

    def test_menu_clears_hierarchy_and_returns_home(self):
        state=self.make_state();state.open_v3_destination('settings')
        state.open_v3_setting('diagnostics')
        state._key(shell.MENU,1)
        self.assertEqual(state.page,'home')
        self.assertEqual(state.navigation_stack,[])

    def test_audio_settings_is_one_test_button(self):
        state=self.make_state();state.open_v3_destination('settings')
        state.open_v3_setting('audio')
        self.assertEqual(state.page,'audio-test')
        model=__import__('guide_field_ui').field_model(state)
        self.assertEqual([(item.label,item.value) for item in model.items],[('Test speakers','test')])

    def test_applications_reuses_installed_cache(self):
        from guide_installer_panel import InstallerPanel
        owner=Mock(page='home')
        panel=InstallerPanel(owner);self.addCleanup(panel.shutdown)
        panel.installed_cache_valid=True
        panel.installed_cache=[{'name':'Cached app','version':'1','state':'committed'}]
        panel.installed_cache_next=None
        panel.refresh=Mock()
        panel.open('installed')
        panel.refresh.assert_not_called()
        self.assertEqual(panel.items[0]['name'],'Cached app')

    def test_select_toggles_home_tray_and_r3_does_not(self):
        state=self.make_state();state.page='home'
        self.assertTrue(state.menu_input.key(314));self.assertTrue(state.v3_home.tray_extended)
        self.assertFalse(state.menu_input.key(318));self.assertTrue(state.v3_home.tray_extended)
        self.assertTrue(state.menu_input.key(314));self.assertFalse(state.v3_home.tray_extended)

    def test_board_start_code_is_treated_as_physical_select_on_home(self):
        state=self.make_state();state.page='home'
        self.assertTrue(state.menu_input.key(315));self.assertTrue(state.v3_home.tray_extended)

    def test_menu_code_is_treated_as_physical_select_on_home(self):
        state=self.make_state();state.page='home'
        self.assertTrue(state.menu_input.key(316));self.assertTrue(state.v3_home.tray_extended)

    def test_cursor_position_survives_navigation_and_dpad_focus(self):
        state=self.make_state();pointer=state.menu_input.pointer
        pointer.move_to(91,137);state.menu_input.pointer_active=True
        state.open_v3_destination('settings')
        self.assertEqual(pointer.position,(91.0,137.0))
        state.menu_input.key(547)
        self.assertEqual(pointer.position,(91.0,137.0))
        self.assertFalse(state.menu_input.pointer_active)

    def test_generic_two_column_grid_moves_relative_to_selection(self):
        state=self.make_state();updates=state.operations.pages['updates']
        updates.status={'protocol':'GUIDE-SIGNED-BUNDLE-1','highest_sequence':45,
                        'transaction':{'id':'next','state':'validated','sequence':46,
                        'review':{'version':'next'}}}
        updates.act('review','next');state.page='updates';state.operations.current='updates'
        ui=V3UI(world_runtime='missing',world_module='missing')
        state.schema_target_provider=lambda:ui.render(state.operations.model()).regions
        state.menu_input.sync_focus()
        self.assertEqual(state.operations.model().focus_id,'install')
        self.assertTrue(state.menu_input.key(547))
        self.assertEqual(state.operations.model().focus_id,'later')
        self.assertTrue(state.menu_input.key(546))
        self.assertEqual(state.operations.model().focus_id,'install')


if __name__ == '__main__':unittest.main()
