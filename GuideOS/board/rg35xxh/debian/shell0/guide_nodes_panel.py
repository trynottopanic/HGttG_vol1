"""Bounded Node Link discovery and pairing UI adapter."""
import json, subprocess, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from guide_ui_model import ScreenModel, MenuItem, ActionHint
from guide_input import TextEntryManager, TextRequest, Keyboard, StickController, KEYBOARD_ACTIONS, renderer

LOCAL_BRIDGE=Path(__file__).resolve().with_name('guide_node_bridge.py')
BRIDGE=str(LOCAL_BRIDGE) if LOCAL_BRIDGE.is_file() else '/usr/lib/guideos/node-link/guide_node_bridge.py'
A,B,MENU,UP,DOWN=305,304,316,544,545
class NodesPanel:
    def __init__(self,text_entries=None):
        self.text_entries=text_entries or TextEntryManager(); self.nodes=[]; self.cursor=0
        self.view='list'; self.selected_index='0'; self.notice='Select Scan to find Desktop Nodes.'; self.capabilities=[]
        self.editor=None; self.stick_input=None; self.keyboard_renderer=None; self.next_scan=0
        self.trusted=False;self.trust_known=False
        self.worker=ThreadPoolExecutor(max_workers=1,thread_name_prefix='node-link');self.pending=None;self.pending_verb=''
    def refresh_trust(self):
        self.trusted=False;self.trust_known=False
        try:
            session_path=Path('/run/guideos-node-session.json')
            trust_path=Path('/var/lib/guideos/node-link/trusted-nodes.json')
            if session_path.stat().st_size>65536:raise ValueError('Session too large')
            session=json.loads(session_path.read_text())
            node_id=session['description']['node_id']
            if trust_path.exists():
                if trust_path.stat().st_size>65536:raise ValueError('Trust record too large')
                trusted=json.loads(trust_path.read_text())
                if not isinstance(trusted,dict):raise ValueError('Invalid trust record')
                self.trusted=node_id in trusted
            self.trust_known=True
        except (OSError,ValueError,KeyError,TypeError):pass
    @staticmethod
    def command(*args,input_text=None):
        try:
            r=subprocess.run(['/usr/bin/python3',BRIDGE,*args],input=(input_text or '').encode(),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=30,check=False)
            output=r.stdout.decode('ascii','replace')[:4096]
            if r.returncode:
                error=next((line[6:] for line in output.splitlines() if line.startswith('ERROR=')),'Node did not answer. Check NDI is open and try again.')
                return '',error[:160]
            return output,''
        except (OSError,subprocess.TimeoutExpired) as error:
            return '',str(error)[:160]
    def request(self,verb,*args,input_text=None):
        if self.pending is not None:return
        self.pending_verb=verb
        self.pending=self.worker.submit(self.command,*args,input_text=input_text)
        self.notice={'discover':'Looking for your computers…','pair':'Connecting…','trust':'Remembering this computer…','untrust':'Forgetting this computer…','unpair':'Disconnecting…','status':'Reading connection status…'}.get(verb,'Connecting…')
    def poll(self):
        if self.pending is None or not self.pending.done():return False
        out,error=self.pending.result();verb=self.pending_verb;self.pending=None;self.pending_verb=''
        if error:self.notice=error;return True
        if verb=='discover':
            self.nodes=[]
            for line in out.splitlines():
                if line.startswith('NODE='):
                    parts=line[5:].split('\t')
                    if len(parts)>=4:self.nodes.append((parts[0],parts[1][:64]))
            self.cursor=0;self.view='list'
            self.notice=f'{len(self.nodes)} computer(s) found.' if self.nodes else 'No computers found. Open NDI on the same network, then scan again.'
            if any(line.startswith('TRUSTED=') for line in out.splitlines()):
                self.view='session';self.refresh_trust();self.notice='Reconnected to your remembered computer.'
        elif verb=='pair':
            self.view='session';self.refresh_trust();self.cursor=0
            self.notice='Connected. Choose Remember this computer to reconnect without a code.'
        elif verb=='status':
            self.capabilities=[line[11:].replace('\t','  ') for line in out.splitlines() if line.startswith('CAPABILITY=')]
            self.refresh_trust();self.notice='Connection ready.'
        elif verb in ('trust','untrust','unpair'):
            self.refresh_trust();self.cursor=0
            self.notice={'trust':'Computer remembered. Future connections use this relationship.','untrust':'Computer forgotten. Enter its code to connect again.','unpair':'Disconnected.'}[verb]
            if verb in ('untrust','unpair'):self.view='list';self.capabilities=[]
        return True
    def scan(self):
        self.request('discover','discover')
    def model(self):
        actions=(ActionHint('A','Select','blue'),ActionHint('B','Back','blue','back','key',B),ActionHint('Menu','Home','blue','home','key',MENU))
        if self.view=='pair':
            rows=(MenuItem('nodes:pair','Enter NDI code','nodes-row','pair'),)
        elif self.view=='session':
            rows=(MenuItem('nodes:status','Refresh Node status','nodes-row','status'),)
            if self.trust_known:
                rows+=(MenuItem('nodes:revoke','Forget this computer','nodes-row','untrust') if self.trusted else MenuItem('nodes:trust','Remember this computer','nodes-row','trust'),)
            rows+=(MenuItem('nodes:disconnect','Disconnect','nodes-row','unpair'),)
            if self.capabilities: rows+=tuple(MenuItem('nodes:cap:'+str(i),c,'disabled',None,False) for i,c in enumerate(self.capabilities[:8]))
        else:
            rows=(MenuItem('nodes:scan','Scan for Nodes','nodes-row','scan'),)+tuple(MenuItem('nodes:node:'+i,n,'nodes-row','select:'+i) for i,n in self.nodes)
        focus=rows[min(self.cursor,len(rows)-1)].identity if rows else None
        return ScreenModel('field-list','Nodes / '+self.view.title(),items=rows,focus_id=focus,notice=self.notice,actions=actions)
    def action(self,verb):
        if verb=='scan': self.scan(); return
        if verb.startswith('select:'):
            self.selected_index=verb.split(':',1)[1]; self.cursor=0
            self.view='pair'; self.notice='Enter the six-digit code shown in NDI.'
            self.action('pair')
            return
        if verb in ('status','trust','untrust','unpair'):
            self.request(verb,verb);return
        if verb=='pair' and self.view=='pair':
            self.editor=Keyboard(self.text_entries,TextRequest(owner_id='system.nodes',field_id='pair-code',label='Node pairing code',purpose='verification-code',secret=True,min_length=6,max_length=6,max_bytes=6,allowed_characters='0123456789',submit_label='PAIR'))
            self.stick_input=StickController(self.editor)
    def draw_editor(self,sink):
        if self.keyboard_renderer is None:self.keyboard_renderer=renderer()
        sink.show(self.keyboard_renderer.render(self.editor,application_label="NODE PAIRING"))

    def finish(self):
        if not self.editor or self.editor.session.state=='editing':return
        result=self.editor.take_result();self.editor=None;self.stick_input=None
        if result and result.state=='submitted':
            self.request('pair','pair-input',input_text=self.selected_index+' '+result.text);result=None
    def sticks(self,sample,now=None):
        if not self.editor:return False
        changed=self.stick_input.update(left=sample.get('left'),right=None if sample.get('right_click') else sample.get('right'),generation=sample.get('generation',0),now=now);self.finish();return changed
    def key(self,code):
        if code==MENU:
            if self.editor:self.editor.handle('cancel');self.finish()
            return 'home'
        if self.editor and code==B:
            self.editor.handle('cancel');self.finish();self.view='list';self.cursor=0
            self.notice='Pairing cancelled.';return 'changed'
        if self.editor:
            self.editor.handle(KEYBOARD_ACTIONS.get(code));self.finish();return 'changed'
        if code==B:
            if self.view in ('list','session'):return 'home'
            self.view='list';self.cursor=0;return 'changed'
        if code in (UP,DOWN):
            rows=self.model().items
            enabled=[i for i,row in enumerate(rows) if row.enabled]
            if enabled:
                position=enabled.index(self.cursor) if self.cursor in enabled else 0
                self.cursor=enabled[(position+(-1 if code==UP else 1))%len(enabled)]
            return 'changed'
        if code==A:
            if self.pending is not None:return False
            rows=self.model().items
            if rows:
                row=rows[min(self.cursor,len(rows)-1)]
                if row.enabled and row.value:self.action(row.value)
            return 'changed'
        return False
