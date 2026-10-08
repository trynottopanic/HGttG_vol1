import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from guide_nearby_panel import NearbyPanel, UP,DOWN,A,B,MENU
from guide_v3_ui import V3UI, SETTINGS
import guide_shell

AP=dict(id='wifi:00:11:22:33:44:55',kind='wifi',name='Test network',address='00:11:22:33:44:55',
        signal=75,seen=0,unit='%',channel=6,frequency=2437,security='WPA2')


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.panel=NearbyPanel(); self.sent=[]
        self.panel.send=lambda action,**values:self.sent.append(dict(action=action,**values)) or True

    def test_scan_selection_inspects_without_connecting_or_probing(self):
        p=self.panel; p.key(A); self.assertEqual(p.view,'wifi')
        self.assertEqual(self.sent,[dict(action='survey',kind='wifi')])
        p.status['rows']=[dict(AP,seen=time.monotonic())]
        p.key(DOWN); p.key(A); self.assertEqual(p.view,'detail')
        self.assertEqual(len(self.sent),1)
        p.key(A); self.assertEqual(p.view,'watch'); self.assertEqual(self.sent[-1]['action'],'watch')
        p.key(B); self.assertEqual(p.view,'detail'); self.assertEqual(self.sent[-1]['action'],'cancel')
        p.key(B); self.assertEqual(p.view,'wifi')
        p.key(MENU); self.assertEqual(self.sent[-1]['action'],'cancel'); self.assertFalse(p.active)

    def test_tools_require_explicit_run_after_target_and_profile(self):
        p=self.panel; p.activate('tools'); p.address='127.0.0.1'; p.activate('services')
        self.assertEqual(p.view,'ready'); self.assertEqual(self.sent,[])
        p.key(A); self.assertEqual(self.sent[-1],dict(action='tool',profile='services',target='127.0.0.1'))
        p.key(B); self.assertEqual(p.view,'tools'); self.assertEqual(self.sent[-1]['action'],'cancel')

    def test_old_observations_and_unknown_rssi_are_visible(self):
        p=self.panel; p.view='detail'; p.target=AP['id']; p.status['rows']=[dict(AP,seen=None)]
        self.assertIn('Unknown',' '.join(p.details(p.selected())))
        self.assertIn('No fresh sighting',' '.join(p.details(p.selected())))

    def test_signal_graph_and_result_regions_match_visible_controls(self):
        p=self.panel; p.view='watch'; p.target=AP['id']; p.status['rows']=[dict(AP,seen=time.monotonic())]
        p.status['history']=[dict(at=time.monotonic()-10,value=50,unit='%'),dict(at=time.monotonic(),value=75,unit='%')]
        layout=p.layout(V3UI())
        self.assertEqual(layout.image.size,(640,480))
        self.assertEqual(layout.regions[0].value,p.rows()[0][0])
        p.view='result'; p.status['result']={'lines':['80/tcp open http']}
        self.assertEqual(p.layout(V3UI()).regions[0].action,'nearby-row')

    def test_status_staleness_does_not_look_like_a_live_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.panel; p.runtime=Path(tmp); p.open()
            (p.runtime/'status.json').write_text(json.dumps(dict(observed=time.monotonic()-4,rows=[AP],history=[],busy=True)))
            self.assertTrue(p.poll()); self.assertFalse(p.status['busy']); self.assertEqual(p.status['rows'],[])

    def test_target_editor_cancels_without_running_a_tool(self):
        p=self.panel; p.activate('tools'); p.activate('target')
        self.assertIsNotNone(p.editor); p.key(B); self.assertIsNone(p.editor)
        self.assertEqual(p.address,''); self.assertEqual(self.sent,[])


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.state=guide_shell.ShellState(); self.sent=[]
        self.state.nearby_panel.send=lambda action,**values:self.sent.append(dict(action=action,**values)) or True
        self.ui=V3UI()
        self.state.schema_target_provider=lambda:self.state.nearby_panel.layout(self.ui).regions if self.state.page=='nearby' else ()
        self.state.page='settings'; self.state.open_v3_setting('nearby')

    def test_dpad_and_pointer_use_same_nearby_focus(self):
        s=self.state; self.assertEqual(s.page,'nearby'); self.assertTrue(s.nearby_panel.active)
        s.key(DOWN,1); self.assertEqual(s.nearby_panel.cursor,1)
        s.key(A,1); self.assertEqual(s.nearby_panel.view,'bluetooth')
        self.assertEqual(self.sent[-1],dict(action='survey',kind='bluetooth'))
        s.key(B,1); self.assertEqual(s.page,'nearby'); self.assertEqual(s.nearby_panel.view,'menu')
        s.key(B,1); self.assertEqual(s.page,'settings'); self.assertFalse(s.nearby_panel.active)

    def test_global_home_and_navigation_cancel_provider(self):
        s=self.state; s.nearby_panel.activate('wifi'); s.go_home()
        self.assertEqual(s.page,'home'); self.assertEqual(self.sent[-1]['action'],'cancel')
        self.assertFalse(s.nearby_panel.active)

    def test_current_settings_exposes_nearby_with_visible_hit_region(self):
        s=self.state; s.page='settings'
        model=self.ui.settings_model(s); layout=self.ui.render(model)
        target=next(r for r in layout.regions if r.value=='nearby')
        self.assertEqual(target.action,'v3-setting')
        self.assertLessEqual(target.rect.bottom,480)


if __name__=='__main__': unittest.main()
