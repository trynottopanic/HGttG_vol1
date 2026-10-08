"""GuideOS Home v3 presentation and bounded right-stick interaction."""
from dataclasses import dataclass
import math
import os
from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageFont
from guide_deck_text import DeckText
from guide_deck_layouts import DeckLayouts
from guide_ui_model import LayoutResult, Rect, Region, ScreenModel, MenuItem

DESTINATIONS = ("files", "applications", "settings", "storage", "media", "nodes", "find")
TRAY_DESTINATIONS = ("files", "media", "applications", "settings")
LABELS = {"files":"File browser", "applications":"Applications",
          "settings":"Settings", "storage":"Storage",
          "media":"Media", "nodes":"Nodes", "find":"Quick Find"}
SETTINGS = (
    ("audio", "Audio", "Volume, output and Bluetooth audio"),
    ("connections", "Connections", "Wi-Fi and confirmed connection state"),
    ("nearby", "Nearby", "Wi-Fi, Bluetooth and network tools"),
    ("storage", "Storage", "Internal and external storage state"),
    ("power", "Power", "Battery and orderly shutdown"),
    ("updates", "Updates", "Review, install and recover GuideOS releases"),
    ("diagnostics", "Diagnostics", "Service and provider status"),
    ("about", "About", "GuideOS, build and hardware identity"),
)
WHEEL_CENTER = (640, 480)
WHEEL_OUTER_RADIUS = 270
WHEEL_INNER_RADIUS = 79
WHEEL_SECTOR_DEGREES = 30


def wheel_sector(slot):
    middle = 255 - WHEEL_SECTOR_DEGREES * slot
    return middle - 15, middle + 15, middle


def wheel_choice(x, y):
    angle = math.degrees(math.atan2(y, x)) % 360
    if not 180 <= angle <= 270:
        return None
    return 2 if angle < 210 else 1 if angle < 240 else 0

@dataclass
class HomeState:
    wheel_offset: int = 0
    wheel_focus: int = 1
    wheel_held: int | None = None
    wheel_pending: str | None = None
    wheel_open_at: float = 0.0
    tray_extended: bool = True
    tray_focus: int = 0
    tray_active: bool = True
    world_active: bool = False
    right_click_down: bool = False
    tray_position: float = 1.0
    tray_from: float = 0.0
    tray_started: float = 0.0
    wheel_previous: tuple | None = None
    wheel_motion_started: float = 0.0
    wheel_motion_direction: int = 0
    wheel_motion: float = 1.0
    highlight_previous: int | None = None
    highlight_started: float = 0.0
    highlight_motion: float = 1.0
    planet_frame: int = -1

    @property
    def visible(self):
        return tuple(DESTINATIONS[(self.wheel_offset+i)%len(DESTINATIONS)] for i in range(3))

    @property
    def mode(self):
        if self.wheel_pending:return "wheel-armed"
        if self.wheel_held is not None:return "wheel-held"
        return "tray-extended" if self.tray_extended else "idle"

    def cancel_wheel(self):
        changed=self.wheel_held is not None or self.wheel_pending is not None
        self.wheel_held=None;self.wheel_pending=None;self.wheel_open_at=0.0
        return changed

    @property
    def animating(self):
        return (abs(self.tray_position-float(self.tray_extended))>.002 or
                self.wheel_motion<1.0 or self.highlight_motion<1.0)

    def tick(self, now=None):
        now=time.monotonic() if now is None else now;changed=False
        frame=int(now*10)%900
        if frame!=self.planet_frame:self.planet_frame=frame;changed=True
        target=float(self.tray_extended)
        if abs(self.tray_position-target)>.002:
            progress=min(1.0,max(0.0,(now-self.tray_started)/.24))
            eased=1.0-(1.0-progress)**3
            position=self.tray_from+(target-self.tray_from)*eased
            changed=abs(position-self.tray_position)>.002;self.tray_position=position
            if progress>=1.0:self.tray_position=target
        if self.wheel_motion<1.0:
            progress=min(1.0,max(0.0,(now-self.wheel_motion_started)/.22))
            changed=changed or abs(progress-self.wheel_motion)>.002;self.wheel_motion=progress
            if progress>=1.0:self.wheel_previous=None;self.wheel_motion_direction=0
        if self.highlight_motion<1.0:
            progress=min(1.0,max(0.0,(now-self.highlight_started)/.10))
            changed=changed or abs(progress-self.highlight_motion)>.002;self.highlight_motion=progress
            if progress>=1.0:self.highlight_previous=None
        return changed

    def scroll(self, amount, now=None):
        now=time.monotonic() if now is None else now;self.tick(now);self.cancel_wheel()
        self.wheel_previous=self.visible;self.wheel_offset=(self.wheel_offset+amount)%len(DESTINATIONS)
        self.wheel_motion_direction=1 if amount>0 else -1;self.wheel_motion_started=now;self.wheel_motion=0.0
        return True

    def toggle_tray(self, now=None):
        now=time.monotonic() if now is None else now;self.tick(now);self.cancel_wheel()
        self.tray_from=self.tray_position;self.tray_extended=not self.tray_extended;self.tray_started=now;self.tray_active=self.tray_extended
        return True

    def update(self, sample, now=None):
        now=time.monotonic() if now is None else now
        # R3 is reserved for the future centered-wheel overlay. Until that
        # interaction exists, a click has no Home action; Select owns the tray.
        self.right_click_down=bool(sample.get("right_click"));changed=False
        right=sample.get("right")
        if not (isinstance(right,(tuple,list)) and len(right)==2 and
                all(type(v) in (int,float) and math.isfinite(v) for v in right)):
            return changed or self.cancel_wheel(),None
        x,y=map(float,right);magnitude=math.hypot(x,y)
        if self.wheel_pending is not None:
            if magnitude>.25:return changed or self.cancel_wheel(),None
            if now>=self.wheel_open_at:
                destination=self.wheel_pending;self.wheel_pending=None;self.wheel_open_at=0.0
                return True,destination
            return changed,None
        if magnitude<=.18:
            if self.wheel_held is not None:
                self.wheel_pending=self.visible[self.wheel_held];self.wheel_held=None
                self.wheel_open_at=now+.06
                return True,None
            return changed,None
        if magnitude<.25:return changed,None
        self.world_active=False
        held=wheel_choice(x,y)
        if held is None:
            if self.wheel_held is not None:
                self.wheel_held=None
                return True,None
            return changed,None
        if held!=self.wheel_held:
            self.highlight_previous=self.wheel_focus;self.highlight_started=now;self.highlight_motion=0.0
            self.wheel_held=held;self.wheel_focus=held;return True,None
        return changed,None

