"""Storage-owned file access and no-overwrite publication for Transfer 0."""
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import stat
import uuid
import time
import struct
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from guide_install_wire import serve

SOCKET='/run/guideos-storage/files.sock'
MAX_ENTRIES=4096

def name_ok(name):
    return (isinstance(name,str) and 0<len(name.encode('utf-8'))<=180 and
            name not in ('.','..') and not name.startswith('.guide-part-') and
            not any(c in name for c in '/\\\0') and not any(ord(c)<32 for c in name))

def fingerprint(st):return [st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns]

def publish_noreplace(parent,source,target):
    libc=ctypes.CDLL(None,use_errno=True)
    result=libc.renameat2(parent,os.fsencode(source),parent,os.fsencode(target),1)
    if result:
        error=ctypes.get_errno()
        raise OSError(error,os.strerror(error))
    os.fsync(parent)

class Files:
    def __init__(self,mount,internal,current=None,writable=None):
        self.mount,self.internal=Path(mount),Path(internal)
        self.internal.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.current=current or (lambda:None)
        self.writable=writable or (lambda:False)
        self.write_available=lambda:True
        self.card=None;self.generation=0;self.epoch=uuid.uuid4().hex
        self.entries={};self.pending={};self.listener=None
        self.snapshots=OrderedDict();self.snapshot_bytes=0;self.scans={}
        self.scan_worker=ThreadPoolExecutor(max_workers=1,thread_name_prefix='guide-directory-scan')
        self.watch_keys={};self.watch_ids={};self.closed=False
        self.libc=ctypes.CDLL(None,use_errno=True)
        self.watch_fd=self.libc.inotify_init1(os.O_NONBLOCK|os.O_CLOEXEC)

    def refresh(self,card,generation):
        if card!=self.card or generation!=self.generation:
            for key in set(self.snapshots)|set(self.scans):
                if key[0]=='external':self.invalidate(key)
            for identity,tx in list(self.pending.items()):
                if tx['location']=='external':self.abort(identity)
            self.entries={k:v for k,v in self.entries.items() if v['location']=='internal'}
        self.card,self.generation=card,generation
    def valid(self,location):
        if location=='external' and (self.card is None or self.current()!=self.card):
            raise ValueError('card-removed')
    def root(self,location):
        if location not in ('internal','external'):raise ValueError('unknown-location')
        self.valid(location)
        return os.open(self.internal if location=='internal' else self.mount,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    def token(self,location,parts,st):
        if len(self.entries)>=MAX_ENTRIES*2:self.entries.pop(next(iter(self.entries)))
        token=secrets.token_hex(16)
        self.entries[token]={'location':location,'parts':parts,'generation':self.generation if location=='external' else 0,'fingerprint':fingerprint(st)}
        return token
    def resolve(self,token,directory=True):
        if token=='external':raise ValueError('refresh-required')
        if token=='internal':
            location=token;parts=[];record=None
        else:
            record=self.entries.get(token)
            if record is None:raise ValueError('refresh-required')
            location=record['location'];parts=record['parts']
            if location=='external' and record['generation']!=self.generation:raise ValueError('changed-location')
        fd=self.root(location)
        try:
            for n,part in enumerate(parts):
                flags=os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC
                if directory or n<len(parts)-1:flags|=os.O_DIRECTORY
                child=os.open(part,flags,dir_fd=fd);os.close(fd);fd=child
            st=os.fstat(fd)
            if not directory and (not stat.S_ISREG(st.st_mode) or record and record['fingerprint']!=fingerprint(st)):
                raise ValueError('changed-source')
            # Directory contents may change; the directory identity must not.
            if directory and record and record['fingerprint'][:2]!=fingerprint(st)[:2]:raise ValueError('changed-folder')
            return fd,location,parts
        except BaseException:os.close(fd);raise
    def roots(self):
        result=[dict(id='internal',name='Internal files',available=True,writable=True)]
        available=self.card is not None and self.current()==self.card
        identity='external-unavailable'
        if available:
            try:
                fd=self.root('external')
                try:identity=self.token('external',[],os.fstat(fd))
                finally:os.close(fd)
            except OSError:available=False
        result.append(dict(id=identity,name='External card',available=available,writable=available and self.write_available()))
        return result
    def invalidate(self,key):
        snapshot=self.snapshots.pop(key,None)
        if snapshot:self.snapshot_bytes-=snapshot['bytes']
        job=self.scans.get(key)
        if job:
            job['cancel'].set()
            if job['future'].cancel():os.close(job['fd']);self.scans.pop(key,None)
            elif job['future'].done():self.scans.pop(key,None)
        wd=self.watch_ids.pop(key,None)
        if wd is not None:
            self.watch_keys.pop(wd,None)
            self.libc.inotify_rm_watch(self.watch_fd,wd)

    def _watch(self,key,fd):
        if self.watch_fd<0 or key in self.watch_ids:return
        wd=self.libc.inotify_add_watch(self.watch_fd,os.fsencode('/proc/self/fd/'+str(fd)),
             0x2|0x4|0x8|0x40|0x80|0x100|0x200|0x400|0x800|0x2000)
        if wd>=0:self.watch_ids[key]=wd;self.watch_keys[wd]=key

    def tick(self):
        for key,job in list(self.scans.items()):
            if job['cancel'].is_set() and job['future'].done():self.scans.pop(key)
        if self.watch_fd<0:return
        # Bounded drain. Overflow invalidates every snapshot; it never certifies
        # unchanged content. A busy provider can retry on the next owning tick.
        for _ in range(4):
            try:data=os.read(self.watch_fd,65536)
            except BlockingIOError:break
            offset=0
            while offset+16<=len(data):
                wd,mask,cookie,length=struct.unpack_from('iIII',data,offset);offset+=16+length
                if mask&0x4000:
                    for key in set(self.snapshots)|set(self.scans):self.invalidate(key)
                elif wd in self.watch_keys:self.invalidate(self.watch_keys[wd])

    @staticmethod
    def _scan(fd,cancel):
        deadline=time.monotonic()+10
        try:
            before=fingerprint(os.fstat(fd));rows=[];budget=0
            with os.scandir(fd) as scan:
                count=0
                for entry in scan:
                    count+=1
                    if cancel.is_set() or time.monotonic()>deadline:raise ValueError('scan-cancelled')
                    if count>MAX_ENTRIES:raise ValueError('directory-limit')
                    if entry.name.startswith('.guide-part-'):continue
                    st=entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode):
                        budget+=1024+4*len(entry.name.encode('utf-8'))
                        if budget>8*1024**2:raise ValueError('directory-limit')
                        rows.append((entry.name,st))
            if before!=fingerprint(os.fstat(fd)):raise ValueError('refresh-required')
            rows.sort(key=lambda x:(not stat.S_ISDIR(x[1].st_mode),x[0].casefold(),x[0]))
            revision=hashlib.sha256(json.dumps([(n,fingerprint(st)) for n,st in rows]).encode()).hexdigest()
            return dict(rows=tuple(rows),signature=before,revision=revision,
                        bytes=budget,observed=time.monotonic())
        finally:os.close(fd)

    def listing(self,token,offset=0,*,revision=None,refresh=False,asynchronous=False):
        if type(offset)is not int or not 0<=offset<MAX_ENTRIES:raise ValueError('invalid-page')
        if revision is not None and (type(revision)is not str or len(revision)!=64):raise ValueError('invalid-page')
        self.tick()
        fd,location,parts=self.resolve(token)
        key=(location,tuple(parts),self.generation if location=='external' else 0)
        try:
            signature=fingerprint(os.fstat(fd));snapshot=self.snapshots.get(key)
            if snapshot and (refresh or snapshot['signature']!=signature or time.monotonic()-snapshot['observed']>10):
                self.invalidate(key);snapshot=None
            if snapshot is None:
                job=self.scans.get(key)
                if job and job['cancel'].is_set():raise ValueError('listing-pending')
                if job and job['signature']!=signature:self.invalidate(key);job=None
                if job is None:
                    if len(self.scans)>=2:raise ValueError('busy')
                    self._watch(key,fd)
                    owned=os.dup(fd);cancel=threading.Event()
                    job=dict(fd=owned,cancel=cancel,signature=signature)
                    try:job['future']=self.scan_worker.submit(self._scan,owned,cancel)
                    except BaseException:os.close(owned);raise
                    self.scans[key]=job
                if asynchronous and not job['future'].done():raise ValueError('listing-pending')
                try:snapshot=job['future'].result(timeout=11)
                except BaseException:self.invalidate(key);raise
                # Card identity, notifications and directory identity are checked
                # again before any worker result becomes opaque provider records.
                self.tick();self.valid(location)
                if self.scans.get(key)is not job or snapshot['signature']!=fingerprint(os.fstat(fd)):
                    raise ValueError('refresh-required')
                self.scans.pop(key)
                while self.snapshots and (len(self.snapshots)>=4 or self.snapshot_bytes+snapshot['bytes']>8*1024**2):
                    self.invalidate(next(iter(self.snapshots)))
                self.snapshots[key]=snapshot;self.snapshot_bytes+=snapshot['bytes']
            self.snapshots.move_to_end(key)
            if revision is not None and revision!=snapshot['revision']:raise ValueError('refresh-required')
            rows=snapshot['rows'];selected=rows[offset:offset+32]
            return dict(folder=token,revision=snapshot['revision'],items=[dict(id=self.token(location,parts+[n],st),name=n,kind='folder' if stat.S_ISDIR(st.st_mode) else 'file',size=None if stat.S_ISDIR(st.st_mode) else st.st_size) for n,st in selected],next=offset+32 if offset+32<len(rows) else None)
        finally:os.close(fd)

    def begin(self,folder,name,identity):
        if not name_ok(name) or not isinstance(identity,str) or len(identity)!=32 or any(c not in '0123456789abcdef' for c in identity):raise ValueError('invalid-name')
        if identity in self.pending or len(self.pending)>=16:raise ValueError('busy')
        parent,location,parts=self.resolve(folder)
        part='.guide-part-'+identity
        try:
            if location=='external' and not self.writable():raise ValueError('read-only-location')
            st=os.fstatvfs(parent)
            if st.f_bavail*st.f_frsize<16*1024**2:raise ValueError('low-space')
            fd=os.open(part,os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=parent)
            self.pending[identity]=dict(parent=parent,part=part,name=name,location=location,generation=self.generation)
            return dict(id=identity),[fd]
        except BaseException:os.close(parent);raise
    def check(self,identity):
        tx=self.pending[identity];self.valid(tx['location'])
        if tx['location']=='external' and tx['generation']!=self.generation:raise ValueError('changed-location')
        st=os.fstatvfs(tx['parent'])
        if st.f_bavail*st.f_frsize<8*1024**2:raise ValueError('low-space')
        return tx
    def finish(self,identity,collision):
        if collision not in ('ask','keep-both','skip'):raise ValueError('unsupported-collision-policy')
        tx=self.check(identity);parent=tx['parent'];name=tx['name']
        fd=os.open(tx['part'],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
        try:os.fsync(fd);size=os.fstat(fd).st_size
        finally:os.close(fd)
        for index in range(1000):
            candidate=name if not index else str(Path(name).stem)+f' ({index})'+Path(name).suffix
            try:publish_noreplace(parent,tx['part'],candidate);break
            except FileExistsError:
                if collision=='ask':return dict(state='needs-attention',reason='name-collision',choices=['keep-both','skip','cancel'])
                if collision=='skip':self.abort(identity);return dict(state='cancelled',reason='skipped-existing',cleanup='removed')
        else:raise ValueError('name-collision-limit')
        os.close(parent);del self.pending[identity]
        for key in set(self.snapshots)|set(self.scans):
            if key[0]==tx['location']:self.invalidate(key)
        return dict(state='completed',name=candidate,bytes=size,location=tx['location'],checksum='not-independently-verified')
    def abort(self,identity):
        tx=self.pending.pop(identity,None)
        if not tx:return dict(cleanup='not-present')
        cleanup='removed'
        try:
            os.unlink(tx['part'],dir_fd=tx['parent']);os.fsync(tx['parent'])
        except OSError:cleanup='retained-hidden-partial'
        finally:os.close(tx['parent'])
        return dict(cleanup=cleanup)
    def dispatch(self,op,args,*,asynchronous=False):
        if op==1:return dict(locations=self.roots()),[]
        if op==2:return self.listing(args['folder'],args.get('offset',0),revision=args.get('revision'),refresh=args.get('refresh',False),asynchronous=asynchronous),[]
        if op==3:
            fd,_,_=self.resolve(args['entry'],False)
            return dict(bytes=os.fstat(fd).st_size),[fd]
        if op==4:return self.begin(args['folder'],args['name'],args['id'])
        if op==5:return self.finish(args['id'],args['collision']),[]
        if op==6:return self.abort(args['id']),[]
        if op==7:self.check(args['id']);return dict(available=True),[]
        raise ValueError('unknown-operation')
    def connect(self,path=SOCKET):
        self.listener=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        Path(path).unlink(missing_ok=True);self.listener.bind(str(path));os.chmod(path,0o600);self.listener.listen(4)
    def wire_dispatch(self,op,args):
        try:return self.dispatch(op,args,asynchronous=isinstance(args,dict) and args.get('async_listing') is True)
        except (ValueError,KeyError,OSError) as exc:
            reason=str(exc)
            known={'card-removed','changed-location','changed-source','changed-folder','read-only-location','low-space','name-collision-limit','directory-limit','refresh-required','invalid-name','busy','listing-pending'}
            return {'errorCode':reason if reason in known else 'file-unavailable'},[]
    def poll(self):
        peer,_=self.listener.accept()
        with peer:
            try:serve(peer,self.wire_dispatch)
            except (OSError,ValueError,EOFError):pass
    def close(self):
        self.closed=True
        for key in set(self.snapshots)|set(self.scans):self.invalidate(key)
        self.scan_worker.shutdown(wait=True,cancel_futures=True)
        if self.watch_fd>=0:os.close(self.watch_fd);self.watch_fd=-1
        for identity in list(self.pending):self.abort(identity)
        if self.listener:self.listener.close()
