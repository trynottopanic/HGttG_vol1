#!/usr/bin/python3
"""Supervised mpv video-plus-audio adapter with bounded buffering policy."""
import secrets, unicodedata
from buffer_policy import BufferController, LOCAL_VIDEO, policy


class MpvVideoAdapter:
    def __init__(self, backend, *, policy_class=LOCAL_VIDEO):
        self.backend=backend; self.buffer=BufferController(policy(policy_class))
        self.position_ms=0; self.duration_ms=None; self.requested_play=False
        self.ready=False; self.dropped_frames=0; self.av_offset_ms=0
        self.backend_paused=True
        self.rendering={}
        self.track_ids={}

    def open(self, descriptor, position_ms):
        self.backend.spawn(descriptor, position_ms,
                           max_buffer_bytes=self.buffer.policy.max_bytes,
                           audio_clock=True, drop_late_video=True)
        self.position_ms=position_ms; self.duration_ms=self.backend.duration_ms()

    def poll(self):
        status=self.backend.status(); self.position_ms=status["position_ms"]
        self.rendering=status.get('rendering',{})
        self.duration_ms=status.get("duration_ms",self.duration_ms)
        if status.get("ended"):
            self.ready=False
            return {"ready":False,"ended":True,"buffered_ms":0}
        self.dropped_frames=status.get("dropped_frames",0)
        self.av_offset_ms=status.get("av_offset_ms",0)
        self.ready=self.buffer.update(status["buffered_ms"],
                                      requested_play=self.requested_play,
                                      input_complete=status.get("input_complete",False))
        paused=not self.ready
        if paused != self.backend_paused:
            self.backend.command("set_property", "pause", paused)
            self.backend_paused=paused
        return {"ready":self.ready,"buffered_ms":status["buffered_ms"],
                "underruns":self.buffer.underruns,
                "dropped_frames":self.dropped_frames,
                "av_offset_ms":self.av_offset_ms}

    def play(self): self.requested_play=True; return self.poll()["ready"]
    def pause(self):
        self.requested_play=False
        if not self.backend_paused:self.backend.command("set_property","pause",True)
        self.backend_paused=True
    def seek(self,value):
        self.backend.command("seek",value/1000,"absolute+exact");self.position_ms=value
        self.buffer=BufferController(self.buffer.policy)
        if self.requested_play:self.poll()
    def tracks(self):
        # Decoder IDs remain private; session callers receive opaque identities.
        self.backend._drain()
        raw=self.backend._property('track-list',[])
        if not isinstance(raw,list) or len(raw)>128:raise ValueError('Invalid track inventory')
        result={'audio':[],'subtitle':[]};current=set()
        for track in raw:
            if not isinstance(track,dict):continue
            kind={'audio':'audio','sub':'subtitle'}.get(track.get('type'))
            identity=track.get('id')
            if kind is None or type(identity) is not int or identity<0:continue
            key=(kind,identity)
            if key in current:continue
            current.add(key)
            if key not in self.track_ids:self.track_ids[key]=secrets.token_bytes(16)
            def clean(value):
                if not isinstance(value,str):return ''
                return ''.join(c for c in value if not unicodedata.category(c).startswith('C'))[:40]
            title=clean(track.get('title'));language=clean(track.get('lang'))
            label=f'{kind.title()} {len(result[kind])+1}'
            if language:label+=' ('+language+')'
            if title:label+=': '+title
            result[kind].append(dict(id=self.track_ids[key],label=label,
                                    selected=track.get('selected') is True))
        self.track_ids={key:value for key,value in self.track_ids.items() if key in current}
        return result
    def _select_track(self,kind,value):
        tracks=self.tracks()[kind]
        if type(value) is not bytes or not any(t['id']==value for t in tracks):
            raise ValueError('Track is unavailable')
        identity=next(key[1] for key,opaque in self.track_ids.items() if key[0]==kind and opaque==value)
        self.backend.command('set_property','aid' if kind=='audio' else 'sid',identity)
        # An acknowledged write alone is not evidence of a selected track.
        if self.backend.command('get_property','aid' if kind=='audio' else 'sid')!=identity:
            raise ValueError('Track selection was not confirmed')
    def select_audio(self,value):
        self._select_track('audio',value)
    def select_subtitle(self,value):
        if value is not None:self._select_track('subtitle',value)
        else:
            self.backend.command("set_property","sid","no")
            observed=self.backend.command('get_property','sid')
            if observed!='no' and observed is not False:
                raise ValueError('Subtitle disable was not confirmed')
    def set_output(self,value): self.backend.set_output(value)
    def stop(self): self.requested_play=False;self.backend.stop(timeout=.75,kill_timeout=.25)
