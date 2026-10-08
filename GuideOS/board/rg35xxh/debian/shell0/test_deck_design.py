"""Layout/control invariants for the approved Deck design consolidation."""
import time
import unittest
from types import SimpleNamespace
from guide_v3_ui import V3UI, HomeState
from guide_ui_model import ScreenModel, MenuItem, Fact, ActionHint
from guide_gpu_framebuffer import compose
from guide_deck_text import clusters

class DeckDesignTests(unittest.TestCase):
    def setUp(self):self.ui=V3UI()
    def test_home_software_and_layered_targets_match(self):
        state=SimpleNamespace(v3_home=HomeState())
        software=self.ui.render_home(state,now=0)
        layered=self.ui.render_home(state,now=0,layered=True)
        self.assertEqual(software.regions,layered.regions)
        self.assertEqual(compose(layered.image,layered.layers).size,(640,480))
        self.assertEqual(len([r for r in software.regions if r.action=='v3-shortcut']),4)
    def test_globe_changes_without_unbounded_frame_cache(self):
        home=HomeState();home.tick(0);first=self.ui._planet(home.planet_frame).tobytes()
        home.tick(22.5);second=self.ui._planet(home.planet_frame).tobytes()
        self.assertNotEqual(first,second)
        self.assertEqual(self.ui._planet_sheet.size,(720,864))
    def test_variable_names_use_full_width_and_follow_focus(self):
        items=tuple(MenuItem(str(i),'Interview with a remarkably long name — Part %02d.flac'%i,'open',i) for i in range(13))
        model=ScreenModel('standard-menu','Music',items=items,focus_id='12')
        layout=self.ui.render(model)
        target=next(r for r in layout.regions if r.identity=='12')
        self.assertGreater(target.rect.right-target.rect.left,590)
        self.assertEqual(target.value,12)
        self.assertEqual(target.label,items[12].label)
    def test_player_transport_targets_preserved(self):
        items=(MenuItem('previous','Previous','key',1),MenuItem('play','Play','key',2),MenuItem('next','Next','key',3))
        model=ScreenModel('audio-player','Music Player',items=items,focus_id='play',facts=(Fact('Title','Long music title '*40),),actions=(ActionHint('B','Back','secondary','back','key',304),))
        layout=self.ui.render(model)
        self.assertEqual({r.identity for r in layout.regions},{'back','previous','play','next'})
        self.assertTrue(self.ui.text.scrolling)
    def test_filename_extension_and_grapheme_clusters(self):
        name='a very long recording title '*10+'.flac'
        value=self.ui.text.shorten(name,24,350,True)
        self.assertTrue(value.endswith('.flac'));self.assertLessEqual(self.ui.text.width(value,24),350)
        self.assertEqual(clusters('e\u0301👩\u200d🚀'),['e\u0301','👩\u200d🚀'])
    def test_shortcut_activation_uses_existing_destination_route(self):
        from guide_menu_input import MenuInput, Target
        opened=[]
        adapter=MenuInput.__new__(MenuInput)
        adapter.state=SimpleNamespace(operations=None,page='home',v3_home=HomeState(),open_v3_destination=lambda name:opened.append(name) or True)
        adapter.sync_focus=lambda:None
        adapter.targets=lambda:[Target('slot','Shortcut',(0,0,1,1),'v3-shortcut',2)]
        self.assertTrue(adapter.activate('slot'))
        self.assertEqual(opened,['browser'])

if __name__=='__main__':unittest.main()
