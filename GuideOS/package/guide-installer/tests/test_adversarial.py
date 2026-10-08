import io,json,os,sys,tempfile,unittest,zipfile,struct,zlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'guide-storage'))
if os.environ.get('GUIDE_INSTALLER_TEST_INSTALLED')=='1':sys.path.insert(0,'/usr/lib/guideos/installer')
from guide_cartridge import *
from test_installer import fixture,inspect
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'guide-ipc/python'))
from cartridge_catalog import Catalog

class Adversarial(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.archive,self.package=fixture(self.root)
        import pwd
        account=pwd.getpwnam('nobody');self.account=patch('guide_installer.pwd.getpwnam',return_value=account);self.account.start()
    def tearDown(self):self.account.stop();self.tmp.cleanup()
    def mutated(self,change):
        with zipfile.ZipFile(self.archive) as z:entries=[(e,z.read(e)) for e in z.infolist()]
        entries=change(entries);result=io.BytesIO()
        with zipfile.ZipFile(result,'w') as z:
            for e,data in entries:z.writestr(e,data)
        result.seek(0);return result
    def test_adversarial_archives(self):
        def rename(entries,name):entries[0][0].filename=name;return entries
        changes={'duplicate':lambda e:e+[e[0]],'traversal':lambda e:rename(e,'CONTENT/../escape.py'),'absolute':lambda e:rename(e,'/escape.py'),'backslash':lambda e:rename(e,'CONTENT\\escape.py'),'ads':lambda e:rename(e,'CONTENT/a:ads.py'),'undeclared':lambda e:e+[(zipfile.ZipInfo('CONTENT/unlisted.txt'),b'x')],'missing':lambda e:e[1:]}
        for name,change in changes.items():
            with self.subTest(name=name),self.assertRaises(Exception):verify(self.mutated(change))
    def test_symlink_encryption_method_and_zip64(self):
        for attr in ('link','encrypted','method','zip64'):
            def mutate(entries):
                e,data=entries[0]
                if attr=='link':e.external_attr=(stat.S_IFLNK|0o777)<<16
                elif attr=='method':e.compress_type=zipfile.ZIP_BZIP2
                elif attr=='zip64':e.extra=b'\x01\x00\x00\x00'
                return entries
            raw=self.mutated(mutate).getvalue()
            if attr=='encrypted':
                raw=bytearray(raw);raw[6]|=1;raw=bytes(raw)
            with self.subTest(kind=attr),self.assertRaises(Exception):verify(io.BytesIO(raw))
    def test_duplicate_manifest_keys(self):
        def mutate(entries):
            return [(e,b'{"format":"bad",'+data[1:] if e.filename=='GUIDE/manifest.json' else data) for e,data in entries]
        with self.assertRaises(ValueError):verify(self.mutated(mutate))
    def test_png_dimensions_and_decompressed_limit(self):
        raw=(self.root/'source/assets/icon.png').read_bytes()
        with self.assertRaises(ValueError):png_check(raw[:-1])
        huge=zlib.compress(b'\0'*1000000)
        def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        malformed=raw[:33]+chunk(b'IDAT',huge)+chunk(b'IEND',b'')
        with self.assertRaises(ValueError):png_check(malformed)
    def test_catalog_stale_provider_and_removed_card(self):
        folder=self.root/'card/GUIDE/CARTRIDGES';folder.mkdir(parents=True)
        archive=folder/'test.guide';archive.write_bytes(self.archive.read_bytes());m=self.package['manifest']
        lines=['GUIDE-CARTRIDGE-INDEX-1']+[k+'='+v for k,v in [('ID',m['id']),('NAME',m['name']),('VERSION',m['version']),('KIND','application'),('SUMMARY',m['summary']),('FILE','test.guide'),('BYTES',str(archive.stat().st_size)),('SHA256',self.package['sha256']),('ACTION','application.install.v0')]]+['CAPABILITY='+c for c in m['capabilities']]
        index=folder/'test.gde';index.write_text('\n'.join(lines)+'\n');present=[{'card':'one'}];catalog=Catalog(self.root/'card',lambda:present[0]);catalog.invalidate(present[0]);listing=catalog.listing();selection=dict(epoch=listing['epoch'],generation=listing['generation'],token=listing['items'][0]['token'])
        result,fds=catalog.open(selection);self.assertEqual(os.read(fds[0],4),b'PK\x03\x04');os.close(fds[0])
        archive.with_suffix('.guide.sha256').write_text('0'*64+'  test.guide\n')
        with self.assertRaises(ValueError):catalog.open(selection)
        archive.with_suffix('.guide.sha256').unlink();present[0]=None
        with self.assertRaises(ValueError):catalog.open(selection)
        present[0]={'card':'one'};catalog.invalidate(present[0])
        with self.assertRaises(ValueError):catalog.open(selection)
    def test_fsync_failures_keep_a_launchable_record(self):
        # Inject each durability failure once; recover using a clean service.
        import guide_installer as module
        for point in range(1,43):
            with self.subTest(point=point):
                base=self.root/str(point);base.mkdir();a,p=fixture(base);e=module.Installer(base/'deck',inspect=inspect,stop=lambda *a:None,health=lambda _:True)
                fd=os.open(a,os.O_RDONLY);e.install(fd,p,list(CAPABILITIES),'a'*32);os.close(fd)
                b,q=fixture(base,'1.1.0');real=os.fsync;count=[0]
                def fault(fd):
                    count[0]+=1
                    if count[0]==point:raise OSError('injected flush failure')
                    return real(fd)
                fd=os.open(b,os.O_RDONLY)
                try:
                    with patch.object(module.os,'fsync',side_effect=fault):
                        try:e.install(fd,q,list(CAPABILITIES),'b'*32)
                        except OSError:pass
                finally:os.close(fd);e.close()
                e=module.Installer(base/'deck',inspect=inspect,stop=lambda *a:None,health=lambda _:True)
                try:
                    e.recover();record=e.record(p['manifest']['id']);self.assertEqual(record['state'],'committed');self.assertIn(record['package']['sha256'],(p['sha256'],q['sha256']))
                    self.assertTrue((e.programs/p['manifest']['id']/'releases'/record['package']['manifest']['version']).is_dir())
                finally:e.close()
if __name__=='__main__':unittest.main()
