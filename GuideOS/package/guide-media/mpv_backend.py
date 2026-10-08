#!/usr/bin/python3
"""Private JSON-IPC mpv subprocess backend for the video adapter."""
from __future__ import annotations
import json, math, os, re, secrets, select, socket, subprocess, time
from pathlib import Path
from cedrus_runtime import select_decoder


class MpvCommandError(RuntimeError):
    def __init__(self, error):
        super().__init__("mpv command failed")
        self.error = error


class MpvJsonBackend:
    PROPERTIES=('demuxer-cache-state','eof-reached','duration','time-pos',
                'demuxer-cache-duration','decoder-frame-drop-count','frame-drop-count','avsync',
                'current-vo','current-gpu-context','hwdec-current','track-list','aid','sid')
    @staticmethod
    def display_device():
        for card in sorted(Path('/sys/class/drm').glob('card[0-9]*')):
            if not re.fullmatch(r'card[0-9]+',card.name):continue
            try:driver=(card/'device/driver').resolve(strict=True).name
            except OSError:continue
            if driver!='sun4i-drm':continue
            device=Path('/dev/dri')/card.name
            if device.exists() and os.access(device,os.R_OK|os.W_OK):return str(device)
        raise RuntimeError('Deck display controller is unavailable')
    def __init__(self, runtime: Path, *, executable="/usr/bin/mpv", popen=subprocess.Popen, headless=False, output_resolver=None, device=None, volume=20, display=False, decoder_selector=select_decoder):
        self.runtime=Path(runtime);self.executable=executable;self.popen=popen;self.headless=headless;self._reply_buffer=b"";self._request_id=0
        self.process=None;self.connection=None;self.socket_path=None
        self.output_resolver=output_resolver
        self.device=device;self.volume=volume;self.display=display
        self.startup_deadline=None
        self.observing=False;self.properties={};self.seek_pending=False
        self.decoder_selector=decoder_selector
        self.decoder_policy=dict(executable=executable,hwdec='no',reason='software-default')

    def spawn(self, descriptor, position_ms, *, max_buffer_bytes,
              audio_clock, drop_late_video):
        if self.process is not None: raise RuntimeError("mpv already active")
        self._reply_buffer=b"";self.properties={};self.observing=False;self.seek_pending=False
        self.runtime.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.socket_path=self.runtime/("mpv-"+secrets.token_hex(8)+".sock")
        self.decoder_policy=(self.decoder_selector() if not self.headless and self.executable=='/usr/bin/mpv'
                             else dict(executable=self.executable,hwdec='no',reason='software-default'))
        args=[self.decoder_policy['executable'],"--no-config","--terminal=no","--pause=yes",
              "--idle=no","--keep-open=yes","--sid=no","--sub-auto=no","--osd-font-size=24",
              f"--hwdec={self.decoder_policy['hwdec']}","--hwdec-codecs=h264",
              "--hwdec-software-fallback=3","--cache=yes",
              # Guide's bounded buffer controller owns pause/resume thresholds.
              "--cache-pause=no","--cache-pause-initial=no",
              f"--demuxer-max-bytes={max_buffer_bytes}",
              "--video-sync=audio" if audio_clock else "--video-sync=display-resample",
              "--framedrop=vo" if drop_late_video else "--framedrop=no",
              f"--input-ipc-server={self.socket_path}",
              f"--start={position_ms/1000:.3f}","--",f"/proc/self/fd/{descriptor}"]
        if self.headless:args[1:1]=["--vo=null","--ao=null"]
        else:
            if not self.device or not self.display:raise ValueError("audio/display lease required")
            # GPU color conversion/scaling avoids the software DRM output path.
            # Cedrus uses copy-back to this established GPU presentation path.
            args[1:1]=["--vo=gpu,drm","--gpu-context=drm","--gpu-api=opengl","--opengl-es=yes","--gpu-sw=no",
                       "--scale=bilinear","--dscale=bilinear","--cscale=bilinear",
                       "--deband=no","--interpolation=no","--vd-lavc-threads=3",
                       "--audio-buffer=0.5","--msg-level=all=warn",
                       f"--drm-device={self.display_device()}","--ao=pipewire",f"--audio-device=pipewire/{self.device}",
                       f"--volume={self.volume}","--audio-fallback-to-null=no",
                       "--input-default-bindings=no","--input-terminal=no","--audio-client-name=GuideOS-Video"]
        ownership = dict(process_group=0) if self.display and not self.headless else dict(start_new_session=True)
        self.process=self.popen(args,pass_fds=(descriptor,),close_fds=True,
                                **ownership,stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL,stderr=None)
        deadline=time.monotonic()+8
        self.startup_deadline=deadline
        while time.monotonic()<deadline:
            if self.process.poll() is not None:
                self.process=None
                if self.socket_path.exists():self.socket_path.unlink()
                raise RuntimeError("mpv exited during open")
            try:
                connection=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
                connection.settimeout(.25);connection.connect(str(self.socket_path))
                self.connection=connection
                break
            except OSError:
                connection.close();time.sleep(.02)
        else:
            self.stop(timeout=.1,kill_timeout=.1);raise TimeoutError("mpv IPC did not appear")
        try:
            # IPC exists before demuxing, shader compilation and VO acquisition
            # finish. Do not send ordinary one-second commands into cold startup.
            while time.monotonic()<deadline:
                if self.process.poll() is not None:raise RuntimeError('mpv exited during initialization')
                if self.headless or self._property('vo-configured',False) is True:
                    params=self._property('video-params',{})
                    if isinstance(params,dict) and params.get('w',0)>0 and params.get('h',0)>0:
                        # Subscribe once. All subsequent status reads drain events;
                        # only this owning service thread reads the IPC stream.
                        for index,name in enumerate(self.PROPERTIES,1):self.command('observe_property',index,name)
                        self.observing=True
                        self._drain()
                        self.startup_deadline=None
                        print('GUIDE_MEDIA_EVENT '+json.dumps(dict(phase='decoder-ready',
                            width=params['w'],height=params['h'],
                            rendering=self.rendering_status(),
                            open_ms=round((time.monotonic()-(deadline-8))*1000))),flush=True)
                        return
                time.sleep(.02)
            raise TimeoutError('mpv video output did not become ready')
        except Exception:
            self.startup_deadline=None
            self.stop(timeout=.75,kill_timeout=.25)
            raise

    def command(self,*values):
        if self.connection is None: raise RuntimeError("mpv IPC unavailable")
        if values and values[0]=='seek':
            self.seek_pending=True
            self.properties['eof-reached']=False
        self._request_id+=1
        request_id=self._request_id
        self.connection.sendall(json.dumps({"command":list(values),"request_id":request_id},separators=(",",":")).encode()+b"\n")
        deadline=self.startup_deadline or (time.monotonic()+1)
        while time.monotonic()<deadline:
            while b"\n" in self._reply_buffer:
                line,self._reply_buffer=self._reply_buffer.split(b"\n",1)
                reply=json.loads(line)
                self._event(reply)
                if reply.get("request_id")!=request_id:continue
                if reply.get("error")!="success":raise MpvCommandError(reply.get("error"))
                return reply.get("data")
            try:
                part=self.connection.recv(4096)
            except socket.timeout:
                continue
            if not part:raise RuntimeError("mpv IPC closed")
            self._reply_buffer+=part
            if len(self._reply_buffer)>32768:raise RuntimeError("mpv reply too large")
        raise TimeoutError("mpv command timed out")

    def _event(self,reply):
        if not isinstance(reply,dict):raise ValueError('Invalid mpv event')
        if reply.get('event')=='property-change':
            name=reply.get('name');identity=reply.get('id')
            if name in self.PROPERTIES and identity==self.PROPERTIES.index(name)+1:
                self.properties[name]=reply.get('data')
        elif reply.get('event')=='seek':
            self.seek_pending=True
            self.properties['eof-reached']=False
        elif reply.get('event')=='playback-restart':self.seek_pending=False

    def _drain(self):
        if self.connection is None:raise RuntimeError('mpv IPC unavailable')
        deadline=time.monotonic()+.005
        for _ in range(256):
            if b'\n' in self._reply_buffer:
                line,self._reply_buffer=self._reply_buffer.split(b'\n',1)
                self._event(json.loads(line))
            else:
                if not select.select([self.connection],[],[],0)[0]:break
                part=self.connection.recv(4096)
                if not part:raise RuntimeError('mpv IPC closed')
                self._reply_buffer+=part
                if len(self._reply_buffer)>32768:raise RuntimeError('mpv reply too large')
            if time.monotonic()>=deadline:break

    def _property(self,name,default=None):
        try:
            value=self.properties.get(name,default) if self.observing else self.command("get_property",name)
        except MpvCommandError as exc:
            if exc.error == "property unavailable":return default
            raise
        return default if value is None else value

    def _number(self,name,default=0):
        value=self._property(name,default)
        if value is None:return default
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError("invalid mpv numeric status")
        return value
    def duration_ms(self):
        if self.observing:self._drain()
        value=self._number("duration",None);return None if value is None else int(value*1000)
    def rendering_status(self):
        # Read only observed values: requested options are not runtime evidence.
        def label(name):
            value=self.properties.get(name)
            return value if type(value) is str and re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',value) else None
        output=label('current-vo');context=label('current-gpu-context');decoder=label('hwdec-current')
        return dict(output=output,context=context,decoder=decoder,
                    decoder_admission=self.decoder_policy['reason'],
                    hardware_rendering=None if output is None or output=='gpu' and context is None else output=='gpu' and context=='drm' and not self.headless,
                    hardware_decoding=None if decoder is None else decoder!='no')
    def status(self):
        if not self.observing:raise RuntimeError('mpv observations unavailable')
        self._drain()
        cache=self._property("demuxer-cache-state",{})
        if type(cache) is not dict:raise ValueError("invalid mpv cache status")
        if self.seek_pending:cache={}
        ended=False if self.seek_pending else self._property("eof-reached",False)
        if type(ended) is not bool:raise ValueError("invalid mpv end status")
        return {"input_complete":cache.get("eof") is True,"ended":ended,
                "duration_ms":None if self._number("duration",None) is None else int(self._number("duration",None)*1000),"position_ms":int(self._number("time-pos",0)*1000),
                "buffered_ms":0 if self.seek_pending else int(self._number("demuxer-cache-duration",0)*1000),
                "dropped_frames":int(self._number("decoder-frame-drop-count",0)+self._number("frame-drop-count",0)),
                "av_offset_ms":int(self._number("avsync",0)*1000),
                "rendering":self.rendering_status()}
    def set_output(self,value):
        if type(value) is not bytes or len(value)!=16:raise ValueError("invalid output")
        if self.output_resolver is None:
            raise ValueError("selected output routing is unavailable")
        # Only the trusted route owner may translate the opaque output ID.
        device=self.output_resolver(value)
        if type(device) is not str or not device or device=="auto" or len(device)>256:
            raise ValueError("invalid selected output route")
        self.command("set_property","audio-device",device)
    def stop(self,*,timeout,kill_timeout):
        process=self.process
        if process is None:return
        try:
            if self.connection is not None:
                try:self.command("quit")
                except Exception:pass
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:process.wait(timeout=kill_timeout)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=kill_timeout)
        finally:
            if self.connection is not None:self.connection.close()
            self.connection=None;self.process=None;self._reply_buffer=b"";self.startup_deadline=None;self.observing=False;self.properties={};self.seek_pending=False
            if self.socket_path is not None:
                try:os.unlink(self.socket_path)
                except FileNotFoundError:pass
