import os,sys,tempfile,threading,time,unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'package/guide-storage'),str(ROOT/'package/guide-installer'),str(ROOT/'package/guide-ipc/python')]
from storage_files import Files
from transfers import Transfers
from unittest.mock import patch
from types import SimpleNamespace
DATA=b'owner-selected download\n'*8192
class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200);self.send_header('Content-Length',str(len(DATA)));self.end_headers();self.wfile.write(DATA[:100] if self.path=='/truncated' else DATA)
    def log_message(self,*_):pass
class TransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.files=Files(self.root/'card',self.root/'files');self.addCleanup(self.files.close)
        self.manager=Transfers(self.root/'jobs',self.files.dispatch);self.addCleanup(self.manager.close)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Fixture);threading.Thread(target=self.server.serve_forever,daemon=True).start();self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.url='http://127.0.0.1:'+str(self.server.server_port)
    def wait(self,identity):
        end=time.monotonic()+10
        while time.monotonic()<end:
            job=self.manager.jobs[identity]
            if job['state'] in ('completed','failed','cancelled') or job['reason']=='name-collision':return job
            time.sleep(.01)
        self.fail('transfer timeout')
    def download(self,name='test.txt'):
        job=self.manager.offer({'url':self.url},name);self.manager.start(job['id'],'internal','ask');return self.wait(job['id'])
    def test_download_finalization(self):
        job=self.download();self.assertEqual(job['state'],'completed');self.assertEqual((self.root/'files/test.txt').read_bytes(),DATA)
    def test_collision_and_keep_both(self):
        (self.root/'files/test.txt').write_text('owner original')
        job=self.download();self.assertEqual(job['state'],'needs-attention')
        self.manager.start(job['id'],'internal','keep-both')
        self.assertEqual((self.root/'files/test.txt').read_text(),'owner original')
        self.assertEqual((self.root/'files/test (1).txt').read_bytes(),DATA)
    def test_cancel_collision_cleans_only_partial(self):
        (self.root/'files/test.txt').write_text('owner original');job=self.download();self.manager.cancel(job['id'])
        self.assertEqual((self.root/'files/test.txt').read_text(),'owner original')
        self.assertFalse(list((self.root/'files').glob('.guide-part-*')))
    def test_symlink_source_rejected(self):
        (self.root/'files/link').symlink_to('/etc/passwd')
        rows=self.files.listing('internal')['items'];self.assertFalse(rows)
    def test_copy_uses_descriptor(self):
        (self.root/'files/original').write_bytes(DATA)
        entry=self.files.listing('internal')['items'][0]['id']
        job=self.manager.offer({'entry':entry},'copy');self.manager.start(job['id'],'internal','ask')
        self.assertEqual(self.wait(job['id'])['state'],'completed')
        self.assertEqual((self.root/'files/copy').read_bytes(),DATA)
    def test_removed_card_cannot_publish(self):
        card=self.root/'card';card.mkdir();current=['one'];self.files.current=lambda:current[0];self.files.writable=lambda:True;self.files.refresh('one',1)
        _,fds=self.files.begin(self.files.roots()[1]['id'],'new','a'*32);os.write(fds[0],b'partial');os.close(fds[0]);current[0]=None
        with self.assertRaises(ValueError):self.files.finish('a'*32,'ask')
        self.assertFalse((card/'new').exists())
    def test_low_space_preserves_existing_files(self):
        (self.root/'files/owner').write_bytes(b'unchanged')
        with patch('storage_files.os.fstatvfs',return_value=SimpleNamespace(f_bavail=0,f_frsize=4096)):
            job=self.download()
        self.assertEqual(job['state'],'failed');self.assertEqual(job['reason'],'low-space')
        self.assertEqual((self.root/'files/owner').read_bytes(),b'unchanged')
        self.assertFalse((self.root/'files/test.txt').exists())
    def test_truncated_download_never_published(self):
        self.url+='/truncated';job=self.download()
        self.assertEqual(job['state'],'failed');self.assertFalse((self.root/'files/test.txt').exists())
        self.assertFalse(list((self.root/'files').glob('.guide-part-*')))
    def test_replaced_card_requires_reselection(self):
        (self.root/'card').mkdir();current=['one'];self.files.current=lambda:current[0]
        self.files.refresh('one',1);folder=self.files.roots()[1]['id']
        current[0]='two';self.files.refresh('two',2)
        with self.assertRaises(ValueError):self.files.begin(folder,'new','b'*32)
        self.assertFalse((self.root/'card/new').exists())
    def test_cancel_during_playback_backpressure(self):
        self.manager.should_yield=lambda:True
        job=self.manager.offer({'url':self.url},'cancelled');self.manager.start(job['id'],'internal','ask')
        end=time.monotonic()+5
        while self.manager.jobs[job['id']]['state']!='paused' and time.monotonic()<end:time.sleep(.01)
        self.assertEqual(self.manager.jobs[job['id']]['state'],'paused')
        self.manager.cancel(job['id']);self.assertEqual(self.wait(job['id'])['state'],'cancelled')
        self.assertFalse((self.root/'files/cancelled').exists())
    def test_service_restart_marks_unfinished_job_honestly(self):
        job=self.manager.offer({'url':self.url},'unfinished')
        second=Transfers(self.root/'jobs',self.files.dispatch)
        try:self.assertEqual(second.jobs[job['id']]['reason'],'interrupted-reselect-or-retry')
        finally:second.close()
    @unittest.skipUnless(os.geteuid()==0,'Root-owned descriptor endpoint requires root')
    def test_real_storage_socket_descriptor_download(self):
        from guide_install_wire import call
        path=self.root/'files.sock';self.files.connect(path);stop=threading.Event()
        def serve():
            import select
            while not stop.is_set():
                if select.select([self.files.listener],[],[],.05)[0]:self.files.poll()
        thread=threading.Thread(target=serve);thread.start()
        def remote(op,args):
            result,fds=call(str(path),op,args)
            if 'errorCode' in result:raise ValueError(result['errorCode'])
            return result,fds
        self.manager.storage=remote
        try:
            job=self.download('socket.txt');self.assertEqual(job['state'],'completed')
            self.assertEqual((self.root/'files/socket.txt').read_bytes(),DATA)
        finally:stop.set();thread.join()
if __name__=='__main__':unittest.main()
