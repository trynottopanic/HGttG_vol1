"""Bounded display work; provider tests do not establish physical GPU speed."""
import gc,time,unittest,weakref
from unittest.mock import patch
from collections import OrderedDict
from dataclasses import replace
from PIL import Image,ImageDraw
from guide_v3_ui import V3UI
from guide_ui_model import Fact
from guide_gpu_framebuffer import GpuFramebuffer,Layer,compose
from test_deck_layouts import fixtures

class DisplayWorkTests(unittest.TestCase):
    def test_warm_scroll_reuses_glyphs_and_title_layout(self):
        ui=V3UI();model=replace(fixtures()[4],facts=(Fact('Name','Long name '*60+'.flac'),Fact('Folder','/Folder/'*40)))
        with patch('guide_deck_text.time.monotonic',return_value=0):ui.render(model)
        with patch.object(ui.text.provider,'measure',wraps=ui.text.provider.measure) as measure,patch.object(ui.text.provider,'render',wraps=ui.text.provider.render) as render:
            for step in range(1,11):
                with patch('guide_deck_text.time.monotonic',return_value=step/10):ui.render(model)
        self.assertEqual(measure.call_count,0);self.assertEqual(render.call_count,0)
        self.assertLessEqual(ui.text.rasters.bytes,4*1024**2)

    def test_cache_eviction_is_bounded_and_style_is_part_of_identity(self):
        ui=V3UI()
        for i in range(160):ui.text.draw(Image.new('RGB',(640,480)),(0,0,600,60),'Distinct glyphs '+str(i),24,'#edf5fb')
        self.assertLessEqual(len(ui.text.rasters.values),128);self.assertLessEqual(ui.text.rasters.bytes,4*1024**2)
        a=Image.new('RGB',(640,480));b=a.copy()
        ui.text.draw(a,(0,0,600,60),'GuideOS',24,'#edf5fb')
        ui.text.draw(b,(0,0,600,60),'GuideOS',24,'#112233',bold=True)
        self.assertNotEqual(a.tobytes(),b.tobytes())

    def test_mutable_texture_has_one_slot_and_only_dirty_pixels_upload(self):
        class Native:
            def __init__(self):self.uploads=[];self.updates=[]
            def guide_gpu_upload(self,*args):self.uploads.append(args);return 0
            def guide_gpu_update(self,*args):self.updates.append(args);return 0
            def guide_gpu_drop(self,*args):return 0
        gpu=GpuFramebuffer.__new__(GpuFramebuffer);gpu.cache=OrderedDict();gpu.lib=Native();gpu.context=1
        base=Image.new('RGB',(640,480));old=weakref.ref(base)
        gpu._texture(base,set(),'base');del base
        for i in range(60):
            frame=Image.new('RGB',(640,480));ImageDraw.Draw(frame).rectangle((20,30,24,34),fill=(i+1,0,0))
            gpu._texture(frame,set(),'base')
        gc.collect();self.assertIsNone(old())
        self.assertEqual(len(gpu.cache),1);self.assertEqual(len(gpu.lib.uploads),1)
        self.assertEqual(sum(args[-1] for args in gpu.lib.updates),60*5*5*4)
        self.assertTrue(all(args[2:6]==(20,30,5,5) for args in gpu.lib.updates))
        self.assertEqual(gpu._texture(frame,set(),'base')[1],0)

    def test_native_size_planet_preserves_software_pixels(self):
        base=Image.new('RGB',(640,480),'#112233');tile=Image.new('RGBA',(144,144))
        ImageDraw.Draw(tile).ellipse((6,6,138,138),fill='#3db89c')
        expected=base.copy();scaled=tile.resize((288,288),Image.Resampling.NEAREST);expected.paste(scaled,(48,56),scaled)
        self.assertEqual(compose(base,[Layer(tile,48,56,size=(288,288))]).tobytes(),expected.tobytes())

if __name__=='__main__':unittest.main()
