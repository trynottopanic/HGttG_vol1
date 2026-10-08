import json,signal,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import tf2_probe as probe
from deploy_core import Rejected
from deploy_server import dispatch

class TF2Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.host=self.root/'4022000.mmc';self.state=self.root/'state'
        (self.host/'power').mkdir(parents=True);self.state.mkdir()
        driver=self.root/'sunxi-mmc';driver.mkdir();(self.host/'driver').symlink_to(driver,target_is_directory=True)
        (self.host/'power/control').write_text('auto\n')
    def request(self,hold):
        (self.state/'request.json').write_text(json.dumps(dict(hold_awake=hold)))
    def test_hold_restores_after_normal_completion(self):
        self.request(True);probe.run_probe(self.host,self.state,seconds=0)
        self.assertEqual(probe.read(self.host/'power/control'),'auto')
        self.assertTrue(json.loads((self.state/'result.json').read_text())['restored'])
        self.assertFalse((self.state/'request.json').exists())
    def test_hold_restores_after_failure(self):
        self.request(True)
        with patch.object(probe,'snapshot',side_effect=RuntimeError()),self.assertRaises(RuntimeError):
            probe.run_probe(self.host,self.state,seconds=1)
        self.assertEqual(probe.read(self.host/'power/control'),'auto')
        self.assertEqual(json.loads((self.state/'result.json').read_text())['state'],'failed')
    def test_hold_restores_after_signal(self):
        self.request(True)
        probe.run_probe(self.host,self.state,seconds=1,sleep=lambda _:signal.raise_signal(signal.SIGTERM))
        self.assertEqual(probe.read(self.host/'power/control'),'auto')
        self.assertEqual(json.loads((self.state/'result.json').read_text())['state'],'interrupted')
    def test_observe_does_not_rewrite_policy(self):
        self.request(False)
        with patch.object(Path,'write_text',side_effect=AssertionError('unexpected policy write')):
            probe.run_probe(self.host,self.state,seconds=0)
    def test_exact_host_required(self):
        wrong=self.root/'4020000.mmc';self.host.rename(wrong)
        with self.assertRaises(Rejected):probe.validate_host(wrong)
    def test_no_arbitrary_remote_arguments(self):
        for action in ('tf2-observe','tf2-hold-awake','tf2-result'):
            with self.assertRaises(Rejected):dispatch(None,dict(op=action,path='/anything'))
    def test_existing_on_policy_preserved(self):
        (self.host/'power/control').write_text('on\n');self.request(True)
        probe.run_probe(self.host,self.state,seconds=0)
        self.assertEqual(probe.read(self.host/'power/control'),'on')
if __name__=='__main__':unittest.main()
