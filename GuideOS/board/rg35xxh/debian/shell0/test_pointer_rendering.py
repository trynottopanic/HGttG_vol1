import unittest
from PIL import Image, ImageDraw
from guide_platform_rg35xxh import Framebuffer
from guide_status_bar import StatusBar

class TrackedMemory(bytearray):
    def __setitem__(self,key,value):
        self.written += len(value)
        super().__setitem__(key,value)

class PointerRenderingTests(unittest.TestCase):
    def test_cursor_move_restores_old_pixels_and_writes_only_changed_rectangle(self):
        for bpp,fields in [(32,[(16,8,0),(8,8,0),(0,8,0)]),(16,[(11,5,0),(5,6,0),(0,5,0)])]:
            with self.subTest(bpp=bpp):
                fb=Framebuffer.__new__(Framebuffer);fb.closed=False
                fb.width=64;fb.height=48;fb.xoff=2;fb.yoff=1;fb.bpp=bpp;fb.fields=fields
                fb.stride=70*(bpp//8);fb.mem=TrackedMemory(fb.stride*50);fb.mem.written=0
                base=Image.new('RGB',(64,48),'black')
                old=base.copy();ImageDraw.Draw(old).rectangle((10,10,14,14),fill='white')
                fb.show(old);fb.mem.written=0
                new=base.copy();ImageDraw.Draw(new).rectangle((20,10,24,14),fill='white')
                fb.show(new)
                self.assertLess(fb.mem.written,64*48*(bpp//8)//10)
                for x,bright in [(10,False),(20,True)]:
                    start=(fb.yoff+10)*fb.stride+(fb.xoff+x)*(bpp//8)
                    self.assertEqual(any(fb.mem[start:start+bpp//8]),bright)
                fb.mem.written=0;fb.show(new);self.assertEqual(fb.mem.written,0)
                self.assertFalse(any(fb.mem[:fb.stride]))

    def test_explicit_cursor_damage_skips_full_frame_difference(self):
        fb=Framebuffer.__new__(Framebuffer);fb.closed=False
        fb.width=64;fb.height=48;fb.xoff=0;fb.yoff=0;fb.bpp=32
        fb.fields=[(16,8,0),(8,8,0),(0,8,0)];fb.stride=64*4
        fb.mem=TrackedMemory(fb.stride*48);fb.mem.written=0
        base=Image.new('RGB',(64,48),'black');fb.show(base)
        moved=base.copy();ImageDraw.Draw(moved).ellipse((20,20,30,30),fill='white')
        fb.mem.written=0;fb.show(moved,dirty=[(18,18,33,33)])
        self.assertEqual(fb.last_metrics['explicit'],1)
        self.assertEqual(fb.last_metrics['boxes'],1)
        self.assertEqual(fb.last_metrics['dirty_pixels'],225)
        self.assertEqual(fb.mem.written,15*15*4)

    def test_wifi_three_shapes_have_no_text_or_companion_marks(self):
        class Draw:
            def __init__(self):self.rects=[]
            def rectangle(self,rect,**kwargs):self.rects.append((rect,kwargs))
        bar=StatusBar('/nonexistent','/nonexistent')
        shapes=[]
        for link,radio,expected in [('unavailable','WiFi OFF','unavailable'),('offline','WiFi ON','disconnected'),('online','WiFi ON','connected')]:
            bar.wifi_link=link;bar.wifi=radio
            self.assertEqual(bar.wifi_icon_state,expected)
            draw=Draw();bar.draw_wifi(draw);self.assertEqual(len(draw.rects),4);shapes.append(draw.rects)
        self.assertNotEqual(shapes[0],shapes[1]);self.assertNotEqual(shapes[1],shapes[2])
        bar.wifi_link='unknown';self.assertEqual(bar.wifi_icon_state,'disconnected')

if __name__=='__main__':unittest.main()
