"""Trusted per-instance provider host. Untrusted source runs only after seccomp.

The persistent services remain C. This Python host exists only while an installed
Python application is running. No application source executes in this process.
"""
import ctypes
import errno
import hashlib
import json
import unicodedata
import os
from pathlib import Path
import re
import resource
import select
import signal
import socket
import stat
import struct
import sys
import time
from guide_ipc import REQUEST, REPLY, encode_packet, send_packet, recv_packet, ProtocolError

REGISTRY = Path('/var/lib/guideos/applications')
BROKER = '/run/guideos/brokers/control.sock'
PRIVATE, VISUAL, ACTIONS, TEXT = 2, 3, 4, 5
MAX_VALUE = 24576

def now():
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME)

def request(sock, op, args, sequence=1):
    send_packet(sock, encode_packet(REQUEST, sequence, {0: op, 1: args, 2: now()+1_000_000_000}))
    header, payload, fds = recv_packet(sock)
    for fd in fds: os.close(fd)
    if fds or header.message_class != REPLY or header.interface_major != 1 or header.request_id != sequence:
        raise ProtocolError('reply correlation')
    if payload.get(0) != 0: raise PermissionError('operation denied')
    return payload.get(1, {})

def bounded_file(path, limit, root_owned=False):
    # Every path component is traversed without symlinks; package parents must
    # remain owner controlled too, not just the final file.
    path = Path(path).absolute()
    fd = os.open('/', os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC, dir_fd=fd)
            os.close(fd); fd = child
            info = os.fstat(fd)
            if root_owned and (info.st_uid != 0 or info.st_mode & 0o022): raise PermissionError('untrusted parent')
        leaf = os.open(path.name, os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC, dir_fd=fd)
        try:
            info = os.fstat(leaf)
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit: raise ValueError('file bound')
            if root_owned and (info.st_uid != 0 or info.st_mode & 0o022): raise PermissionError('untrusted record')
            data = os.read(leaf, limit+1)
            if len(data) != info.st_size: raise ValueError('file changed')
            return data
        finally: os.close(leaf)
    finally: os.close(fd)

def load_policy(code, health=False):
    import json
    if type(code) is not int or not 10000 <= code <= 0xffffffff: raise ValueError('application code')
    raw=bounded_file(REGISTRY/f'{code}.policy',2047,True).decode('ascii')
    match=re.fullmatch(r'format=2\ncode=([0-9]+)\nid=([a-z_][a-z0-9_.-]{0,62})\nmodule=([a-z_][a-z0-9_]{0,62})\nentry=([a-z_][a-z0-9_]{0,62})\nsha256=([a-f0-9]{64})\ncapabilities=([0-9]+)\nprivate_bytes=([0-9]+)\nversion=([A-Za-z0-9.-]{1,48})\nbinding=([a-f0-9]{64})\n',raw)
    if not match:raise ValueError('policy format')
    c,ident,module,entry,digest,mask,quota,version,binding=match.groups()
    if c!=str(code) or str(int(mask))!=mask or str(int(quota))!=quota or int(mask)&~254 or not 0<int(quota)<=524288 or version in ('.','..'):raise ValueError('policy values')
    record=json.loads(bounded_file(REGISTRY/ident/'installation.json',32768,True))
    if record['runtime_policy']!=raw or record['state']!=('testing' if health else 'committed'):raise ValueError('activation unavailable')
    source=bounded_file(Path('/opt/guideos/applications')/ident/'releases'/version/'application'/(module+'.py'),2097152,True)
    if hashlib.sha256(source).hexdigest()!=digest:raise ValueError('release integrity')
    return dict(code=code,id=ident,module=module,entry=entry,digest=digest,mask=int(mask),quota=int(quota)),compile(source,'<installed-application>','exec')

class Broker:
    def call(self, op, args):
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as sock:
            sock.settimeout(.2); sock.connect(BROKER)
            return request(sock, op, args)
    def acquire(self, cap): return self.call(3,{0:cap})[0]
    def valid(self, grant, cap): self.call(6,{0:grant,1:cap})
    def release(self, grant): self.call(5,{0:grant})
    def renew(self,grant,cap): self.call(7,{0:grant,1:cap})

