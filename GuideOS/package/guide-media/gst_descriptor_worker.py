"""Isolated descriptor-only GStreamer decoder; parent enforces call/stop bounds."""
import json, os, select, sys
import gi
gi.require_version('Gst','1.0')
from gi.repository import Gst
Gst.init(None)

class Decoder:
    def __init__(self,fd,output,volume,test=False):
        self.ended=False;self.complete=False;self.failed=False
        self.pipeline=Gst.ElementFactory.make('playbin')
        self.queue=Gst.ElementFactory.make('queue')
        sink=Gst.ElementFactory.make('fakesink' if test else 'pipewiresink')
        if None in (self.pipeline,self.queue,sink):raise RuntimeError('decoder components')
        self.queue.set_property('max-size-time',Gst.SECOND)
        self.queue.set_property('max-size-bytes',2*1024*1024)
        self.queue.set_property('max-size-buffers',0)
        self.queue.set_property('min-threshold-time',750*Gst.MSECOND)
        self.queue.set_property('leaky',0)
        self.queue.set_property('flush-on-eos',False)
        self.queue.get_static_pad('sink').add_probe(Gst.PadProbeType.EVENT_DOWNSTREAM,self.event)
        if test:sink.set_property('sync',True)
        else:
            sink.set_property('target-object',output)
            props=Gst.Structure.new_empty('props')
            props.set_value('node.dont-reconnect',True);props.set_value('node.dont-fallback',True)
            props.set_value('media.role','Music');sink.set_property('stream-properties',props)
        self.pipeline.set_property('audio-filter',self.queue)
        self.pipeline.set_property('audio-sink',sink)
        self.pipeline.set_property('flags',2|16)
        self.pipeline.set_property('volume',volume/100)
        self.pipeline.set_property('uri','fd://%d'%fd)
        self.state(False)
    def event(self,pad,info):
        if info.get_event().type==Gst.EventType.EOS:self.complete=True
        return Gst.PadProbeReturn.OK
    def state(self,present):
        if self.pipeline.set_state(Gst.State.PLAYING if present else Gst.State.PAUSED)==Gst.StateChangeReturn.FAILURE:
            raise RuntimeError('decoder state')
    def status(self):
        bus=self.pipeline.get_bus()
        for _ in range(32):
            message=bus.pop()
            if message is None:break
            if message.type==Gst.MessageType.ERROR:self.failed=True
            if message.type==Gst.MessageType.EOS:self.ended=True
        if self.failed:raise RuntimeError('decoder or selected output failed')
        ok,pos=self.pipeline.query_position(Gst.Format.TIME)
        duration_ok,duration=self.pipeline.query_duration(Gst.Format.TIME)
        return dict(position_ms=max(0,int(pos/Gst.MSECOND)) if ok else 0,
                    duration_ms=max(0,int(duration/Gst.MSECOND)) if duration_ok else None,
                    buffered_ms=int(self.queue.get_property('current-level-time')/Gst.MSECOND),
                    input_complete=self.complete,ended=self.ended)
    def command(self,op,args):
        if op=='status':return self.status()
        if op=='present':self.state(args[0])
        elif op=='seek':
            self.complete=False;self.ended=False
            if not self.pipeline.seek_simple(Gst.Format.TIME,Gst.SeekFlags.FLUSH|Gst.SeekFlags.ACCURATE,args[0]*Gst.MSECOND):
                raise RuntimeError('seek unavailable')
        elif op=='volume':self.pipeline.set_property('volume',args[0]/100)
        else:raise ValueError('worker operation')
        return self.status()

def main():
    fd=int(sys.argv[1]);output=sys.argv[2];volume=int(sys.argv[3])
    decoder=Decoder(fd,output,volume,sys.argv[4:] == ['--test-null'])
    print(json.dumps(dict(ready=True)),flush=True)
    try:
        while True:
            line=sys.stdin.buffer.readline(4097)
            if not line:break
            if len(line)>4096:break
            try:
                req=json.loads(line);result=decoder.command(req['op'],req['args'])
                reply=dict(id=req['id'],ok=True,result=result)
            except Exception:reply=dict(id=req.get('id',0),ok=False)
            print(json.dumps(reply,separators=(',',':')),flush=True)
    finally:
        decoder.pipeline.set_state(Gst.State.NULL);os.close(fd)
if __name__=='__main__':main()
