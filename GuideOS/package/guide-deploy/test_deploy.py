import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from deploy_core import Store, Rejected, LIMIT, CHUNK, REQUIRED, atomic_json, canonical, digest
from deploy_server import dispatch
from guide_deploy_shell import ShellBridge

class PowerLoss(BaseException): pass

class Host:
    def __init__(self):
        self.calls = []
        self.fail = None
        self.crash = None
    def call(self, name):
        self.calls.append(name)
        if self.crash == name: raise PowerLoss()
        if self.fail == name: raise Rejected('test-' + name)
    def schedule(self): self.call('schedule')
    def check_candidate(self, path): self.call('check')
    def admit(self): self.call('admit')
    def quiesce(self, token): self.call('quiesce')
    def unquiesce(self): self.call('unquiesce')
    def stop(self, recovery=False): self.call('recovery-stop' if recovery else 'stop')
    def start(self): self.call('start')
    def healthy(self, identity): self.call('healthy-' + identity[0])

class Deployment(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'releases'/('a'*64)).mkdir(parents=True)
        atomic_json(self.root/'config.json', dict(device='deck-test',enabled=True))
        atomic_json(self.root/'active.json', dict(release='a'*64,version='old'))
        self.host = Host()
        self.store = Store(self.root,self.host)
    def package(self, transform=None, extra=None):
        data={name: b'# test module\n' for name in REQUIRED}
        manifest=dict(format='GUIDE-DEPLOY-1',device='deck-test',base='a'*64,arch='arm64',version='new',
                      files={name:dict(bytes=len(value),sha256=hashlib.sha256(value).hexdigest()) for name,value in data.items()})
        if transform: transform(manifest)
        package=self.root/'test.zip'
        with zipfile.ZipFile(package,'w') as archive:
            archive.writestr('manifest.json',canonical(manifest))
            for name,value in data.items(): archive.writestr(name,value)
            if extra: archive.writestr(*extra)
        return package
    def stage(self, package=None):
        package=package or self.package()
        identity=digest(package)
        self.store.begin(identity,package.stat().st_size,'a'*64)
        data=package.read_bytes()
        for offset in range(0,len(data),CHUNK): self.store.chunk(identity,offset,data[offset:offset+CHUNK])
        self.store.validate(identity)
        return identity
    def test_commit(self):
        identity=self.stage(); self.store.queue(identity); self.store.apply()
        self.assertEqual(self.store.active()['release'],identity)
        self.assertEqual(self.store.transaction()['state'],'committed')
        self.assertEqual(self.store.previous()['release'],'a'*64)

    def test_successive_updates_keep_only_active_and_one_rollback(self):
        first=self.stage();self.store.queue(first);self.store.apply()
        package=self.package(lambda manifest:manifest.update(base=first,version='next'))
        second=digest(package);raw=package.read_bytes()
        self.store.begin(second,len(raw),first)
        for offset in range(0,len(raw),CHUNK):
            self.store.chunk(second,offset,raw[offset:offset+CHUNK])
        self.store.validate(second);self.store.queue(second);self.store.apply()
        self.assertEqual({p.name for p in self.store.releases.iterdir()},{first,second})
        self.assertEqual(self.store.previous()['release'],first)
        self.assertFalse(self.store.archive.exists())
        self.assertFalse(self.store.staging.exists())
        self.store.rollback();self.store.apply()
        self.assertEqual(self.store.active()['release'],first)
        self.assertEqual(self.store.previous()['release'],second)
        self.assertEqual({p.name for p in self.store.releases.iterdir()},{first,second})
    def test_size_limit(self):
        for size in (0,-1,LIMIT+1,True):
            with self.assertRaises(Rejected): self.store.begin('b'*64,size,'a'*64)
        self.assertFalse(self.store.archive.exists())
    def test_begin_reserves_for_actual_archive_not_maximum_package(self):
        size=300_000
        with patch('deploy_core.shutil.disk_usage',return_value=type('Usage',(),{'free':size+31_999_999})()):
            with self.assertRaisesRegex(Rejected,'insufficient-storage'):
                self.store.begin('b'*64,size,'a'*64)
        with patch('deploy_core.shutil.disk_usage',return_value=type('Usage',(),{'free':size+32_000_000})()):
            self.assertEqual(self.store.begin('b'*64,size,'a'*64)['state'],'receiving')
    def test_wrong_device(self):
        with self.assertRaisesRegex(Rejected,'wrong-device'): self.stage(self.package(lambda m:m.update(device='another')))
    def test_wrong_base(self):
        with self.assertRaisesRegex(Rejected,'stale-base'): self.stage(self.package(lambda m:m.update(base='b'*64)))
    def test_undeclared_content(self):
        with self.assertRaisesRegex(Rejected,'undeclared-content'): self.stage(self.package(extra=('../escape',b'x')))
        self.assertFalse((self.root.parent/'escape').exists())
    def test_traversal_in_manifest(self):
        def change(m): m['files']['input/../escape.py']=dict(bytes=1,sha256='a'*64)
        with self.assertRaisesRegex(Rejected,'bad-path'): self.stage(self.package(change))
    def test_bad_file_hash(self):
        def change(m): m['files']['input/guide_keyboard.py']['sha256']='a'*64
        with self.assertRaisesRegex(Rejected,'file-hash-mismatch'): self.stage(self.package(change))
    def test_resume_truncates_unacknowledged_tail(self):
        package=self.package(); data=package.read_bytes(); identity=digest(package)
        self.store.begin(identity,len(data),'a'*64); self.store.chunk(identity,0,data[:100])
        with self.store.archive.open('ab') as stream: stream.write(b'unacknowledged garbage')
        self.store=Store(self.root,self.host)
        self.assertEqual(self.store.begin(identity,len(data),'a'*64)['received'],100)
        self.store.chunk(identity,100,data[100:]); self.store.validate(identity)
    def test_wrong_offset(self):
        self.store.begin('b'*64,200,'a'*64)
        with self.assertRaisesRegex(Rejected,'offset-mismatch'): self.store.chunk('b'*64,1,b'123')
    def test_corrupt_upload(self):
        self.store.begin('b'*64,3,'a'*64); self.store.chunk('b'*64,0,b'123')
        with self.assertRaisesRegex(Rejected,'incomplete-or-corrupt'): self.store.validate('b'*64)
    def test_isolated_check_failure(self):
        self.host.fail='check'
        with self.assertRaisesRegex(Rejected,'test-check'): self.stage()
        self.assertEqual(self.store.active()['release'],'a'*64)
    def test_busy_retains_staging(self):
        identity=self.stage(); self.host.fail='admit'; self.store.queue(identity); self.store.apply()
        self.assertEqual(self.store.transaction()['state'],'validated')
        self.assertTrue(self.store.staging.exists()); self.assertNotIn('stop',self.host.calls)
        self.host.fail=None; self.store.queue(identity); self.store.apply()
        self.assertEqual(self.store.transaction()['state'],'committed')
    def test_quiescence_failure_unparks(self):
        identity=self.stage(); self.host.fail='quiesce'; self.store.queue(identity); self.store.apply()
        self.assertEqual(self.host.calls[-1],'unquiesce')
        self.assertNotIn('stop',self.host.calls)
    def test_failed_launch_rolls_back(self):
        identity=self.stage(); self.host.fail='healthy-'+identity[0]
        # Distinguish old health even in the unlikely case the hash begins with a.
        self.host.healthy=lambda release: (_ for _ in ()).throw(Rejected('new-failed')) if release==identity else None
        self.store.queue(identity); self.store.apply()
        self.assertEqual(self.store.active()['release'],'a'*64)
        self.assertEqual(self.store.transaction()['state'],'rolled-back')
        self.assertFalse((self.store.releases/identity).exists())
    def test_interrupted_activation_boot_recovery(self):
        identity=self.stage(); self.host.crash='start'; self.store.queue(identity)
        with self.assertRaises(PowerLoss): self.store.apply()
        self.assertEqual(self.store.active()['release'],identity)
        self.host.crash=None; Store(self.root,self.host).recover()
        self.assertEqual(self.store.active()['release'],'a'*64)
        self.assertEqual(self.store.transaction()['health'],'pending-boot')
    def test_interrupted_before_switch(self):
        identity=self.stage(); self.host.crash='stop'; self.store.queue(identity)
        with self.assertRaises(PowerLoss): self.store.apply()
        self.host.crash=None; self.store.recover()
        self.assertEqual(self.store.active()['release'],'a'*64)
    def test_queued_boot_does_not_auto_apply(self):
        identity=self.stage(); self.store.queue(identity); self.store.recover()
        self.assertEqual(self.store.transaction()['state'],'validated')
    def test_manual_rollback_is_detached(self):
        identity=self.stage(); self.store.queue(identity); self.store.apply()
        txn=self.store.rollback()
        self.assertEqual(txn['state'],'queued'); self.assertEqual(self.store.active()['release'],identity)
        self.store.apply(); self.assertEqual(self.store.active()['release'],'a'*64)
        self.assertEqual(self.store.previous()['release'],identity)
    def test_idempotent_commit(self):
        identity=self.stage(); self.store.queue(identity); self.store.apply()
        self.assertEqual(self.store.begin(identity,(self.root/'test.zip').stat().st_size,'a'*64)['state'],'committed')
        self.store.queue(identity); self.store.apply()
        self.assertEqual(self.host.calls.count('stop'),1)
    def test_revoke_before_apply(self):
        identity=self.stage(); self.store.queue(identity)
        atomic_json(self.root/'config.json',dict(device='deck-test',enabled=False)); self.store.apply()
        self.assertNotIn('stop',self.host.calls)
        self.assertFalse(self.store.status()['enabled'])
    def test_cancel_retains_active(self):
        identity=self.stage(); self.store.cancel(identity)
        self.assertFalse(self.store.staging.exists()); self.assertEqual(self.store.active()['release'],'a'*64)
        self.assertEqual(self.store.begin(identity,(self.root/'test.zip').stat().st_size,'a'*64)['received'],0)
    def test_worker_death_restores_live_shell(self):
        identity=self.stage(); self.host.crash='start'; self.store.queue(identity)
        with self.assertRaises(PowerLoss): self.store.apply()
        self.host.crash=None; self.store.rescue()
        self.assertEqual(self.store.transaction()['state'],'rolled-back')
        self.assertEqual(self.store.active()['release'],'a'*64)
        self.assertIn('healthy-a',self.host.calls)
    def test_protocol_rejects_extra_arguments(self):
        for request in ({'op':'status','command':'id'},{'op':'shell'},{'op':'chunk','id':'x','offset':0,'data':'!'}):
            with self.assertRaises(Rejected): dispatch(self.store,request)
    def test_shell_bridge_defers_private_work(self):
        with patch.dict(os.environ,GUIDE_DEPLOY_RUNTIME=str(self.root),GUIDE_RELEASE_ID='a'*64): bridge=ShellBridge()
        atomic_json(self.root/'quiesce.json',dict(token='test'))
        self.assertFalse(bridge.poll(False)); self.assertTrue(bridge.poll(True))
        data=json.loads((self.root/'shell.json').read_text())
        self.assertEqual(set(data),{'pid','release','monotonic','ready','can_restart','quiesced','stopped','clean'})
        (self.root/'quiesce.json').unlink(); self.assertFalse(bridge.poll(True))
        bridge.publish(False,stopped=True,clean=True)
        self.assertTrue(json.loads((self.root/'shell.json').read_text())['clean'])

if __name__=='__main__': unittest.main()