class PrivateStore:
    def __init__(self, path, quota):
        self.path, self.quota = Path(path), quota
        self.path.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.fd = os.open(self.path,os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        # Only our fixed temporary name can survive interrupted atomic writes.
        try: os.unlink('.pending',dir_fd=self.fd); os.fsync(self.fd)
        except FileNotFoundError: pass
    @staticmethod
    def key(key):
        if type(key) is not str or not re.fullmatch(r'[a-z][a-z0-9_-]{0,31}',key): raise ValueError('private key')
        return key
    def read(self, key):
        key=self.key(key)
        try: fd=os.open(key,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=self.fd)
        except FileNotFoundError: return ''
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size>MAX_VALUE: raise ValueError('private value')
            data=os.read(fd,MAX_VALUE+1)
            if len(data)!=info.st_size: raise ValueError('private value changed')
            return data.decode('utf-8')
        finally: os.close(fd)
    def write(self,key,text):
        key=self.key(key)
        if type(text) is not str: raise ValueError('private text')
        data=text.encode('utf-8')
        if len(data)>MAX_VALUE: raise ValueError('private value limit')
        names=os.listdir(self.fd)
        if len(names)>32 or (key not in names and len(names)>=32): raise ValueError('private object limit')
        total=0
        for name in names:
            info=os.stat(name,dir_fd=self.fd,follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode): raise ValueError('private object type')
            total+=info.st_size
        if total+len(data)>self.quota: raise ValueError('private quota including staging')
        fd=os.open('.pending',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.fd)
        try:
            view=memoryview(data)
            while view: view=view[os.write(fd,view):]
            os.fsync(fd)
        finally: os.close(fd)
        os.replace('.pending',key,src_dir_fd=self.fd,dst_dir_fd=self.fd);os.fsync(self.fd)
        return hashlib.sha256(data).digest()
    def close(self): os.close(self.fd)

def sandbox(channel):
    """Kernel allow-list after source compilation and runtime preload, before exec.

    No open, socket, connect, exec, clone, fork, ptrace, ioctl, filesystem mutation,
    mount, signal-to-peer or process-memory syscalls. Filtering is irreversible.
    """
    lib=ctypes.CDLL('libseccomp.so.2',use_errno=True)
    lib.seccomp_init.argtypes=[ctypes.c_uint32];lib.seccomp_init.restype=ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p];lib.seccomp_syscall_resolve_name.restype=ctypes.c_int
    lib.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
    lib.seccomp_load.argtypes=[ctypes.c_void_p];lib.seccomp_release.argtypes=[ctypes.c_void_p]
    ctx=lib.seccomp_init(0x00050000|errno.EPERM)
    if not ctx: raise RuntimeError('seccomp unavailable')
    calls='read write readv writev close fstat lseek brk mmap mmap2 munmap mremap madvise mprotect futex futex_time64 clock_gettime clock_gettime64 clock_nanosleep clock_nanosleep_time64 nanosleep gettimeofday time getrandom getpid getppid gettid getuid geteuid getgid getegid getresuid getresgid rt_sigaction rt_sigprocmask rt_sigreturn sigaltstack restart_syscall sched_yield getrusage poll ppoll ppoll_time64 select pselect6 pselect6_time64 recvmsg sendmsg recvfrom sendto getsockopt fcntl fcntl64 exit exit_group'
    try:
        for name in calls.split():
            number=lib.seccomp_syscall_resolve_name(name.encode())
            if number>=0 and lib.seccomp_rule_add(ctx,0x7fff0000,number,0)<0: raise RuntimeError('seccomp rule')
        # Prevent channel poisoning with extraneous inherited handles (including
        # journal fds, which could otherwise record private text).
        inherited=[int(name) for name in os.listdir('/proc/self/fd')]
        for fd in inherited:
            if fd!=channel.fileno():
                try: os.close(fd)
                except OSError: pass
        if lib.seccomp_load(ctx)<0: raise RuntimeError('seccomp load')
    finally: lib.seccomp_release(ctx)

