"""Native Music/Video views; all decoder and source work stays off the UI loop."""
import json,socket,time,subprocess
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from guide_audio_panel import AudioPanel, A, B, MENU

L1,R1,L2,R2=308,309,314,315
SELECT,UP,DOWN=314,544,545

class MediaPanel(AudioPanel):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.items=[];self.more=False;self.after=None;self.kind=1
        self.view='library';self.current=None;self.desired=None
        self.playback=dict(state='stopped',position=0,video=False)
        self.video_busy=False;self.display_pending=False;self.tasks=deque();self.future=None
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='media-control')
        self.next_media=0;self.closed=False;self.view_stack=[]
        self.playback_error=''
        self.video_options=False
        self.launch_generation=0;self.pending_launch=None;self.inflight=None
        self.cleanup_pending=False;self.cleanup_video=False;self.display_return_pending=False
    @staticmethod
    def request(request):
        with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as connection:
            # Cold decoder/GPU startup has its own eight-second provider bound.
            connection.settimeout(12);connection.connect('/run/guideos-player/control.sock')
            connection.send(json.dumps({k:v for k,v in request.items() if not k.startswith('_')}).encode())
            data=connection.recv(65537)
            if len(data)>65536:raise ValueError('Media response too large')
            reply=json.loads(data)
            if not reply.get('ok'):raise RuntimeError(reply.get('error','Media request failed'))
            return reply['result']
    @staticmethod
    def recover():
        # The system shell owns global recovery if the provider stops answering.
        try:subprocess.run(['systemctl','stop','guide-media-player.service'],timeout=5,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except (OSError,subprocess.SubprocessError):
            subprocess.run(['systemctl','kill','--kill-whom=all','--signal=SIGKILL','guide-media-player.service'],timeout=2,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            subprocess.run(['systemctl','stop','guide-media-player.service'],timeout=5,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return dict(state='stopped',position=0,video=False,message='Player stopped during recovery')
    def _sync_video(self):
        held=self.display_pending or self.cleanup_video or bool(self.playback.get('video'))
        if self.video_busy and not held:self.display_return_pending=True
        if held:self.display_return_pending=False
        self.video_busy=held
    def _cleanup(self,video=False,recover=False):
        # This barrier runs after the single worker's abandoned open, before any
        # replacement launch. Display ownership is retained until acknowledgement.
        self.cleanup_pending=True;self.cleanup_video=self.cleanup_video or video
        self.tasks=deque(r for r in self.tasks if r['action'] not in ('pause','resume','seek'))
        queued=next((r for r in self.tasks if r.get('_cleanup')),None)
        if queued is not None:
            if recover:queued['action']='recover'
        elif not (self.future is not None and self.inflight.get('_cleanup') and not recover):
            self.tasks.appendleft(dict(action='recover' if recover else 'stop',_cleanup=True))
        self._sync_video()
    def cancel_pending_launch(self):
        token=self.pending_launch
        self.launch_generation+=1;self.pending_launch=None;self.desired=None
        self.tasks=deque(r for r in self.tasks if '_launch' not in r)
        if (token is not None and self.future is not None and
                self.inflight.get('action')=='open' and self.inflight.get('_launch')==token):
            if self.future.cancel():self.future=None;self.inflight=None
            else:self._cleanup(video=bool(self.inflight.get('display')))
        self.display_pending=False;self._sync_video()
        return token is not None
    def queue(self,action,**args):
        if action=='stop':
            self.video_options=False
            self.cancel_pending_launch()
            self.tasks=deque(r for r in self.tasks if r.get('_cleanup'))
            if self.cleanup_pending:return True
        if action=='list':args.setdefault('_launch',self.launch_generation)
        if action=='video-options':args.setdefault('_video_generation',self.launch_generation)
        if len(self.tasks)>=4:return False
        self.tasks.append(dict(action=action,**args));return True
    def primary_control(self):
        if self.pending_launch is not None:return ('media-wait','Opening…')
        if self.cleanup_pending:return ('media-wait','Stopping…')
        stopping=any(r and r['action'] in ('stop','recover') for r in [self.inflight if self.future else None,*self.tasks])
        state='stopped' if stopping else self.playback.get('state')
        if state in ('playing','buffering','opening'):return ('media-pause','Pause')
        if state=='paused':return ('media-resume','Resume')
        return ('media-play','Play')
    def control_enabled(self,identity):
        if identity in ('media-previous','media-next'):
            if not self.current or self.current not in self.items:return False
            index=self.items.index(self.current)+(1 if identity=='media-next' else -1)
            return 0<=index<len(self.items)
        return identity!='media-wait' and (identity!='media-play' or self.current is not None)
    def rows(self):
        if self.view in ('audio','outputs','bluetooth'):return super().rows()
        if self.view=='player':
            return [('media-previous','Previous'),
                    self.primary_control(),
                    ('media-next','Next'),('media-stop','Stop')]
        if self.view in ('music','video'):
            rows=[('refresh-media','Refresh card files')]
            rows += [('media:'+r['id'],r['title']) for r in self.items]
            if self.more:rows.append(('next-media','Next page'))
            if self.after:rows.append(('first-media','First page'))
            return rows
        return [('music','Music on card'),('video','Video on card')]
    def open_item(self,item):
        self.cancel_pending_launch()
        self.tasks=deque(r for r in self.tasks if r['action'] in ('stop','recover'))
        if item['kind']==2 and not self.video_busy and not getattr(self,'pause_display',lambda:True)():
            self.notice='The interface could not release the display.'
            return False
        if self.view!='player':self.view_stack.append((self.view,self.cursor))
        self.current=item;self.kind=item['kind'];self.pending_launch=self.launch_generation
        self.playback_error=''
        self.display_pending=self.kind==2;self._sync_video()
        self.queue('open',id=item['id'],generation=item['generation'],display=self.kind==2,_launch=self.pending_launch)
        self.view='player';self.cursor=1;self.notice='Opening…'
        return True
    def open_path(self,offer):
        if (not isinstance(offer,dict) or offer.get('kind') not in (1,2) or
                not isinstance(offer.get('title'),str) or not isinstance(offer.get('folder'),str)):
            return False
        self.cancel_pending_launch()
        self.tasks=deque(r for r in self.tasks if r['action'] in ('stop','recover'))
        self.pending_launch=self.launch_generation;self.current=None
        self.desired=dict(offer);self.kind=offer['kind'];self.after=None;self.items=[];self.view_stack.clear()
        self.view='player';self.cursor=1;self.notice='Opening…'
        self.queue('list',kind=self.kind)
        return True
    def activate(self,identity):
        if identity in ('music','video'):
            self.cancel_pending_launch()
            self.view_stack.append((self.view,self.cursor))
            self.view=identity;self.kind=1 if identity=='music' else 2
            self.cursor=0;self.after=None;self.items=[]
            if not self.queue('list',kind=self.kind):self.notice='Player is busy. Try Refresh again.'
        elif identity in ('refresh-media','first-media','next-media'):
            self.cancel_pending_launch()
            self.after=self.items[-1]['id'] if identity=='next-media' and self.items else None
            if not self.queue('list',kind=self.kind,after=self.after):self.notice='Player is busy. Try Refresh again.'
        elif identity.startswith('media:'):
            item=next((r for r in self.items if r['id']==identity[6:]),None)
            if item is None:return False
            return self.open_item(item)
        elif identity.startswith('media-'):
            operation=identity[6:]
            if operation in ('pause','resume','play','wait'):
                if identity!=self.primary_control()[0] or not self.control_enabled(identity):return False
                if operation=='play':return self.open_item(self.current)
                self.queue(operation);return True
            if operation in ('previous','next'):
                if not self.current or self.current not in self.items:return False
                index=self.items.index(self.current)+(1 if operation=='next' else -1)
                if not 0<=index<len(self.items):return False
                return self.open_item(self.items[index])
            if operation in ('back','forward'):
                if self.pending_launch is not None or self.cleanup_pending:return False
                self.queue('seek',position=max(0,self.playback.get('position',0)+(-10000 if operation=='back' else 10000)))
            elif operation=='stop':self.queue(operation)
        elif identity.startswith('view:'):
            self.cancel_pending_launch()
            self.view_stack.append((self.view,self.cursor))
            return super().activate(identity)
        else:return super().activate(identity)
        return True
    def back_view(self):
        self.cancel_pending_launch()
        if not self.view_stack:return False
        self.view,self.cursor=self.view_stack.pop()
        self.notice=''
        return True
    def poll(self):
        changed=super().poll()
        if self.future is not None and self.future.done():
            future,request=self.future,self.inflight;self.future=None
            stale=('_launch' in request and request['_launch']!=self.launch_generation or
                   '_video_generation' in request and request['_video_generation']!=self.launch_generation)
            try:
                result=future.result()
                if stale:
                    if request['action']=='open':self._cleanup(video=bool(request.get('display')))
                elif request['action']=='list':
                    self.items=result['items'];self.more=result['more'];self.cursor=1 if self.items else 0
                    if self.desired:
                        match=next((item for item in self.items
                                    if item['kind']==self.desired['kind'] and
                                    item['title']==self.desired['title'] and
                                    item.get('folder','')==self.desired['folder']),None)
                        if match:
                            self.desired=None;self.open_item(match)
                        elif self.more and self.items:
                            self.queue('list',kind=self.kind,after=self.items[-1]['id'])
                        else:
                            self.desired=None;self.pending_launch=None;self.notice='This file is not available in the media library.'
                    else:self.notice='' if self.items else 'No matching media on the card'
                else:
                    if request.get('_cleanup') and (result.get('video') or result.get('state')!='stopped'):
                        raise RuntimeError('Player has not acknowledged stop')
                    self.playback=result
                    if (request['action'] in ('video-options','open','stop','recover') and
                            not any(r['action'] in ('video-options','open','stop','recover') for r in self.tasks)):
                        self.video_options=bool(result.get('options_view'))
                    if request['action']=='open':self.display_pending=False;self.pending_launch=None
                    if request.get('_cleanup'):self.cleanup_pending=False;self.cleanup_video=False
                    self._sync_video()
                    if self.view=='player' and self.pending_launch is None:self.notice=self.playback_error
            except Exception:
                if request['action']=='video-options' and not stale:
                    self.notice='Video options unavailable. Press Select to close.'
                    # A failed request gives no acknowledgement that the OSD
                    # closed. Keep input captured until an explicit close.
                    self.video_options=True
                    changed=True
                    # A failed track/menu request must not stop valid playback.
                    return changed
                if not stale:
                    if '_launch' in request:
                        self.desired=None;self.pending_launch=None;self.display_pending=False
                    if self.pending_launch is None:
                        self.playback_error=('Video could not start. Display or decoder unavailable.' if self.kind==2 else 'Media unavailable. Check the card and selected audio output.')
                        if self.view=='player':self.notice=self.playback_error
                if request['action']=='open' or request.get('_cleanup') or (not stale and self.video_busy):
                    self._cleanup(video=self.video_busy or bool(request.get('display')),recover=True)
            changed=True
        if self.future is None and not self.closed:
            if self.tasks:self.inflight=self.tasks.popleft()
            elif time.monotonic()>=self.next_media:
                self.inflight=dict(action='status');self.next_media=time.monotonic()+.4
            else:self.inflight=None
            if self.inflight is not None:
                self.future=self.executor.submit(self.recover if self.inflight['action']=='recover' else self.request,
                    *([] if self.inflight['action']=='recover' else [self.inflight]))
        return changed
    def video_key(self,code):
        pending_options=any(r and r['action']=='video-options' and
                            r.get('_video_generation',self.launch_generation)==self.launch_generation
                            for r in [self.inflight if self.future else None,*self.tasks])
        if code==SELECT and not self.cleanup_pending and self.pending_launch is None:
            if self.queue('video-options',key='close' if self.video_options else 'open'):
                self.video_options=not self.video_options
            return 'options'
        # Keep capturing menu input until its close is acknowledged. The OSD
        # can still be visible while the worker is processing an earlier key.
        if (self.video_options or pending_options) and code in (A,B,UP,DOWN,546,547):
            self.queue('video-options',key={A:'choose',B:'back',UP:'up',DOWN:'down',546:'up',547:'down'}[code])
            return 'options'
        if code in (B,MENU,116):self.queue('stop')
        elif code==A and not self.cleanup_pending and self.pending_launch is None and not any(
                r and r['action'] in ('stop','recover') for r in [self.inflight if self.future else None,*self.tasks]):
            self.activate(self.primary_control()[0])
        elif code in (546,547) and self.pending_launch is None and not self.cleanup_pending:
            self.queue('seek',position=max(0,self.playback.get('position',0)+(-10000 if code==546 else 10000)))
        return True
    def player_key(self,code):
        if self.view!='player' or self.video_busy:return False
        if code==A:
            self.activate(self.primary_control()[0])
        elif code in (L1,R1):
            self.activate('media-'+('previous' if code==L1 else 'next'))
        elif code in (L2,R2):
            self.activate('media-'+('back' if code==L2 else 'forward'))
        elif code==MENU:
            self.cancel_pending_launch();self.view='library';self.cursor=0
            return False
        else:return False
        return True
    def close(self):
        self.closed=True;self.tasks.clear()
        if self.future is not None and not self.future.cancel():
            try:self.future.result(timeout=12.5)
            except Exception:pass
        try:self.request(dict(action='stop'))
        except Exception:
            if self.video_busy:
                try:self.recover()
                except Exception:pass
        self.executor.shutdown(wait=False,cancel_futures=True)
