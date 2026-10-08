import hashlib,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'package/guide-deploy'),str(ROOT/'package/guide-storage'),str(ROOT/'package/guide-installer'),str(ROOT/'package/guide-ipc/python')]
from deploy_core import REQUIRED,atomic_json,CHUNK,digest,Rejected
from test_deploy import Host
from signed_store import SignedStore
from build_signed_release import build,trust

class SignedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.base=self.root/'store';self.base.mkdir()
        (self.base/'releases'/('a'*64)).mkdir(parents=True)
        atomic_json(self.base/'active.json',dict(release='a'*64,version='0.3.9'))
        atomic_json(self.base/'config.json',dict(device='deck',enabled=True,board='rg35xx-h',release_sequence=39,state_schema=1,signed_updates=True))
        self.release=self.root/'release'
        for name in REQUIRED:
            p=self.release/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# verified fixture\n')
        self.bundle=self.root/'update.zip'
        self.m,self.pub=build(self.release,self.bundle,b'x'*32,'0.4.0',40,39)
        trust(self.base,self.pub);self.host=Host();self.store=SignedStore(self.base,self.host)
    def stage(self):
        identity=digest(self.bundle);self.store.begin(identity,self.bundle.stat().st_size,'a'*64)
        with self.bundle.open('rb') as f:
            offset=0
            while block:=f.read(CHUNK):self.store.chunk(identity,offset,block);offset+=len(block)
        self.store.validate(identity);return identity
    def test_signed_commit_requires_local_approval(self):
        identity=self.stage()
        with self.assertRaisesRegex(Rejected,'local-approval'):self.store.queue(identity)
        self.store.authorize(identity);self.store.queue(identity);self.store.apply()
        self.assertEqual(self.store.sequence(),40);self.assertEqual(self.store.transaction()['state'],'committed')
        self.assertEqual(self.store.previous()['release'],'a'*64)
    def test_service_umask_keeps_public_browser_code_readable(self):
        old=os.umask(0o077)
        try:
            identity=self.stage();self.store.authorize(identity);self.store.queue(identity);self.store.apply()
        finally:os.umask(old)
        self.assertEqual((self.base/'active.json').stat().st_mode&0o777,0o644)
        self.assertEqual((self.base/'releases'/identity/'shell0').stat().st_mode&0o777,0o755)
    def test_corruption_rejected(self):
        raw=bytearray(self.bundle.read_bytes());raw[100]^=1;self.bundle.write_bytes(raw)
        with self.assertRaises(Rejected):self.stage()
        self.assertEqual(self.store.active()['release'],'a'*64)
    def test_revoked_after_approval_cannot_activate(self):
        identity=self.stage();self.store.authorize(identity);self.store.queue(identity)
        folder=self.base/'trust/revoked';folder.mkdir();(folder/self.m['signing']['keyId'][7:]).write_text('revoked')
        self.store.apply();self.assertEqual(self.store.transaction()['state'],'rejected')
        self.assertEqual(self.store.active()['release'],'a'*64)
    def test_health_failure_restores_previous(self):
        identity=self.stage();self.store.authorize(identity);self.store.queue(identity)
        with patch.object(self.host,'healthy',side_effect=[Rejected('health-failed'),None]):self.store.apply()
        self.assertEqual(self.store.active()['release'],'a'*64)
        self.assertEqual(self.store.transaction()['state'],'rolled-back')
    def test_descriptor_import_same_validation(self):
        with self.bundle.open('rb') as f:result=self.store.import_descriptor(f.fileno())
        self.assertEqual(result['state'],'validated');self.assertFalse(result['approved'])
    def test_unknown_key_rejected(self):
        for p in (self.base/'trust').glob('*.json'):p.unlink()
        with self.assertRaises(Rejected):self.stage()

if __name__=='__main__':unittest.main()