class Client:
    """Application SDK: handles and semantic data only; no system paths."""
    def __init__(self,channel): self.channel=channel;self.sequence=0
    def call(self,op,args=None):
        self.sequence+=1
        return request(self.channel,op,args or {},self.sequence)
    def acquire(self,cap): return self.call(1,{0:cap})[0]
    def release(self,grant): return self.call(2,{0:grant})
    def ready(self): return self.call(3)
    def present(self,grant,title,body,actions,presentation=None):
        args={0:grant,1:title,2:body,3:actions}
        if presentation is not None:args[4]=presentation
        return self.call(4,args)
    def event(self): return self.call(5)
    def text(self,grant,initial='',limit=5120,*,label=None,multiline=True,caret=None,submit_label='Done'):
        args={0:grant,1:initial,2:limit}
        if label is not None:args[3]={0:label,1:multiline,2:len(initial) if caret is None else caret,3:submit_label}
        return self.call(6,args)
    def read(self,grant,key): return self.call(7,{0:grant,1:key})[0]
    def write(self,grant,key,text): return self.call(8,{0:grant,1:key,2:text})[0]
    def checkpointed(self,receipt): return self.call(9,{0:receipt})

def short_label(value,limit=64):
    return type(value)is str and len(value)<=limit and not any(unicodedata.category(c) in ('Cc','Cs') for c in value)

def presentation_checked(value,actions):
    if type(value)is not dict or value.get(0) not in ('notes','document','menu'):raise ValueError('view presentation')
    kind=value[0];allowed={'notes':{0,1,4},'document':{0,1,2,3,5,6},'menu':{0,5}}[kind]
    if set(value)!=allowed:raise ValueError('presentation fields')
    if kind=='notes':
        if not actions or not short_label(value[1],32) or type(value[4])is not list or len(value[4])!=len(actions) or any(not short_label(p,96) for p in value[4]):raise ValueError('note summaries')
    if kind=='document':
        if not short_label(value[1]) or not short_label(value[2],32) or value[3] not in ('saved','unsaved') or not short_label(value[6],200):raise ValueError('document labels')
    if kind in ('document','menu'):
        bindings=value[5]
        if kind=='document' and (type(bindings)is not dict or set(bindings)!={0,1,2,3}):raise ValueError('document bindings')
        if type(bindings)is not dict or not set(bindings)<={0,1,2,3} or any(type(k)is not int or type(v)is not int or not 0<=v<len(actions) for k,v in bindings.items()):raise ValueError('view bindings')
    return value

