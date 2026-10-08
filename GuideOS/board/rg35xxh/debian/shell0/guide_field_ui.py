"""Field Theme 1: presentation only, with shared visual/hit geometry."""
from dataclasses import replace
from pathlib import Path
import os
import re
import tomllib
from PIL import Image, ImageDraw, ImageFont
from guide_ui_model import LayoutResult, Region, Rect, ScreenModel, MenuItem, Fact, ActionHint, UIError

class FieldUI:
    def __init__(self, root, text_provider=None):
        root=Path(root)/'field-1'
        with (root/'tokens.toml').open('rb') as source:self.tokens=tomllib.load(source)
        with (root/'components.toml').open('rb') as source:self.components=tomllib.load(source)
        display=self.tokens['display']
        if display['profile']!='deck-640x480' or (display['width'],display['height'])!=(640,480):raise UIError('Field renderer supports only deck-640x480')
        if self.tokens['schema']['version']!=self.components['schema']['version'] or self.components['schema']['display_profile']!=display['profile']:raise UIError('Field schema mismatch')
        self.colors=self.tokens['colors']
        self.fonts={name:self._font(spec) for name,spec in self.tokens['typography'].items()}
        self.text_provider=text_provider
        for name in ('ground','context','field','panel','selected','focus','primary','secondary','dark'):
            if not re.fullmatch(r'#[0-9a-fA-F]{6}',self.colors.get(name,'')):
                raise UIError('Invalid Field Theme color')
        if self.tokens['schema']['theme']!='field-1':raise UIError('Invalid Field Theme')

    @staticmethod
    def _font_roots():
        return (Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts',Path('/usr/share/fonts/truetype/noto'),Path('/usr/share/fonts/truetype/dejavu'))

    def _font(self,role):
        spec=self.tokens['fonts'][role['family']][role['weight']]
        for name in spec['production']+spec['reduced']+spec['preview']:
            for root in self._font_roots():
                path=root/name
                if path.is_file():return ImageFont.truetype(str(path),role['size'])
        raise UIError('no font available for '+role['family']+'.'+role['weight'])

    def color(self,name):
        try:return self.colors[name]
        except KeyError as error:raise UIError('unknown color: '+name) from error

    @staticmethod
    def _clean(value,limit=160):
        return ''.join(character for character in str(value) if character.isprintable())[:limit]

    def _text(self,draw,xy,value,role,color='primary',anchor=None):
        if role not in self.fonts:raise UIError('unknown typography role: '+role)
        if self.text_provider is not None:
            self.text_provider.draw(draw,xy,self._clean(value),self.tokens['typography'][role],self.color(color),anchor);return
        draw.text(xy,self._clean(value),font=self.fonts[role],fill=self.color(color),anchor=anchor)

    def _width(self,draw,value,role):
        if self.text_provider is not None:return self.text_provider.measure(value,self.tokens['typography'][role])
        return draw.textlength(value,font=self.fonts[role])

    def text(self,image,box,value,role='body',color='primary',lines=1):
        # Clip in an isolated surface, including Pango glyph overhangs.
        from guide_unicode import ImageCanvas
        x,y,w,h=box
        tile=Image.new('RGBA',(w,h))
        draw=ImageCanvas(tile)
        value=self._clean(value,512)
        words=value.split(); rows=[];line=''
        for word in words:
            proposed=(line+' '+word).strip()
            if line and self._width(draw,proposed,role)>w:
                rows.append(line);line=word
            else:line=proposed
        if line:rows.append(line)
        pitch=self.tokens['typography'][role]['size']+4
        for i,line in enumerate(rows[:lines]):
            shortened=line
            while shortened and self._width(draw,shortened+('â€¦' if shortened!=line else ''),role)>w:shortened=shortened[:-1]
            if shortened!=line or (i==lines-1 and len(rows)>lines):
                while shortened and self._width(draw,shortened+'â€¦',role)>w:shortened=shortened[:-1]
                shortened+='â€¦'
            self._text(draw,(0,i*pitch),shortened,role,color)
        image.paste(tile,(x,y),tile)

    def panel(self,image,rect,label,selected=False,detail='',grid=False):
        d=ImageDraw.Draw(image);x,y,r,b=rect
        d.rectangle(rect,fill=self.color('selected' if selected else 'panel'))
        if selected:d.rectangle((x,y,x+4,b),fill=self.color('focus'))
        if grid:
            d.line((x+10,y+18,r-10,y+18),fill=self.color('secondary'))
            self.text(image,(x+10,y+23,r-x-18,66),label,'body_strong',lines=2)
            if detail:self.text(image,(x+12,b-20,r-x-22,18),detail,'metadata','secondary')
        else:
            self.text(image,(x+14,y+5,r-x-26,36),label,'body_strong')
            if detail:self.text(image,(x+14,y+34,r-x-26,b-y-34),detail,'metadata','secondary')

    def slide_home(self, previous, current, progress, direction):
        """Slide only the icon grid; keep system chrome and hints stationary."""
        progress=max(0.0,min(1.0,progress))
        eased=progress*progress*(3-2*progress)
        offset=round(640*eased)*direction
        image=current.copy()
        grid=Image.new('RGB',(640,192),self.color('field'))
        grid.paste(previous.crop((0,230,640,422)),(-offset,0))
        grid.paste(current.crop((0,230,640,422)),(direction*640-offset,0))
        image.paste(grid,(0,230))
        return image

    def render(self,model):
        if model.pattern not in ('standard-menu','facts-status','field-home','field-list','field-confirm'):
            raise UIError('Unknown Field screen')
        ids=[item.identity for item in model.items]
        action_ids=[action.identity for action in model.actions if action.identity]
        if len(ids)!=len(set(ids)):raise UIError('Duplicate items')
        if model.items and model.focus_id not in ids and model.focus_id not in action_ids:raise UIError('focused item is unavailable')
        if any(action.color not in self.colors for action in model.actions):raise UIError('unknown color')
        image=Image.new('RGB',(640,480),self.color('field'));d=ImageDraw.Draw(image)
        d.rectangle((0,0,639,27),fill=self.color('ground'))
        d.rectangle((0,28,639,77),fill=self.color('context'))
        self.text(image,(18,34,545,40),model.title,'screen_title','dark')
        d.rectangle((0,440,639,479),fill=self.color('ground'))
        regions=[];visible=[]
        if model.pattern=='field-home':
            if len(model.items)>10:raise UIError('Home grid capacity exceeded')
            for i in range(10):
                x=15+(i%5)*122;y=230+(i//5)*96;rect=(x,y,x+120,y+94)
                item=model.items[i] if i<len(model.items) else None
                self.panel(image,rect,item.label if item else '',item is not None and item.identity==model.focus_id,grid=True)
                if item and item.enabled:regions.append(Region(item.identity,item.label,Rect(*rect),item.action,item.value));visible.append(item.identity)
        elif model.pattern=='facts-status':
            system=model.title=='System / Deck status'
            if system:
                capsule=Image.new('RGBA',(58,28));cd=ImageDraw.Draw(capsule)
                cd.rounded_rectangle((1,1,56,26),radius=13,fill='#F2F7FA')
                mask=Image.new('L',capsule.size);md=ImageDraw.Draw(mask);md.rounded_rectangle((1,1,56,26),radius=13,fill=255)
                blue=Image.new('RGBA',capsule.size,'#3E86DF');clip=Image.new('L',capsule.size);clip.paste(mask.crop((0,0,29,28)),(0,0));capsule.paste(blue,(0,0),clip)
                capsule=capsule.rotate(35,expand=True);image.paste(capsule,(581-capsule.width//2,53-capsule.height//2),capsule)
            for i,fact in enumerate(model.facts[:9]):
                y=91+i*36;left=16;d.rectangle((left,y,623,y+34),fill=self.color('panel'))
                self.text(image,(left+10,y+3,132,30),fact.label,'metadata','secondary')
                self.text(image,(168,y+1,443,34),fact.value,'body')
        else:
            expanded=len(model.items)<=3
            self.text(image,(18,82,604,99 if expanded else 67),model.notice,'body','dark',lines=3 if expanded else 2)
            focus=ids.index(model.focus_id) if model.focus_id in ids else 0
            first=max(0,min(focus-2,len(ids)-4))
            for index,item in enumerate(model.items[first:first+4]):
                y=(187 if expanded else 155)+index*66;rect=(18,y,621,y+61)
                label,separator,detail=item.label.partition('  Â·  ')
                self.panel(image,rect,label,item.identity==model.focus_id,detail)
                if item.enabled:regions.append(Region(item.identity,item.label,Rect(*rect),item.action,item.value))
                visible.append(item.identity)
            if len(ids)>4:
                d.rectangle((629,160,632,400),fill=self.color('context'))
                height=max(20,240*4//len(ids));top=160+round((240-height)*first/(len(ids)-4))
                d.rectangle((629,top,632,top+height),fill=self.color('panel'))
        if model.pattern in ('field-home','facts-status') and model.notice:
            self.text(image,(18,190 if model.pattern=='field-home' else 415,604,25),model.notice,'metadata','dark')
        x=18
        for action in model.actions:
            label=action.button+' '+action.label
            width=min(250,round(self._width(d,label,'control'))+20)
            if action.identity and action.identity==model.focus_id:d.rectangle((x-5,449,x-2,472),fill=self.color('focus'))
            self.text(image,(x,444,width-8,34),label,'control','primary')
            if action.identity and action.action:
                regions.append(Region(action.identity,action.label,Rect(x,443,min(x+width,623),478),action.action,action.value))
            x+=width+15
        return LayoutResult(image,tuple(regions),tuple(visible))


def field_model(state,status=None):
    """Map acknowledged shell/provider values; never inspect editor text."""
    from guide_shell_schema_adapter import home_model,status_model,HOME_PAGE_SIZE
    back=ActionHint('B','Back','blue','back','key',304)
    home=ActionHint('Menu','Home','blue','home','key',316)
    actions=(ActionHint('A','Select','blue'),back,home)
    if state.page=='home':
        m=home_model(state.pages,state.choices,state.selection)
        labels={'media':'Media','status':'System','wifi':'Wi-Fi','storage':'External Card','power':'Power','applications':'Applications'}
        page=state.selection//HOME_PAGE_SIZE
        count=(len(m.items)+HOME_PAGE_SIZE-1)//HOME_PAGE_SIZE
        visible=m.items[page*HOME_PAGE_SIZE:(page+1)*HOME_PAGE_SIZE]
        return replace(m,pattern='field-home',title='Home / Functions',
                       notice=f'Page {page+1} / {count}' if count>1 else '',
                       items=tuple(replace(i,label=labels.get(i.identity[5:],i.label.title())) for i in visible),actions=())
    if state.page=='status':
        m=status_model(status or [],audio_test_label=('Stop test' if state.audio_panel.status.get('test_active') else 'Audio test') if state.audio_panel else None)
        if state.wifi_panel:
            wifi=state.wifi_panel.status
            network=next((r for r in wifi.get('networks',[]) if r['id']==wifi.get('connected')),None)
            value=network['ssid']+' / connected' if network else 'Not connected' if wifi.get('state')!='unavailable' else 'Unavailable'
            m=replace(m,facts=tuple(replace(f,value=value) if f.label=='Wi-Fi' else f for f in m.facts))
        return replace(m,title='System / Deck status',focus_id=m.actions[state.status_selection%len(m.actions)].identity)
    if state.page=='nodes':
        return state.nodes_panel.model()
    if state.page=='diagnostics':
        wifi=state.wifi_panel.status if state.wifi_panel else {}
        network=next((row for row in wifi.get('networks',[]) if row.get('id')==wifi.get('connected')),None)
        connection=(network.get('ssid','Connected')+' / connected') if network else wifi.get('message','Wi-Fi controls unavailable')
        address=wifi.get('ipv4') if isinstance(wifi.get('ipv4'),str) else None
        address=address or ('Waiting for a Wi-Fi address' if network else 'No Wi-Fi address')
        current={}
        for row in status or []:
            label,separator,value=row.partition(': ')
            if separator:current[label]=value
        return ScreenModel('facts-status','Diagnostics / Desktop link',facts=(
            Fact('Wi-Fi',connection),
            Fact('Deck IPv4',address),
            Fact('Desktop link','Open NDI on your computer'),
            Fact('Diagnostics','Select your Deck, then Run diagnostics'),
            Fact('Build',current.get('Build','Unavailable'))),
            notice='Open Nodes to connect to your computer. NDI uses that connection to find this Deck and save its diagnostics.',actions=(back,home))
    if state.page=='about':
        current={}
        for row in status or []:
            label,separator,value=row.partition(': ')
            if separator:current[label]=value
        return ScreenModel('facts-status','About / GuideOS',facts=(
            Fact('Release',current.get('GuideOS','Unavailable')),
            Fact('Build ID',current.get('Build','Unavailable')),
            Fact('Hardware','Anbernic RG35XX H'),
            Fact('Architecture',os.uname().machine),
            Fact('Kernel',os.uname().release)),
            notice='Build and hardware identity for this Deck.',actions=(back,home))
    if state.page=='unavailable':
        return ScreenModel('field-list','Unavailable',notice=state.unavailable_message,actions=(back,home))
    if state.page=='storage':
        rows=state.storage_panel.rows() if state.storage_panel else [('Status','Card service unavailable')]
        return ScreenModel('facts-status','External Card',facts=tuple(Fact(*r) for r in rows),actions=(ActionHint('A','Cartridges','blue','cartridges','key',305),back,home))
    if state.page=='audio-test':
        active=bool(state.audio_panel and state.audio_panel.status.get('test_active'))
        message=(state.audio_panel.notice or state.audio_panel.status.get('test_message','')) if state.audio_panel else 'Audio service unavailable'
        return ScreenModel('field-list','Audio',items=(MenuItem('audio:test','Test speakers','audio-row','test',enabled=not active),),focus_id='audio:test',notice=message)
    if state.page=='power':
        return ScreenModel('field-confirm','Power / Safe shutdown',notice='Confirm to shut down safely. Opening this screen does not turn off the Deck.',items=(MenuItem('power:confirm','Confirm shutdown','key',305),MenuItem('power:cancel','Cancel','key',304)),focus_id=('power:confirm','power:cancel')[state.power_selection],actions=(back,home))
    if state.page in ('media','audio'):
        panel=state.audio_panel
        if not panel:return ScreenModel('field-list',state.page.title(),notice='Audio service is not installed.',actions=(back,home))
        rows=panel.rows();focus=rows[min(panel.cursor,len(rows)-1)][0]
        if state.page=='audio':
            title={'audio':'Audio','outputs':'Audio / Output','bluetooth':'Audio / Bluetooth earbuds'}.get(panel.view,'Audio')
            message=(panel.status.get('bluetooth_message') or 'No Bluetooth information available.') if panel.view=='bluetooth' else panel.output_summary()
            notice=' · '.join(part for part in (message,panel.notice) if part)
            return ScreenModel('field-list',title,items=tuple(MenuItem('audio:'+i,l,'audio-row',i) for i,l in rows),focus_id='audio:'+focus,notice=notice,actions=actions)
        notice=panel.notice or {'library':'Choose Music or Video','music':'Choose music','video':'Choose a video'}.get(panel.view,'')
        if panel.view=='player' and getattr(panel,'current',None):
            current=panel.current;playback=panel.playback
            if current.get('kind')==2:
                primary=panel.primary_control()
                video_actions=((ActionHint('A',primary[1],'blue','audio:'+primary[0],'audio-row',primary[0]),)
                               if panel.control_enabled(primary[0]) else ())
                return ScreenModel('facts-status','Video',facts=(
                    Fact('Title',current.get('title','Untitled')),
                    Fact('Source',current.get('folder') or 'External storage'),
                    Fact('State',playback.get('state','opening'))),
                    notice=panel.notice,actions=video_actions+(back,home))
            controls=rows[:3]
            return ScreenModel('audio-player','Music Player',facts=(
                Fact('Title',current.get('title','Untitled')),
                Fact('Source',current.get('folder') or 'External storage'),
                Fact('Output',playback.get('output') or 'Deck speakers'),
                Fact('Elapsed',str(max(0,int(playback.get('position') or 0))//1000)),
                Fact('Duration',str(max(0,int(playback['duration']))//1000) if playback.get('duration') is not None else ''),
                Fact('State',playback.get('state','opening'))),
                items=tuple(MenuItem('audio:'+i,l,'audio-row',i,enabled=panel.control_enabled(i)) for i,l in controls),
                focus_id='audio:'+controls[min(panel.cursor,len(controls)-1)][0],notice=panel.notice,actions=(back,home))
        records={str(r['id']):r for r in getattr(panel,'items',[])}
        descriptions={'music':'Audio recordings on the external card','video':'Video recordings on the external card',
                      'refresh-media':'Reload the card catalogue','next-media':'More recordings','first-media':'Return to the first page'}
        items=[]
        for identity,label in rows:
            record=records.get(identity[6:]) if identity.startswith('media:') else None
            detail=(' · '.join(part for part in (record.get('folder') or 'External card',Path(label).suffix[1:].upper()) if part)
                    if record else descriptions.get(identity,''))
            items.append(MenuItem('audio:'+identity,label,'audio-row',identity,
                                  enabled=getattr(panel,'control_enabled',lambda _:True)(identity),metadata=detail))
        return ScreenModel('media-library','Media Library',items=tuple(items),focus_id='audio:'+focus,
                           notice=panel.notice,actions=actions)
    panel=state.wifi_panel
    if panel is None:
        return ScreenModel('field-list','Wi-Fi',notice=state.wifi.get('message','Unavailable'),items=(MenuItem('wifi:scan','Rescan','key',305),),focus_id='wifi:scan',actions=actions)
    if panel.editor is not None:return ScreenModel('field-list','Wi-Fi / Password')
    items=[];focus=None;notice=panel.notice or panel.status.get('message','')
    if panel.view=='list':
        for i,label in panel.rows():
            row=next((r for r in panel.status.get('networks',[]) if r['id']==i),None)
            if row:
                detail=('connected' if row['active'] else 'saved' if row['saved'] else row['security'])+' / '+(str(row['signal'])+'%' if row['available'] else 'out of range')
                label=label+'  Â·  '+detail
            items.append(MenuItem('wifi:row:'+i,label,'wifi-row',i))
        focus=items[min(panel.cursor,len(items)-1)].identity
    elif panel.view in ('detail','forget'):
        row=panel.selected()
        notice='Network no longer available' if not row else row['ssid']+' / '+row['security']+' / '+(str(row['signal'])+'% signal' if row['available'] else 'out of range')
        if row and panel.view=='forget':
            notice+=' â€” Remove saved credentials? This also disconnects an active network.'
            items=[MenuItem('wifi:confirm-forget:'+str(panel.target),'Forget network','key',305)]
        elif row:
            items=[MenuItem(('wifi:disconnect:' if row['active'] else 'wifi:connect:')+panel.target,'Disconnect' if row['active'] else 'Connect / switch','wifi-detail',0)]
            if row['saved']:items.append(MenuItem('wifi:forget:'+panel.target,'Forget saved network','wifi-detail',1))
        if items:focus=items[min(panel.detail_cursor,len(items)-1)].identity
    elif panel.view=='working':
        notice=panel.notice if panel.pending_token else panel.status.get('message','')
        actions=(replace(back,label='Cancel' if panel.status.get('busy') or panel.pending_token else 'Back'),home)
    return ScreenModel('field-list','Wi-Fi / '+panel.view.title(),items=tuple(items),focus_id=focus,notice=notice,actions=actions)
