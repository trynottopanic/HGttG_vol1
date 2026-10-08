import os
import unittest
from types import SimpleNamespace

from guide_v3_ui import (HomeState, V3UI, WHEEL_CENTER, WHEEL_OUTER_RADIUS,
                         WHEEL_INNER_RADIUS, wheel_choice, wheel_sector)
from guide_ui_model import Fact, ScreenModel


class HomeStateTests(unittest.TestCase):
    def test_right_stick_holds_arms_and_opens_once(self):
        home = HomeState()
        changed, destination = home.update({'right': (0, -1), 'right_click': False}, now=0)
        self.assertTrue(changed);self.assertIsNone(destination);self.assertEqual(home.wheel_held, 0)
        changed, destination = home.update({'right': (0, 0), 'right_click': False}, now=.1)
        self.assertTrue(changed);self.assertIsNone(destination);self.assertEqual(home.wheel_pending, 'files')
        self.assertEqual(home.update({'right': (0, 0), 'right_click': False}, now=.15), (False, None))
        self.assertEqual(home.update({'right': (0, 0), 'right_click': False}, now=.17), (True, 'files'))
        self.assertEqual(home.update({'right': (0, 0), 'right_click': False}, now=.3), (False, None))

    def test_r3_is_reserved_and_does_not_toggle_tray(self):
        home = HomeState(tray_extended=False,tray_position=0)
        self.assertEqual(home.update({'right': (0, 0), 'right_click': True}, now=0),(False,None))
        self.assertFalse(home.tray_extended)
        self.assertEqual(home.update({'right': (0, 0), 'right_click': True}, now=.05),(False,None))
        home.update({'right': (0, 0), 'right_click': False}, now=.1)
        home.update({'right': (0, 0), 'right_click': True}, now=.2)
        self.assertFalse(home.tray_extended)

    def test_direction_tracks_three_quarter_circle_sectors(self):
        for right,expected in (((0,-.27),0),((-.2,-.2),1),((-.27,0),2)):
            home=HomeState();home.update({'right':right,'right_click':False},now=0)
            self.assertEqual(home.wheel_held,expected)

    def test_facing_away_cancels_selection_before_release(self):
        home=HomeState();home.update({'right':(-1,0),'right_click':False},now=0)
        self.assertEqual(home.wheel_held,2)
        self.assertEqual(home.update({'right':(1,0),'right_click':False},now=.1),(True,None))
        self.assertIsNone(home.wheel_held);self.assertIsNone(home.wheel_pending)
        self.assertEqual(home.update({'right':(0,0),'right_click':False},now=.2),(False,None))

    def test_wheel_geometry_is_exact_bottom_right_quarter_circle(self):
        self.assertEqual(WHEEL_CENTER,(640,480))
        self.assertEqual((WHEEL_OUTER_RADIUS,WHEEL_INNER_RADIUS),(270,79))
        self.assertEqual([wheel_sector(i) for i in range(3)],
                         [(240,270,255),(210,240,225),(180,210,195)])
        self.assertIsNone(wheel_choice(1,0));self.assertIsNone(wheel_choice(0,1))

    def test_tray_and_wheel_motion_are_time_based(self):
        home=HomeState(tray_extended=False,tray_position=0);home.toggle_tray(now=0);home.tick(.12)
        self.assertGreater(home.tray_position,.5);self.assertLess(home.tray_position,1)
        home.scroll(1,now=.3);home.tick(.41)
        self.assertGreater(home.wheel_motion,.4);self.assertLess(home.wheel_motion,1)

    def test_wheel_scroll_brings_storage_into_view(self):
        home = HomeState();self.assertEqual(home.visible, ('files','applications','settings'))
        home.scroll(1);self.assertEqual(home.visible, ('applications','settings','storage'))
        home.scroll(1);self.assertEqual(home.visible, ('settings','storage','media'))


