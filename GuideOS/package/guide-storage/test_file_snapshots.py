"""Directory snapshots retain provider authority and bounded scan lifetimes."""
import os,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from storage_files import Files

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.files=Files(self.root/'card',self.root/'files');self.addCleanup(self.files.close)
    def populate(self,count=70):
        for i in range(count):(self.root/'files'/f'{i:04d}.txt').write_text('owner content')
    def test_pages_share_one_scan_and_revision(self):
        self.populate(1024)
        with patch.object(self.files,'_scan',wraps=self.files._scan) as scan:
            a=self.files.listing('internal');b=self.files.listing('internal',32,revision=a['revision'])
            self.assertEqual(scan.call_count,1);self.assertEqual(a['revision'],b['revision'])
            self.assertEqual(len(a['items'])+len(b['items']),64)
    def test_content_write_invalidates_revision_and_old_opaque_entry(self):
        self.populate();a=self.files.listing('internal');entry=a['items'][0]['id']
        (self.root/'files/0000.txt').write_text('replacement content')
        with self.assertRaisesRegex(ValueError,'refresh-required'):self.files.listing('internal',32,revision=a['revision'])
        with self.assertRaisesRegex(ValueError,'changed-source'):self.files.resolve(entry,False)
        b=self.files.listing('internal',refresh=True);self.assertNotEqual(a['revision'],b['revision'])
    def test_new_name_and_explicit_refresh_invalidate_snapshot(self):
        self.populate();a=self.files.listing('internal');(self.root/'files/new.txt').touch()
        b=self.files.listing('internal');self.assertNotEqual(a['revision'],b['revision'])
        with patch.object(self.files,'_scan',wraps=self.files._scan) as scan:
            self.files.listing('internal',refresh=True);self.assertEqual(scan.call_count,1)
    def test_slow_scan_returns_pending_and_cancellation_cannot_publish_old_card(self):
        card=self.root/'card';card.mkdir();(card/'owner.txt').write_text('preserved');current=['one']
        self.files.current=lambda:current[0];self.files.refresh('one',1);folder=self.files.roots()[1]['id']
        gate=threading.Event();entered=threading.Event();original=self.files._scan
        def scan(fd,cancel):entered.set();gate.wait(1);return original(fd,cancel)
        with patch.object(self.files,'_scan',side_effect=scan):
            try:
                start=time.monotonic();r,_=self.files.wire_dispatch(2,{'folder':folder,'async_listing':True});self.assertLess(time.monotonic()-start,.1)
                self.assertEqual(r['errorCode'],'listing-pending');self.assertTrue(entered.wait(.5))
                current[0]='two';self.files.refresh('two',2);gate.set()
                self.files.scan_worker.shutdown(wait=True);self.files.tick()
                self.assertFalse(self.files.snapshots);self.assertEqual((card/'owner.txt').read_text(),'preserved')
                r,_=self.files.wire_dispatch(2,{'folder':folder});self.assertEqual(r['errorCode'],'refresh-required')
            finally:gate.set()
    def test_cache_and_jobs_are_bounded(self):
        for i in range(7):
            folder=self.root/'files'/str(i);folder.mkdir()
            token=next(row['id'] for row in self.files.listing('internal',refresh=True)['items'] if row['name']==str(i))
            self.files.listing(token)
        self.assertLessEqual(len(self.files.snapshots),4);self.assertLessEqual(self.files.snapshot_bytes,8*1024**2)
        self.assertLessEqual(len(self.files.watch_ids),4);self.assertLessEqual(len(self.files.scans),2)

    @unittest.skipUnless(os.geteuid()==0,'Storage endpoint is owner-only')
    def test_real_endpoint_pending_listing_is_retried_by_ui_worker(self):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'guide-ui'))
        from guide_files_panel import FilesPanel
        import guide_install_wire
        self.populate();path=self.root/'files.sock';self.files.connect(path);self.files.listener.settimeout(.1)
        stopped=threading.Event();errors=[];original_scan=self.files._scan;original_call=guide_install_wire.call
        def scan(fd,cancel):time.sleep(.15);return original_scan(fd,cancel)
        def owner():
            while not stopped.is_set():
                try:self.files.poll()
                except TimeoutError:pass
                except Exception as error:errors.append(error);break
        def call(path_arg,op,args):
            self.assertEqual(path_arg,'/run/guideos-storage/files.sock')
            self.assertTrue(args['async_listing'])
            return original_call(str(path),op,args)
        with patch.object(self.files,'_scan',side_effect=scan),patch.object(guide_install_wire,'call',side_effect=call) as requests:
            thread=threading.Thread(target=owner);thread.start()
            try:
                result=FilesPanel.storage(2,{'folder':'internal','refresh':True})
                self.assertEqual(len(result['items']),32);self.assertGreaterEqual(requests.call_count,2)
                self.assertFalse(errors)
            finally:stopped.set();thread.join(2)
        self.assertFalse(thread.is_alive())

if __name__=='__main__':unittest.main()
