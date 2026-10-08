"""Deck media layouts adapted by visual analysis of the owner-approved drafts.

All text is live, clipped and measured. Draft pixels are never a runtime asset.
The existing semantic model supplies identities, actions and provider values.
"""
from PIL import Image, ImageDraw
from dataclasses import replace
from guide_ui_model import LayoutResult, Rect, Region

GROUND='#142936'
FIELD='#cee2ef'
PANEL='#d5dde3'
ROW='#4e6575'
SELECTED='#446a82'
INK='#213a49'
PRIMARY='#f2f7fa'
SECONDARY='#c4e6ed'
FOCUS='#eba52e'
DISABLED='#738694'


def clock_text(value,unknown='--:--'):
    try:seconds=max(0,int(value))
    except (ValueError,TypeError):return unknown
    return (f'{seconds//3600}:{seconds//60%60:02d}:{seconds%60:02d}' if seconds>=3600
            else f'{seconds//60}:{seconds%60:02d}')


class DeckLayouts:
    PATTERNS=('media-library','audio-player','file-details','deck-facts')

    def __init__(self,text):self.text=text

    def title_lines(self,value):
        return self.text.titles.get(str(value),lambda:self._title_lines(value),lambda v:len(v.encode('utf-8')))

    def _title_lines(self,value):
        """Balance a two-line title; preserve longer values for viewport scrolling."""
        value=str(value)
        if '\n' in value or len(self.text.lines(value,24,584))!=2:return value
        choices=[]
        for index,c in enumerate(value):
            if c!=' ':continue
            left,right=value[:index],value[index+1:]
            if right.startswith(('—','–')):continue
            a,b=self.text.width(left,24),self.text.width(right,24)
            if max(a,b)<=584:choices.append((abs(a-b),left+'\n'+right))
        return min(choices,key=lambda item:item[0])[1] if choices else value

    def button(self,image,regions,item,rect,selected=False,ready=True):
        draw=ImageDraw.Draw(image)
        draw.rectangle(rect,fill=SELECTED if selected and item.enabled else ROW)
        if selected and item.enabled:draw.rectangle(rect,outline=FOCUS,width=3)
        label=self.text.shorten(item.label,20,rect[2]-rect[0]-24,bold=True)
        width=round(self.text.width(label,20,bold=True))
        self.text.draw(image,((rect[0]+rect[2]-width)//2,rect[1]+13,width+2,30),
                       label,20,PRIMARY if item.enabled else '#bac5cd',bold=True)
        if item.enabled and ready:regions.append(Region(item.identity,item.label,Rect(*rect),item.action,item.value))

    def chrome(self,model,regions):
        image=Image.new('RGB',(640,480),GROUND);draw=ImageDraw.Draw(image)
        draw.rectangle((0,28,639,91),fill=PANEL)
        draw.rectangle((0,92,639,431),fill=FIELD)
        self.text.draw(image,(16,2,300,24),'GuideOS',14,PANEL)
        back=next((a for a in model.actions if a.identity=='back' or a.value==304),None)
        refresh=next((item for item in model.items if item.value=='refresh-media'),None) if model.pattern=='media-library' else None
        self.text.draw(image,(16,40,370 if refresh else 486 if back else 608,44),model.title,28,INK,
                       policy='scroll',key='deck-heading',bold=True)
        if back:
            rect=(516,37,624,81)
            self.text.draw(image,(526,47,96,30),'B Back',20,INK,bold=True)
            regions.append(Region('back',back.label,Rect(*rect),'key',304))
        if refresh:self.button(image,regions,replace(refresh,label='Refresh'),(398,37,503,81),refresh.identity==model.focus_id)
        return image

    def footer(self,image,value):
        self.text.draw(image,(16,442,608,30),value,20,PANEL)

    def library(self,image,model,regions):
        draw=ImageDraw.Draw(image)
        rows=[item for item in model.items if item.value!='refresh-media']
        focus=next((i for i,item in enumerate(rows) if item.identity==model.focus_id),0)
        first=(focus//4)*4
        for index,item in enumerate(rows[first:first+4]):
            top=100+index*56;rect=(16,top,623,top+55)
            selected=item.identity==model.focus_id
            draw.rectangle(rect,fill=SELECTED if selected and item.enabled else ROW)
            if selected and item.enabled:draw.rectangle((16,top,19,top+55),fill=FOCUS)
            self.text.draw(image,(32,top+1,580,32),item.label,24,
                           PRIMARY if item.enabled else '#bac5cd',policy='filename',bold=selected)
            self.text.draw(image,(32,top+28,580,28),item.metadata,20,SECONDARY)
            if item.enabled:regions.append(Region(item.identity,item.label,Rect(*rect),item.action,item.value))
        draw.rectangle((16,332,623,423),fill=PANEL)
        item=next((item for item in model.items if item.identity==model.focus_id),rows[focus] if rows else None)
        value=item.label if item else 'No recordings available.'
        progress=self.text.draw(image,(28,360,584,64),self.title_lines(value),24,INK,policy='scroll',key=('selected',item.identity if item else None))
        caption=model.notice or ('Selected file · Full name' if item and item.action=='audio-row' and str(item.value).startswith('media:') else 'Selected option · Full name')
        if progress['overflow'] and not model.notice:caption+=' · More below ↓' if not progress['offset'] else ' · Scrolled ↑'
        self.text.draw(image,(28,336,584,28),caption,20,INK,policy='scroll',key='library-notice')
        action='Play' if item and str(item.value).startswith('media:') else 'Select'
        self.footer(image,f'↑↓ Select   A {action}   B Back   Menu Home')

    def player(self,image,model,regions):
        draw=ImageDraw.Draw(image);facts={fact.label:fact.value for fact in model.facts}
        draw.rectangle((16,100,623,191),fill=PANEL)
        progress=self.text.draw(image,(28,126,584,64),self.title_lines(facts.get('Title','Untitled')),24,INK,policy='scroll',key='player-title')
        caption=facts.get('State','opening').title()+' · Full title'
        if progress['overflow']:caption+=' · More below ↓' if not progress['offset'] else ' · Scrolled ↑'
        self.text.draw(image,(28,104,584,28),caption,20,INK)
        for y,label in ((200,'Source'),(224,'Output')):
            self.text.draw(image,(16,y,608,28),label+': '+facts.get(label,'Unavailable'),20,INK,policy='scroll',key='player-'+label)
        try:elapsed=max(0,int(facts.get('Elapsed') or 0));duration=max(0,int(facts.get('Duration') or 0))
        except (ValueError,TypeError):elapsed=duration=0
        draw.rectangle((16,256,623,263),fill=PANEL)
        width=round(608*min(1,elapsed/duration)) if duration else 0
        if width:draw.rectangle((16,256,15+width,263),fill=INK)
        self.text.draw(image,(16,270,300,30),clock_text(elapsed),20,INK)
        total=clock_text(duration) if duration else '--:--'
        total_width=round(self.text.width(total,20))
        self.text.draw(image,(624-total_width,270,total_width+2,30),total,20,INK)
        for index,item in enumerate(model.items[:3]):
            left=16+index*212
            self.button(image,regions,item,(left,312,left+183,367),item.identity==model.focus_id)
        draw.rectangle((16,376,623,423),fill=PANEL)
        paused=facts.get('State')=='paused'
        note=model.notice or (f'Resume continues from {clock_text(elapsed)}.' if paused else 'Playback continues when you return.')
        self.text.draw(image,(28,380,584,40),note,20,INK,policy='scroll',key='player-notice')
        primary=model.items[1].label if len(model.items)>1 else 'Play'
        self.footer(image,f'A {primary}   B Return   Menu Home')

    def details(self,image,model,regions):
        draw=ImageDraw.Draw(image);facts={fact.label:fact.value for fact in model.facts}
        for label,rect,box in (('Name',(16,100,623,203),(28,132,584,64)),
                               ('Folder',(16,212,623,303),(28,240,584,64))):
            draw.rectangle(rect,fill=PANEL)
            value=facts.get(label,'Unavailable')
            progress=self.text.draw(image,box,self.title_lines(value) if label=='Name' else value,24,INK,policy='scroll',key='details-'+label)
            caption=label
            if progress['overflow']:caption+=' · More below ↓' if not progress['offset'] else ' · Scrolled ↑'
            self.text.draw(image,(28,rect[1]+4,584,28),caption,20,INK)
        extension=facts.get('Extension','').upper()
        kind='folder' if facts.get('Type')=='Folder' else 'audio' if extension in ('AAC','FLAC','M4A','MP3','OGG','OPUS','WAV') else 'video' if extension in ('AVI','M4V','MKV','MOV','MP4','MPEG','MPG','WEBM') else 'file'
        size=facts.get('Size','Unknown')
        try:
            size_bytes=int(size.split(' ')[0].replace(',',''))
            size=f'{size_bytes/1_000_000:g} MB' if size_bytes>=1_000_000 else f'{size_bytes/1000:g} KB' if size_bytes>=1000 else f'{size_bytes} bytes'
        except ValueError:pass
        metadata=(' '.join(p for p in (extension if extension not in ('NONE','NOT APPLICABLE') else '',kind) if p)+' · '+size)
        if facts.get('Duration'):metadata+=' · '+clock_text(facts['Duration'])
        self.text.draw(image,(16,312,608,28),metadata,20,INK)
        for index,item in enumerate(model.items[:3]):
            left=16+index*212
            self.button(image,regions,item,(left,344,left+183,399),item.identity==model.focus_id,model.transition>.95)
        self.text.draw(image,(16,402,608,28),model.notice,20,INK,policy='scroll',key='details-notice')
        self.footer(image,'←→ Browse   A Select   B Return   Menu Home')

    def facts(self,image,model,regions):
        draw=ImageDraw.Draw(image);draw.rectangle((16,100,623,327),fill=PANEL)
        body='\n\n'.join(str(f.label)+'\n'+str(f.value) for f in model.facts)
        self.text.draw(image,(28,108,584,212),body,24,INK,policy='scroll',key='complete-file-details')
        for item in model.items[:1]:self.button(image,regions,item,(16,344,307,399),True)
        self.footer(image,'A Return to summary   B Back   Menu Home')

    def render(self,model):
        regions=[];self.text.scrolling=False
        image=self.chrome(model,regions)
        method={'media-library':self.library,'audio-player':self.player,
                'file-details':self.details,'deck-facts':self.facts}[model.pattern]
        method(image,model,regions)
        return LayoutResult(image,tuple(regions),tuple(r.identity for r in regions))
