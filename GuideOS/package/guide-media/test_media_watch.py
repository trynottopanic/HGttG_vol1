import os,select,socket,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from storage_media_runtime import MediaLibraryEndpoint
from media_library import StorageMediaCatalog
from guide_ipc import REQUEST,EVENT,encode_packet,send_packet,recv_packet
from guide_grants import GrantError
class Grants:
    denied=False
    def validate_peer(self,*a,**kw):
        if self.denied:raise GrantError('revoked')
class WatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.catalog=StorageMediaCatalog(self.root,source_id=b'S'*16,id_key=b'K'*32)
        self.catalog.refresh(dict(state='absent',generation=1,folders=[]))
        self.listener=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET);self.listener.bind(str(self.root/'socket'));self.listener.listen(10)
        self.grants=Grants();self.endpoint=MediaLibraryEndpoint(self.listener,self.catalog,grants=self.grants)
        self.clients=[]
    def tearDown(self):
        self.endpoint.close()
        for c in self.clients:c.close()
        self.tmp.cleanup()
    def watch(self,revision=None):
        c=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET);c.settimeout(.3);c.connect(str(self.root/'socket'));self.clients.append(c)
        send_packet(c,encode_packet(REQUEST,1,{0:5,1:{0:b'G'*16,1:self.catalog.library_revision if revision is None else revision},2:time.clock_gettime_ns(time.CLOCK_BOOTTIME)+2_000_000_000}))
        self.endpoint.poll();return c,recv_packet(c)[1]
    def test_delivers_change_without_paths_and_revalidates(self):
        c,reply=self.watch();self.assertEqual(reply[0],0)
        self.catalog.refresh(dict(state='absent',generation=2,folders=[]));self.endpoint.tick()
        header,payload,fds=recv_packet(c);self.assertEqual(header.message_class,EVENT);self.assertEqual(payload[0],1);self.assertNotIn(str(self.root),repr(payload));self.assertFalse(fds)
        self.grants.denied=True;self.endpoint.watchers[0]['next_check']=0;self.endpoint.tick();self.assertFalse(self.endpoint.watchers);self.assertEqual(c.recv(1),b'')
    def test_old_revision_requires_resnapshot(self):
        c,reply=self.watch(0);self.assertEqual(reply[0],0);self.assertEqual(recv_packet(c)[1][0],3)
    def test_deadline_closes_without_event(self):
        c,_=self.watch();self.endpoint.watchers[0]['deadline']=0;self.endpoint.tick();self.assertEqual(c.recv(1),b'')
    def test_limit_is_bounded_and_shutdown_releases_all(self):
        for _ in range(8):self.assertEqual(self.watch()[1][0],0)
        self.assertEqual(self.watch()[1][0],14);self.assertEqual(len(self.endpoint.watchers),8)
    def test_ungranted_watch_denied(self):
        self.grants.denied=True;self.assertEqual(self.watch()[1][0],6);self.assertFalse(self.endpoint.watchers)
if __name__=='__main__':unittest.main()
