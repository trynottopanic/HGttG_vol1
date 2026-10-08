"""System-owned native Music/Video sessions, separate from application grants."""
import hashlib,json,math,os,select,signal,socket,struct,subprocess,sys,time
from pathlib import Path
from types import SimpleNamespace
sys.path[:0]=['/usr/lib/guideos/ipc','/usr/lib/guideos/media','/usr/lib/guideos/audio']
from audio_lease import AudioLease
from media_source_channel import SourceClient
from media_session import MediaSessionManager, CLOSED, PLAYING, BUFFERING, PAUSED
from gst_descriptor_backend import GstDescriptorBackend
from gst_audio_adapter import GStreamerAudioAdapter
from mpv_backend import MpvJsonBackend
from mpv_video_adapter import MpvVideoAdapter
from video_options import VideoOptions

RUNTIME=Path('/run/guideos-player')
STATE=Path('/var/lib/guideos-player')
AUDIO=Path('/run/guideos-audio/status.json')

def audio_status():
    try:
        if AUDIO.stat().st_size>131072:raise ValueError('size')
        with AUDIO.open('rb') as file:raw=file.read(131073)
        if len(raw)>131072:raise ValueError('size')
        value=json.loads(raw)
        if not isinstance(value,dict) or not recent(value.get('observed'),4):raise ValueError('age')
    except (OSError,ValueError,TypeError,RecursionError):
        raise RuntimeError('Audio service unavailable') from None
    return value

def recent(observed,limit):
    if type(observed) not in (int,float):return False
    try:return math.isfinite(observed) and 0<=time.monotonic()-observed<=limit
    except OverflowError:return False

