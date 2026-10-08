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
CENTER, RADIUS, SEED = (160, 120), 45, 0x4753494F53
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
    unit=13;image=Image.new("RGBA",(91,91));draw=ImageDraw.Draw(image)
    for y,row in enumerate(PIXELS[letter]):
        for x,bit in enumerate(row):
            if bit=="1":draw.rectangle((x*unit,y*unit,(x+1)*unit-1,(y+1)*unit-1),fill=(*color,alpha))
    return image
def corona(seconds):
    strength=smooth((seconds-1.5)/4.0)
    if strength<=0:return Image.new("RGBA",LOW)
    cx,cy=CENTER;layer=Image.new("RGBA",LOW);draw=ImageDraw.Draw(layer)
    # Six authored, uneven solar flares: long, segmented and deliberately non-uniform.
    flares=((1.56,76,.18),(.78,57,.13),(2.39,52,.12),(-2.08,42,.10),(-1.06,35,.09),(.10,29,.07))
    for number,(angle,length,spread) in enumerate(flares):
        reach=round(length*strength);base=RADIUS+2;tip=base+reach
        left=(cx+math.cos(angle-spread)*base,cy+math.sin(angle-spread)*base)
        right=(cx+math.cos(angle+spread)*base,cy+math.sin(angle+spread)*base)
        point=(cx+math.cos(angle)*tip,cy+math.sin(angle)*tip)
        draw.polygon((left,point,right),fill=(236,86,44,round(112*strength)))
        # Staggered bright blocks make each flare read as a small constructed pixel form.
        for step in range(3,9):
            progress=step/9;distance=base+reach*progress
            wobble=math.sin((number+2)*step)*spread*.7
            x=round(cx+math.cos(angle+wobble)*distance);y=round(cy+math.sin(angle+wobble)*distance)
            block=max(1,round((4-progress*3)*strength))
            tone=((255,186,48,round(190*strength)) if step%2 else (255,230,112,round(175*strength)))
            draw.rectangle((x-block,y-block,x+block,y+block),fill=tone)
        branch=angle+(-.52 if number%2 else .52);branch_start=base+reach*.52;branch_end=branch_start+reach*.25
        draw.line((cx+math.cos(angle)*branch_start,cy+math.sin(angle)*branch_start,cx+math.cos(branch)*branch_end,cy+math.sin(branch)*branch_end),fill=(255,151,39,round(135*strength)),width=max(1,round(2*strength)))
    rng=random.Random(SEED+round(seconds*10))
    # Dense uneven ember pixels, contained near the rim instead of a uniform halo.
    for _ in range(round(260*strength)):
        angle=rng.random()*math.tau;distance=RADIUS+rng.randrange(-2,round(17+20*strength));x=round(cx+math.cos(angle)*distance);y=round(cy+math.sin(angle)*distance);size=rng.choice((1,1,1,2,2,3));tone=rng.choice(((255,71,39,110),(255,121,37,145),(255,182,49,180),(255,223,104,205)))
        draw.rectangle((x,y,x+size,y+size),fill=(*tone[:3],round(tone[3]*strength)))
    pulse=.93+.07*math.sin(seconds*math.tau*1.1)
    # Multi-tone stepped rings form the rising, complex eclipse corona.
    for thickness,opacity,tone in ((20,24,(104,42,37)),(16,42,(178,56,34)),(12,68,(238,84,32)),(8,105,(255,139,39)),(5,165,(255,194,66)),(2,235,(255,241,166))):
        radius=RADIUS+round(thickness*strength*pulse);draw.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),outline=(*tone,round(opacity*strength)),width=max(1,round(thickness/4)))
    return Image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(3)),layer)
def eclipse_disk(alpha):
    disk=Image.new("RGBA",(RADIUS*2,RADIUS*2));ImageDraw.Draw(disk).ellipse((0,0,RADIUS*2-1,RADIUS*2-1),fill=(0,0,0,alpha));return disk
def render_frames():
    space,stars=build_space()
    with tempfile.TemporaryDirectory() as temporary:
        output=Path(temporary)/"world-test"/"assets";guide_boot_world.generate(ROOT/"apps"/"boot_animation"/"assets",output,1);renderer=HomeWorldRenderer(output);frames=[]
        for frame in range(round(DURATION*FPS)):
            seconds=frame/FPS;image=Image.alpha_composite(space.convert("RGBA"),stars_layer(stars,seconds));background_fade=smooth((seconds-5.5)/2.0)
            if background_fade:image=Image.alpha_composite(image,Image.new("RGBA",LOW,(0,0,0,round(255*background_fade))))
            image=Image.alpha_composite(image,corona(seconds));planet=renderer.render((RADIUS*2,RADIUS*2),seconds/23,seconds/29).convert("RGBA");fade=1-smooth((seconds-2.5)/2.0)
            if fade>0:
                mask=Image.new("L",planet.size);ImageDraw.Draw(mask).ellipse((0,0,planet.width-1,planet.height-1),fill=round(255*fade));planet.putalpha(mask);image.alpha_composite(planet,(CENTER[0]-RADIUS,CENTER[1]-RADIUS))
            eclipse=smooth((seconds-2.5)/2.0)
            if eclipse:image.alpha_composite(eclipse_disk(round(235*eclipse)),(CENTER[0]-RADIUS,CENTER[1]-RADIUS))
            letters=smooth((seconds-5.5)/.28)
            if letters:
                alpha=round(255*letters);image.alpha_composite(glyph("G",(152,211,255),alpha),(21,74));image.alpha_composite(glyph("S",(244,248,255),alpha),(208,74))
            frames.append(image.convert("RGB").resize((640,480),Image.Resampling.NEAREST))
    return frames
def main():
    folder=Path(__file__).resolve().parent;frames=render_frames();frames[0].save(folder/"guideos-boot-eclipse-draft-3-keyframe.png");frames[-1].save(folder/"guideos-boot-eclipse-draft-3-final.png");frames[0].save(folder/"guideos-boot-eclipse-draft-3.gif",save_all=True,append_images=frames[1:],duration=round(1000/FPS),loop=0,optimize=False)
if __name__=="__main__":main()
