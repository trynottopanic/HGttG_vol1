import hashlib,json,sys,tempfile,unittest
from pathlib import Path
from stage_operations import stage
from deploy_core import atomic_json,read_json
class StagingTests(unittest.TestCase):
    def test_staging_preserves_owner_data_and_active_release(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'root';data=Path(d)/'owner';(root/'etc').mkdir(parents=True);data.mkdir()
            (root/'etc/os-release').write_text('ID=debian\n')
            owner=data/'notepad';owner.write_bytes(b'owner saved work')
            base=root/'opt/guideos/deploy';base.mkdir(parents=True)
            active={'release':'a'*64,'version':'0.3.9'};atomic_json(base/'active.json',active)
            atomic_json(base/'config.json',{'device':'deck','enabled':True})
            result=stage(root,data,b'x'*32,39,1)
            self.assertEqual(read_json(base/'active.json'),active);self.assertEqual(owner.read_bytes(),b'owner saved work')
            self.assertTrue(result['activeReleasePreserved'])
            self.assertTrue((data/'guideos/files').is_dir())
            for entry in result['files']:
                self.assertEqual(hashlib.sha256((root/entry['path']).read_bytes()).hexdigest(),entry['after'])
            self.assertIn('launch_browser.py',(root/'usr/lib/systemd/system/guide-browser.service').read_text())
    def test_escaping_owner_path_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'root';data=Path(d)/'owner';(root/'etc').mkdir(parents=True);data.mkdir()
            (root/'etc/os-release').write_text('ID=debian\n');(data/'guideos').symlink_to(root,target_is_directory=True)
            base=root/'opt/guideos/deploy';base.mkdir(parents=True)
            atomic_json(base/'config.json',{'device':'deck','enabled':True});atomic_json(base/'active.json',{'release':'a'*64,'version':'0.3.9'})
            with self.assertRaises(ValueError):stage(root,data,b'x'*32,39,1)
if __name__=='__main__':unittest.main()
