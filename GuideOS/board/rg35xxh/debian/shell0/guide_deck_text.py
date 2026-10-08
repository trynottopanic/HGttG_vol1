"""Measured, clipped Deck text; display shortening never changes model values."""
import time
import unicodedata
from collections import OrderedDict
from PIL import Image, ImageDraw
from guide_unicode import UnicodeText

class TextCache:
    """LRU with a byte budget; caches belong to the display thread."""
    def __init__(self, count, budget):
        self.count=count;self.budget=budget;self.bytes=0;self.values=OrderedDict()
    def get(self,key,build,charge):
        if key in self.values:
            self.values.move_to_end(key)
            return self.values[key][0]
        value=build();cost=len(repr(key).encode('utf-8'))+charge(value)
        if cost<=self.budget:
            while self.values and (len(self.values)>=self.count or self.bytes+cost>self.budget):
                _,(_,old)=self.values.popitem(last=False);self.bytes-=old
            self.values[key]=(value,cost);self.bytes+=cost
        return value

def clusters(text):
    result=[];join=False;regional=0
    for c in str(text):
        flag=0x1f1e6<=ord(c)<=0x1f1ff
        extend=unicodedata.combining(c) or unicodedata.category(c) in ('Mn','Mc','Me') or c=='\u200d' or 0xfe00<=ord(c)<=0xfe0f or 0x1f3fb<=ord(c)<=0x1f3ff or join or (flag and regional%2)
        if result and extend:result[-1]+=c
        else:result.append(c)
        join=c=='\u200d';regional=regional+1 if flag else 0
    return result

class DeckText:
    def __init__(self, fonts, bold_fonts=None):
        self.fonts=fonts;self.bold_fonts=bold_fonts or fonts;self.provider=UnicodeText();self.readers={};self.scrolling=False;self.layouts={};self.layout_bytes=0
        self.measures=TextCache(256,65536)
        self.wraps=TextCache(32,65536)
        self.titles=TextCache(32,65536)
        self.rasters=TextCache(128,4*1024*1024)
    def width(self,text,size,bold=False):
        if self.provider.available:return self.measure(text,size,bold)[0]
        return ImageDraw.Draw(Image.new('L',(1,1))).textlength(text,font=(self.bold_fonts if bold else self.fonts)[size])
    def measure(self,text,size,bold=False):
        return self.measures.get((str(text),size,bold),lambda:self.provider.measure(str(text),size,bold=bold),lambda _:16)
    def shorten(self,text,size,width,filename=False,bold=False):
        text=str(text)
        if self.width(text,size,bold)<=width:return text
        parts=clusters(text);suffix=''
        if filename and '.' in text:
            ext='.'+text.rsplit('.',1)[1]
            if self.width('…'+ext,size,bold)<width/2:suffix=ext
        if filename:
            # Keep both distinguishing tail and extension, within a measured box.
            left=parts[:];right=parts[-min(max(24,len(clusters(suffix))),len(parts)//2):]
            left=left[:-len(right)] if right else left
            while left and self.width(''.join(left)+'…'+''.join(right),size,bold)>width:left.pop()
            while right and self.width('…'+''.join(right),size,bold)>width:right.pop(0)
            return ''.join(left)+'…'+''.join(right)
        while parts and self.width(''.join(parts)+'…',size,bold)>width:parts.pop()
        return ''.join(parts)+'…'
    def lines(self,text,size,width,bold=False):
        return list(self.wraps.get((str(text),size,width,bold),
                    lambda:tuple(self._lines(text,size,width,bold)),
                    lambda lines:sum(len(line.encode('utf-8')) for line in lines)))
    def _lines(self,text,size,width,bold=False):
        # Prefixes are cold wrapping work, not reusable labels. Do not evict
        # stable measurements with hundreds of one-use intermediate strings.
        measure=lambda value:self.provider.measure(value,size,bold=bold)[0] if self.provider.available else self.width(value,size,bold)
        lines=[]
        for paragraph in str(text).split('\n'):
            line=''
            for unit in clusters(paragraph):
                if line and measure(line+unit)>width:
                    split=line.rfind(' ')
                    if split>0:lines.append(line[:split]);line=line[split+1:]+unit
                    else:lines.append(line);line=unit
                else:line+=unit
            lines.append(line)
        return lines
    def draw(self,image,box,text,size=24,color='#edf5fb',policy='wrap',key=None,bold=False):
        x,y,w,h=box;tile=Image.new('RGBA',(w,h));pitch=size+6
        layout_key=(str(text),size,w,policy=='filename',bold)
        if layout_key not in self.layouts:
            lines=self.lines(text,size,w,bold) if policy!='filename' else [self.shorten(text,size,w,True,bold)]
            budget=len(str(text).encode('utf-8'))+sum(len(line.encode('utf-8')) for line in lines)
            if len(self.layouts)>=32 or self.layout_bytes+budget>65536:self.layouts.clear();self.layout_bytes=0
            if budget<=65536:self.layouts[layout_key]=tuple(lines);self.layout_bytes+=budget
        else:lines=list(self.layouts[layout_key])
        tail_height=self.measure(lines[-1],size,bold)[1] if self.provider.available else pitch
        content_height=(len(lines)-1)*pitch+max(pitch,tail_height)
        offset=0;overflow=content_height>h
        if policy=='scroll' and overflow:
            identity=(key,str(text),w,h)
            now=time.monotonic();started,last=self.readers.get(identity,(now,now))
            if now-last>.5:started=now
            if len(self.readers)>16:self.readers.clear()
            self.readers[identity]=(started,now)
            distance=content_height-h;cycle=4+distance/18
            phase=(now-started)%cycle
            offset=min(distance,max(0,(phase-2)*18));self.scrolling=True
        elif overflow:
            count=max(1,h//pitch)
            if len(lines)>count:
                lines=lines[:count];lines[-1]=self.shorten(lines[-1]+'…',size,w,bold=bold)
        rgb=tuple(int(color[i:i+2],16) for i in (1,3,5))
        for index,line in enumerate(lines):
            top=round(index*pitch-offset)
            if top+pitch<0 or top>=h:continue
            if self.provider.available:
                rendered=self.rasters.get((line,size,rgb,bold),lambda:self.provider.render(line,size,rgb,bold=bold),lambda im:im.width*im.height*4)
                tile.alpha_composite(rendered,(0,top))
            else:ImageDraw.Draw(tile).text((0,top),line,font=(self.bold_fonts if bold else self.fonts)[size],fill=color)
        image.paste(tile,(x,y),tile)
        return dict(overflow=overflow,offset=offset)
