from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from guide_status_bar import StatusBar


class StatusTests(unittest.TestCase):
    def test_pending_update_icon_is_left_of_wifi_and_clears(self):
        from PIL import Image
        bar=StatusBar();bar.labels=()
        base=Image.new('RGB',(640,480));bar.draw(base)
        bar.pending_update=True
        active=Image.new('RGB',(640,480));bar.draw(active)
        self.assertNotEqual(active.getpixel((325,10)),base.getpixel((325,10)))
        self.assertEqual(active.crop((340,0,380,28)).tobytes(),base.crop((340,0,380,28)).tobytes())
        self.assertEqual(active.crop((0,28,640,480)).tobytes(),base.crop((0,28,640,480)).tobytes())
        bar.pending_update=False
        cleared=Image.new('RGB',(640,480));bar.draw(cleared)
        self.assertEqual(cleared.tobytes(),base.tobytes())

    def test_tone_changes_redraw_without_clock_change_and_expire(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);now=[10]
            bar=StatusBar(root,root,clock=lambda:datetime(2026,9,25,13,7),monotonic=lambda:now[0])
            bar.poll()
            path=root/'guideos-tone-status.json'
            for i,phase in enumerate(('countdown','playing','finished')):
                now[0]=11+i
                path.write_text(json.dumps(dict(tone='internal-sine',phase=phase,seconds=3,expires=20)))
                self.assertTrue(bar.poll());self.assertEqual(bar.tone['phase'],phase)
            now[0]=21;self.assertTrue(bar.poll());self.assertIsNone(bar.tone)
            path.write_text('x'*3000);now[0]=22;bar.poll();self.assertIsNone(bar.tone)
    def test_live_values_and_sync_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            battery=root/'sys/class/power_supply/battery'
            radio=root/'sys/class/rfkill/rfkill0'
            audio=root/'run/guideos-audio'
            for p in (battery,radio,audio):p.mkdir(parents=True)
            for name,value in {'type':'Battery','capacity':'78','status':'Charging'}.items():(battery/name).write_text(value)
            for name,value in {'type':'wlan','soft':'0','hard':'0'}.items():(radio/name).write_text(value)
            (audio/'status.json').write_text(json.dumps(dict(observed=10,devices=[dict(connected=True)],volume=65)))
            now=[10]
            bar=StatusBar(root/'sys',root/'run',clock=lambda:datetime(2026,9,25,13,7),monotonic=lambda:now[0])
            self.assertTrue(bar.poll())
            self.assertEqual(bar.labels,('BAT 78%+','13:07*','09/25/26','WiFi ON','','VOL 65%'))
            self.assertTrue(bar.bluetooth_connected)
            sync=root/'run/systemd/timesync/synchronized'
            sync.parent.mkdir(parents=True);sync.touch()
            (radio/'soft').write_text('1');now[0]=15
            self.assertTrue(bar.poll())
            self.assertEqual(bar.labels[1],'13:07')
            self.assertEqual(bar.labels[3],'WiFi OFF')
            now[0]=30;bar.poll()
            self.assertEqual(bar.labels[-2:],('','VOL --'))
            self.assertFalse(bar.bluetooth_connected)

    def test_missing_values_and_bounded_refresh(self):
        with tempfile.TemporaryDirectory() as folder:
            now=[10]
            bar=StatusBar(folder,folder,monotonic=lambda:now[0])
            bar.poll()
            self.assertEqual(bar.labels[0],'BAT --')
            self.assertEqual(bar.labels[3],'WiFi N/A')
            previous=bar.labels
            now[0]=10.2
            self.assertFalse(bar.poll())
            self.assertEqual(bar.labels,previous)


class VolumeOverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.audio = self.root/'guideos-audio/status.json'; self.audio.parent.mkdir()
        self.now = [10.0]
        self.bar = StatusBar(self.root,self.root,clock=lambda:datetime(2026,9,25,13,7),monotonic=lambda:self.now[0])
    def volume(self,value):
        self.audio.write_text(json.dumps(dict(observed=self.now[0],devices=[],volume=value)))
        self.bar.poll()
    def test_startup_and_unchanged_level_do_not_show(self):
        self.volume(20); self.assertEqual(self.bar.volume_alpha(),0)
        self.now[0]+=.2; self.volume(20); self.assertEqual(self.bar.volume_alpha(),0)
    def test_confirmed_changes_restart_then_fade_and_clear(self):
        self.volume(20); self.now[0]+=.2; self.volume(25)
        self.assertEqual(self.bar.volume_alpha(),1)
        self.now[0]+=.8; self.assertAlmostEqual(self.bar.volume_alpha(),2/3)
        self.volume(30); self.assertEqual(self.bar.volume_alpha(),1)
        self.now[0]+=1.2; self.assertTrue(self.bar.poll())
        self.assertEqual(self.bar.volume_alpha(),0)
        self.now[0]+=.2; self.assertFalse(self.bar.poll())
    def test_expiry_redraw_does_not_wait_for_status_poll(self):
        self.volume(20); self.now[0]+=.2; self.volume(25)
        self.bar.next_poll = 100
        self.now[0]+=1.095; self.assertTrue(self.bar.poll())
        self.assertGreater(self.bar.volume_frame,0)
        self.now[0]+=.01; self.assertTrue(self.bar.poll())
        self.assertEqual(self.bar.volume_frame,0)
    def test_stale_provider_clears_and_reconnection_is_silent(self):
        self.volume(20); self.now[0]+=.2; self.volume(25)
        self.now[0]+=13; self.bar.poll()
        self.assertIsNone(self.bar.volume)
        self.now[0]+=.2; self.volume(30)
        self.assertEqual(self.bar.volume_alpha(),0)
    def test_transparent_composite_is_local_and_disappears(self):
        from PIL import Image
        self.volume(20); self.now[0]+=.2; self.volume(25)
        original=Image.new('RGB',(640,480),(200,200,200)); visible=original.copy()
        self.bar.draw_volume(visible)
        self.assertNotEqual(visible.getpixel((15,200)),original.getpixel((15,200)))
        self.assertTrue(15 < visible.getpixel((15,200))[0] < 200)
        self.assertEqual(visible.getpixel((100,200)),original.getpixel((100,200)))
        self.now[0]+=1.2; finished=original.copy();self.bar.draw_volume(finished)
        self.assertEqual(finished.tobytes(),original.tobytes())
    def test_zero_and_maximum_render(self):
        from PIL import Image
        self.volume(50)
        for value in (0,100):
            self.now[0]+=.2; self.volume(value)
            image=Image.new('RGB',(640,480),(200,200,200));self.bar.draw_volume(image)
            self.assertEqual(self.bar.volume,value)
            self.assertEqual(self.bar.volume_alpha(),1)


class WiFiIndicatorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.path=self.root/'guideos-wifi/status.json';self.path.parent.mkdir()
        self.now=[10.0];self.bar=StatusBar(self.root,self.root,monotonic=lambda:self.now[0])
    def status(self,**values):
        state=dict(observed=self.now[0],state='ready',connected='ours',networks=[dict(id='ours',active=True,signal=37),dict(id='nearby',active=False,signal=100)])
        state.update(values);self.path.write_text(json.dumps(state));self.bar.next_wifi=0
        return self.bar.poll_wifi(self.now[0])
    def test_strength_comes_from_connected_network(self):
        self.assertTrue(self.status());self.assertEqual((self.bar.wifi_link,self.bar.wifi_strength),('online',37))
        self.assertFalse(self.status())
    def test_disconnected_and_blocked_do_not_show_nearby_strength(self):
        for values in (dict(connected=None),dict(state='blocked'),dict(state='off')):
            self.status(**values);self.assertEqual((self.bar.wifi_link,self.bar.wifi_strength),('offline' if 'connected' in values else 'unavailable',None))
    def test_missing_stale_and_failed_provider_are_unknown(self):
        self.bar.poll_wifi(self.now[0]);self.assertEqual(self.bar.wifi_link,'unknown')
        self.status();self.now[0]+=16;self.bar.poll_wifi(self.now[0]);self.assertEqual(self.bar.wifi_link,'unknown')
        self.status(result='unavailable');self.assertEqual(self.bar.wifi_link,'unknown')
    def test_connection_without_signal_is_not_disconnection(self):
        self.status(connected='external');self.assertEqual((self.bar.wifi_link,self.bar.wifi_strength),('online',None))
    def test_malformed_status_is_bounded(self):
        for raw in ('x'*65537,'null','{}'):
            self.path.write_text(raw);self.bar.next_wifi=0;self.bar.poll_wifi(self.now[0]);self.assertEqual(self.bar.wifi_link,'unknown')
