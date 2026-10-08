"""Bounded atlas-based globe generation. All image operations run once per boot."""
import argparse
import hashlib
import json
import math
import random
import shutil
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

VERSION = 'atlas-world-v4'
SEED_VERSION = 'atlas-world-v1'  # Keep existing word-to-landform selections stable.
W, H = 1024, 512
LAYERS = ('terrain','clouds','lights')

def selection(boot, vocabulary):
    if type(boot) is not int or not 1 <= boot < 2**63:
        raise ValueError('Invalid boot number')
    result = {}
    for name in LAYERS:
        entries = vocabulary[name]
        if not isinstance(entries,list) or not 1 <= len(entries) <= 4096 or any(not isinstance(x,str) or not x or len(x)>80 for x in entries):
            raise ValueError('Invalid vocabulary')
        index = (boot-1) % len(entries)
        word = entries[index]
        result[name] = dict(index=index+1,word=word,seed=int.from_bytes(hashlib.sha256((SEED_VERSION+':'+name+':'+word).encode()).digest()[:8],'big'))
    return result

def rgb565(image):
    r,g,b = image.convert('RGB').split()
    low = ImageChops.add(g.point(lambda v:(v&28)<<3), b.point(lambda v:v>>3))
    high = ImageChops.add(r.point(lambda v:v&248), g.point(lambda v:v>>5))
    return Image.merge('LA',(low,high)).tobytes()

def atlas_tiles(path):
    with Image.open(path) as source:
        if source.width*source.height > 8_000_000:
            raise ValueError('Oversized atlas')
        atlas=source.convert('RGBA').resize((W,H),Image.Resampling.NEAREST)
    # Alpha is a binary construction mask; strip fluorescent generation fringes.
    r,g,b,a=atlas.split()
    fringe=ImageChops.multiply(ImageChops.multiply(r.point(lambda v:255 if v<65 else 0),g.point(lambda v:255 if v>180 else 0)),b.point(lambda v:255 if v<90 else 0))
    a=ImageChops.subtract(a.point(lambda v:255 if v>=160 else 0),fringe)
    atlas.putalpha(a)
    return [atlas.crop((x*128,y*128,(x+1)*128,(y+1)*128)) for y in range(4) for x in range(8)]

def wrapped_paste(target, layer, pos, mask):
    x,y=pos
    for shift in (-W,0,W):target.paste(layer,(x+shift,y),mask)

