"""Durable background downloads/copies; storage owns every destination."""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import threading
import time
import urllib.request
from urllib.parse import urlsplit
import uuid
from concurrent.futures import ThreadPoolExecutor

LIMIT=2*1024**3
TERMINAL={'completed','failed','cancelled'}

def atomic(path,value):
    temporary=path.with_suffix('.tmp')
    with temporary.open('w') as f:
        json.dump(value,f);f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)
    fd=os.open(path.parent,os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        old,new=urlsplit(req.full_url),urlsplit(newurl)
        if new.scheme not in ('http','https') or old.scheme=='https' and new.scheme!='https':
            raise ValueError('redirect-not-allowed')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

class Transfers:
    def __init__(self,root,storage,should_yield=None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.should_yield=should_yield or (lambda:False)
        self.storage=storage;self.jobs={};self.cancelled={};self.cookies={}
        self.lock=threading.RLock();self.pool=ThreadPoolExecutor(max_workers=1)
        for path in sorted(self.root.glob('*.json'))[-128:]:
            job=json.loads(path.read_text())
            if job['state'] not in TERMINAL:
                job.update(state='failed',reason='interrupted-reselect-or-retry',cleanup='partial-may-be-retained-hidden')
                atomic(path,job)
            self.jobs[job['id']]=job
    def save(self,job,**values):
        with self.lock:
            job.update(values,updated=time.time());atomic(self.root/(job['id']+'.json'),job)
    def public(self,job):
        return {k:v for k,v in job.items() if k not in ('source','owner')}
    def snapshot(self,owner=0,offset=0):
        if type(offset)is not int or not 0<=offset<=128 or offset%16:raise ValueError('invalid-page')
        with self.lock:
            rows=[self.public(j) for j in reversed(list(self.jobs.values())) if owner==0 or j['owner']==owner]
            return dict(jobs=rows[offset:offset+16],next=offset+16 if offset+16<len(rows) else None)
    def offer(self,source,name,owner=0,cookies=None):
        if len(self.jobs)>=128:
            old=next((j for j in self.jobs.values() if j['state'] in TERMINAL),None)
            if old is None:raise ValueError('transfer-queue-full')
            self.jobs.pop(old['id']);self.cookies.pop(old['id'],None);self.cancelled.pop(old['id'],None)
            (self.root/(old['id']+'.json')).unlink()

        if not isinstance(name,str) or not name or len(name.encode())>180 or any(c in name for c in '/\\\0') or any(ord(c)<32 for c in name):raise ValueError('invalid-name')
        if set(source)=={'url'}:
            p=urlsplit(source['url'])
            if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or len(source['url'])>8192:raise ValueError('unsupported-download')
        elif set(source)!={'entry'}:raise ValueError('unsupported-source')
        if cookies is not None and (not isinstance(cookies,list) or len(cookies)>64 or len(json.dumps(cookies))>16000):raise ValueError('cookie-limit')
        identity=uuid.uuid4().hex
        job=dict(id=identity,name=name,owner=owner,source=source,state='needs-attention',reason='choose-destination',bytes=0,total=None,retry='restart',can_pause=False,requires_session=bool(cookies))
        self.cookies[identity]=cookies or []
        self.jobs[identity]=job;self.cancelled[identity]=threading.Event();self.save(job)
        return self.public(job)
    def start(self,identity,folder,collision,owner=0):
        job=self.owned(identity,owner)
        if job['state'] not in ('needs-attention','failed','cancelled'):raise ValueError('transfer-busy')
        if collision not in ('ask','keep-both','skip'):raise ValueError('unsupported-collision-policy')
        if job.get('reason')=='name-collision':
            result,_=self.storage(5,dict(id=identity,collision=collision));self.save(job,**result);return self.public(job)
        if job.get('requires_session') and identity not in self.cookies:raise ValueError('reopen-browser-download-to-refresh-session')
        self.cancelled[identity]=threading.Event()
        self.save(job,state='queued',reason='',folder=folder,collision=collision,bytes=0,total=None)
        self.pool.submit(self.run,identity)
        return self.public(job)
    def owned(self,identity,owner):
        job=self.jobs[identity]
        if owner not in (0,job['owner']):raise ValueError('not-your-transfer')
        return job
    def cancel(self,identity,owner=0):
        job=self.owned(identity,owner)
        if job['state'] in TERMINAL:return self.public(job)
        with self.lock:
            if job['state']=='finalizing':raise ValueError('already-finalizing')
            self.cancelled[identity].set()
        if job['state']=='needs-attention':
            cleanup,_=self.storage(6,{'id':identity})
            self.save(job,state='cancelled',**cleanup)
        return self.public(job)
    def opener(self,identity):
        jar=http.cookiejar.CookieJar(policy=http.cookiejar.DefaultCookiePolicy(strict_ns_domain=http.cookiejar.DefaultCookiePolicy.DomainStrictNonDomain))
        for c in self.cookies.get(identity,[]):
            if set(c)!={'name','value','domain','path','secure'} or not all(isinstance(c[k],str) for k in ('name','value','domain','path')) or type(c['secure'])is not bool:raise ValueError('invalid-cookies')
            jar.set_cookie(http.cookiejar.Cookie(0,c['name'],c['value'],None,False,c['domain'],c['domain'].startswith('.'),c['domain'].startswith('.'),c['path'],True,c['secure'],None,True,None,None,{}))
        return urllib.request.build_opener(urllib.request.ProxyHandler({}),Redirects(),urllib.request.HTTPCookieProcessor(jar))
    def run(self,identity):
        job=self.jobs[identity];out=-1;source=None
        try:
            if self.cancelled[identity].is_set():raise InterruptedError()
            self.save(job,state='preparing',reason='')
            if 'url' in job['source']:
                source=self.opener(identity).open(urllib.request.Request(job['source']['url'],headers={'Accept-Encoding':'identity'}),timeout=5)
                if source.headers.get('Content-Encoding','identity').lower()!='identity':raise ValueError('unsupported-content-encoding')
                length=source.headers.get('Content-Length');total=int(length) if length is not None else None
            else:
                metadata,fds=self.storage(3,job['source']);source=os.fdopen(fds[0],'rb');total=metadata['bytes']
            if total is not None and not 0<=total<=LIMIT:raise ValueError('size-limit')
            _,fds=self.storage(4,dict(id=identity,folder=job['folder'],name=job['name']));out=fds[0]
            self.save(job,state='transferring',total=total)
            count=0;next_update=0;digest=hashlib.sha256()
            while True:
                if self.cancelled[identity].is_set():raise InterruptedError()
                paused=False
                while self.should_yield():
                    if not paused:self.save(job,state='paused',reason='waiting-for-playback');paused=True
                    if self.cancelled[identity].wait(.25):raise InterruptedError()
                if paused:self.save(job,state='transferring',reason='')
                block=source.read(65536)
                if not block:break
                count+=len(block)
                if count>LIMIT:raise ValueError('size-limit')
                st=os.fstatvfs(out)
                if st.f_bavail*st.f_frsize<len(block)+8*1024**2:raise ValueError('low-space')
                view=memoryview(block)
                while view:
                    written=os.write(out,view)
                    if written<=0:raise OSError('write-failed')
                    view=view[written:]
                digest.update(block)
                if time.monotonic()>=next_update:
                    self.storage(7,dict(id=identity));self.save(job,bytes=count)
                    next_update=time.monotonic()+.5
            if total is not None and total!=count:raise ValueError('incomplete-download')
            if self.cancelled[identity].is_set():raise InterruptedError()
            os.fsync(out);os.close(out);out=-1
            with self.lock:
                if self.cancelled[identity].is_set():raise InterruptedError()
                self.save(job,state='finalizing',bytes=count,sha256=digest.hexdigest())
            result,_=self.storage(5,dict(id=identity,collision=job['collision']))
            self.save(job,**result)
        except Exception as exc:
            cleanup={'cleanup':'partial-may-be-retained-hidden'}
            try:cleanup,_=self.storage(6,dict(id=identity))
            except Exception:pass
            reason='cancelled' if isinstance(exc,InterruptedError) else str(exc) if isinstance(exc,ValueError) else 'source-or-destination-unavailable'
            self.save(job,state='cancelled' if isinstance(exc,InterruptedError) else 'failed',reason=reason,**cleanup)
        finally:
            if source:source.close()
            if out>=0:os.close(out)
    def close(self):
        for event in self.cancelled.values():event.set()
        self.pool.shutdown(wait=True,cancel_futures=True)
