"""Signed receipt adapters over the existing durable release/trial controller."""
import os,shutil,zipfile
from pathlib import Path
from deploy_core import Store,Rejected,require,read_json,atomic_json,digest,sync_dir,CHUNK,LIMIT
from signed_release import verify

class SignedStore(Store):
    def save(self,txn,state=None,reason=None):
        if state=='committed':
            path=self.base/'highest-sequence.json'
            old=read_json(path)['sequence'] if path.exists() else self.config['release_sequence']
            atomic_json(path,dict(sequence=max(old,self.sequence())))
        return super().save(txn,state,reason)
    def sequence(self):
        path=self.releases/self.active()['release']/'signed-manifest.json'
        return read_json(path)['profile']['manifest']['releaseSequence'] if path.exists() else self.config['release_sequence']
    def checked(self):
        return verify(self.archive,self.config.get('trust_root',self.base/'trust'),self.config,self.sequence())
    def status(self):
        result=super().status();result.update(protocol='GUIDE-SIGNED-BUNDLE-1',scope='signed-guide-release',sequence=self.sequence(),highest_sequence=max(self.sequence(),read_json(self.base/'highest-sequence.json')['sequence'] if (self.base/'highest-sequence.json').exists() else self.sequence()))
        return result
    def validate(self,identity):
        self.policy();txn=self.matching(identity,('receiving','validated'))
        require(txn['received']==txn['bytes'] and digest(self.archive)==identity,'incomplete-or-corrupt')
        try:
            manifest,files=self.checked();p=manifest['profile']['manifest']
            require(shutil.disk_usage(self.base).free>=max(manifest['requirements']['requiredFreeBytes'],manifest['requirements']['payloadBytes']+32_000_000),'insufficient-storage')
            if self.staging.exists():shutil.rmtree(self.staging)
            self.staging.mkdir(mode=0o755);self.staging.chmod(0o755)
            with zipfile.ZipFile(self.archive) as z:
                for name,record in files.items():
                    target=self.staging/name;target.parent.mkdir(exist_ok=True,mode=0o755);target.parent.chmod(0o755)
                    with z.open('payload/'+name) as source,target.open('xb') as output:
                        shutil.copyfileobj(source,output,CHUNK);output.flush();os.fsync(output.fileno())
                    require(digest(target)==record['sha256'],'payload-changed');target.chmod(0o644)
            # Keep the existing release launcher/checker contract while retaining
            # the authenticated manifest for sequence, scope and review evidence.
            atomic_json(self.staging/'manifest.json',dict(format='GUIDE-DEPLOY-1',device=self.config['device'],base=txn['base'],version=p['version'],arch='arm64',files=files))
            atomic_json(self.staging/'signed-manifest.json',manifest)
            for directory in self.staging.iterdir():
                if directory.is_dir():sync_dir(directory)
            sync_dir(self.staging);self.host.check_candidate(self.staging)
            txn.update(candidate=identity,version=p['version'],bundleId=manifest['bundleId'],signer=manifest['signing']['keyId'],sequence=p['releaseSequence'],approved=False,
                       review=dict(source=txn.get('source','Paired Wi-Fi transfer'),version=p['version'],signer=manifest['signing']['keyId'],bytes=txn['bytes'],components=sorted({n.split('/')[0] for n in files}),interruption='Restart Guide interface',reboot=False,rollback=True))
            self.save(txn,'validated');return txn
        except Exception as exc:
            reason=str(exc) if isinstance(exc,Rejected) else 'invalid-or-untrusted-package'
            self.save(txn,'rejected',reason);raise Rejected(reason) from None
    def authorize(self,identity,downgrade=False):
        txn=self.matching(identity,('validated',));manifest,_=self.checked()
        high_path=self.base/'highest-sequence.json'
        high=max(self.sequence(),read_json(high_path)['sequence'] if high_path.exists() else self.sequence())
        require(type(downgrade)is bool,'bad-approval')
        require(txn['sequence']>high or downgrade,'downgrade-approval-required')
        require(txn['bundleId']==manifest['bundleId'],'package-changed')
        txn.update(approved=True,downgrade=downgrade);self.save(txn);return txn
    def queue(self,identity):
        txn=self.matching(identity,('validated','queued','activating','trial','committed','rolled-back'))
        require(txn.get('approved') is True,'local-approval-required')
        if txn['state'] in ('validated','queued'):self.checked()
        return super().queue(identity)
    def apply(self):
        txn=self.transaction()
        if txn and txn['state']=='queued' and txn.get('mode')!='rollback':
            try:
                require(txn.get('approved') is True,'local-approval-required')
                manifest,_=self.checked()
                self.host.trial_seconds=manifest['profile']['manifest']['trialSeconds']
            except Exception:
                self.save(txn,'rejected','signature-or-admission-changed');return
        super().apply()
        txn=self.transaction()
        if txn and txn['state']=='committed':
            path=self.base/'highest-sequence.json'
            old=read_json(path)['sequence'] if path.exists() else self.config['release_sequence']
            atomic_json(path,dict(sequence=max(old,self.sequence())))
    def import_descriptor(self,fd):
        # Storage supplied a revalidated descriptor, never a caller-selected path.
        import stat,hashlib
        st=os.fstat(fd);require(stat.S_ISREG(st.st_mode) and 0<st.st_size<=LIMIT,'source-limit')
        h=hashlib.sha256();os.lseek(fd,0,0)
        while block:=os.read(fd,CHUNK):h.update(block)
        identity=h.hexdigest();txn=self.begin(identity,st.st_size,self.active()['release'])
        if txn['state'] in ('validated','committed','rolled-back'):return txn
        os.lseek(fd,txn['received'],0)
        while txn['received']<txn['bytes']:
            block=os.read(fd,min(CHUNK,txn['bytes']-txn['received']));require(block,'source-removed')
            self.chunk(identity,txn['received'],block);txn=self.transaction()
        txn['source']='External or internal file';self.save(txn)
        return self.validate(identity)
