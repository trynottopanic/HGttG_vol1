"""Notepad concept screens only; no application/runtime changes."""
from pathlib import Path
import sys
from PIL import Image,ImageDraw,ImageFont
P=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(P/'board/rg35xxh/debian/shell0'))
from guide_deck_layouts import GROUND,FIELD,PANEL,ROW,SELECTED,INK,PRIMARY,SECONDARY,FOCUS
OUT=Path(__file__).resolve().parent
FONT=Path('/usr/share/fonts/truetype/dejavu')
def font(size,bold=False):return ImageFont.truetype(str(FONT/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')),size)
def text(d,xy,value,size=22,fill=INK,bold=False):d.text(xy,value,font=font(size,bold),fill=fill)
def base():
    image=Image.new('RGB',(640,480),GROUND);d=ImageDraw.Draw(image)
    d.rectangle((0,28,639,91),fill=PANEL)
    d.rectangle((0,92,639,431),fill=FIELD)
    text(d,(16,4),'GuideOS',14,PANEL)
    text(d,(16,43),'Notepad',28,INK,True)
    text(d,(506,51),'Menu Home',17,INK)
    return image,d

def key(d,x,y,button,label):
    d.rounded_rectangle((x,y,x+26,y+26),5,fill=PANEL)
    f=font(17,True);box=d.textbbox((0,0),button,font=f);w=box[2]-box[0]
    d.text((x+(26-w)/2,y+1),button,font=f,fill=INK)
    text(d,(x+35,y+1),label,19,PANEL)

def launch():
    image,d=base()
    text(d,(18,106),'Internal drafts',18,'#3c5969')
    text(d,(552,106),'3 notes',16,'#3c5969')
    d.rounded_rectangle((16,139,624,194),7,fill=SELECTED,outline=FOCUS,width=3)
    d.line((40,158,40,176),fill=PRIMARY,width=2);d.line((31,167,49,167),fill=PRIMARY,width=2)
    text(d,(66,150),'New note',24,PRIMARY,True)
    rows=[('Earth observation','Clouds drift across the blue hemisphere.'),
          ('Trip packing','Cable, headphones, spare card…'),
          ('Ideas','Things to come back to.')]
    for index,(name,preview) in enumerate(rows):
        y=208+index*69
        d.rounded_rectangle((16,y,624,y+61),6,fill='#d5dde3')
        text(d,(31,y+3),name,23,INK,True)
        text(d,(31,y+33),preview,17,'#3c5969')
    key(d,18,445,'A','Select');key(d,182,445,'B','Back')
    text(d,(391,445),'↑↓ Choose a note',19,PANEL)
    return image

BODY='''Clouds drift across the blue hemisphere.

The mountain ridges catch the morning light. Beyond them, the far coast disappears beneath a narrow band of cloud.

Return here later and compare the evening light.'''

def wrap(value,d,width):
    lines=[]
    for paragraph in value.split('\n'):
        if not paragraph:lines.append('');continue
        line=''
        for word in paragraph.split():
            next_line=(line+' '+word).strip()
            if d.textlength(next_line,font=font(24))>width and line:
                lines.append(line);line=word
            else:line=next_line
        lines.append(line)
    return lines

def document():
    image,d=base()
    text(d,(18,109),'Earth observation',27,INK,True)
    text(d,(19,150),'Internal draft',17,'#3c5969')
    d.ellipse((536,153,544,161),fill='#386e58');text(d,(552,145),'Saved',17,'#386e58')
    d.rounded_rectangle((16,181,624,405),6,fill='#e5eff3')
    viewport=Image.new('RGB',(564,205),'#e5eff3');vd=ImageDraw.Draw(viewport)
    lines=wrap(BODY,vd,555)
    for index,line in enumerate(lines):text(vd,(0,2+index*34),line,24,INK)
    image.paste(viewport,(31,190))
    d=ImageDraw.Draw(image)
    d.rounded_rectangle((609,195,613,390),2,fill='#c4d6df')
    thumb=round(195*min(1,205/(len(lines)*34)))
    d.rounded_rectangle((609,195,613,195+thumb),2,fill='#839cab')
    text(d,(18,408),'↑↓ Scroll',15,'#3c5969')
    key(d,18,445,'A','Edit');key(d,160,445,'Y','Save')
    key(d,308,445,'X','Actions');key(d,492,445,'B','Notes')
    return image

launch().save(OUT/'notepad-launch.png')
document().save(OUT/'notepad-document.png')
print('Rendered two 640 x 480 Notepad concept screens.')