def atomic(path,value):
    temporary=path.with_suffix('.tmp');data=json.dumps(value,separators=(',',':'))
    with temporary.open('w') as file:file.write(data);file.flush();os.fsync(file.fileno())
    temporary.chmod(0o600);temporary.replace(path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

class Checkpoints:
    def save(self,owner,media,position,audio,subtitle):
        # Fixed bounded recent history; identity only, never source paths.
        path=STATE/'resume.json'
        try:
            if path.stat().st_size>65536:raise ValueError()
            value=json.loads(path.read_text())
        except (OSError,ValueError):value={}
        key=hashlib.sha256((owner+media.hex()).encode()).hexdigest()
        value.pop(key,None);value[key]=dict(position=max(0,int(position)),updated=time.time())
        while len(value)>64:value.pop(next(iter(value)))
        atomic(path,value)

class Admission:
    def __init__(self,service):self.service=service;self.lease=None;self.audio_lease=AudioLease()
    def acquire(self,context,identity,output):
        if self.lease is not None:raise RuntimeError('Another player owns the output')
        service=self.service
        record=service.source.describe(identity,service.open_generation)[0]
        status=audio_status();selected=status.get('output')
        observed=status.get('inventory_observed',status.get('observed'))
        if status.get('inventory_state','ready')!='ready' or not recent(observed,10):
            raise RuntimeError('Audio outputs are being checked. Refresh and try again.')
        if selected not in {item['id'] for item in status['outputs']}:raise RuntimeError('Choose an available audio output first')
        if status.get('test_active') or status.get('state') in ('playing','starting'):
            raise RuntimeError('Stop the audio test or other playback first')
        if output is not None:raise ValueError('Use the selected output for this native release')
        if record[3]==2 and not service.display_offer:raise RuntimeError('Video requires shell display admission')
        service.kind=record[3];service.output=selected;service.volume=status['volume']
        self.audio_lease.acquire()
        try:
            if selected.startswith('alsa_output.platform-5096000.codec.'):
                node=next(o.get('node_id') for o in status['outputs'] if o['id']==selected)
                if type(node) is not int or node<0:raise ValueError('Selected output unavailable')
                for args in (['set-mute',str(node),'0'],['set-volume',str(node),'1.0']):
                    subprocess.run(['wpctl',*args],check=True,timeout=1,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except Exception:self.audio_lease.release();raise
        self.lease=object();return self.lease
    def release(self,lease):
        if self.lease is lease:self.lease=None;self.audio_lease.release()

class Service:
    def __init__(self):
        self.source=SourceClient();self.admission=Admission(self)
        self.manager=MediaSessionManager(self.source,self.engine,self.admission,Checkpoints(),session_limit=4)
        self.owner=None;self.sid=None;self.owner_fd=None;self.identity=None;self.generation=None
        self.kind=0;self.output=None;self.volume=20;self.message='Choose Music or Video.'
        self.video_options=VideoOptions()
        self.display_offer=False;self.open_generation=0;self.title='';self.last_check=0;self.last_save=0;self.last_refresh=0
    def engine(self):
        if self.kind==1:return GStreamerAudioAdapter(GstDescriptorBackend(self.output,self.volume))
        return MpvVideoAdapter(MpvJsonBackend(RUNTIME/'decoder',device=self.output,volume=self.volume,display=self.display_offer))
    def active(self):
        return self.sid is not None and self.manager.sessions[self.sid].state!=CLOSED
    def stop(self,message='Stopped'):
        self.video_options.reset()
        try:
            if self.active():
                session=self.manager.sessions[self.sid]
                try:self.manager.checkpoint(self.owner,self.sid,session.revision)
                finally:self.manager.stop(self.owner,self.sid)
        finally:
            if self.owner_fd is not None:os.close(self.owner_fd);self.owner_fd=None
            self.message=message;self.display_offer=False
    def open(self,peer,args):
        self.stop()
        self.identity=bytes.fromhex(args['id']);self.generation=int(args['generation'])
        self.open_generation=self.generation
        record=self.source.describe(self.identity,self.generation)[0]
        self.display_offer=record[3]==2 and args.get('display') is True
        self.owner=SimpleNamespace(instance_id=hashlib.sha256(('shell:'+str(peer)).encode()).hexdigest()[:32],generation=1)
        self.owner_fd=os.pidfd_open(peer)
        self.title=record[4]
        try:
            opened=self.manager.open(self.owner,self.identity,self.generation)
            self.sid=opened[0];self.manager.play(self.owner,self.sid,opened[2]);self.message='Opening...'
            if self.kind==2:self.manager.sessions[self.sid].engine.backend.command('show-text','A: pause/resume   Select: video options   B/Menu: exit',5000)
        except Exception as exc:
            print('GUIDE_MEDIA_EVENT '+json.dumps(dict(phase='open',kind=self.kind,
                  error_type=type(exc).__name__,error_number=getattr(exc,'errno',0) or 0)),flush=True)
            self.stop('Could not open media');raise
    def status(self):
        state='stopped';position=0;duration=None
        video_stats={}
        if self.sid is not None:
            session=self.manager.sessions[self.sid]
            state={CLOSED:'stopped',PLAYING:'playing',BUFFERING:'buffering',PAUSED:'paused'}.get(session.state,'opening')
            position=session.engine.position_ms;duration=session.engine.duration_ms
            if self.kind==2:
                video_stats=dict(dropped_frames=session.engine.dropped_frames,
                    av_offset_ms=session.engine.av_offset_ms,underruns=session.engine.buffer.underruns,
                    rendering=getattr(session.engine,'rendering',{}))
        return dict(state=state,position=position,duration=duration,title=self.title,
                    message=self.message,video=self.active() and self.kind==2,video_stats=video_stats,
                    options_view=self.video_options.view)
    def command(self,pid,request):
        action=request.get('action')
        if action=='list':
            after=bytes.fromhex(request['after']) if request.get('after') else None
            result=self.source.list(after,request.get('kind'))
            return dict(items=[dict(id=r[0].hex(),kind=r[3],title=r[4],folder=r[5],
                                    size=r[6],modified_ns=r[7],generation=r[10]) for r in result[1]],
                        more=result[2],revision=result[0])
        if action=='status':return self.status()
        if action=='video-options':
            if not self.active() or self.kind!=2:raise RuntimeError('Video is not active')
            if self.owner.instance_id!=hashlib.sha256(('shell:'+str(pid)).encode()).hexdigest()[:32]:
                raise PermissionError('Player belongs to another shell')
            session=self.manager.sessions[self.sid]
            def select_track(kind,identity):
                operation=self.manager.select_subtitle if kind=='subtitle' else self.manager.select_audio
                operation(self.owner,self.sid,session.revision,identity)
            self.video_options.handle(request.get('key'),session.engine,select_track)
            return self.status()
        if action=='open':self.open(pid,request)
        elif action=='stop':self.stop()
        elif action in ('pause','resume','seek'):
            if not self.active():raise RuntimeError('Choose a file first')
            session=self.manager.sessions[self.sid]
            if action=='pause':self.manager.pause(self.owner,self.sid,session.revision)
            elif action=='resume':self.manager.play(self.owner,self.sid,session.revision)
            else:self.manager.seek(self.owner,self.sid,session.revision,max(0,int(request['position'])))
            if self.kind==2:session.engine.backend.command('show-text','Paused' if session.state==PAUSED else 'Playing',1500)
        else:raise ValueError('Unknown media action')
        return self.status()
    def tick(self):
        if not self.active():return
        if self.owner_fd is not None and select.select([self.owner_fd],[],[],0)[0]:
            self.stop('Player view closed');return
        try:
            if time.monotonic()-self.last_check>=.5:
                self.source.describe(self.identity,self.generation)
                status=audio_status()
                if status.get('output')!=self.output or (status.get('inventory_state','ready')=='ready' and self.output not in {o['id'] for o in status['outputs']}):
                    self.stop('Selected output disconnected or changed');return
                if status.get('test_active') or status.get('state') in ('playing','starting'):
                    self.stop('Audio output is in use');return
                if status['volume']!=self.volume:
                    self.volume=status['volume'];backend=self.manager.sessions[self.sid].engine.backend
                    if self.kind==1:backend.set_volume(self.volume)
                    else:backend.command('set_property','volume',self.volume)
                self.last_check=time.monotonic()
            now=time.monotonic()
            if now-self.last_refresh<.25:return
            self.manager.refresh(self.owner,self.sid);self.last_refresh=now
            if not self.active():self.stop('Playback finished')
            else:
                self.message={PLAYING:'Playing',BUFFERING:'Buffering...',PAUSED:'Paused'}.get(self.manager.sessions[self.sid].state,'Opening...')
                if time.monotonic()-self.last_save>10:
                    session=self.manager.sessions[self.sid]
                    if self.kind==2:
                        print('GUIDE_MEDIA_EVENT '+json.dumps(dict(phase='playback',
                            renderer=session.engine.backend._property('current-vo','unknown'),
                            **self.status()['video_stats'])),flush=True)
                    self.manager.checkpoint(self.owner,self.sid,session.revision);self.last_save=time.monotonic()
        except Exception as exc:
            print('GUIDE_MEDIA_EVENT '+json.dumps(dict(phase='refresh',kind=self.kind,
                error_type=type(exc).__name__,error_number=getattr(exc,'errno',0) or 0)),flush=True)
            self.stop('Playback stopped: source or decoder unavailable')

def main():
    service=Service();stopping=False
    def stop(*args):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    if int(os.environ.get('LISTEN_PID','0'))!=os.getpid() or int(os.environ.get('LISTEN_FDS','0'))!=1:
        raise RuntimeError('Native media control socket missing')
    listener=socket.socket(fileno=3);listener.setblocking(False)
    try:
        while not stopping:
            if select.select([listener],[],[],.1)[0]:
                connection,_=listener.accept()
                try:
                    connection.settimeout(.1)
                    pid,uid,gid=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                    if uid!=0:raise PermissionError('System control only')
                    packet=connection.recv(8193)
                    if len(packet)>8192:raise ValueError('Control bound')
                    request=json.loads(packet)
                    result=service.command(pid,request)
                    connection.send(json.dumps(dict(ok=True,result=result),separators=(',',':')).encode())
                except Exception as exc:
                    # Only fixed messages are reflected; no decoder/path exception data.
                    try:connection.send(json.dumps(dict(ok=False,error='Media request failed; check card and selected audio output.')).encode())
                    except OSError:pass
                finally:connection.close()
            service.tick()
    finally:service.stop();listener.close()
if __name__=='__main__':main()