class Session:
    def __init__(self,policy,store,broker):
        self.policy,self.store,self.broker=policy,store,broker
        self.grants={};self.next_renew=time.monotonic()+20;self.ready=False;self.view=None;self.text_request=None;self.events=[]
        self.checkpoint='none';self.receipt=None;self.checkpoint_receipt=None;self.stopping=False
    def valid(self,grant,cap):
        if type(grant) is not bytes or self.grants.get(grant)!=cap: raise PermissionError('grant scope')
        self.broker.valid(grant,cap)
    def release(self,grant):
        cap=self.grants.get(grant)
        if cap is None: raise PermissionError('unknown grant')
        self.broker.release(grant)
        # Keep bounded tombstones for idempotent release, but never authorize use.
        self.grants[grant]=-cap if cap>0 else cap
        if cap==VISUAL:self.view=None
        if cap==TEXT:self.text_request=None;self.events=[e for e in self.events if e[0]!=2]
        if cap==ACTIONS:self.events=[e for e in self.events if e[0]!=1]
    def has(self,cap):
        for grant,kind in self.grants.items():
            if kind==cap:
                try:self.valid(grant,cap);return True
                except (PermissionError,OSError):continue
        return False
    def maintain(self):
        if time.monotonic()<self.next_renew:return
        self.next_renew=time.monotonic()+20
        for grant,cap in list(self.grants.items()):
            if cap>0:
                try:self.broker.renew(grant,cap)
                except (OSError,PermissionError):
                    self.grants[grant]=-cap
                    if cap==VISUAL:self.view=None
                    if cap==TEXT:self.text_request=None
    def dispatch(self,op,args):
        if type(args) is not dict:raise ValueError('arguments')
        keys={1:{0},2:{0},3:set(),4:{0,1,2,3},5:set(),6:{0,1,2},7:{0,1},8:{0,1,2},9:{0}}
        optional={4:{4},6:{3}}.get(op,set())
        if op not in keys or not keys[op]<=set(args) or not set(args)<=keys[op]|optional:raise ValueError('operation fields')
        if op==1:
            cap=args[0]
            if type(cap) is not int or cap not in (2,3,4,5,6,7,8) or not self.policy['mask']&(1<<(cap-1)) or len(self.grants)>=32:raise PermissionError('capability policy')
            if self.stopping and cap!=PRIVATE:raise PermissionError('stopping')
            grant=self.broker.acquire(cap);self.grants[grant]=cap;return {0:grant}
        if op==2:self.release(args[0]);return {0:1}
        if op==3:
            if self.stopping:raise PermissionError('stopping')
            self.ready=True;return {0:1}
        if op==4:
            self.valid(args[0],VISUAL)
            if type(args[1]) is not str or not 1<=len(args[1])<=64 or type(args[2]) is not str or len(args[2])>5120 or len(args[2].encode('utf-8'))>20480:raise ValueError('view text')
            actions=args[3]
            maximum=17 if isinstance(args.get(4),dict) and args[4].get(0)=='notes' else 8
            if type(actions) is not list or len(actions)>maximum or any(not short_label(a,32) or not a for a in actions):raise ValueError('view actions')
            view={0:args[1],1:args[2],2:actions}
            if 4 in args:view[3]=presentation_checked(args[4],actions)
            self.view=view;return {0:1}
        if op==5:
            while self.events:
                event=self.events.pop(0)
                if event[0]==3 or self.has(ACTIONS if event[0]==1 else TEXT):return event
            return {0:0}
        if op==6:
            self.valid(args[0],TEXT)
            if type(args[1]) is not str or type(args[2]) is not int or not 1<=args[2]<=5120 or len(args[1])>args[2] or len(args[1].encode('utf-8'))>20480:raise ValueError('text bounds')
            if self.text_request is not None:raise ValueError('text session busy')
            text={0:args[1],1:args[2]}
            if 3 in args:
                meta=args[3]
                if type(meta)is not dict or set(meta)!={0,1,2,3} or not short_label(meta[0]) or not meta[0] or type(meta[1])is not bool or type(meta[2])is not int or not 0<=meta[2]<=len(args[1]) or not short_label(meta[3],16) or not meta[3]:raise ValueError('text metadata')
                if not meta[1] and any(c in args[1] for c in '\n\r\t'):raise ValueError('single-line text')
                text[2]=meta
            self.text_request=text;return {0:1}
        if op in (7,8):
            self.valid(args[0],PRIVATE)
            if op==7:return {0:self.store.read(args[1])}
            receipt=self.store.write(args[1],args[2]);self.receipt=receipt
            if self.checkpoint=='pending' and args[1]=='checkpoint':self.checkpoint_receipt=receipt
            return {0:receipt}
        if op==9:
            if self.checkpoint!='pending' or self.checkpoint_receipt is None or args[0]!=self.checkpoint_receipt:raise ValueError('unacknowledged checkpoint')
            self.checkpoint='durable';return {0:1}
    def shell(self,op,args):
        if op==1:
            # Revalidate before displaying cached state; broker restart/revocation
            # must not leave a granted surface or keyboard on screen.
            if not self.has(VISUAL):self.view=None
            if not self.has(TEXT):self.text_request=None
            return {0:int(self.ready),1:self.view,2:self.text_request,3:self.checkpoint}
        if op==2:
            action=args.get(0)
            if not self.has(ACTIONS) or not self.view or type(action)is not int or not 0<=action<len(self.view[2]):raise PermissionError('action focus')
            if len(self.events)>=16:raise ValueError('event queue full')
            self.events.append({0:1,1:action});return {0:1}
        if op==3:
            text=args.get(0)
            if not self.has(TEXT) or self.text_request is None or type(text)is not str or len(text)>self.text_request[1] or len(text.encode('utf-8'))>20480:raise ValueError('text result')
            if len(self.events)>=16:raise ValueError('event queue full')
            if set(args)-{0,1,2} or (1 in args and type(args[1])is not bool):raise ValueError('text result flags')
            if 2 in args and (type(args[2])is not int or not 0<=args[2]<=len(text)):raise ValueError('text caret')
            if 2 in self.text_request and not self.text_request[2][1] and any(c in text for c in '\n\r\t'):raise ValueError('single-line text')
            event={0:2,1:text}
            if args.get(1):event[2]=True # Interrupted editor: recovery, not an explicit Save As.
            if 2 in args:event[3]=args[2]
            self.text_request=None;self.events.append(event);return {0:1}
        if op==4:
            self.checkpoint='pending';self.checkpoint_receipt=None
            # Preserve already submitted text before requesting a stop checkpoint.
            self.events=[e for e in self.events if e[0]==2]+[{0:3,1:'checkpoint'}]
            return {0:1}
        if op==5:
            cap=args.get(0)
            if cap not in (2,3,4,5,6,7,8):raise ValueError('capability')
            for grant,kind in list(self.grants.items()):
                if kind==cap:self.release(grant)
            return {0:1}
        if op==6:
            self.text_request=None
            if len(self.events)<16:self.events.append({0:2,1:None})
            return {0:1}
        raise ValueError('shell operation')

