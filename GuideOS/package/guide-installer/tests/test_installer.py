import io,json,os,sys,tempfile,unittest,zipfile,struct,zlib,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if os.environ.get('GUIDE_INSTALLER_TEST_INSTALLED')=='1':sys.path.insert(0,'/usr/lib/guideos/installer')
from guide_cartridge import *
from guide_installer import Installer,encode_record

def fixture(root,version='1.0.0',extra=b''):
    source=root/'source';(source/'application').mkdir(parents=True,exist_ok=True);(source/'assets').mkdir(exist_ok=True)
    app=dict(profile='guide.application.v0',icon='assets/icon.png',runtime='guide.python-application',interfaceMajor=1,display=[640,480],privateBytes=524288,temporaryBytes=131072,memoryMinimumBytes=50331648,memoryPeakBytes=67108864,dataSchema=1,lifecycle=['ready','checkpoint','stop'],offline=True,health='isolated-ready-checkpoint-v0',optionalCapabilities=[])
    (source/'application/application.json').write_bytes(canonical(app));(source/'application/reference.py').write_bytes(b'def application(api):\n api.ready()\n'+extra)
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',64,64,8,6,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+bytes([50,100,150,255])*64)*64))+chunk(b'IEND',b'')
    (source/'assets/icon.png').write_bytes(png)
    manifest=dict(format='GUIDE-CARTRIDGE-1',id='org.hhgtg.runtime-proof',name='Application test',version=version,kind='application',summary='Harmless cartridge proof.',capabilities=list(CAPABILITIES),installAction='application.install.v0',entrypoint=dict(runtime='guide.python-application',interfaceMajor=1,module='reference',callable='application'))
    archive=root/(version+'.guide');package=build(source,manifest,archive);return archive,package

def inspect(path,expected,tree=None):
    with open(path,'rb') as f:return verify(f,expected,tree)

