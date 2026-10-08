import json
from pathlib import Path
import tempfile
import time
import unittest
from guide_storage_panel import StoragePanel

class StoragePanelTests(unittest.TestCase):
    def test_missing_stale_and_oversize_snapshots(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'status'; panel=StoragePanel(path)
            panel.poll();self.assertEqual(panel.status['state'],'unavailable')
            for value in (json.dumps(dict(updated=-100,message='Old card',folders=[])), 'x'*4097):
                path.write_text(value);panel.next_poll=0;panel.poll()
                self.assertEqual(panel.status['state'],'unavailable')
    def test_ready_does_not_claim_package_verification(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'status';path.write_text(json.dumps(dict(updated=time.monotonic(),state='guide',message='Guide layout recognized',folders=['CARTRIDGES'],filesystem='exfat',packages=2)))
            panel=StoragePanel(path);self.assertTrue(panel.poll())
            self.assertIn(('Cartridges','2 files; unverified'),panel.rows())
            panel.next_poll=0;self.assertFalse(panel.poll())
    def test_full_layout_fits_above_footer(self):
        panel=StoragePanel();panel.status=dict(state='guide',message='Guide layout recognized',filesystem='exfat',folders=['CARTRIDGES','APPLICATIONS','MEDIA','DOCUMENTS','GENERAL','MISC'],packages=1)
        class Screen:
            def __init__(self):self.points=[]
            def _text(self,draw,xy,text,*args):self.points.append((xy,text))
        screen=Screen();panel.draw(screen,None)
        self.assertTrue(all(xy[1]<405 for xy,text in screen.points if not text.startswith('B:')))

if __name__=='__main__':unittest.main()
