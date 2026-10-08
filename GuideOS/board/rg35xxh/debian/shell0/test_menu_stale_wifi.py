"""Current rendered targets must survive provider changes without retargeting."""
import unittest
from unittest.mock import patch
from pathlib import Path
from PIL import Image
import guide_shell as shell

class Sink:
    supports_layers=False
    def show(self,image,dirty=None):self.image=image.copy()

class StaleWifiTests(unittest.TestCase):
    def state(self):
        with patch.multiple(shell,WIFI_CONTROL_ENABLED=True,AUDIO_ENABLED=False,
                            STORAGE_ENABLED=False,OPERATIONS_ENABLED=False):
            state=shell.ShellState()
        self.addCleanup(state.text_entries.teardown)
        self.addCleanup(state.nodes_panel.worker.shutdown,wait=True)
        self.addCleanup(state.wifi_panel._address_worker.shutdown,wait=True)
        state.open_v3_setting('connections')
        state.wifi_panel.status['networks']=[dict(id='a'*24,ssid='Example',security='WPA2',
            saved=True,available=True,active=False,supported=True,signal=80)]
        state.wifi_panel.target='a'*24
        return state

    def capture(self,state):
        original=Image.open
        def open_image(path,*args,**kwargs):
            if isinstance(path,Path) and path.name=='opening-video.png':
                path=Path(__file__).resolve().parents[1]/'assets/opening-video.png'
            return original(path,*args,**kwargs)
        with patch('PIL.Image.open',side_effect=open_image):screen=shell.Screen(Sink())
        screen.draw(state)
        regions=screen._schema_targets(state)
        state.schema_target_provider=lambda:regions
        return state.menu_input.targets()

    def test_removed_row_in_presented_frame_is_rejected_without_connecting_another(self):
        state=self.state();targets=self.capture(state)
        target=next(t for t in targets if t.action=='wifi-row' and t.value=='a'*24)
        state.wifi_panel.status['networks']=[];before=state.revision
        with patch.object(state.wifi_panel,'send') as send:
            self.assertFalse(state.menu_input.activate(target.identity));send.assert_not_called()
        self.assertGreater(state.revision,before)
        self.assertEqual(state.wifi_panel.view,'list')

    def test_presented_connect_target_cannot_become_disconnect(self):
        state=self.state();state.wifi_panel.view='detail';targets=self.capture(state)
        target=next(t for t in targets if t.action=='wifi-detail' and t.value==0)
        state.wifi_panel.status['networks'][0]['active']=True
        with patch.object(state.wifi_panel,'send') as send:
            self.assertFalse(state.menu_input.activate(target.identity));send.assert_not_called()
        self.assertEqual(state.wifi_panel.view,'detail')