def serve(sock,handler):
    header,payload,fds=recv_packet(sock)
    for fd in fds:os.close(fd)
    if fds or header.message_class!=REQUEST or header.interface_major!=1 or set(payload)!={0,1,2} or type(payload[2])is not int or not now()<payload[2]<=now()+5_000_000_000:raise ProtocolError('request envelope')
    try: result=handler(payload[0],payload[1]);outcome=0
    except (ValueError,KeyError,TypeError,PermissionError,OSError):result={};outcome=6
    send_packet(sock,encode_packet(REPLY,header.request_id,{0:outcome,1:result}))

def child_main(channel,code,entry):
    signal.signal(signal.SIGTERM,signal.SIG_DFL)
    sandbox(channel)
    namespace={'__name__':'guide_application','__builtins__':__builtins__}
    try:
        exec(code,namespace)
        namespace[entry](Client(channel))
        os._exit(0)
    except BaseException:os._exit(70)

def notify_ready():
    path=os.environ.get('NOTIFY_SOCKET')
    if not path:raise RuntimeError('systemd notification unavailable')
    if path.startswith('@'):path='\0'+path[1:]
    with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as sock:sock.sendto(b'READY=1',path)

def main(code, health=False):
    policy,compiled=load_policy(code,health)
    # The app never inherits the store, broker socket or shell listener.
    parent,child=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
    pid=os.fork()
    if pid==0:
        parent.close();child_main(child,compiled,policy['entry'])
    child.close();parent.settimeout(.2)
    store=PrivateStore(Path(os.environ['RUNTIME_DIRECTORY'])/'health-private' if health else Path(os.environ['STATE_DIRECTORY'])/'objects',policy['quota'])
    session=Session(policy,store,Broker())
    listener=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET)
    endpoint=Path(os.environ['RUNTIME_DIRECTORY'])/'shell.sock'
    if not health:listener.bind(str(endpoint));os.chmod(endpoint,0o600);listener.listen(2)
    stop=[False];signal.signal(signal.SIGTERM,lambda *_:stop.__setitem__(0,True))
    start=time.monotonic();deadline=None;notified=False;exit_code=0
    try:
        while True:
            session.maintain()
            dead,status=os.waitpid(pid,os.WNOHANG)
            if dead:
                pid=0
                if not session.stopping or session.checkpoint!='durable' or not os.WIFEXITED(status) or os.WEXITSTATUS(status):exit_code=70
                break
            if stop[0] and not session.stopping:
                session.stopping=True;session.shell(4,{});deadline=time.monotonic()+1
            if deadline and (time.monotonic()>=deadline or session.checkpoint=='durable'):break
            if not session.ready and time.monotonic()-start>1.9:exit_code=71;break
            readable,_,_=select.select([parent] if health else [parent,listener],[],[],.02)
            for stream in readable:
                if stream is parent:serve(parent,session.dispatch)
                else:
                    peer,_=listener.accept()
                    with peer:
                        peer.settimeout(.05)
                        _,uid,_=struct.unpack('3i',peer.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                        if uid==0:
                            try:serve(peer,session.shell)
                            except (OSError,ValueError,EOFError):pass
            if session.ready and not notified:
                notify_ready();notified=True
                if health:stop[0]=True
    except (OSError,ValueError,EOFError):exit_code=72
    finally:
        if session.stopping and session.checkpoint!='durable':exit_code=73
        for grant,cap in list(session.grants.items()):
            if cap>0:
                try:session.release(grant)
                except (OSError,PermissionError):pass
        if pid:
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
            os.waitpid(pid,0)
        parent.close();listener.close();store.close()
        # Content-free typed outcome; never filenames, app exceptions or text.
        print('GUIDE_APPLICATION_EXIT',exit_code,'CHECKPOINT',session.checkpoint,file=sys.stderr)
    return exit_code