class Death(BaseException):pass
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        from unittest.mock import patch
        import pwd
        account=pwd.getpwnam('nobody');self.account=patch('guide_installer.pwd.getpwnam',return_value=account);self.account.start()
    def tearDown(self):self.account.stop();self.tmp.cleanup()
    def install(self,engine,archive,package,token='a'*32):
        fd=os.open(archive,os.O_RDONLY)
        try:return engine.install(fd,package,list(CAPABILITIES),token)
        finally:os.close(fd)
    def engine(self,**kwargs):return Installer(self.root/'deck',inspect=inspect,stop=lambda *a:None,health=lambda _:True,**kwargs)
    def test_deterministic(self):
        a,p=fixture(self.root);before=a.read_bytes();fixture(self.root);self.assertEqual(before,a.read_bytes());self.assertTrue(p['unsigned'])
    def test_paths_and_json(self):
        for name in ('../x','/x','CONTENT/x:ads','CONTENT/a\\b','CONTENT/NUL','CONTENT/a/../b','CONTENT/a.','CONTENT/e\u0301.txt'):
            with self.assertRaises(ValueError):path_check(name)
        with self.assertRaises(ValueError):json_read(b'{"a":1,"a":2}')
    def test_corrupt_inventory(self):
        a,p=fixture(self.root);data=bytearray(a.read_bytes());data[45]^=1
        with self.assertRaises(Exception):verify(io.BytesIO(data))
    def test_install_health_and_idempotence(self):
        a,p=fixture(self.root);e=self.engine()
        try:
            result=self.install(e,a,p);self.assertEqual(result['phase'],'committed');record=e.record(p['manifest']['id']);self.assertEqual(record['state'],'committed')
            self.assertEqual(self.install(e,a,p)['phase'],'committed')
            self.assertEqual(self.install(e,a,p,'b'*32)['phase'],'already-installed')
        finally:e.close()
    def test_failed_update_preserves_program_data(self):
        a,p=fixture(self.root);e=self.engine()
        try:
            self.install(e,a,p);private=e.registry/p['manifest']['id']/'private';private.mkdir();(private/'sentinel').write_text('owner work')
            b,q=fixture(self.root,'1.1.0');e.health=lambda _:False
            with self.assertRaises(ValueError):self.install(e,b,q,'b'*32)
            self.assertEqual(e.record(p['manifest']['id'])['package']['sha256'],p['sha256']);self.assertEqual((private/'sentinel').read_text(),'owner work')
        finally:e.close()
    def test_power_loss_boundaries(self):
        points=['after-journal-staging','after-journal-activation-intent','after-record-preparing','before-release-rename','after-release-rename','after-record-testing','after-projection-testing','after-journal-health-check','after-journal-commit-intent','after-record-committed','after-projection-committed','after-journal-committed']
        for number,point in enumerate(points):
            with self.subTest(point=point):
                deck=self.root/str(number);deck.mkdir();a,p=fixture(deck);e=Installer(deck/'deck',inspect=inspect,stop=lambda *a:None,health=lambda _:True)
                self.install(e,a,p);b,q=fixture(deck,'1.1.0')
                def fault(got):
                    if got==point:raise Death()
                e.fault=fault
                with self.assertRaises(Death):self.install(e,b,q,'b'*32)
                e.close();e=Installer(deck/'deck',inspect=inspect,stop=lambda *a:None,health=lambda _:True)
                try:
                    e.recover();r=e.record(p['manifest']['id']);self.assertEqual(r['state'],'committed');self.assertIn(r['package']['sha256'],(p['sha256'],q['sha256']))
                    release=e.programs/r['package']['manifest']['id']/'releases'/r['package']['manifest']['version'];self.assertTrue(release.is_dir())
                    self.assertEqual((e.registry/(str(r['code'])+'.policy')).read_text(),r['runtime_policy'])
                finally:e.close()
    def test_uninstall_reinstall_identity_data(self):
        a,p=fixture(self.root);e=self.engine()
        try:
            self.install(e,a,p);r=e.record(p['manifest']['id']);private=e.registry/p['manifest']['id']/'private';private.mkdir();(private/'sentinel').write_text('retained')
            e.uninstall(p['manifest']['id'],'b'*32);self.assertTrue((private/'sentinel').exists());self.assertFalse((e.registry/(str(r['code'])+'.policy')).exists())
            self.install(e,a,p,'c'*32);self.assertEqual(e.record(p['manifest']['id'])['code'],r['code']);self.assertTrue((private/'sentinel').exists())
        finally:e.close()
    def test_failed_reinstall_removes_candidate_and_preserves_identity_data(self):
        a,p=fixture(self.root);e=self.engine();ident=p['manifest']['id']
        try:
            self.install(e,a,p);prior=e.record(ident)
            private=e.registry/ident/'private';private.mkdir();(private/'sentinel').write_text('retained')
            e.uninstall(ident,'b'*32);e.health=lambda _:False
            with self.assertRaises(ValueError):self.install(e,a,p,'c'*32)
            self.assertFalse((e.programs/ident/'releases'/p['manifest']['version']).exists())
            self.assertEqual(e.record(ident)['state'],'uninstalled')
            self.assertEqual((private/'sentinel').read_text(),'retained')
            e.health=lambda _:True;self.install(e,a,p,'d'*32)
            self.assertEqual(e.record(ident)['code'],prior['code'])
            self.assertEqual(e.record(ident)['agreement']['granted'],prior['agreement']['granted'])
            self.assertEqual((private/'sentinel').read_text(),'retained')
        finally:e.close()
    def test_same_version_changed_rejected(self):
        a,p=fixture(self.root);e=self.engine()
        try:
            self.install(e,a,p);a,q=fixture(self.root,extra=b'# changed\n')
            with self.assertRaises(ValueError):self.install(e,a,q,'b'*32)
        finally:e.close()
    def test_cancel_before_mutation(self):
        a,p=fixture(self.root);e=self.engine(fault=lambda point:None)
        try:
            e.fault=lambda point:e.cancel.set() if point=='after-journal-staging' else None
            self.assertEqual(self.install(e,a,p)['phase'],'cancelled');self.assertIsNone(e.record(p['manifest']['id']))
        finally:e.close()
    def test_low_space_rejected_before_activation(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        a,p=fixture(self.root);e=self.engine()
        try:
            with patch('os.statvfs',return_value=SimpleNamespace(f_frsize=4096,f_bavail=1)):
                with self.assertRaises(ValueError):self.install(e,a,p)
            self.assertIsNone(e.record(p['manifest']['id']))
        finally:e.close()
    def test_quarantine_blocks_later_restart(self):
        e=self.engine()
        try:
            (e.transactions/('a'*32+'.json')).write_text('{broken')
            with self.assertRaises(ValueError):e.recover()
            with self.assertRaises(ValueError):e.recover()
        finally:e.close()
    def test_stale_source_never_activates(self):
        a,p=fixture(self.root);e=self.engine();fd=os.open(a,os.O_RDONLY)
        try:
            with self.assertRaises(ValueError):e.install(fd,p,list(CAPABILITIES),'a'*32,source_current=lambda:False)
            self.assertIsNone(e.record(p['manifest']['id']))
        finally:os.close(fd);e.close()
    def test_schema_downgrade_and_agreement_binding(self):
        import copy
        a,p=fixture(self.root,'1.1.0');e=self.engine()
        try:
            self.install(e,a,p);old=e.record(p['manifest']['id']);q=copy.deepcopy(p);q['application']['dataSchema']=2
            with self.assertRaises(ValueError):e.check_update(q,old,False)
            q=copy.deepcopy(p);q['manifest']['version']='1.0.0'
            with self.assertRaises(ValueError):e.check_update(q,old,False)
            e.check_update(q,old,True)
            with self.assertRaises(ValueError):e.make_record(p,old,[])
            with self.assertRaises(ValueError):e.uninstall(p['manifest']['id'],'b'*32,expected_generation=old['generation']+1)
        finally:e.close()
    def test_language_neutral_profile_matches_verifier(self):
        profile=json.loads((Path(__file__).resolve().parents[1]/'application-profile-v0.json').read_text())
        self.assertEqual(profile['limits']['archiveBytes'],ARCHIVE_MAX)
        self.assertEqual(profile['limits']['expandedBytes'],EXPANDED_MAX)
        self.assertEqual(profile['limits']['metadataBytes'],METADATA_MAX)
        self.assertEqual(profile['capabilityCodes'],CAPABILITIES)
    def test_uninstall_failed_checkpoint_retains_program(self):
        a,p=fixture(self.root);e=self.engine()
        try:
            self.install(e,a,p)
            def denied(*args):raise ValueError('checkpoint not confirmed')
            e.stop=denied
            with self.assertRaises(ValueError):e.uninstall(p['manifest']['id'],'b'*32)
            self.assertEqual(e.record(p['manifest']['id'])['state'],'committed')
            self.assertTrue((e.programs/p['manifest']['id']/'releases/1.0.0').is_dir())
        finally:e.close()
if __name__=='__main__':unittest.main()
