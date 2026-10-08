"""Exercise physical button routing against actual Field render geometry."""
from pathlib import Path
import unittest
from unittest.mock import patch
import guide_shell as shell
from guide_menu_input import UP, DOWN, LEFT, RIGHT, A, B
from guide_field_ui import FieldUI, field_model

class SpatialNavigationTests(unittest.TestCase):
    def setUp(self):
        pages=('media','status','wifi','storage','power','applications')
        self.patches=[patch.object(shell,'PAGES',pages),patch.object(shell,'CHOICES',pages),
                      patch.object(shell,'AUDIO_ENABLED',False),patch.object(shell,'WIFI_CONTROL_ENABLED',False)]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        self.state=shell.ShellState()
        self.ui=FieldUI(Path(__file__).resolve().parents[4]/'package/guide-ui')
        self.state.schema_target_provider=lambda:self.ui.render(field_model(self.state)).regions
        self.state.menu_input.sync_focus()

    def test_horizontal_transition_and_selection_guard(self):
        from PIL import Image
        s=self.state;s.pages=tuple('option'+str(i) for i in range(12));s.choices=s.pages
        screen=shell.Screen.__new__(shell.Screen);screen.schema=self.ui
        s.schema_target_provider=lambda:screen._field_layout(s).regions
        screen._field_layout(s)
        s.key(313,1);self.assertEqual(s.home_slide[1],1)
        self.assertEqual(screen._field_layout(s).regions,())
        self.assertFalse(s.key(A,1));self.assertEqual(s.page,'home')
        s.tick_home_slide(s.home_slide[2]+.21);self.assertIsNone(s.home_slide)
        self.assertEqual(s.menu_input.hovered().identity,'home:option10')
        old=Image.new('RGB',(640,480),'red');new=Image.new('RGB',(640,480),'blue')
        for direction in (-1,1):
            mid=self.ui.slide_home(old,new,.5,direction)
            self.assertEqual(mid.getpixel((20,20)),(0,0,255))
            self.assertEqual(mid.getpixel((100,260)),(255,0,0) if direction==1 else (0,0,255))
            self.assertEqual(mid.getpixel((540,260)),(0,0,255) if direction==1 else (255,0,0))
            end=self.ui.slide_home(old,new,1,direction)
            self.assertEqual(end.tobytes(),new.tobytes())

    def test_triggers_leave_single_page_unchanged(self):
        for code in (312,313):self.assertFalse(self.state.key(code,1))
        self.assertEqual(self.state.selection,0)
        self.assertFalse(field_model(self.state).notice)

    def test_trigger_pages_keep_slot_and_clamp_partial_last_page(self):
        s=self.state;s.pages=tuple('option'+str(i) for i in range(23));s.choices=s.pages
        s.selection=4;s.menu_input.sync_focus()
        self.assertTrue(s.key(313,1));self.assertEqual(s.selection,14)
        model=field_model(s);self.assertEqual(model.notice,'Page 2 / 3')
        self.assertEqual([i.value for i in model.items],list(range(10,20)))
        self.assertEqual(s.menu_input.hovered().identity,'home:option14')
        self.assertFalse(s.key(313,2));self.assertFalse(s.key(313,0))
        s.key(313,1);self.assertEqual(s.selection,22)
        self.assertEqual(len(field_model(s).items),3)
        self.assertFalse(s.key(313,1));s.key(312,1);self.assertEqual(s.selection,12)
        s.key(312,1);self.assertEqual(s.selection,2);self.assertFalse(s.key(312,1))

    def test_paged_grid_dpad_and_activation_use_global_option_identity(self):
        s=self.state;s.pages=tuple('option'+str(i) for i in range(21));s.choices=s.pages
        s.key(313,1);s.key(RIGHT,1);self.assertEqual(s.selection,11)
        s.key(A,1);self.assertEqual(s.page,'option11')

    def test_grid_moves_in_all_four_directions(self):
        s=self.state
        for key,expected in [(RIGHT,1),(LEFT,0),(DOWN,5),(UP,0)]:
            self.assertTrue(s.key(key,1));self.assertEqual(s.selection,expected)
            self.assertEqual(s.menu_input.hovered().identity,'home:'+s.pages[expected])

    def test_edges_and_empty_cells_do_not_wrap(self):
        s=self.state
        for key in (UP,LEFT):self.assertFalse(s.key(key,1));self.assertEqual(s.selection,0)
        s.key(RIGHT,1);self.assertFalse(s.key(DOWN,1));self.assertEqual(s.selection,1)
        s.selection=5;s.menu_input.sync_focus()
        self.assertFalse(s.key(RIGHT,1));self.assertEqual(s.selection,5)

    def test_power_cancel_is_visible_and_does_not_shutdown(self):
        s=self.state;s.selection=4;s.key(A,1)
        self.assertEqual(s.page,'power');self.assertFalse(s.shutdown_requested)
        self.assertTrue(s.key(DOWN,1));self.assertEqual(field_model(s).focus_id,'power:cancel')
        self.assertEqual(s.menu_input.hovered().identity,'power:cancel')
        s.key(A,1);self.assertEqual(s.page,'home');self.assertFalse(s.shutdown_requested)
        s.key(A,1);self.assertEqual(field_model(s).focus_id,'power:confirm')
        s.key(DOWN,1);s.key(UP,1);s.key(A,1);self.assertTrue(s.shutdown_requested)

    def test_pointer_cancel_and_back_still_work(self):
        s=self.state;s.selection=4;s.key(A,1)
        target=next(t for t in s.menu_input.targets() if t.identity=='power:cancel')
        s.menu_input.pointer.move_to((target.rect[0]+target.rect[2])/2,(target.rect[1]+target.rect[3])/2)
        s.key(A,1);self.assertEqual(s.page,'home');self.assertFalse(s.shutdown_requested)
        s.key(A,1);s.key(B,1);self.assertEqual(s.page,'home')

if __name__=='__main__':unittest.main()
