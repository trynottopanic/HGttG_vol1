"""Durable application installation. All paths derive from validated IDs/versions.

Only this owner service publishes releases. A single transaction lock covers
activation, health, recovery, uninstall and explicit private-data deletion.
"""
import fcntl, hashlib, json, os, pwd, re, shutil, socket, stat, subprocess, sys, threading, time, uuid
from pathlib import Path
from guide_cartridge import *

class Cancelled(Exception):pass

def sync_dir(path):
    fd=os.open(path,os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

def atomic(path,data,limit=32768):
    require(len(data)<=limit,'record bound');path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.pending')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        with os.fdopen(fd,'wb',closefd=False) as f:f.write(data);f.flush();os.fsync(fd)
    finally:os.close(fd)
    os.chmod(tmp,0o644);os.replace(tmp,path);sync_dir(path.parent)

def encode_record(record):
    # C loader checks this canonical prefix without needing a second JSON parser.
    ordered={'runtime_policy':record['runtime_policy'],'state':record['state']}
    ordered.update({k:v for k,v in record.items() if k not in ordered})
    return json.dumps(ordered,ensure_ascii=True,separators=(',',':')).encode('ascii')

def policy(record):
    m=record['package']['manifest'];a=record['package']['application'];ep=m['entrypoint']
    binding=digest(canonical({k:record[k] for k in ('code','generation','package','agreement')}))
    mask=sum(1<<(CAPABILITIES[c]-1) for c in record['agreement']['granted'])
    return f"format=2\ncode={record['code']}\nid={m['id']}\nmodule={ep['module']}\nentry={ep['callable']}\nsha256={record['package']['sourceHash']}\ncapabilities={mask}\nprivate_bytes={a['privateBytes']}\nversion={m['version']}\nbinding={binding}\n"

def version_key(value):
    m=re.fullmatch(VERSION,value);require(m is not None,'version')
    pre=m.group(4);return (int(m[1]),int(m[2]),int(m[3]),1 if pre is None else 0,tuple((0,int(x)) if x.isdigit() else (1,x) for x in pre.split('.')) if pre else ())

def supervisor(op,args):
    from guide_application_runtime import request
    with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as s:
        s.settimeout(.8);s.connect('/run/guideos/supervisor/control.sock');return request(s,op,args)

def stop_application(code,require_checkpoint=True):
    found=supervisor(6,{0:code})
    if not found[0]:return
    identity={0:found[1],1:found[2]};supervisor(3,identity);end=time.monotonic()+4
    while time.monotonic()<end:
        state=supervisor(4,identity)
        if state[0] in (7,8):
            require(not require_checkpoint or state[1]==2,'checkpoint not confirmed');return
        time.sleep(.05)
    raise ValueError('application stop not observed')

def health_check(code):
    identity=supervisor(5,{0:code});end=time.monotonic()+5
    try:
        while time.monotonic()<end:
            state=supervisor(4,identity)
            if state[0] in (7,8):return state[0]==7 and state[1]==2
            time.sleep(.05)
        return False
    finally:stop_application(code,False)

def helper(archive,expected,extract=None):
    """The parser starts unprivileged; the root publisher never parses ZIP."""
    from guide_ipc import REQUEST,REPLY,encode_packet,send_packet,recv_packet
    from guide_install_wire import now
    transaction=None
    if extract is not None:
        path=Path(extract);transaction=path.parent.name
        require(path.name=='release' and re.fullmatch(r'[a-f0-9]{32}',transaction),'parser transaction')
    fd=os.open(archive,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as peer:
            peer.settimeout(12);peer.connect('/run/guideos/installer/parser.sock')
            send_packet(peer,encode_packet(REQUEST,1,{0:1,1:{0:canonical({'sha256':expected,'transaction':transaction})},2:now()+12_000_000_000},descriptor_count=1),[fd])
            h,p,fds=recv_packet(peer)
            for extra in fds:os.close(extra)
            require(not fds and h.message_class==REPLY and h.request_id==1 and p[0]==0,'cartridge verification failed')
            return json_read(p[1][0])
    finally:os.close(fd)

class Installer:
    def __init__(self,root='/',health=health_check,stop=stop_application,inspect=helper,fault=lambda point:None,reserve_bytes=0):
        self.root=Path(root);self.registry=self.root/'var/lib/guideos/applications';self.programs=self.root/'opt/guideos/applications';self.base=self.root/'var/lib/guideos/installer'
        self.transactions=self.base/'transactions';self.staging=self.base/'staging'
        for p in (self.registry,self.programs,self.transactions,self.staging):p.mkdir(parents=True,exist_ok=True)
        self.health,self.stop,self.inspect,self.fault=health,stop,inspect,fault
        self.reserve=reserve_bytes;self.cancel=threading.Event();self.lock=threading.Lock();self.status={'phase':'idle','revision':0}
        self.lockfd=os.open(self.base/'lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);fcntl.flock(self.lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def close(self):os.close(self.lockfd)
    def checkpoint(self,point):self.fault(point)
    def record(self,ident):
        require(type(ident)is str and re.fullmatch(IDENT,ident),'application ID')
        path=self.registry/ident/'installation.json'
        if not path.exists():return None
        require(not path.is_symlink() and path.stat().st_size<=32768,'installation record')
        return json_read(path.read_bytes())
    def publish(self,record,state):
        record=dict(record,state=state);ident=record['package']['manifest']['id']
        self.checkpoint('before-record-'+state);atomic(self.registry/ident/'installation.json',encode_record(record));self.checkpoint('after-record-'+state)
        projection=self.registry/(str(record['code'])+'.policy')
        if state in ('committed','testing','preparing'):atomic(projection,record['runtime_policy'].encode('ascii'),2047)
        else:
            projection.unlink(missing_ok=True);sync_dir(self.registry)
        self.checkpoint('after-projection-'+state)
    def journal(self,tx,phase):
        updated=dict(tx,phase=phase,revision=tx.get('revision',0)+1)
        self.checkpoint('before-journal-'+phase);atomic(self.transactions/(tx['id']+'.json'),canonical(updated),65536)
        tx.update(updated);self.status=dict(tx);self.checkpoint('after-journal-'+phase)
    def prune_receipts(self):
        receipts=sorted(self.transactions.glob('*.json'),key=lambda p:p.stat().st_mtime_ns)
        for path in receipts[:-15]:
            tx=json_read(path.read_bytes())
            require(tx.get('phase') in ('committed','failed','cancelled','recovered'),'unfinished transaction')
            path.unlink();sync_dir(self.transactions)
    def alias(self,ident,old):
        if old:return old['code']
        require(sum(1 for _ in self.registry.glob('*/installation.json'))<128,'application registry capacity')
        path=self.base/'next-code';code=int(path.read_text()) if path.exists() else 10000
        used={10010}|{self.record(p.parent.name)['code'] for p in self.registry.glob('*/installation.json')}  # Reserved trusted Planegotchi host
        while code in used:code+=1
        require(10000<=code<0xffffffff,'runtime code exhaustion');atomic(path,str(code+1).encode(),32);return code
    def make_record(self,package,old,granted):
        m=package['manifest'];app=package['application'];caps=m['capabilities'];optional=app['optionalCapabilities']
        require(type(granted)is list and len(granted)==len(set(granted)) and set(granted)<=set(caps) and set(caps)-set(optional)<=set(granted),'agreement capabilities')
        record={'code':self.alias(m['id'],old),'generation':old['generation']+1 if old else 1,'package':package,'agreement':{'revision':old['agreement']['revision']+1 if old else 1,'granted':sorted(granted),'archiveHash':package['sha256']},'state':'testing'}
        record['runtime_policy']=policy(record);return record
    def check_update(self,package,old,downgrade):
        if not old:return
        before=old['package'];m=package['manifest'];prior=before['manifest']
        if m['version']==prior['version']:
            require(package['sha256']==before['sha256'],'same version has different content')
        require(package['application']['dataSchema']==before['application']['dataSchema'],'data migration unsupported')
        require(downgrade or version_key(m['version'])>=version_key(prior['version']),'downgrade agreement required')
    def ensure_space(self,package):
        # Treat even the unprivileged helper's plan as bounded input to the root
        # publisher. No helper-supplied path becomes an arbitrary destination.
        require(type(package['archiveBytes'])is int and 0<package['archiveBytes']<=ARCHIVE_MAX,'publication archive bound')
        require(type(package['expandedBytes'])is int and 0<package['expandedBytes']<=EXPANDED_MAX,'publication expanded bound')
        for key in ('sha256','sourceHash','inventoryHash'):require(type(package[key])is str and re.fullmatch(r'[a-f0-9]{64}',package[key]),'publication digest')
        files=package['manifest']['files'];require(type(files)is list and len(files)<=64,'publication inventory bound')
        names=set();total=0
        for item in files:
            name=item['path'];path_check(name);require(name.startswith('CONTENT/') and name.casefold() not in names,'publication path');names.add(name.casefold())
            require(type(item['bytes'])is int and 0<=item['bytes']<=EXPANDED_MAX and re.fullmatch(r'[a-f0-9]{64}',item['sha256']),'publication file bound')
            total+=item['bytes'];require(total<=EXPANDED_MAX,'publication total bound')
        st=os.statvfs(self.base);block=st.f_frsize
        rounding=(len(package['manifest']['files'])+24)*block
        needed=max(package['archiveBytes']+package['expandedBytes'],2*package['expandedBytes'])+262144+rounding+self.reserve
        require(st.f_bavail*block>=needed,'insufficient internal storage')
        require(os.stat(self.staging).st_dev==os.stat(self.programs).st_dev,'publication filesystem differs')
    def cancelled(self):
        if self.cancel.is_set():raise Cancelled()
    def inventory(self,tree,package):
        expected={f['path'].removeprefix('CONTENT/'):f for f in package['manifest']['files']};actual=set()
        entries=0
        for path in tree.rglob('*'):
            entries+=1;require(entries<=512,'publication tree bound')
            require(not path.is_symlink(),'staged symlink')
            if path.is_dir():continue
            rel=path.relative_to(tree).as_posix();require(rel in expected and path.is_file(),'staged unexpected object');actual.add(rel)
            info=expected[rel];require(path.stat().st_nlink==1 and path.stat().st_size==info['bytes'] and digest(path.read_bytes())==info['sha256'],'staged inventory changed')
            os.chown(path,0,0) if os.geteuid()==0 else None;os.chmod(path,0o444)
            with path.open('rb') as f:os.fsync(f.fileno())
        require(actual==set(expected),'staged inventory missing')
        for path in sorted([tree]+[p for p in tree.rglob('*') if p.is_dir()],key=lambda p:len(p.parts),reverse=True):
            if os.geteuid()==0:os.chown(path,0,0)
            os.chmod(path,0o555);sync_dir(path)
    def remove_owned(self,path,parent):
        # Cleanup only known transaction/release children. Never follow symlinks.
        require(path.parent.resolve()==parent.resolve() and path!=parent,'cleanup scope')
        if path.is_symlink():raise ValueError('cleanup symlink')
        if path.exists():
            for p in [path]+list(path.rglob('*')):
                if p.is_dir() and not p.is_symlink():p.chmod(0o700)
            shutil.rmtree(path);sync_dir(parent)
    def publish_tree(self,tree,target,tx,package):
        # systemd bind mounts can make rename return EXDEV even when st_dev
        # matches. Copy into an owned sibling, then atomically rename locally.
        pending=target.parent/('.pending-'+tx['id']);require(not pending.exists(),'publication residue')
        pending.mkdir(mode=0o700);sync_dir(target.parent)
        for item in package['manifest']['files']:
            relative=item['path'].removeprefix('CONTENT/');source=tree/relative;dest=pending/relative
            path_check(item['path']);dest.parent.mkdir(parents=True,exist_ok=True)
            with source.open('rb') as src,dest.open('xb') as dst:
                while True:
                    chunk=src.read(65536)
                    if not chunk:break
                    used=sum(p.stat().st_size for base in (tree.parent,pending) for p in base.rglob('*') if p.is_file())
                    require(used+len(chunk)<=4194304,'transaction staging bound')
                    dst.write(chunk)
                dst.flush();os.fsync(dst.fileno())
            source.unlink();sync_dir(source.parent)
        self.inventory(pending,package);self.checkpoint('before-release-rename')
        os.rename(pending,target);sync_dir(target.parent);self.checkpoint('after-release-rename')
        self.remove_owned(tree,tree.parent)
    def install(self,source_fd,package,granted,request_id,downgrade=False,source_current=lambda:True):
        require(re.fullmatch(r'[a-f0-9]{32}',request_id or ''),'request ID')
        with self.lock:
            journal=self.transactions/(request_id+'.json')
            if journal.exists():
                prior=json_read(journal.read_bytes());require(prior['archiveHash']==package['sha256'],'request ID reused');self.status=prior;return prior
            m=package['manifest'];ident=m['id'];version=m['version']
            require(re.fullmatch(IDENT,ident) and re.fullmatch(VERSION,version),'publication identity')
            self.prune_receipts()
            old=self.record(ident);self.check_update(package,old,downgrade)
            if old and old['state']=='committed' and old['package']['sha256']==package['sha256']:
                self.status={'id':request_id,'phase':'already-installed','revision':1,'code':old['code']};return self.status
            self.ensure_space(package);stage=self.staging/request_id;stage.mkdir(mode=0o711);sync_dir(self.staging)
            tx={'id':request_id,'application':ident,'version':version,'archiveHash':package['sha256'],'phase':'staging','revision':0,'hadPrior':old is not None,'code':old['code'] if old else 0}
            if old:atomic(stage/'prior.json',encode_record(old))
            self.journal(tx,'staging');record=None
            try:
                self.cancelled();require(source_current(),'source changed')
                archive=stage/'archive.guide';os.lseek(source_fd,0,os.SEEK_SET);total=0;sha=hashlib.sha256()
                with archive.open('xb') as target:
                    while True:
                        self.cancelled();chunk=os.read(source_fd,65536)
                        if not chunk:break
                        total+=len(chunk);require(total<=ARCHIVE_MAX,'archive copy bound');sha.update(chunk);target.write(chunk)
                    target.flush();os.fsync(target.fileno())
                sync_dir(stage);require(total==package['archiveBytes'] and sha.hexdigest()==package['sha256'] and source_current(),'source changed')
                tree=stage/'release';tree.mkdir(mode=0o700)
                if os.geteuid()==0:os.chown(tree,pwd.getpwnam('guide-archive').pw_uid,pwd.getpwnam('guide-archive').pw_gid)
                checked=self.inspect(archive,package['sha256'],tree);require(checked==package,'staged verification changed')
                self.inventory(tree,package);archive.unlink();sync_dir(stage);self.cancelled()
                record=self.make_record(package,old,granted);tx['code']=record['code'];atomic(stage/'candidate.json',encode_record(record))
                self.journal(tx,'activation-intent')
                if old and old['state']=='committed':self.publish(old,'preparing');self.stop(old['code'])
                self.cancelled();releases=self.programs/ident/'releases';releases.mkdir(parents=True,exist_ok=True)
                target=releases/version;require(not target.exists(),'release already present')
                self.publish_tree(tree,target,tx,package)
                self.publish(record,'testing');self.journal(tx,'health-check')
                self.cancelled();require(self.health(record['code']),'health check failed');self.cancelled()
                self.journal(tx,'commit-intent');self.publish(record,'committed');self.journal(tx,'committed')
                self.retain(record,old);self.remove_owned(stage,self.staging);return self.status
            except BaseException as error:
                # Simulated process death intentionally bypasses rollback. On a
                # real abrupt death the next service start follows this journal.
                if not isinstance(error,Exception):raise
                self.restore(tx,stage,old,record)
                self.journal(tx,'cancelled' if isinstance(error,Cancelled) else 'failed')
                self.remove_owned(stage,self.staging)
                if not isinstance(error,Cancelled):raise
                return self.status
    def restore(self,tx,stage,old,record):
        if tx['phase'] in ('activation-intent','health-check','commit-intent'):
            if tx['code']:self.stop(tx['code'],False)
            if old:self.publish(old,old['state'])
            elif record:self.publish(record,'uninstalled')
            releases=self.programs/tx['application']/'releases';target=releases/tx['version']
            pending=releases/('.pending-'+tx['id'])
            if pending.exists():self.remove_owned(pending,releases)
            if tx.get('operation')!='rollback' and target.exists() and (not old or old['state']=='uninstalled' or old['package']['manifest']['version']!=tx['version']):self.remove_owned(target,releases)
    def retain(self,record,old):
        ident=record['package']['manifest']['id'];recovery=self.registry/ident/'recovery';recovery.mkdir(exist_ok=True)
        keep={record['package']['manifest']['version']}
        if old and old['state']=='committed':
            version=old['package']['manifest']['version'];keep.add(version);atomic(recovery/(version+'.json'),encode_record(old))
        releases=self.programs/ident/'releases'
        for p in releases.iterdir():
            if p.name not in keep:self.remove_owned(p,releases)
        for p in recovery.iterdir():
            if p.suffix=='.json' and p.stem not in keep:p.unlink();sync_dir(recovery)
    def uninstall(self,ident,request_id,delete_data=False,expected_generation=None):
        require(re.fullmatch(r'[a-f0-9]{32}',request_id or ''),'request ID')
        with self.lock:
            path=self.transactions/(request_id+'.json')
            if path.exists():
                prior=json_read(path.read_bytes());require(prior['application']==ident and prior.get('operation')==('delete-data' if delete_data else 'uninstall'),'request ID reused');return prior
            old=self.record(ident);require(old is not None,'application missing')
            require(expected_generation is None or old['generation']==expected_generation,'installation changed')
            require(not delete_data or old['state']=='uninstalled','remove program before private data')
            stage=self.staging/request_id;stage.mkdir();atomic(stage/'prior.json',encode_record(old))
            tx={'id':request_id,'application':ident,'version':old['package']['manifest']['version'],'archiveHash':old['package']['sha256'],'code':old['code'],'hadPrior':True,'operation':'delete-data' if delete_data else 'uninstall','revision':0}
            self.journal(tx,'removal-preparing')
            try:
                if old['state']=='committed':self.publish(old,'preparing');self.stop(old['code'])
                self.cancelled()
            except Exception:
                self.publish(old,old['state']);self.journal(tx,'failed');self.remove_owned(stage,self.staging);raise
            self.journal(tx,'removal-intent')
            self.finish_removal(tx,old);self.journal(tx,'committed');self.remove_owned(stage,self.staging);return self.status
    def finish_removal(self,tx,old):
        self.stop(old['code'],False);self.publish(old,'uninstalled')
        ident=tx['application'];releases=self.programs/ident/'releases'
        if releases.exists():
            for path in releases.iterdir():self.remove_owned(path,releases)
        if tx['operation']=='delete-data':
            private=self.registry/ident/'private'
            if private.is_symlink():
                expected=self.root/'var/lib/private/guideos/applications'/ident/'private'
                require(private.resolve()==expected.resolve() and not expected.is_symlink(),'private store ownership')
                if expected.exists():self.remove_owned(expected,expected.parent)
                private.unlink();sync_dir(private.parent)
            elif private.exists():self.remove_owned(private,private.parent)
            recovery=self.registry/ident/'recovery'
            if recovery.exists():self.remove_owned(recovery,recovery.parent)
    def rollback(self,ident,version,request_id,expected_generation=None):
        require(re.fullmatch(VERSION,version or ''),'rollback version')
        with self.lock:
            old=self.record(ident);require(old and old['state']=='committed','installed application required')
            require(expected_generation is None or old['generation']==expected_generation,'installation changed')
            path=self.registry/ident/'recovery'/(version+'.json');require(path.exists() and not path.is_symlink(),'retained release missing')
            prior=json_read(path.read_bytes());require(prior['package']['application']['dataSchema']==old['package']['application']['dataSchema'],'data migration unsupported')
            require(re.fullmatch(r'[a-f0-9]{32}',request_id or ''),'request ID')
            journal=self.transactions/(request_id+'.json')
            if journal.exists():return json_read(journal.read_bytes())
            stage=self.staging/request_id;stage.mkdir();atomic(stage/'prior.json',encode_record(old))
            candidate=self.make_record(prior['package'],old,prior['agreement']['granted']);atomic(stage/'candidate.json',encode_record(candidate))
            tx={'id':request_id,'application':ident,'version':version,'archiveHash':prior['package']['sha256'],'code':old['code'],'hadPrior':True,'operation':'rollback','revision':0}
            self.journal(tx,'activation-intent')
            try:
                self.publish(old,'preparing');self.stop(old['code']);self.inventory(self.programs/ident/'releases'/version,prior['package'])
                self.cancelled();self.publish(candidate,'testing');self.journal(tx,'health-check');require(self.health(old['code']),'rollback health failed');self.cancelled()
                self.journal(tx,'commit-intent');self.publish(candidate,'committed');self.journal(tx,'committed');self.retain(candidate,old)
            except Exception:
                self.restore(tx,stage,old,candidate);self.journal(tx,'failed');raise
            finally:self.remove_owned(stage,self.staging)
            return self.status
    def recover(self):
        with self.lock:
            require(not any(self.transactions.glob('*.quarantine')),'installer recovery requires inspection')
            for path in sorted(self.transactions.glob('*.json')):
                try:
                    tx=json_read(path.read_bytes());require(tx['id']==path.stem and re.fullmatch(r'[a-f0-9]{32}',tx['id']) and re.fullmatch(IDENT,tx['application']) and re.fullmatch(VERSION,tx['version']),'journal identity')
                    stage=self.staging/tx['id']
                    if tx['phase'] in ('committed','failed','cancelled','recovered'):
                        if stage.exists():
                            if tx['phase']=='committed' and not tx.get('operation'):
                                candidate=json_read((stage/'candidate.json').read_bytes());old=json_read((stage/'prior.json').read_bytes()) if tx['hadPrior'] else None;self.retain(candidate,old)
                            self.remove_owned(stage,self.staging)
                        continue
                    require(tx['phase'] in ('staging','activation-intent','health-check','commit-intent','removal-preparing','removal-intent'),'journal phase')
                    old=json_read((stage/'prior.json').read_bytes()) if tx['hadPrior'] else None
                    candidate=json_read((stage/'candidate.json').read_bytes()) if (stage/'candidate.json').exists() else None
                    if tx['phase']=='removal-intent':self.finish_removal(tx,old)
                    elif tx['phase']=='removal-preparing':self.stop(old['code'],False);self.publish(old,old['state'])
                    else:self.restore(tx,stage,old,candidate)
                    self.journal(tx,'recovered')
                    if stage.exists():self.remove_owned(stage,self.staging)
                except (ValueError,KeyError,TypeError,OSError):
                    # Keep all residues and withhold catalog until reviewed.
                    quarantine=path.with_suffix('.quarantine');os.replace(path,quarantine);sync_dir(self.transactions)
                    self.status={'phase':'recovery-required','revision':1};raise ValueError('installer recovery requires inspection')
    def catalog(self):
        result=[]
        for path in sorted(self.registry.glob('*/installation.json')):
            record=self.record(path.parent.name)
            if record['state'] not in ('committed','uninstalled'):continue
            m=record['package']['manifest'];result.append(dict(id=m['id'],name=m['name'],version=m['version'],code=record['code'],generation=record['generation'],state=record['state'],retainedData=(self.registry/m['id']/'private').exists(),rollbackVersions=[p.stem for p in (self.registry/m['id']/'recovery').glob('*.json') if p.stem!=m['version'] and (self.programs/m['id']/'releases'/p.stem).is_dir()]))
            require(len(result)<=128,'installed catalog bound')
        return result
