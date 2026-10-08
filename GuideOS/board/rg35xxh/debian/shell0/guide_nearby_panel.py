"""Shell-owned nearby inspection, signal history and explicit network tools."""
import json
from pathlib import Path
import socket
import time
import uuid

from guide_input import TextEntryManager, TextRequest, Keyboard, StickController, KEYBOARD_ACTIONS, renderer
from guide_ui_model import ScreenModel, MenuItem, ActionHint, LayoutResult

UP,DOWN,LEFT,RIGHT,A,B,MENU=544,545,546,547,305,304,316
TOOLS=(('ports','Nmap: common TCP ports'),('services','Nmap: service details'),
       ('ping','Ping'),('dns','DNS lookup'),('route','Route trace'))


def text(value, length=180):
    return ''.join(c if c.isprintable() else ' ' for c in str(value))[:length]


class NearbyPanel:
    def __init__(self, runtime='/run/guideos-nearby', text_entries=None):
        self.runtime=Path(runtime); self.text_entries=text_entries if text_entries is not None else TextEntryManager()
        self.view='menu'; self.kind='wifi'; self.cursor=0; self.target=None; self.address=''
        self.profile='ports'; self.notice=''; self.editor=None; self.stick_input=None; self.keyboard_renderer=None
        self.status=dict(busy=False,rows=[],history=[],result={},message='Choose a survey or tool.')
        self.next_poll=0; self.next_heartbeat=0; self.signature=None; self.scroll=0; self.active=False

    def send(self, action, **values):
        try:
            with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as sock:
                sock.setblocking(False)
                sock.sendto(json.dumps(dict(action=action,token=uuid.uuid4().hex,**values)).encode(),str(self.runtime/'control.sock'))
            if action not in ('keepalive','cancel'): self.notice='Request sent...'
            return True
        except OSError:
            self.notice='Nearby service unavailable.'; return False

    def open(self): self.active=True

    def leave(self):
        if self.editor: self.editor.close()
        self.editor=None; self.stick_input=None; self.active=False
        self.send('cancel'); self.view='menu'; self.cursor=0

    def poll(self):
        now=time.monotonic()
        if not self.active: return False
        if now>=self.next_heartbeat:
            self.send('keepalive'); self.next_heartbeat=now+1
        if now<self.next_poll: return False
        self.next_poll=now+.25
        try:
            path=self.runtime/'status.json'
            if path.stat().st_size>128*1024: raise ValueError('Snapshot limit')
            value=json.loads(path.read_text())
            if now-value['observed']>3 or len(value['rows'])>64 or len(value['history'])>60: raise ValueError('Stale snapshot')
            old=self.rows()[min(self.cursor,len(self.rows())-1)][0]
            self.status=value; self.notice=''
            rows=self.rows(); ids=[r[0] for r in rows]
            self.cursor=ids.index(old) if old in ids else min(self.cursor,len(rows)-1)
            # The provider's timestamp changes every tick; only repaint when
            # visible observations or displayed reading ages change.
            stable={k:v for k,v in value.items() if k not in ('observed','generation')}
            signature=json.dumps(stable,sort_keys=True)+str(int(now))
        except (OSError,ValueError,KeyError,TypeError):
            self.status=dict(busy=False,rows=[],history=[],result={},message='Nearby service unavailable.'); signature='unavailable'
        changed=signature!=self.signature; self.signature=signature; return changed

    def selected(self): return next((r for r in self.status['rows'] if r['id']==self.target),None)

    def rows(self):
        if self.view=='menu': return [('wifi','Wi-Fi survey'),('bluetooth','Bluetooth explorer'),('tools','Network tools')]
        if self.view in ('wifi','bluetooth'):
            control=[('cancel','Stop discovery')] if self.status.get('busy') else [('rescan','Rescan')]
            if self.kind=='bluetooth' and self.status.get('message','').startswith('Bluetooth is off'):
                control=[('enable','Enable Bluetooth and scan')]
            return control+[(r['id'],r['name']) for r in self.status['rows'] if r['kind']==self.kind]
        if self.view=='detail': return [('watch','Watch signal')]
        if self.view=='watch': return [('cancel-watch','Stop signal watch')] if self.status.get('busy') else [('watch','Watch again')]
        if self.view=='tools': return [('target','Target: '+(self.address or 'set IP address / DNS name'))]+list(TOOLS)
        if self.view=='ready': return [('run','Run '+dict(TOOLS)[self.profile])]
        if self.view=='result': return [('cancel-tool','Cancel tool')] if self.status.get('busy') else [('again','Run again')]
        return [('back','Back')]

    def activate(self, identity):
        if identity in ('wifi','bluetooth'):
            self.kind=self.view=identity; self.cursor=0; self.target=None
            self.send('survey',kind=identity)
        elif identity=='tools': self.view='tools'; self.cursor=0
        elif identity in ('rescan','enable'):
            self.send('survey',kind=self.kind,power=identity=='enable')
        elif identity=='cancel': self.send('cancel')
        elif identity in ('watch','cancel-watch'):
            if identity=='cancel-watch': self.send('cancel')
            else:
                self.send('watch',kind=self.kind,id=self.target); self.view='watch'; self.cursor=0
        elif identity=='target': self.begin_editor()
        elif identity in dict(TOOLS):
            self.profile=identity
            if not self.address: self.begin_editor()
            else: self.view='ready'; self.cursor=0
        elif identity in ('run','again'):
            self.send('tool',profile=self.profile,target=self.address); self.view='result'; self.cursor=0; self.scroll=0
        elif identity=='cancel-tool': self.send('cancel')
        elif identity.startswith(('wifi:','bt:')):
            if not any(r['id']==identity for r in self.status['rows']): return False
            self.target=identity; self.view='detail'; self.cursor=0
        else: return False
        return True

    def begin_editor(self):
        self.editor=Keyboard(self.text_entries,TextRequest(owner_id='system.nearby',field_id='target',
            label='Target IP address / DNS name',initial=self.address,min_length=1,max_length=253,max_bytes=253,
            allowed_characters='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-:',submit_label='SET'))
        self.stick_input=StickController(self.editor)

    def finish_editor(self):
        if self.editor is None or self.editor.session.state=='editing': return
        result=self.editor.take_result(); self.editor=None; self.stick_input=None
        if result is not None and result.state=='submitted': self.address=result.text.strip()

    def sticks(self, sample, now=None):
        if not self.stick_input: return False
        changed=self.stick_input.update(left=sample.get('left'),right=sample.get('right'),generation=sample.get('generation',0),now=now)
        self.finish_editor(); return changed

    def key(self, code):
        if self.editor:
            if code==MENU: self.leave(); return 'home'
            self.editor.handle(KEYBOARD_ACTIONS.get(code,'noop')); self.finish_editor(); return 'changed'
        if code==MENU: self.leave(); return 'home'
        if code==B:
            if self.view=='menu': self.leave(); return 'home'
            if self.view in ('wifi','bluetooth','watch','result'): self.send('cancel')
            self.view={'detail':self.kind,'watch':'detail','ready':'tools','result':'tools'}.get(self.view,'menu')
            self.cursor=0; return 'changed'
        if code in (UP,DOWN,LEFT,RIGHT):
            if self.view=='result' and code in (LEFT,RIGHT):
                limit=max(0,len(self.status.get('result',{}).get('lines',[]))-8)
                self.scroll=max(0,min(limit,self.scroll+(5 if code==RIGHT else -5)))
            else: self.cursor=(self.cursor+(1 if code in (DOWN,RIGHT) else -1))%len(self.rows())
            return 'changed'
        if code==A: self.activate(self.rows()[self.cursor][0]); return 'changed'
        return None

    def age(self,row):
        if row.get('seen') is None: return 'No fresh sighting'
        return str(max(0,int(time.monotonic()-row['seen'])))+'s ago'

    def details(self, row):
        if row is None: return ['Observation is no longer available.']
        signal='Unknown' if row.get('signal') is None or row.get('seen') is None else str(row['signal'])+' '+row['unit']
        result=[row['name'], 'Address: '+row['address'], 'Signal: '+signal+' / '+self.age(row)]
        if row['kind']=='wifi': result += ['Channel: '+str(row.get('channel') or '?')+' / '+str(row.get('frequency',0))+' MHz',
                                         'Security: '+row['security']]
        else:
            result += ['Type: '+row.get('type','Unknown device type'),
                       'Paired: '+('yes' if row.get('paired') else 'no')+' / Connected: '+('yes' if row.get('connected') else 'no'),
                       'Address type: '+row.get('addressType','unknown'),
                       'Class: '+hex(row.get('deviceClass',0))+' / Appearance: '+str(row.get('appearance',0))]
            names={'0000110b-0000-1000-8000-00805f9b34fb':'Audio sink','00001124-0000-1000-8000-00805f9b34fb':'Human interface device',
                   '0000180f-0000-1000-8000-00805f9b34fb':'Battery service'}
            services=row.get('services',[])
            result += ['Services: '+(', '.join(names.get(s,s) for s in services) or 'None advertised')]
            if row.get('manufacturers'): result += ['Manufacturer IDs: '+', '.join(hex(v) for v in row['manufacturers'])]
        return result

    def model(self):
        actions=(ActionHint('B','Back','blue','back','key',B),ActionHint('Menu','Home','blue','home','key',MENU))
        rows=self.rows(); focus='nearby:'+rows[min(self.cursor,len(rows)-1)][0]
        items=[]
        for identity,label in rows:
            record=next((r for r in self.status['rows'] if r['id']==identity),None)
            detail=''
            if record:
                detail=(str(record['signal'])+' '+record['unit'] if record.get('seen') is not None and record.get('signal') is not None else 'Signal unknown')+' / '+self.age(record)
                if record['kind']=='wifi': detail+=' / Ch '+str(record.get('channel') or '?')+' / '+record['security']
            items.append(MenuItem('nearby:'+identity,text(label),'nearby-row',identity,metadata=text(detail)))
        title={'menu':'Nearby','wifi':'Wi-Fi survey','bluetooth':'Bluetooth explorer','tools':'Network tools',
               'detail':'Inspect','watch':'Signal watch','ready':dict(TOOLS)[self.profile],'result':dict(TOOLS)[self.profile]}[self.view]
        notice=self.notice or self.status.get('message','')
        if self.view=='menu': notice='Inspect Wi-Fi, Bluetooth and selected network targets.'
        if self.view=='tools': notice='Choose a target and a tool. Selecting it opens Run.'
        if self.view=='ready': notice='Target: '+self.address+' / '+('50 common TCP ports' if self.profile in ('ports','services') else dict(TOOLS)[self.profile])
        return ScreenModel('v3-list',title,items=tuple(items),focus_id=focus,notice=text(notice),actions=actions)

    def layout(self, schema):
        model=self.model()
        if self.view not in ('detail','watch','result'): return schema.render(model)
        from PIL import ImageDraw
        from guide_ui_model import Region, Rect
        base=schema.render(ScreenModel('facts-status',model.title,actions=model.actions)).image
        image=base.copy(); draw=ImageDraw.Draw(image)
        lines=(self.status.get('result',{}).get('lines',[]) if self.view=='result' else self.details(self.selected()))
        if self.view=='result': lines=lines[self.scroll:self.scroll+8]
        y=112
        for index,line in enumerate(lines[:5 if self.view=='watch' else 8]):
            schema.text.draw(image,(18,y,604,29),text(line),16,policy='scroll',key='nearby-detail:'+str(index)); y+=30
        if self.view=='watch':
            history=self.status.get('history',[]); box=(25,285,615,375)
            draw.rectangle(box,outline='#70869a')
            if len(history)>1:
                first=history[-1]['at']-60
                low,high=(0,100) if self.kind=='wifi' else (-110,-20)
                points=[(max(box[0],min(box[2],box[0]+(s['at']-first)/60*(box[2]-box[0]))),
                         box[3]-max(0,min(1,(s['value']-low)/(high-low)))*(box[3]-box[1])) for s in history]
                for point in points: draw.ellipse((point[0]-2,point[1]-2,point[0]+2,point[1]+2),fill='#81d9ef')
                for i in range(1,len(points)):
                    if history[i]['at']-history[i-1]['at'] <= (15 if self.kind=='wifi' else 3):
                        draw.line((points[i-1],points[i]),fill='#81d9ef',width=2)
            schema.text.draw(image,(25,377,590,24),'Sampled readings / last 60 seconds',14)
        schema.text.draw(image,(18,397,604,23),text(self.notice or self.status.get('message','')),14)
        row=self.rows()[0]; rect=(18,425,395,468)
        draw.rounded_rectangle(rect,6,fill='#294d65')
        schema.text.draw(image,(30,433,355,30),row[1],18)
        regions=(Region('nearby:'+row[0],row[1],Rect(*rect),'nearby-row',row[0]),
                 Region('back','Back',Rect(550,43,626,79),'key',B))
        return LayoutResult(image,regions,('nearby:'+row[0],))

    def draw_editor(self,sink):
        if self.keyboard_renderer is None: self.keyboard_renderer=renderer()
        sink.show(self.keyboard_renderer.render(self.editor,application_label='NETWORK TOOLS'))
