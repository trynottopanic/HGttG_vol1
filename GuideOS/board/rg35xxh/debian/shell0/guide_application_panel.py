"""Shell-owned, asynchronous adapter for installed application views and input."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import socket
import sys
import time

for candidate in (Path('/usr/lib/guideos/application-host'),Path(__file__).resolve().parents[4]/'package/guide-foundation/python',Path('/usr/lib/guideos/ipc'),Path(__file__).resolve().parents[4]/'package/guide-ipc/python'):
    if candidate.is_dir():sys.path.insert(0,str(candidate))
from guide_application_runtime import request
from guide_input import Keyboard, TextRequest, StickController, KEYBOARD_ACTIONS, renderer

class ApplicationPanel:
    def __init__(self,code,text_entries):
        if type(code)is not int or not 10000<=code<=0xffffffff:raise ValueError('application code')
        self.code,self.text_entries=code,text_entries
        self.owner='application:'+str(code);self.identity=None;self.editor=None;self.stick_input=None
        self.keyboard_renderer=None;self.cursor=0;self.view=None;self.notice='Starting application…'
        self.closing=False;self.finished=False;self.failed=False;self.commands=[];self.next_poll=0
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='guide-app-io')
        self.pending=self.executor.submit(self.rpc,'/run/guideos/supervisor/control.sock',1,{0:code})
        self.operation='launch';self.close_deadline=None;self.close_text=None;self.close_text_failed=False;self.cancel_confirmation=False;self.editor_initial=''
        self.editor_metadata=False;self.document_scroll=0;self.scroll_limit=0;self.document_identity=None
        self.close_destination='back'
    @staticmethod
    def rpc(path,op,args):
        with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as sock:
            sock.settimeout(.3);sock.connect(path);return request(sock,op,args)
    def submit(self,op,args):
        if self.closing or len(self.commands)>=16:return False
        self.commands.append((op,args));return True
    def close_editor(self):
        if self.editor:self.editor.close()
        self.editor=self.stick_input=None
    def close(self):
        if self.closing:return
        if self.editor:
            self.close_text={0:self.editor.session.text,1:True}
            if getattr(self,'editor_metadata',False):self.close_text[2]=self.editor.session.cursor
        elif self.commands:
            submitted=[args for op,args in self.commands if op==3]
            if submitted:self.close_text=submitted[-1]
        self.close_editor();self.closing=True;self.view=None;self.commands=[]
        self.notice='Saving checkpoint…';self.close_deadline=time.monotonic()+3
    def poll(self):
        changed=False
        if self.pending is not None:
            if not self.pending.done():return False
            try:
                result=self.pending.result()
                if self.operation=='launch':self.identity=result
                elif self.operation=='status':
                    if result[0] in (7,8):
                        self.finished=result[1]==2 and not self.close_text_failed;self.failed=not self.finished
                        self.notice='Checkpoint saved.' if self.finished else 'Application stopped; checkpoint was not confirmed.'
                elif self.operation=='snapshot' and not self.closing:
                    old_actions=self.view[2] if self.view else []
                    self.view=result[1];self.notice='' if result[0] else 'Starting application…'
                    if self.view and self.view[2]!=old_actions:self.cursor=0
                    meta=self.presentation()
                    if meta.get(0)=='document':
                        identity=(meta[1],self.view[1])
                        if identity!=self.document_identity:self.document_scroll=0;self.document_identity=identity
                    text=result[2]
                    if text is None:self.close_editor()
                    elif self.editor is None:
                        self.editor_initial=text[0]
                        self.editor_metadata=2 in text
                        meta=text.get(2,{0:'Application text',1:True,2:len(text[0]),3:'Done'})
                        self.editor=Keyboard(self.text_entries,TextRequest(owner_id=self.owner,field_id='document' if meta[1] else 'name',label=meta[0],initial=text[0],multiline=meta[1],max_length=text[1],max_bytes=20480,submit_label=meta[3]))
                        self.editor.session.move(meta[2]-self.editor.session.cursor)
                        self.stick_input=StickController(self.editor)
            except (OSError,ValueError,KeyError,TypeError):
                # Disconnect/revocation clears private presentation immediately.
                self.close_editor();self.view=None
                self.notice='Application unavailable. Its last saved checkpoint is retained.'
                if self.operation=='launch':self.failed=True
                if self.operation=='close-text':self.close_text_failed=True
            self.pending=None;changed=True
        if self.finished or self.failed:return changed
        if self.closing and time.monotonic()>self.close_deadline:
            self.failed=True;self.notice='Stop timed out; checkpoint was not confirmed.';return True
        if self.identity is None:return changed
        if self.closing:
            if self.close_text is not None:
                path=f'/run/guideos/apps/{self.code}/shell.sock';op=3;args=self.close_text;self.close_text=None;self.operation='close-text'
            elif self.operation not in ('stop','status'):
                path='/run/guideos/supervisor/control.sock';op=3;args=self.identity;self.operation='stop'
            else:path='/run/guideos/supervisor/control.sock';op=4;args=self.identity;self.operation='status'
        elif self.commands:
            op,args=self.commands.pop(0);path=f'/run/guideos/apps/{self.code}/shell.sock';self.operation='command'
        else:
            if time.monotonic()<self.next_poll:return changed
            self.next_poll=time.monotonic()+.1;path=f'/run/guideos/apps/{self.code}/shell.sock';op=1;args={};self.operation='snapshot'
        self.pending=self.executor.submit(self.rpc,path,op,args);return changed
    def action(self,index):return self.submit(2,{0:index})
    def presentation(self):return (self.view or {}).get(3,{})
    def finish_editor(self, previous_text=None, previous_caret=None):
        if self.editor and self.editor.session.state!='editing':
            if self.editor.session.state=='cancelled' and previous_text is not None and previous_text!=self.editor_initial:
                request=replace(self.editor.session.request,initial=previous_text)
                self.close_editor()
                self.editor=Keyboard(self.text_entries,request)
                if previous_caret is not None:self.editor.session.move(previous_caret-self.editor.session.cursor)
                self.stick_input=StickController(self.editor);self.cancel_confirmation=True
                return
            result=self.editor.take_result();self.editor=self.stick_input=None
            if result is not None and result.state=='submitted':
                args={0:result.text}
                if getattr(self,'editor_metadata',False):args[2]=result.cursor
                self.submit(3,args)
            else:self.submit(6,{})
    def key(self,code):
        if self.cancel_confirmation and code!=316:
            if code==305:self.cancel_confirmation=False;self.close_editor();self.submit(6,{})
            elif code==304:self.cancel_confirmation=False
            return True
        if code==316:self.close_destination='home';self.close();return True
        if self.editor:
            before=self.editor.session.text;caret=self.editor.session.cursor
            self.editor.handle(KEYBOARD_ACTIONS.get(code))
            self.finish_editor(before,caret)
            return True
        meta=self.presentation();bindings=meta.get(5,{})
        if meta.get(0)=='document' and code in (544,545):
            self.document_scroll=max(0,min(self.scroll_limit,self.document_scroll+(1 if code==545 else -1)))
            return True
        action=bindings.get({305:0,307:1,308:2,304:3}.get(code,-1))
        if action is not None:self.action(action);return True
        if code==304:self.close();return True
        if self.view:
            if code in (544,545):self.cursor=max(0,min(len(self.view[2])-1,self.cursor+(1 if code==545 else -1)))
            elif code==305:self.action(self.cursor)
        return True
    def sticks(self,sample,now=None):
        if self.cancel_confirmation:return False
        if self.stick_input:
            before=self.editor.session.text;caret=self.editor.session.cursor
            changed=self.stick_input.update(left=sample.get('left'),right=None if sample.get('right_click') else sample.get('right'),generation=sample.get('generation',0),now=now)
            self.finish_editor(before,caret);return changed
        return False
    def model(self):
        from guide_ui_model import ScreenModel,MenuItem,ActionHint,Fact
        view=self.view or {0:'Application',1:self.notice,2:[]}
        meta=self.presentation();previews=meta.get(4,['']*len(view[2]))
        items=tuple(MenuItem('application:'+str(i),label,'application-action',i,metadata=previews[i]) for i,label in enumerate(view[2]))
        if meta.get(0)=='notes':
            return ScreenModel('application-notes',view[0],items=items,focus_id='application:'+str(self.cursor),notice=self.notice or view[1],facts=(Fact('Location',meta[1]),))
        if meta.get(0)=='document':
            ordered=tuple(items[meta[5][i]] for i in range(4))
            return ScreenModel('application-document',view[0],items=ordered,focus_id=ordered[0].identity,notice=self.notice or meta[6],content=view[1],scroll=self.document_scroll,facts=(Fact('Name',meta[1]),Fact('Location',meta[2]),Fact('Status',meta[3])))
        if meta.get(0)=='menu':return ScreenModel('application-menu',view[0],items=items,focus_id='application:'+str(self.cursor),notice=self.notice or view[1])
        return ScreenModel('field-list',view[0],items=items,focus_id='application:'+str(self.cursor),notice=self.notice or view[1],actions=(ActionHint('A','Select','blue'),ActionHint('Menu','Home','blue','home','key',316)))
    def draw_editor(self,sink):
        if self.keyboard_renderer is None:self.keyboard_renderer=renderer()
        image=self.keyboard_renderer.render(self.editor,application_label=self.view[0].split(' / ')[0].upper() if self.view else 'APPLICATION')
        if self.cancel_confirmation:
            from PIL import ImageDraw,ImageFont
            draw=ImageDraw.Draw(image);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',24)
            draw.rectangle((15,145,624,305),fill='#d9e7ee',outline='#244452',width=3)
            draw.text((35,170),'Discard these text-entry changes?',font=font,fill='#244452')
            draw.text((35,239),'A Discard    B Keep editing',font=font,fill='#244452')
        sink.show(image)
    def shutdown(self):
        self.close()
        deadline=time.monotonic()+3
        while not self.finished and not self.failed and time.monotonic()<deadline:self.poll();time.sleep(.02)
        self.executor.shutdown(wait=True,cancel_futures=True)
