"""Shell-rendered semantic notes/document surfaces; no app/device ownership."""
from PIL import Image,ImageDraw
import unicodedata
from guide_deck_layouts import GROUND,FIELD,PANEL,SELECTED,INK,PRIMARY,FOCUS
from guide_ui_model import LayoutResult,Rect,Region

class ApplicationViews:
    def __init__(self,text):self.text=text;self.max_scroll=0
    def draw_text(self,image,box,value,size=24,color=INK,bold=False):
        return self.text.draw(image,box,value,size,color,policy='wrap',bold=bold)
    def chrome(self,model):
        image=Image.new('RGB',(640,480),GROUND);draw=ImageDraw.Draw(image)
        draw.rectangle((0,28,639,91),fill=PANEL);draw.rectangle((0,92,639,431),fill=FIELD)
        self.draw_text(image,(16,2,300,24),'GuideOS',14,PANEL)
        self.draw_text(image,(16,40,475,44),model.title,28,INK,True)
        self.draw_text(image,(506,48,124,30),'Menu Home',16,INK)
        return image,[Region('app-home','Home',Rect(500,37,630,81),'key',316)]
    def key(self,image,regions,x,button,label,item=None,width=135):
        draw=ImageDraw.Draw(image);draw.rounded_rectangle((x,445,x+26,471),5,fill=PANEL)
        self.draw_text(image,(x+6,445,22,28),button,16,INK,True)
        self.draw_text(image,(x+35,443,width-35,30),label,20,PANEL)
        if item:regions.append(Region(item.identity,item.label,Rect(x,440,x+width,479),item.action,item.value))
    def render(self,model):
        image,regions=self.chrome(model);draw=ImageDraw.Draw(image);self.text.scrolling=False
        facts={f.label:f.value for f in model.facts};visible=[]
        if model.pattern=='application-notes':
            self.draw_text(image,(18,104,470,30),model.notice or facts['Location'],18,'#3c5969')
            self.draw_text(image,(552,104,80,30),str(max(0,len(model.items)-1))+' notes',16,'#3c5969')
            first=model.items[0];selected=model.focus_id==first.identity
            draw.rounded_rectangle((16,139,624,194),7,fill=SELECTED,outline=FOCUS if selected else None,width=3)
            draw.line((40,158,40,176),fill=PRIMARY,width=2);draw.line((31,167,49,167),fill=PRIMARY,width=2)
            self.draw_text(image,(66,149,540,37),first.label,24,PRIMARY,True)
            regions.append(Region(first.identity,first.label,Rect(16,139,624,194),first.action,first.value));visible.append(first.identity)
            notes=model.items[1:];focus=next((i for i,r in enumerate(notes) if r.identity==model.focus_id),0)
            start=max(0,min(focus-1,len(notes)-3))
            for i,row in enumerate(notes[start:start+3]):
                y=208+i*69;selected=row.identity==model.focus_id
                draw.rounded_rectangle((16,y,624,y+61),6,fill=PANEL,outline=FOCUS if selected else None,width=3)
                self.draw_text(image,(31,y+2,576,30),row.label,24,INK,True)
                self.draw_text(image,(31,y+33,576,25),row.metadata,18,'#3c5969')
                regions.append(Region(row.identity,row.label,Rect(16,y,624,y+61),row.action,row.value));visible.append(row.identity)
            if len(notes)>3:self.draw_text(image,(610,202,22,228),'↕',18,'#3c5969')
            if not notes:self.draw_text(image,(25,215,582,100),model.notice or 'No notes yet. Select New note to begin.',24,INK)
            self.key(image,regions,18,'A','Select');self.key(image,regions,182,'B','Back')
            regions.append(Region('app-back','Back',Rect(182,440,320,479),'key',304))
            self.draw_text(image,(391,443,237,32),'↑↓ Choose a note',18,PANEL)
        elif model.pattern=='application-document':
            self.draw_text(image,(18,104,604,38),facts['Name'],28,INK,True)
            self.draw_text(image,(19,147,330,28),facts['Location'],18,'#3c5969')
            status='Saved' if facts['Status']=='saved' else 'Unsaved changes'
            color='#386e58' if facts['Status']=='saved' else '#86531b'
            self.draw_text(image,(398,147,226,28),status,18,color)
            draw.rounded_rectangle((16,181,624,405),6,fill='#e5eff3')
            display=''.join(c if c in '\n\t' or unicodedata.category(c)!='Cc' else '�' for c in model.content)
            lines=self.text.lines(display or '(Empty note)',24,555)
            self.max_scroll=max(0,len(lines)-6);offset=min(self.max_scroll,max(0,model.scroll))
            for i,line in enumerate(lines[offset:offset+6]):self.draw_text(image,(31,190+i*34,564,33),line,24,INK)
            if self.max_scroll:
                draw.rounded_rectangle((609,195,613,390),2,fill='#c4d6df')
                thumb=max(10,round(195*6/len(lines)));top=195+round((195-thumb)*offset/self.max_scroll)
                draw.rounded_rectangle((609,top,613,top+thumb),2,fill='#839cab')
            if model.notice:
                draw.rounded_rectangle((16,332,624,429),6,fill=PANEL,outline=FOCUS,width=2)
                self.draw_text(image,(28,339,582,85),model.notice,18,INK)
            else:self.draw_text(image,(18,408,604,22),'↑↓ Scroll',16,'#3c5969')
            for i,(x,button,label,width) in enumerate(((18,'A','Edit',132),(160,'Y','Save',138),(308,'X','Actions',174),(492,'B','Notes',138))):
                self.key(image,regions,x,button,label,model.items[i],width);visible.append(model.items[i].identity)
        else:
            self.draw_text(image,(18,108,604,80),model.notice,24,INK)
            focus=next((i for i,row in enumerate(model.items) if row.identity==model.focus_id),0)
            start=max(0,min(focus-1,len(model.items)-3))
            for i,row in enumerate(model.items[start:start+3]):
                y=210+i*65;draw.rounded_rectangle((16,y,624,y+57),6,fill=PANEL,outline=FOCUS if row.identity==model.focus_id else None,width=3)
                self.draw_text(image,(31,y+10,576,38),row.label,24,INK,True)
                regions.append(Region(row.identity,row.label,Rect(16,y,624,y+57),row.action,row.value));visible.append(row.identity)
            self.key(image,regions,18,'A','Select');self.key(image,regions,182,'B','Back')
            regions.append(Region('app-back','Back',Rect(182,440,320,479),'key',304))
        return LayoutResult(image,tuple(regions),tuple(visible))
