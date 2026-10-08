"""Bounded parent for the descriptor-only GStreamer worker."""
import json,os,select,subprocess,sys,time
from pathlib import Path

class GstDescriptorBackend:
    def __init__(self,output,volume=20,*,test_null=False):
        self.output=output;self.volume=volume;self.test_null=test_null
        self.process=None;self.sequence=0;self.buffer=b'';self.last={};self.ready=False;self.open_deadline=0;self.resume_ms=0
    def open_descriptor(self,fd,position_ms,*,max_buffer_bytes):
        if max_buffer_bytes!=2*1024*1024:raise ValueError('unsupported buffer bound')
        args=[sys.executable,str(Path(__file__).with_name('gst_descriptor_worker.py')),str(fd),self.output,str(self.volume)]
        if self.test_null:args.append('--test-null')
        self.process=subprocess.Popen(args,pass_fds=(fd,),close_fds=True,start_new_session=True,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
        self.open_deadline=time.monotonic()+8;self.resume_ms=position_ms
        self.last=dict(position_ms=position_ms,duration_ms=None,buffered_ms=0,input_complete=False,ended=False)
    def request(self,op,*args):
        if self.process is None:raise RuntimeError('audio worker unavailable')
        self.sequence+=1
        payload=json.dumps(dict(id=self.sequence,op=op,args=args),separators=(',',':')).encode()+b'\n'
        end=time.monotonic()+1
        if not select.select([], [self.process.stdin], [], 1)[1]:raise TimeoutError('audio worker input')
        if os.write(self.process.stdin.fileno(),payload)!=len(payload):raise RuntimeError('audio worker short request')
        while time.monotonic()<end:
            if b'\n' in self.buffer:
                line,self.buffer=self.buffer.split(b'\n',1);reply=json.loads(line)
                if reply.get('id')!=self.sequence or not reply.get('ok'):raise RuntimeError('audio worker failed')
                self.last=reply['result'];return self.last
            if select.select([self.process.stdout],[],[],max(0,end-time.monotonic()))[0]:
                part=os.read(self.process.stdout.fileno(),4096)
                if not part:raise RuntimeError('audio worker exited')
                self.buffer+=part
                if len(self.buffer)>8192:raise RuntimeError('audio worker response bound')
        raise TimeoutError('audio worker deadline')
    def status(self):
        if not self.ready:
            if self.process is None or self.process.poll() is not None:raise RuntimeError('audio worker exited during open')
            if time.monotonic()>self.open_deadline:raise TimeoutError('audio initialization deadline')
            if select.select([self.process.stdout],[],[],0)[0]:
                part=os.read(self.process.stdout.fileno(),4096)
                if not part:raise RuntimeError('audio worker initialization failed')
                self.buffer+=part
                if len(self.buffer)>8192:raise RuntimeError('audio worker initialization bound')
            if b'\n' not in self.buffer:return self.last
            line,self.buffer=self.buffer.split(b'\n',1)
            if json.loads(line)!={'ready':True}:raise RuntimeError('audio worker handshake')
            self.ready=True
            self.request('volume',self.volume)
        result=self.request('status')
        if self.resume_ms and result.get('duration_ms') is not None:
            position=self.resume_ms;self.resume_ms=0
            self.request('seek',position);result=self.request('status')
        return result
    def duration_ms(self):return self.last.get('duration_ms')
    def set_presenting(self,value):
        if self.ready:self.request('present',bool(value))
    def seek(self,value):self.request('seek',value)
    def set_volume(self,value):
        self.volume=value
        if self.ready:self.request('volume',value)
    def set_output(self,value):raise ValueError('stop before changing output')
    def stop(self):
        if self.process is None:return
        p=self.process
        p.terminate()
        try:p.wait(timeout=.5)
        except subprocess.TimeoutExpired:p.kill();p.wait(timeout=.5)
        finally:
            p.stdin.close();p.stdout.close();self.process=None;self.buffer=b'';self.ready=False
