"""Render the first pre-baked GuideOS eclipse boot-animation draft."""
from __future__ import annotations
import math, random, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "boot_animation"))
import guide_boot_world
from guide_home_world import HomeWorldRenderer
LOW, FPS, DURATION = (320, 240), 10, 7.5
CENTER, RADIUS, SEED = (160, 120), 50, 0x4753494F53
def smooth(value):
    value=max(0.0,min(1.0,value));return value*value*(3.0-2.0*value)
def build_space():
    rng=random.Random(SEED);image=Image.new("RGB",LOW,"#03050b");pixels=image.load()
    clouds=[(rng.randrange(320),rng.randrange(240),rng.randrange(30,85),rng.choice(((8,25,54),(11,31,64),(17,28,58)))) for _ in range(8)]
    for y in range(240):
        for x in range(320):
            r,g,b=3,5,11
            for cx,cy,radius,tone in clouds:
                distance=math.hypot(x-cx,y-cy)/radius
                if distance<1:
                    intensity=(1-distance)**2;r+=round(tone[0]*intensity);g+=round(tone[1]*intensity);b+=round(tone[2]*intensity)
            pixels[x,y]=(min(255,r),min(255,g),min(255,b))
    return image,[(rng.randrange(4,316),rng.randrange(4,236),rng.choice((1,1,1,2)),rng.random()*math.tau) for _ in range(210)]
def stars_layer(stars,seconds):
    layer=Image.new("RGBA",LOW);draw=ImageDraw.Draw(layer)
    for x,y,size,phase in stars:
        alpha=round(70+125*(.5+.5*math.sin(seconds*(1.4+size*.3)+phase)))
        draw.rectangle((x,y,x+size-1,y+size-1),fill=((174,211,255,alpha) if size==1 else (220,237,255,alpha)))
    return layer
PIXELS={"G":("0111110","1100011","1100000","1101111","1100011","1100011","0111110"),"S":("0111111","1100000","1100000","0111110","0000011","0000011","1111110")}
def glyph(letter,color,alpha):
    unit=14;image=Image.new("RGBA",(98,98));draw=ImageDraw.Draw(image)
    for y,row in enumerate(PIXELS[letter]):
        for x,bit in enumerate(row):
            if bit=="1":draw.rectangle((x*unit,y*unit,(x+1)*unit-1,(y+1)*unit-1),fill=(*color,alpha))
    return image
def corona(seconds):
    strength=smooth((seconds-2.5)/3.0)
    if strength<=0:return Image.new("RGBA",LOW)
    cx,cy=CENTER;rise=smooth((seconds-2.5)/2.2)
    layer=Image.new("RGBA",LOW);draw=ImageDraw.Draw(layer)
    # Light first crests from below, then becomes a deliberately dramatic eclipse crown.
    angles=(-2.72,-2.34,-2.03,-1.72,-1.42,-1.10,-.80,-.49,-.18,.20,.57,.92,1.28,1.66,2.02,2.36,2.70)
    for index,angle in enumerate(angles):
        lower=.32+.68*max(0,math.sin(angle));visible=strength*lower
        if visible<=.08:continue
        length=round((18+(index%4)*9+54*strength)*visible);width=.018+.055*visible*(1 if index%3 else 1.55)
        sx=cx+math.cos(angle)*RADIUS;sy=cy+math.sin(angle)*RADIUS;ex=cx+math.cos(angle)*(RADIUS+length);ey=cy+math.sin(angle)*(RADIUS+length)
        left=(cx+math.cos(angle-width)*RADIUS,cy+math.sin(angle-width)*RADIUS);right=(cx+math.cos(angle+width)*RADIUS,cy+math.sin(angle+width)*RADIUS)
        draw.polygon((left,(ex,ey),right),fill=(128,197,255,round(70*visible)));draw.line((sx,sy,ex,ey),fill=(225,248,255,round(112*visible)),width=1)
    pulse=.91+.09*math.sin(seconds*math.tau*1.1)
    for thickness,opacity,tone in ((18,12,(64,141,255)),(11,28,(93,180,255)),(6,96,(172,224,255)),(2,224,(239,250,255))):
        radius=RADIUS+round(thickness*strength*pulse);draw.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),outline=(*tone,round(opacity*strength)),width=max(1,round(thickness/5)))
    return Image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(4)),layer)
def eclipse_disk(alpha):
    disk=Image.new("RGBA",(RADIUS*2,RADIUS*2));ImageDraw.Draw(disk).ellipse((0,0,RADIUS*2-1,RADIUS*2-1),fill=(0,0,0,alpha));return disk
def render_frames():
    space,stars=build_space()
    with tempfile.TemporaryDirectory() as temporary:
        output=Path(temporary)/"world-test"/"assets";guide_boot_world.generate(ROOT/"apps"/"boot_animation"/"assets",output,1);renderer=HomeWorldRenderer(output);frames=[]
        for frame in range(round(DURATION*FPS)):
            seconds=frame/FPS;image=Image.alpha_composite(space.convert("RGBA"),stars_layer(stars,seconds));image=Image.alpha_composite(image,corona(seconds));planet=renderer.render((RADIUS*2,RADIUS*2),seconds/23,seconds/29).convert("RGBA");fade=1-smooth((seconds-2.5)/2.0)
            if fade>0:
                mask=Image.new("L",planet.size);ImageDraw.Draw(mask).ellipse((0,0,planet.width-1,planet.height-1),fill=round(255*fade));planet.putalpha(mask);image.alpha_composite(planet,(CENTER[0]-RADIUS,CENTER[1]-RADIUS))
            eclipse=smooth((seconds-2.5)/2.0)
            if eclipse:image.alpha_composite(eclipse_disk(round(235*eclipse)),(CENTER[0]-RADIUS,CENTER[1]-RADIUS))
            letters=smooth((seconds-5.5)/.28)
            if letters:
                alpha=round(255*letters);image.alpha_composite(glyph("G",(152,211,255),alpha),(10,71));image.alpha_composite(glyph("S",(244,248,255),alpha),(212,71))
            frames.append(image.convert("RGB").resize((640,480),Image.Resampling.NEAREST))
    return frames
def main():
    folder=Path(__file__).resolve().parent;frames=render_frames();frames[0].save(folder/"guideos-boot-eclipse-draft-1-keyframe.png");frames[-1].save(folder/"guideos-boot-eclipse-draft-1-final.png");frames[0].save(folder/"guideos-boot-eclipse-draft-1.gif",save_all=True,append_images=frames[1:],duration=round(1000/FPS),loop=0,optimize=False)
if __name__=="__main__":main()