class V3RenderTests(unittest.TestCase):
    def test_file_details_first_animation_frame_is_drawable(self):
        ui=V3UI(world_runtime='missing',world_module='missing')
        model=ScreenModel('file-details','Folder',
                          facts=(Fact('Name','example.mp3'),),transition=0.0)
        first=ui.render(model).image
        complete=ui.render(ScreenModel('file-details','Folder',
                           facts=model.facts,transition=1.0)).image
        self.assertEqual(first.size,(640,480))
        self.assertNotEqual(first.tobytes(),complete.tobytes())

    def test_audio_player_is_a_complete_interactive_view(self):
        ui=V3UI(world_runtime='missing',world_module='missing')
        model=ScreenModel('audio-player','Music',facts=(
            Fact('Title','Answer Song.mp3'),Fact('Source','Albums/Guide'),
            Fact('Output','Deck speakers'),Fact('Elapsed','42'),
            Fact('Duration','180'),Fact('State','playing')),
            items=tuple(__import__('guide_ui_model').MenuItem('audio:'+value,label,'audio-row',value)
                        for value,label in (('media-previous','Previous'),('media-pause','Pause'),('media-next','Next'))),
            focus_id='audio:media-pause')
        rendered=ui.render(model)
        self.assertEqual(rendered.image.size,(640,480))
        self.assertEqual([region.value for region in rendered.regions],
                         ['media-previous','media-pause','media-next'])

    def test_wheel_is_neutral_until_right_stick_actively_selects(self):
        ui=V3UI(world_runtime='missing',world_module='missing')
        state=SimpleNamespace(v3_home=HomeState(),settings_selection=0)
        neutral=ui.render_home(state,now=0).image
        state.v3_home.update({'right':(0,-1),'right_click':False},now=.1)
        state.v3_home.tick(.2)
        active=ui.render_home(state,now=.2).image
        self.assertNotEqual(neutral.tobytes(),active.tobytes())
        state.v3_home.update({'right':(0,0),'right_click':False},now=.3)
        pending=ui.render_home(state,now=.31).image
        self.assertNotEqual(active.tobytes(),pending.tobytes())

    def test_world_placeholder_is_still_across_frames(self):
        ui = V3UI(world_runtime='missing', world_module='missing')
        state = SimpleNamespace(v3_home=HomeState(), settings_selection=0)
        first = ui.render_home(state, now=0).image.crop((24,55,286,283))
        second = ui.render_home(state, now=30).image.crop((24,55,286,283))
        self.assertEqual(first.tobytes(), second.tobytes())

    def test_world_placeholder_is_expanded_by_requested_proportions(self):
        ui=V3UI(world_runtime='missing',world_module='missing')
        self.assertEqual(ui._placeholder_world().size,(262,228))

    def test_home_and_settings_are_interactive(self):
        ui = V3UI(world_runtime='missing', world_module='missing')
        state = SimpleNamespace(v3_home=HomeState(), settings_selection=0)
        home = ui.render_home(state, now=0)
        self.assertEqual(home.image.size, (640,480))
        self.assertEqual([r.value for r in home.regions], ['files','applications','settings'])
        state.v3_home.toggle_tray(now=1)
        state.v3_home.tick(now=2)
        self.assertEqual(len(ui.render_home(state, now=2).regions), 7)
        settings = ui.render(ui.settings_model(state))
        self.assertEqual(len(settings.regions), 7)
        self.assertEqual(settings.regions[0].value, 'audio')
        self.assertEqual(settings.regions[4].value, 'updates')

    def test_pending_update_does_not_cover_home(self):
        ui=V3UI(world_runtime='missing',world_module='missing')
        state=SimpleNamespace(v3_home=HomeState(),settings_selection=0,update_notice_id='release')
        image=ui.render_home(state,now=0).image
        state.update_notice_id=None
        self.assertEqual(image.tobytes(),ui.render_home(state,now=0).image.tobytes())

    def test_shortcut_tray_tiles_touch_from_fixed_a_position(self):
        ui=V3UI(world_runtime='missing',world_module='missing')
        state=SimpleNamespace(v3_home=HomeState(),settings_selection=0)
        state.v3_home.toggle_tray(now=0);state.v3_home.tick(now=1)
        regions=ui.render_home(state,now=1).regions[3:]
        self.assertEqual([r.rect.tuple() for r in regions],
                         [(12,370,100,470),(100,370,188,470),
                          (188,370,276,470),(276,370,364,470)])

    def test_settings_updates_opens_real_updates_panel(self):
        os.environ['GUIDE_OPERATIONS']='1'
        from guide_shell import ShellState
        state=ShellState()
        self.addCleanup(state.text_entries.teardown)
        self.addCleanup(state.operations.close)
        self.assertTrue(state.open_v3_setting('updates'))
        self.assertEqual(state.page,'updates')
        self.assertEqual(state.operations.current,'updates')

    def test_pending_update_does_not_consume_home_a(self):
        from unittest.mock import patch
        import guide_shell
        with patch.object(guide_shell, 'OPERATIONS_ENABLED', True):
            state=guide_shell.ShellState()
        self.addCleanup(state.text_entries.teardown);self.addCleanup(state.operations.close)
        state.update_notice_id='candidate';state.page='home'
        state.menu_input.key(305)
        self.assertEqual(state.update_notice_id,'candidate')
        self.assertIsNone(state.update_notice_dismissed)


if __name__ == '__main__':unittest.main()
