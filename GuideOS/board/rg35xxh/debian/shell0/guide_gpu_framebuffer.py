"""Optional hardware compositor behind the board's existing display contract.
All calls stay on the shell thread. Assets are immutable; named viewports replace
their current CPU image and update the same texture slot. At most
32 textures and 16 MiB live in the native adapter. No helper owns another lease.
"""
from collections import OrderedDict
import ctypes as C
from dataclasses import dataclass
import math
import os
import threading
import time
from PIL import Image, ImageChops
from guide_telemetry import emit

@dataclass(frozen=True)
class Layer:
    image: Image.Image
    x: float = 0
    y: float = 0
    angle: float = 0
    pivot: tuple = (0, 0)
    opacity: float = 1
    size: tuple = None
    cache_key: str = None
    quads: tuple = ()
    clip: tuple = (0, 0, 640, 480)
    planet: tuple = ()
    fallback: object = None

def compose(base, layers):
    """Bounded software recovery, also usable by non-GPU preview surfaces."""
    image = base.convert('RGBA')
    for layer in layers:
        if layer.quads:
            canvas=Image.new('RGBA',image.size)
            for x,y,w,h,u0,v0,u1,v1 in layer.quads:
                tile=layer.image.crop((round(u0*layer.image.width),round(v0*layer.image.height),round(u1*layer.image.width),round(v1*layer.image.height))).convert('RGBA')
                if tile.size!=(round(w),round(h)):tile=tile.resize((round(w),round(h)),Image.Resampling.NEAREST)
                canvas.alpha_composite(tile,(round(x),round(y)))
            x,y,w,h=layer.clip
            image.alpha_composite(canvas.crop((x,y,x+w,y+h)),(x,y))
            continue
        tile = (layer.fallback() if layer.planet else layer.image).convert('RGBA')
        if layer.size is not None:tile=tile.resize(layer.size,Image.Resampling.NEAREST)
        if layer.opacity != 1:
            tile = tile.copy()
            tile.putalpha(tile.getchannel('A').point(lambda a: round(a*layer.opacity)))
        if layer.angle:
            # A full viewport preserves offscreen pivots and clipping exactly.
            canvas = Image.new('RGBA', image.size)
            canvas.paste(tile, (round(layer.x), round(layer.y)))
            tile = canvas.rotate(-layer.angle, center=layer.pivot,
                                 resample=Image.Resampling.NEAREST)
            image = Image.alpha_composite(image, tile)
        else:
            image.alpha_composite(tile, (round(layer.x), round(layer.y)))
    return image.convert('RGB')