def ocean(seed):
    """Low-contrast water bands and small wave crests; no per-frame work."""
    rng=random.Random(seed ^ 0x57415645)
    phase=rng.random()*math.tau
    field=Image.new('RGB',(128,64));pixels=[]
    for y in range(64):
        latitude=1-abs(y-32)/32
        for x in range(128):
            longitude=x/127*math.tau
            variation=math.sin(longitude*3+math.sin(y/12)+phase)*5 + math.sin(longitude*7-y/9+phase)*3
            pixels.append((15,round(87+36*latitude+variation),round(152+43*latitude+variation)))
    field.putdata(pixels)
    water=field.resize((512,256),Image.Resampling.BILINEAR)
    draw=ImageDraw.Draw(water)
    for _ in range(950):
        x=rng.randrange(512);y=rng.randrange(256);length=rng.randrange(4,14)
        r,g,b=water.getpixel((x,y));delta=rng.choice((-7,8,12,16))
        color=(max(0,r+delta//3),g+delta,b+delta)
        bend=rng.choice((-1,1))
        for shift in (-512,0,512):
            draw.line([(x+shift,y),(x+length//3+shift,y+bend),(x+2*length//3+shift,y+bend),(x+length+shift,y)],fill=color,width=1)
    water=water.resize((W,H),Image.Resampling.NEAREST)
    water.paste(water.crop((0,0,1,H)),(W-1,0))
    return water


def terrain(tiles, seed):
    rng=random.Random(seed)
    world=ocean(seed)
    land=Image.new('L',(W,H))
    # Three broad composite continents; atlas stamps supply coast and biome detail.
    for region in range(3):
        # Draft atlas coast-edge connectors are not authored to match yet.
        # Use its enclosed land stamps, rather than expose rectangular joins.
        patch=Image.new('RGB',(256,224),(84,140,93));mask=Image.new('L',patch.size)
        for number,(x,y,size) in enumerate(((30,26,(192,172)),(95,90,(126,112)))):
            tile=tiles[rng.choice((11,17,19))]
            tile=tile.transpose(rng.choice((Image.Transpose.FLIP_LEFT_RIGHT,Image.Transpose.FLIP_TOP_BOTTOM,Image.Transpose.ROTATE_180))).resize(size,Image.Resampling.NEAREST)
            alpha=tile.getchannel('A')
            # Discard neighboring-cell bleed at the perimeter of source stamps.
            border=Image.new('L',size);ImageDraw.Draw(border).rectangle((4,4,size[0]-5,size[1]-5),fill=255)
            alpha=ImageChops.darker(alpha,border)
            patch.paste(tile.convert('RGB'),(x,y),alpha)
            stamp=Image.new('L',mask.size);stamp.paste(alpha,(x,y));mask=ImageChops.lighter(mask,stamp)
        size=(rng.randrange(216,281,8),rng.randrange(144,201,8))
        patch=patch.resize(size,Image.Resampling.NEAREST);mask=mask.resize(size,Image.Resampling.NEAREST)
        pos=(region*W//3+rng.randrange(-70,45),rng.randrange(132,220))
        wrapped_paste(world,patch,pos,mask);wrapped_paste(land,Image.new('L',size,255),pos,mask)
    # Continuous polar caps. Coast heights are sampled from approved atlas pieces.
    for south in (False,True):
        strip=Image.new('RGB',(W,64),(188,222,227));heights=[]
        for column in range(8):
            tile=tiles[(24 if south else 0)+rng.randrange(8)]
            if south:tile=ImageOps.flip(tile)
            tile=tile.resize((128,64),Image.Resampling.NEAREST)
            colors=tile.convert('RGB')
            colors=colors.crop((7,0,121,64)).resize((128,64),Image.Resampling.NEAREST)
            alpha=tile.getchannel('A').crop((7,0,121,64)).resize((128,64),Image.Resampling.NEAREST)
            strip.paste(colors,(column*128,0),alpha)
            for x in range(0,128,8):
                bounds=tile.getchannel('A').crop((x,0,x+8,64)).getbbox()
                heights.append(max(32,min(64,bounds[3] if bounds else 40)))
        # Circular moving average joins every cell and the longitude seam.
        heights=[round(sum(heights[(i+j)%128] for j in (-2,-1,0,1,2))/5) for i in range(128)]
        cap=Image.new('L',(W,64));cd=ImageDraw.Draw(cap)
        for i,height in enumerate(heights):cd.rectangle((i*8,0,i*8+7,height-1),fill=255)
        ImageDraw.Draw(strip).rectangle((0,0,W-1,15),fill=(225,242,244))
        if south:strip=ImageOps.flip(strip);cap=ImageOps.flip(cap)
        world.paste(strip,(0,H-64 if south else 0),cap);land.paste(255,(0,H-64 if south else 0,W,H if south else 64),cap)
    # Exact periodic endpoint without blending the entire painted terrain.
    world.paste(world.crop((0,0,1,H)),(W-1,0));land.paste(land.crop((0,0,1,H)),(W-1,0))
    return world,land

def cloud_tiles(path):
    """Use neutral cloud opacity only; reject the draft's saturated edge noise."""
    with Image.open(path) as source:
        if source.width*source.height > 8_000_000:
            raise ValueError('Oversized cloud atlas')
        atlas=source.convert('RGBA').resize((512,256),Image.Resampling.LANCZOS)
    r,g,b,alpha=atlas.split()
    darkest=ImageChops.darker(ImageChops.darker(r,g),b)
    brightest=ImageChops.lighter(ImageChops.lighter(r,g),b)
    neutral=ImageChops.subtract(brightest,darkest).point(lambda v:255 if v<=40 else 0)
    value=darkest.point(lambda v:0 if v<120 else min(255,(v-120)*2))
    opacity=ImageChops.multiply(ImageChops.multiply(alpha,neutral),value)
    opacity=opacity.filter(ImageFilter.MedianFilter(3)).point(lambda v:0 if v<32 else v)
    tiles=[]
    for y in range(2):
        for x in range(4):
            tile=opacity.crop((x*128,y*128,(x+1)*128,(y+1)*128))
            border=Image.new('L',(128,128));ImageDraw.Draw(border).rectangle((5,5,122,122),fill=255)
            tile=ImageChops.multiply(tile,border)
            if tile.getbbox() is None:raise ValueError('Empty cloud stamp')
            tiles.append(tile)
    return tiles


def clouds(tiles,seed):
    rng=random.Random(seed);small=Image.new('L',(512,128))
    for _ in range(30):
        tile=rng.choice(tiles).transpose(rng.choice((Image.Transpose.FLIP_LEFT_RIGHT,Image.Transpose.FLIP_TOP_BOTTOM,Image.Transpose.ROTATE_180)))
        tile=tile.resize((rng.randrange(48,113,8),rng.randrange(24,57,4)),Image.Resampling.NEAREST)
        strength=rng.choice((128,160,192,224))
        tile=tile.point(lambda v:v*strength//255)
        x=rng.randrange(512);y=rng.randrange(4,125)-tile.height//2
        layer=Image.new('L',small.size)
        for shift in (-512,0,512):layer.paste(tile,(x+shift,y))
        small=ImageChops.lighter(small,layer)
    small.paste(small.crop((0,0,1,128)),(511,0))
    return small.resize((2048,H),Image.Resampling.NEAREST)

def settlements(land,seed):
    rng=random.Random(seed);lights=Image.new('L',(W,H));roads=Image.new('L',(W,H));ld=ImageDraw.Draw(lights);rd=ImageDraw.Draw(roads)
    points=[]
    safe_land=land.filter(ImageFilter.MinFilter(7))
    for _ in range(1600):
        x=rng.randrange(W);y=rng.randrange(96,H-96)
        if safe_land.getpixel((x,y)) and all((x-a)**2+(y-b)**2>30**2 for a,b in points):
            points.append((x,y))
            if len(points)==24:break
    for x,y in points:
        ld.point((x,y),fill=255)
        rd.line((x-3,y,x+3,y),fill=85,width=1)
        ld.point((x-3,y),fill=110);ld.point((x+3,y),fill=110)
        for _ in range(22):
            a=x+rng.randrange(-10,11);b=y+rng.randrange(-7,8)
            if 0<=a<W and 0<=b<H and land.getpixel((a,b)):ld.point((a,b),fill=rng.choice((60,110,180)))
        others=sorted((p for p in points if p!=(x,y)),key=lambda p:(x-p[0])**2+(y-p[1])**2)
        for a,b in others[:3]:
            length=max(abs(a-x),abs(b-y))
            if length>170:continue
            line=[(round(x+(a-x)*t/length),round(y+(b-y)*t/length)) for t in range(length+1)]
            if all(land.getpixel(p) for p in line):rd.line(line,fill=255 if length>90 else 170,width=1);break
    return lights,roads

def word_caption(assets, seeds):
    text=' '.join(seeds[name]['word'] for name in LAYERS)
    if len(text)*11>588 or any(not 32<=ord(c)<=126 for c in text):
        raise ValueError('Boot words exceed caption glyph bounds')
    glyphs=Image.frombytes('L',(1330,24),(Path(assets)/'caption-glyphs-v2.r8').read_bytes())
    caption=Image.new('L',(600,24))
    x=(600-len(text)*11)//2
    for char in text:
        offset=(ord(char)-32)*14
        glyph=glyphs.crop((offset,0,offset+14,24))
        caption.paste(glyph,(x,0),glyph)
        x+=11
    return caption

def generate(assets, output, boot):
    assets,output=Path(assets),Path(output);output.mkdir(parents=True,exist_ok=False)
    vocabulary=json.loads((assets/'world-vocabulary-v1.json').read_text())
    seeds=selection(boot,vocabulary)
    world,land=terrain(atlas_tiles(assets/'terrain-atlas-draft-v1.png'),seeds['terrain']['seed'])
    cloud=clouds(cloud_tiles(assets/'cloud-atlas-draft-v1.png'),seeds['clouds']['seed']);lights,roads=settlements(land,seeds['lights']['seed'])
    payloads={'terrain-fixed-v2.rgb565':rgb565(world),'clouds-fixed-v2.r8':cloud.tobytes(),'lights-fixed-v2.r8':lights.tobytes(),'roads-fixed-v2.r8':roads.tobytes(),'caption-world-words.r8':word_caption(assets,seeds).tobytes()}
    for name,data in payloads.items():(output/name).write_bytes(data)
    for name in ('silhouette-standard-v3.r8','caption-dont-panic-v4.r8'):shutil.copyfile(assets/name,output/name)
    metadata=dict(caption_glyphs_sha256=hashlib.sha256((assets/'caption-glyphs-v2.r8').read_bytes()).hexdigest(),generator=VERSION,seed_version=SEED_VERSION,cloud_atlas_sha256=hashlib.sha256((assets/'cloud-atlas-draft-v1.png').read_bytes()).hexdigest(),boot=boot,words={k:v['word'] for k,v in seeds.items()},indices={k:v['index'] for k,v in seeds.items()},sha256={k:hashlib.sha256(v).hexdigest() for k,v in payloads.items()},atlas_sha256=hashlib.sha256((assets/'terrain-atlas-draft-v1.png').read_bytes()).hexdigest(),vocabulary_sha256=hashlib.sha256((assets/'world-vocabulary-v1.json').read_bytes()).hexdigest())
    (output/'world.json').write_text(json.dumps(metadata,indent=2))
    return world,land,metadata

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--assets',required=True);parser.add_argument('--output',required=True);parser.add_argument('--boot',required=True,type=int)
    args=parser.parse_args();generate(args.assets,args.output,args.boot)