class V3UI:
    GROUND="#06111d";PANEL="#111b26";PANEL2="#172f43";PRIMARY="#edf5fb"
    SECONDARY="#9ec9ed";MUTED="#7690a8";FOCUS="#9bd6ff";RULE="#46677f"
    def __init__(self,world_runtime="/run/guideos-boot-animation",
                 world_module="/usr/lib/guideos/boot-animation"):
        candidates=(Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                    Path(os.environ.get("WINDIR", "C:/Windows"))/"Fonts/arial.ttf")
        font=next((path for path in candidates if path.is_file()),None)
        self.fonts={s:(ImageFont.truetype(str(font),s) if font else ImageFont.load_default())
                    for s in (12,14,16,18,20,24,28,42)}
        # Home is assembled from a cached static layer. Dynamic wheel/tray
        # geometry is drawn over it, keeping animation work bounded.
        bold_path=font.with_name('DejaVuSans-Bold.ttf' if font.name=='DejaVuSans.ttf' else 'arialbd.ttf') if font else None
        bold_fonts={s:ImageFont.truetype(str(bold_path),s) if bold_path and bold_path.is_file() else self.fonts[s] for s in self.fonts}
        self.text=DeckText(self.fonts,bold_fonts)
        self.deck=DeckLayouts(self.text)
        from guide_application_views import ApplicationViews
        self.application_views=ApplicationViews(self.text)
        self.design_assets=Path(__file__).parent/"assets/home-design"
        if not self.design_assets.is_dir():self.design_assets=Path(__file__).resolve().parents[1]/"assets"
        self.world_available=(Path(__file__).parent/'guide_planegotchi.py').is_file()
        self.planet_assets_available=(self.design_assets/'planet-00.png').is_file()
        self._planet_sheet=None;self._planet_sheet_index=-1
        self._planet_tile=None;self._planet_frame=-1
        self._icons={name:Image.open(self.design_assets/("icon-"+name+".png")).convert("RGBA") for name in DESTINATIONS if name!='find'}
        find=Image.new('RGBA',(44,40));find_draw=ImageDraw.Draw(find)
        find_draw.ellipse((5,3,28,26),outline='white',width=3)
        find_draw.line((26,24,39,37),fill='white',width=4)
        self._icons['find']=find
        self._background_image=self._build_background()
        self._home_static=self._build_home_static()
        self._gpu_tiles={}
        self._gpu_message=None

    def _build_background(self):
        image=Image.new("RGB",(640,480),self.GROUND);draw=ImageDraw.Draw(image)
        for y in range(28,480):
            t=(y-28)/452;color=tuple(round(a+(b-a)*t) for a,b in zip((4,47,91),(2,24,50)))
            draw.line((0,y,639,y),fill=color)
        return image

    def _background(self):
        return self._background_image.copy()

    def _text(self,draw,xy,value,size=16,fill=None,anchor=None):
        draw.text(xy,str(value),font=self.fonts[size],fill=fill or self.PRIMARY,anchor=anchor)

    def _placeholder_world(self):
        """Still bounded placeholder; world generation is intentionally absent."""
        image=Image.new("RGB",(262,228),"#020508");draw=ImageDraw.Draw(image)
        for x in range(0,262,17):draw.line((x,0,x,227),fill="#0b2233")
        for y in range(0,228,17):draw.line((0,y,261,y),fill="#0b2233")
        draw.ellipse((85,48,177,140),outline="#5a8eaa",width=2)
        draw.arc((96,59,166,129),198,344,fill="#9bd6ff",width=3)
        draw.line((80,94,182,94),fill="#24465e",width=1)
        self._text(draw,(131,207),"WORLD VIEW / STANDBY",12,self.MUTED,"mm")
        return image

    def _build_home_static(self):
        image=self._background();draw=ImageDraw.Draw(image)
        draw.rounded_rectangle((16,47,368,360),12,fill="#03070b")
        self._text(draw,(192,351),"PLANEGOTCHI / OPEN WORLD" if self.world_available else "WORLD APPLICATION / NOT INSTALLED",12,self.SECONDARY,"mm")
        self._text(draw,(390,55),"HOME / LOCAL",14,self.SECONDARY)
        self._text(draw,(390,82),"Your Guide",24)
        return image

    def _icon(self,draw,destination,center,selected=False):
        x,y=center;tile=self._icon_tile(destination,selected)
        draw.bitmap((round(x-tile.width/2),round(y-tile.height/2)),tile.getchannel('A'),fill=self.PRIMARY if selected else '#b4c3ce')

    def _planet(self,frame):
        frame=max(0,frame)%900;sheet,cell=divmod(frame,30)
        if not self.planet_assets_available:
            if self._planet_tile is None:
                self._planet_tile=Image.new('RGBA',(144,144))
                draw=ImageDraw.Draw(self._planet_tile)
                draw.ellipse((12,12,132,132),outline=self.SECONDARY,width=2)
                draw.ellipse((48,12,96,132),outline=self.RULE,width=1)
                draw.line((12,72,132,72),fill=self.RULE)
            return self._planet_tile
        if frame!=self._planet_frame:
            if sheet!=self._planet_sheet_index:
                with Image.open(self.design_assets/('planet-%02d.png'%sheet)) as asset:self._planet_sheet=asset.convert('RGBA')
                self._planet_sheet_index=sheet
            x,y=cell%5*144,cell//5*144
            self._planet_tile=self._planet_sheet.crop((x,y,x+144,y+144))
            self._planet_frame=frame
        return self._planet_tile

    @staticmethod
    def _mix(first,second,amount):
        amount=max(0.0,min(1.0,amount))
        a=tuple(int(first[i:i+2],16) for i in (1,3,5));b=tuple(int(second[i:i+2],16) for i in (1,3,5))
        return tuple(round(x+(y-x)*amount) for x,y in zip(a,b))

    def _gpu_tile(self,key,build):
        if key not in self._gpu_tiles:self._gpu_tiles[key]=build()
        return self._gpu_tiles[key]

    def _wheel_tile(self,selected):
        image=Image.new('RGBA',(541,541));draw=ImageDraw.Draw(image)
        draw.pieslice((0,0,540,540),240,270,fill='#24465e' if selected else self.PANEL,
                      outline=None,width=1)
        draw.pieslice((191,191,349,349),239,271,fill='#0d1a27',outline=None,width=1)
        return image

    def _icon_tile(self,destination,selected):
        source=self._icons[destination];tile=Image.new('RGBA',source.size,self.PRIMARY if selected else '#b4c3ce');tile.putalpha(source.getchannel('A'))
        return tile.resize((50,46),Image.Resampling.LANCZOS) if selected else tile

    def _tray_tile(self,label,selected):
        destination=TRAY_DESTINATIONS['ABCD'.index(label)]
        tile=Image.new('RGBA',(82,92));draw=ImageDraw.Draw(tile)
        draw.rounded_rectangle((0,0,81,91),8,fill='#294d65' if selected else self.PANEL)
        icon=self._icon_tile(destination,selected);tile.paste(icon,((82-icon.width)//2,12),icon)
        self._text(draw,(41,72),{'files':'Files','media':'Media','applications':'Apps','settings':'Settings'}[destination],14,self.PRIMARY if selected else '#b4c3ce','mm')
        return tile.resize((86,97),Image.Resampling.LANCZOS) if selected else tile

    def render_home(self,state,now=None,layered=False):
        if layered:from guide_gpu_framebuffer import Layer
        now=time.monotonic() if now is None else now;home=state.v3_home
        image=self._home_static if layered else self._home_static.copy()
        draw=ImageDraw.Draw(image);regions=[];layers=[]
        planet=self._planet(home.planet_frame)
        if layered:layers.append(Layer(planet,48,56,size=(288,288),cache_key='planet'))
        else:
            planet=planet.resize((288,288),Image.Resampling.NEAREST)
            image.paste(planet,(48,56),planet)
        regions.append(Region('v3-world','Open Planegotchi' if self.world_available else 'World application not installed',Rect(16,47,368,360),'v3-destination','planegotchi'))
        if home.world_active:
            def world_focus():
                tile=Image.new('RGBA',(336,28));d=ImageDraw.Draw(tile)
                d.rounded_rectangle((0,0,335,27),6,fill='#17364e')
                self._text(d,(168,14),'PLANEGOTCHI / A TO OPEN' if self.world_available else 'WORLD APPLICATION / UNAVAILABLE',14,self.PRIMARY,'mm')
                return tile
            tile=self._gpu_tile(('world-focus',),world_focus)
            if layered:layers.append(Layer(tile,24,334))
            else:image.paste(tile,(24,334),tile)
        cx,cy=WHEEL_CENTER;outer,inner=WHEEL_OUTER_RADIUS,WHEEL_INNER_RADIUS;visible=home.visible
        motion=1.0-(1.0-home.wheel_motion)**3
        if home.wheel_previous is None:
            wheel_items=[(destination,float(index),False) for index,destination in enumerate(visible)]
        else:
            direction=home.wheel_motion_direction
            wheel_items=[(destination,index+direction*(1.0-motion),False) for index,destination in enumerate(visible)]
            outgoing=home.wheel_previous[0 if direction>0 else 2]
            wheel_items.append((outgoing,(0.0-motion) if direction>0 else (2.0+motion),True))
        for destination,slot,outgoing in wheel_items:
            if not -.7<=slot<=2.7:continue
            start,end,middle_degrees=wheel_sector(slot)
            index=visible.index(destination) if destination in visible else -1
            # Show the current controller focus or held right-stick choice.
            selected=not home.world_active and not outgoing and (index==home.wheel_held or (not home.tray_active and index==home.wheel_focus))
            strength=1.0 if selected else 0.0
            if selected and home.highlight_motion<1.0:
                eased=1.0-(1.0-home.highlight_motion)**3
                strength=eased
            fill=self._mix(self.PANEL,"#24465e",strength)
            outline=self._mix(self.RULE,self.FOCUS,strength)
            if layered:
                neutral=self._gpu_tile(('wheel',False),lambda:self._wheel_tile(False))
                layers.append(Layer(neutral,cx-outer,cy-outer,-30*slot,(cx,cy)))
                if strength:
                    highlight=self._gpu_tile(('wheel',True),lambda:self._wheel_tile(True))
                    layers.append(Layer(highlight,cx-outer,cy-outer,-30*slot,(cx,cy),strength))
            else:
                draw.pieslice((cx-outer,cy-outer,cx+outer,cy+outer),start,end,fill=fill,outline=None,width=1)
                draw.pieslice((cx-inner,cy-inner,cx+inner,cy+inner),start-1,end+1,fill="#0d1a27",outline=None,width=1)
            middle=math.radians(middle_degrees);icon_radius=(outer+inner)/2
            ix=cx+math.cos(middle)*icon_radius;iy=cy+math.sin(middle)*icon_radius
            if layered:
                tile=self._gpu_tile(('icon',destination,strength>.45),lambda:self._icon_tile(destination,strength>.45))
                layers.append(Layer(tile,round(ix-tile.width/2),round(iy-tile.height/2)))
            else:self._icon(draw,destination,(ix,iy),strength>.45)
        for index,destination in enumerate(visible):
            top=(180,310,395)[index];bottom=(309,394,479)[index]
            regions.append(Region("v3-wheel:"+destination,LABELS[destination],Rect(400,top,639,bottom),"v3-destination",destination))
        if home.tray_position>.002:
            for index,label in enumerate("ABCD"):
                local=max(0.0,min(1.0,(home.tray_position-index*.07)/.79));local=1.0-(1.0-local)**3
                final_left=16+index*90;left=round(final_left+(652-final_left)*(1.0-local));selected=not home.world_active and home.tray_active and home.wheel_held is None and index==home.tray_focus
                tile=self._gpu_tile(('tray',label,selected),lambda:self._tray_tile(label,selected))
                x,y=left-(2 if selected else 0),374-(2 if selected else 0)
                if layered:layers.append(Layer(tile,x,y))
                else:image.paste(tile,(x,y),tile)
                if home.tray_extended:regions.append(Region("v3-tray:"+label,"Shortcut "+label,Rect(x,y,x+tile.width,y+tile.height),"v3-shortcut",index))
        if home.mode=="wheel-held":message=LABELS[visible[home.wheel_held]]
        elif home.mode=="wheel-armed":message=LABELS[home.wheel_pending]
        elif home.mode=="tray-extended":message="Shortcut Tray"
        else:message=""
        if message:
            if layered:
                if not self._gpu_message or self._gpu_message[0]!=message:
                    tile=Image.new('RGBA',(238,24))
                    self._text(ImageDraw.Draw(tile),(0,0),message,14,self.SECONDARY)
                    self._gpu_message=(message,tile)
                layers.append(Layer(self._gpu_message[1],390,110))
            else:self._text(draw,(390,110),message,14,self.SECONDARY)
        return LayoutResult(image,tuple(regions),tuple(r.identity for r in regions),tuple(layers))

    def settings_model(self,state):
        items=tuple(MenuItem("settings:"+identity,label+"  ·  "+detail,"v3-setting",identity) for identity,label,detail in SETTINGS)
        return ScreenModel("v3-grid","Settings",items=items,focus_id=items[state.settings_selection%len(items)].identity,notice="Current providers and confirmed system state")

    def render(self,model):
        if model.pattern in ('application-notes','application-document','application-menu'):return self.application_views.render(model)
        if model.pattern in DeckLayouts.PATTERNS:return self.deck.render(model)
        image=self._background();draw=ImageDraw.Draw(image);regions=[];self.text.scrolling=False
        text=self.text.draw
        back=next((a for a in model.actions if a.identity=="back" or a.value==304),None)
        text(image,(18,40,510 if back else 604,70),model.title,28,policy='scroll',key='heading')
        if back:
            rect=(550,43,626,79);draw.rounded_rectangle(rect,6,fill=self.PANEL)
            text(image,(560,49,64,30),back.label,20,self.SECONDARY);regions.append(Region("back",back.label,Rect(*rect),"key",304))
        if model.pattern=='audio-player':
            facts={fact.label:fact.value for fact in model.facts}
            text(image,(18,113,604,90),facts.get('Title',model.title),24,policy='scroll',key='player-title')
            text(image,(18,211,604,28),'Source: '+facts.get('Source','External storage'),20,self.SECONDARY)
            text(image,(18,245,604,28),'Output: '+facts.get('Output','Deck speakers'),20,self.SECONDARY)
            elapsed=int(facts.get('Elapsed','0') or 0);duration=int(facts.get('Duration','0') or 0)
            ratio=max(0,min(1,elapsed/duration)) if duration else 0
            draw.rounded_rectangle((18,287,622,293),3,fill=self.PANEL2)
            if ratio:draw.rounded_rectangle((18,287,18+round(604*ratio),293),3,fill=self.FOCUS)
            text(image,(18,302,604,28),f'{elapsed//60}:{elapsed%60:02d} / {duration//60}:{duration%60:02d}',20,self.SECONDARY)
            for i,item in enumerate(model.items[:3]):
                rect=(18+i*204,346,214+i*204,396);draw.rounded_rectangle(rect,8,fill='#294d65' if item.identity==model.focus_id else self.PANEL)
                text(image,(rect[0]+12,rect[1]+10,172,32),item.label,20,self.PRIMARY if item.enabled else '#718391')
                if item.enabled:regions.append(Region(item.identity,item.label,Rect(*rect),item.action,item.value))
            text(image,(18,408,604,60),model.notice or facts.get('State','Opening').title(),20,self.SECONDARY)
        elif model.pattern=='file-details':
            # Full-width values replace the narrow drawer; actions stay fixed.
            body='\n\n'.join(str(f.label)+'\n'+str(f.value) for f in model.facts)
            text(image,(18,114,604,273),body,24,policy='scroll',key='file-details')
            text(image,(18,387,604,22),model.notice,14,self.SECONDARY)
            for i,item in enumerate(model.items[:3]):
                rect=(18+i*204,414,214+i*204,464);draw.rounded_rectangle(rect,8,fill='#294d65' if item.identity==model.focus_id and item.enabled else self.PANEL)
                text(image,(rect[0]+12,424,172,32),item.label,20,self.PRIMARY if item.enabled else '#718391')
                if item.enabled and model.transition>.95:regions.append(Region(item.identity,item.label,Rect(*rect),item.action,item.value))
        elif model.pattern=='facts-status':
            body='\n'.join(str(f.label)+': '+str(f.value) for f in model.facts)
            text(image,(18,114,604,285),body,24,policy='scroll',key=model.title)
            primary=next((a for a in model.actions if a.button=='A' and a.identity and a.action),None)
            if primary:
                rect=(18,418,300,468);draw.rounded_rectangle(rect,8,fill=self.PANEL2);text(image,(30,428,258,32),primary.label,20)
                regions.append(Region(primary.identity,primary.label,Rect(*rect),primary.action,primary.value))
        elif model.pattern=='v3-grid':
            text(image,(18,82,604,22),model.notice,14,self.SECONDARY)
            for index,item in enumerate(model.items):
                col,row=index%2,index//2;left,top=18+col*307,109+row*91
                rect=(left,top,left+289,top+84)
                selected=item.identity==model.focus_id
                visual=(left-2,top-1,left+291,top+85) if selected else rect
                draw.rounded_rectangle(visual,8,fill='#294d65' if selected else self.PANEL)
                label,_,detail=item.label.partition('  \u00b7  ')
                text(image,(left+12,top+4,265,30),label,24)
                text(image,(left+12,top+34,265,48),detail,16,self.SECONDARY)
                if item.enabled:regions.append(Region(item.identity,item.label,Rect(*visual),item.action,item.value))
        else:
            text(image,(18,110,604,54),model.notice,20,self.SECONDARY,policy='scroll',key='notice')
            grid=model.pattern=='v3-grid'
            focus=next((i for i,item in enumerate(model.items) if item.identity==model.focus_id),0)
            count=8 if grid else 4;start=(focus//count)*count
            for index,item in enumerate(model.items[start:start+count]):
                if grid:
                    col,row=index%2,index//2;left,top=18+col*307,174+row*70;rect=(left,top,left+289,top+62)
                else:rect=(18,174+index*49,622,220+index*49)
                selected=item.identity==model.focus_id
                visual=(rect[0]-2,rect[1]-1,rect[2]+2,rect[3]+1) if selected else rect
                draw.rounded_rectangle(visual,8,fill='#294d65' if selected and item.enabled else self.PANEL)
                label,_,detail=item.label.partition('  \u00b7  ')
                text(image,(rect[0]+12,rect[1]+5,rect[2]-rect[0]-24,32),label,24,self.PRIMARY if item.enabled else '#718391',policy='filename' if not grid else 'wrap')
                if detail and grid:text(image,(rect[0]+12,rect[1]+34,rect[2]-rect[0]-24,26),detail,20,self.SECONDARY)
                if item.enabled:regions.append(Region(item.identity,item.label,Rect(*visual),item.action,item.value))
            if not grid and model.items:
                selected=model.items[focus]
                caption=selected.label+('\n'+selected.metadata if selected.metadata else '')
                text(image,(18,379,604,90),caption,24,policy='scroll',key=selected.identity)
        ids=tuple(r.identity for r in regions)
        return LayoutResult(image,tuple(regions),ids)
