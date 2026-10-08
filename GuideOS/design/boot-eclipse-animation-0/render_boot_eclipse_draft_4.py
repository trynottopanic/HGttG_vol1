"""Higher-density SNES-style eclipse draft."""
from __future__ import annotations
import math, random, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'apps'/'boot_animation'))
import guide_boot_world
from guide_home_world import HomeWorldRenderer
SIZE=(640,480);CENTER=(320,240);RADIUS=90;FPS=10;DURATION=7.5;SEED=0x4753494F53
def smooth(v):
 v=max(0,min(1,v));return v*v*(3-2*v)
def space(seconds):
 rng=random.Random(SEED);base=Image.new('RGB',SIZE,(2,4,9));p=base.load();clouds=[(rng.randrange(640),rng.randrange(480),rng.randrange(80,170),rng.choice(((5,20,48),(8,29,66),(12,22,55)))) for _ in range(9)]
 for y in range(480):
  for x in range(640):
   r,g,b=2,4,9
   for cx,cy,rad,tone in clouds:
    d=math.hypot(x-cx,y-cy)/rad
    if d<1:
     a=(1-d)**2;r+=round(tone[0]*a);g+=round(tone[1]*a);b+=round(tone[2]*a)
   p[x,y]=(r,g,b)
 stars=[]
 for _ in range(330):stars.append((rng.randrange(5,635),rng.randrange(5,475),rng.choice((1,1,1,2)),rng.random()*math.tau))
 layer=Image.new('RGBA',SIZE);draw=ImageDraw.Draw(layer)
 for x,y,size,phase in stars:
  a=round(60+145*(.5+.5*math.sin(seconds*(.55+size*.16)+phase)));draw.rectangle((x,y,x+size-1,y+size-1),fill=(174,211,255,a))
 return Image.alpha_composite(base.convert('RGBA'),layer)
def corona(seconds):
 strength=smooth((seconds-1.5)/4.0)
 if strength<=0:return Image.new('RGBA',SIZE)
 cx,cy=CENTER;layer=Image.new('RGBA',SIZE);draw=ImageDraw.Draw(layer);rng=random.Random(SEED+round(seconds*1.25))
 # Five deliberately authored flares; their dense stepped interiors are stable between slow shimmer updates.
 flares=((1.57,176,.16),(.72,132,.115),(2.42,121,.115),(-2.05,92,.09),(-1.08,76,.08))
 for number,(angle,length,spread) in enumerate(flares):
  reach=round(length*strength);base=RADIUS+3;tip=base+reach;left=(cx+math.cos(angle-spread)*base,cy+math.sin(angle-spread)*base);right=(cx+math.cos(angle+spread)*base,cy+math.sin(angle+spread)*base);point=(cx+math.cos(angle)*tip,cy+math.sin(angle)*tip)
  draw.polygon((left,point,right),fill=(184,47,29,round(130*strength)))
  for step in range(4,18):
   f=step/18;distance=base+reach*f;wiggle=math.sin((number+3)*step)*spread*.6;x=round(cx+math.cos(angle+wiggle)*distance);y=round(cy+math.sin(angle+wiggle)*distance);block=max(1,round((5-f*3)*strength));tone=((255,82,34,155),(255,131,38,185),(255,190,62,215),(255,235,153,225))[step%4]
   draw.rectangle((x-block,y-block,x+block,y+block),fill=(*tone[:3],round(tone[3]*strength)))
   if step in (7,12):
    branch=angle+(-.42 if number%2 else .42);end=distance+reach*.18;draw.line((x,y,cx+math.cos(branch)*end,cy+math.sin(branch)*end),fill=(255,145,45,round(150*strength)),width=max(1,round(2*strength)))
 # Dense individual pixels and small clusters provide SNES-era tonal variation around the limb.
 for _ in range(round(1050*strength)):
  angle=rng.random()*math.tau;distance=RADIUS+rng.randrange(-3,round(27+25*strength));x=round(cx+math.cos(angle)*distance);y=round(cy+math.sin(angle)*distance);block=rng.choice((1,1,1,2,2,3));tone=rng.choice(((114,39,36,110),(176,50,31,130),(231,72,31,165),(255,116,37,185),(255,174,56,205),(255,223,124,220)))
  draw.rectangle((x,y,x+block,y+block),fill=(*tone[:3],round(tone[3]*strength)))
 pulse=.97+.03*math.sin(seconds*math.tau*.32)
 for thickness,opacity,tone in ((35,20,(81,28,35)),(28,35,(129,38,31)),(21,56,(186,51,29)),(15,88,(235,78,30)),(10,130,(255,128,38)),(6,182,(255,190,64)),(2,242,(255,242,175))):
  rad=RADIUS+round(thickness*strength*pulse);draw.ellipse((cx-rad,cy-rad,cx+rad,cy+rad),outline=(*tone,round(opacity*strength)),width=max(1,round(thickness/5)))
 return Image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(2)),layer)
PIXELS={'G':('0111110','1100011','1100000','1101111','1100011','1100011','0111110'),'S':('0111111','1100000','1100000','0111110','0000011','0000011','1111110')}
def glyph(letter,color,alpha):
 unit=26;im=Image.new('RGBA',(182,182));draw=ImageDraw.Draw(im)
 for y,row in enumerate(PIXELS[letter]):
  for x,bit in enumerate(row):
   if bit=='1':draw.rectangle((x*unit,y*unit,(x+1)*unit-1,(y+1)*unit-1),fill=(*color,alpha))
 return im
def disk(alpha):
 im=Image.new('RGBA',(180,180));ImageDraw.Draw(im).ellipse((0,0,179,179),fill=(0,0,0,alpha));return im
def render():
 with tempfile.TemporaryDirectory() as temp:
  output=Path(temp)/'world'/'assets';guide_boot_world.generate(ROOT/'apps'/'boot_animation'/'assets',output,1);world=HomeWorldRenderer(output);frames=[]
  for frame in range(round(FPS*DURATION)):
   seconds=frame/FPS;image=space(seconds);fade_bg=smooth((seconds-5.5)/2);image=Image.alpha_composite(image,Image.new('RGBA',SIZE,(0,0,0,round(255*fade_bg)))) if fade_bg else image;image=Image.alpha_composite(image,corona(seconds));planet=world.render((180,180),seconds/23,seconds/29).convert('RGBA');fade=1-smooth((seconds-2.5)/2)
   if fade:
    mask=Image.new('L',planet.size);ImageDraw.Draw(mask).ellipse((0,0,179,179),fill=round(255*fade));planet.putalpha(mask);image.alpha_composite(planet,(230,150))
   eclipse=smooth((seconds-2.5)/2)
   if eclipse:image.alpha_composite(disk(round(235*eclipse)),(230,150))
   letters=smooth((seconds-5.5)/.28)
   if letters:
    a=round(255*letters);image.alpha_composite(glyph('G',(152,211,255),a),(43,149));image.alpha_composite(glyph('S',(244,248,255),a),(415,149))
   frames.append(image.convert('RGB'))
 return frames
def main():
 folder=Path(__file__).resolve().parent;frames=render();frames[0].save(folder/'guideos-boot-eclipse-draft-4-keyframe.png');frames[-1].save(folder/'guideos-boot-eclipse-draft-4-final.png');frames[0].save(folder/'guideos-boot-eclipse-draft-4.gif',save_all=True,append_images=frames[1:],duration=100,loop=0,optimize=False)
if __name__=='__main__':main()
