import json,os,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import Future
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'board/rg35xxh/debian/shell0'),str(ROOT/'package/guide-ui'),str(ROOT/'package/guide-ipc/python'),str(ROOT/'package/guide-installer')]
if os.environ.get('GUIDE_INSTALLER_TEST_INSTALLED')=='1':sys.path.insert(0,'/usr/lib/guideos/shell0')
from guide_installer_panel import InstallerPanel
class PanelTests(unittest.TestCase):
    def setUp(self):
        self.state=SimpleNamespace(page='installer',revision=0,shutdown_requested=False,open_application=Mock())
        self.panel=InstallerPanel(self.state)
    def tearDown(self):self.panel.pool.shutdown(wait=True,cancel_futures=True)
    def status(self,record):
        self.panel.view='progress';self.panel.operation='status';self.panel.pending=Future();self.panel.pending.set_result({'status':record,'busy':False,'error':None,'preview':None});self.panel.poll()
    def test_no_automatic_launch(self):
        self.status({'phase':'committed','code':10000});self.state.open_application.assert_not_called()
        self.assertEqual(self.panel.make_rows()[0][1],'open');self.panel.action(0);self.state.open_application.assert_called_once_with(10000)
    def test_uninstall_never_offers_open_or_says_installed(self):
        self.status({'phase':'committed','code':10000,'operation':'uninstall'})
        self.assertIn('removed',self.panel.notice);self.assertNotIn('open',[r[1] for r in self.panel.make_rows()])
    def test_private_delete_has_distinct_result(self):
        self.status({'phase':'committed','code':10000,'operation':'delete-data'})
        self.assertIn('deleted',self.panel.notice);self.assertNotIn('open',[r[1] for r in self.panel.make_rows()])
    def test_uninstalled_metadata_only_is_explicit(self):
        self.panel.items=[dict(name='Notepad',version='0.1',state='uninstalled',retainedData=False)]
        self.assertTrue(self.panel.make_rows()[0][0].startswith('Not installed'))
        self.panel.action(0)
        actions=[row[1] for row in self.panel.make_rows()]
        self.assertNotIn('open',actions);self.assertNotIn('confirm-delete',actions)
        self.assertIn('Installation record only',[row[0] for row in self.panel.make_rows()])
    def test_uninstalled_private_store_can_be_deleted_but_not_opened(self):
        self.panel.view='detail';self.panel.selected=dict(state='uninstalled',retainedData=True)
        actions=[row[1] for row in self.panel.make_rows()]
        self.assertIn('confirm-delete',actions);self.assertNotIn('open',actions)
    def test_reinstall_agreement_preserves_prior_version(self):
        self.panel.view='agreement';self.panel.preview=dict(name='Notepad',version='0.1',summary='Notes',previousVersion='0.1',previousState='uninstalled')
        self.assertIn('Agree and reinstall',[row[0] for row in self.panel.make_rows()])
        self.assertEqual(self.panel.preview['previousVersion'],'0.1')
    def test_home_does_not_cancel_transaction(self):
        self.panel.view='progress';self.panel.busy=True;self.panel.submit=Mock();self.panel.key(316)
        self.assertEqual(self.state.page,'home');self.panel.submit.assert_not_called()
    def test_reading_agreement_has_no_deadline(self):
        self.panel.view='agreement';self.panel.submit=Mock();self.panel.next_poll=0
        self.panel.poll();self.assertEqual(self.panel.view,'agreement');self.panel.submit.assert_not_called()
    def test_power_wait_is_cancellable(self):
        self.state.shutdown_requested=True;self.panel.submit=Mock();self.assertFalse(self.panel.prepare_shutdown())
        self.panel.action(0);self.assertFalse(self.state.shutdown_requested)
if __name__=='__main__':unittest.main()