class GpuFramebuffer:
    supports_layers = True
    def __init__(self):
        from guide_platform_rg35xxh import Framebuffer
        self.software = Framebuffer()
        self.thread = threading.get_ident()
        self.lib = None
        self.context = None
        self.disabled = False
        self.suspended = False
        self.cache = OrderedDict()
        self.last_metrics = {}
        self.next_metrics=0
        self.frames=self.uploads=0
        try:
            self.lib = C.CDLL('/usr/lib/guideos/ui/libguidegpu.so')
            self.lib.guide_gpu_open.argtypes = []
            self.lib.guide_gpu_open.restype = C.c_void_p
            self.lib.guide_gpu_close.argtypes = [C.c_void_p]
            self.lib.guide_gpu_upload.argtypes = [C.c_void_p,C.c_uint,C.c_uint,C.c_uint,C.c_void_p,C.c_uint]
            self.lib.guide_gpu_update.argtypes = [C.c_void_p]+[C.c_uint]*5+[C.c_void_p,C.c_uint]
            self.lib.guide_gpu_drop.argtypes = [C.c_void_p,C.c_uint]
            self.lib.guide_gpu_begin.argtypes = [C.c_void_p]
            self.lib.guide_gpu_draw.argtypes = [C.c_void_p,C.c_uint]+[C.c_float]*8
            self.lib.guide_gpu_planet.argtypes=[C.c_void_p]+[C.c_uint]*4+[C.c_float]*6
            self.lib.guide_gpu_batch.argtypes=[C.c_void_p,C.c_uint,C.c_uint,C.POINTER(C.c_float)]+[C.c_int]*4
            self.lib.guide_gpu_present.argtypes = [C.c_void_p]
        except (OSError, AttributeError) as exc:
            self.disabled = True
            emit('UI_RENDERER',backend='framebuffer',reason=str(exc)[:200])
    @property
    def old_mode(self): return self.software.old_mode
    @old_mode.setter
    def old_mode(self, value): self.software.old_mode = value
    def _owner(self):
        if threading.get_ident() != self.thread:
            raise RuntimeError('Display renderer called outside the shell thread')
    def _release(self):
        self._owner()
        if self.context:
            if self.lib.guide_gpu_close(self.context):
                emit('UI_RENDERER',backend='gles2',phase='release-failed')
                return False
            self.context = None
            self.cache.clear()
        return True
    def suspend(self,image=None):
        self._owner()
        # The saved CRTC points at fbdev, whose pixels may still be the initial
        # Home frame. Refresh that recovery image before restoring its scanout.
        if image is not None:self.software.show(image)
        if not self._release(): return False
        if not self.software.suspend():return False
        self.suspended = True
        return True
    def resume(self):
        self._owner()
        self.suspended = False
        self.software.resume()
    def invalidate(self):
        self.software.invalidate()
    def _texture(self, image, pinned, cache_key=None):
        key = ('viewport',cache_key) if cache_key is not None else ('asset',id(image))
        if key in self.cache:
            slot, saved = self.cache[key]
            if saved is image:
                self.cache.move_to_end(key)
                pinned.add(slot)
                return slot, 0
            if cache_key is not None and saved.size==image.size:
                rgba=image.convert('RGBA')
                diff=ImageChops.difference(saved.convert('RGBA'),rgba)
                channels=diff.split();mask=channels[0]
                for channel in channels[1:]:mask=ImageChops.lighter(mask,channel)
                box=mask.getbbox();uploaded=0
                if box:
                    region=rgba.crop(box);data=region.tobytes();uploaded=len(data)
                    if self.lib.guide_gpu_update(self.context,slot,box[0],box[1],region.width,region.height,data,uploaded):
                        raise RuntimeError('GPU texture region upload failed')
                self.cache[key]=(slot,image);self.cache.move_to_end(key);pinned.add(slot)
                return slot,uploaded
            if cache_key is not None:
                self.cache.pop(key)
                if self.lib.guide_gpu_drop(self.context,slot):raise RuntimeError('GPU texture release failed')
        used = {row[0] for row in self.cache.values()}
        incoming=image.width*image.height*4
        while (len(self.cache)>=32 or
               sum(row[1].width*row[1].height*4 for row in self.cache.values())+incoming>16*1024*1024):
            victim=next((k for k,row in self.cache.items() if row[0] not in pinned),None)
            if victim is None:raise RuntimeError('Display texture budget exceeded')
            old,_=self.cache.pop(victim)
            if self.lib.guide_gpu_drop(self.context,old):raise RuntimeError('GPU texture release failed')
        used = {row[0] for row in self.cache.values()}
        slot = next((i for i in range(32) if i not in used), None)
        if slot is None:
            victim = next((k for k,row in self.cache.items() if row[0] not in pinned), None)
            if victim is None: raise RuntimeError('Too many simultaneous display layers')
            slot, _ = self.cache.pop(victim)
        rgba = image.convert('RGBA').tobytes()
        if self.lib.guide_gpu_upload(self.context,slot,image.width,image.height,rgba,len(rgba)):
            raise RuntimeError('GPU texture upload failed')
        self.cache[key] = (slot,image)
        pinned.add(slot)
        return slot, len(rgba)
    def show(self, image, dirty=None):
        self.show_layers(image, ())
    def show_layers(self, base, layers):
        self._owner()
        if self.suspended: raise RuntimeError('Shell display is leased to another surface')
        layers = tuple(layers)
        if base.size != (640,480) or len(layers)>512:
            raise ValueError('Invalid display scene')
        for layer in layers:
            if (layer.image.width>1024 or layer.image.height>1024 or
                not all(math.isfinite(v) for v in (layer.x,layer.y,layer.angle,*layer.pivot,layer.opacity)) or
                not 0<=layer.opacity<=1 or layer.size is not None and
                (len(layer.size)!=2 or any(type(v)is not int or not 1<=v<=1024 for v in layer.size))): raise ValueError('Invalid display layer')
            if len(layer.quads)>512 or len(layer.clip)!=4 or any(type(v)is not int for v in layer.clip):raise ValueError('Invalid atlas batch')
            cx,cy,cw,ch=layer.clip
            if cx<0 or cy<0 or cw<1 or ch<1 or cx+cw>640 or cy+ch>480:raise ValueError('Invalid layer clip')
            for q in layer.quads:
                if len(q)!=8 or not all(math.isfinite(v) for v in q) or q[2]<=0 or q[3]<=0 or not 0<=q[4]<q[6]<=1 or not 0<=q[5]<q[7]<=1:raise ValueError('Invalid atlas quad')
            if layer.planet and (len(layer.planet)!=5 or not callable(layer.fallback)):raise ValueError('Invalid planet layer')
        started = time.monotonic()
        if not self.disabled and not self.context:
            # Keep a current recovery frame in the saved fbdev scanout.
            self.software.show(compose(base,layers))
            self.context = self.lib.guide_gpu_open()
            if not self.context:
                self.disabled = True
                emit('UI_RENDERER',backend='framebuffer',reason='Hardware compositor unavailable')
        if self.context:
            try:
                scene=(Layer(base,cache_key='base'),)+layers
                keys=[layer.cache_key for layer in scene if layer.cache_key is not None]
                if len(keys)!=len(set(keys)):raise RuntimeError('Duplicate mutable display layer')
                pinned=set();uploaded=0
                # Upload before drawing. Pinned slots cannot be evicted mid-scene.
                prepared=[]
                for layer in scene:
                    slot,size=self._texture(layer.image,pinned,layer.cache_key);uploaded+=size
                    extra=[]
                    if layer.planet:
                        for im in layer.planet[:3]:
                            other,n=self._texture(im,pinned);uploaded+=n;extra.append(other)
                    prepared.append((slot,layer,extra))
                if self.lib.guide_gpu_begin(self.context): raise RuntimeError('GPU frame begin failed')
                for slot,layer,extra in prepared:
                    if layer.planet:
                        if self.lib.guide_gpu_planet(self.context,slot,*extra,layer.x,layer.y,*(layer.size or (396,396)),*layer.planet[3:]):raise RuntimeError('GPU planet draw failed')
                        continue
                    if layer.quads:
                        data=(C.c_float*(len(layer.quads)*8))(*(v for q in layer.quads for v in q))
                        if self.lib.guide_gpu_batch(self.context,slot,len(layer.quads),data,*layer.clip):raise RuntimeError('GPU atlas batch failed')
                        continue
                    if self.lib.guide_gpu_draw(self.context,slot,layer.x,layer.y,
                        *(layer.size or layer.image.size),layer.angle,*layer.pivot,layer.opacity):
                        raise RuntimeError('GPU layer draw failed')
                if self.lib.guide_gpu_present(self.context): raise RuntimeError('GPU presentation failed')
                self.last_metrics=dict(renderer='gles2',upload_bytes=uploaded,
                    layers=len(scene),present_ms=(time.monotonic()-started)*1000)
                self.frames+=1;self.uploads+=uploaded
                if time.monotonic()>=self.next_metrics:
                    emit('UI_RENDERER',backend='gles2',frames=self.frames,upload_bytes=self.uploads,
                         textures=len(self.cache),texture_bytes=sum(im.width*im.height*4 for _,im in self.cache.values()))
                    self.frames=self.uploads=0;self.next_metrics=time.monotonic()+30
                return
            except RuntimeError as exc:
                self.disabled = True
                emit('UI_RENDERER',backend='framebuffer',reason=str(exc))
                if not self._release():
                    raise RuntimeError('GPU display recovery has not released scanout') from exc
                self.software.invalidate()
        self.software.show(compose(base,layers))
        self.last_metrics=dict(self.software.last_metrics,renderer='framebuffer')
    def close(self):
        if not self._release(): return ['GPU display release failed']
        return self.software.close()
