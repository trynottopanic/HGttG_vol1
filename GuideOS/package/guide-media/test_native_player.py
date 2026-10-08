import os,socket,sys,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'guide-audio'),str(HERE.parent/'guide-ipc/python'),str(HERE.parent/'guide-ipc/generated')]
from media_library import StorageMediaCatalog
from media_source_channel import SourceEndpoint,SourceClient,provider_peer
from media_player_service import Service
from audio_lease import AudioLease
from test_media_session import Engine

class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        folder=self.root/'GUIDE/MEDIA';folder.mkdir(parents=True)
        (folder/'song.mp3').write_bytes(b'music');(folder/'clip.mp4').write_bytes(b'video')
        self.catalog=StorageMediaCatalog(self.root,source_id=b'S'*16,id_key=b'K'*32)
        self.catalog.refresh(dict(state='guide',generation=1,folders=['MEDIA']))
    def tearDown(self):self.temp.cleanup()
    def test_descriptor_channel_and_stale_generation(self):
        endpoint=SourceEndpoint(self.catalog,self.root/'source.sock',authorize=lambda c:None)
        client=SourceClient(str(self.root/'source.sock'))
        def exchange(fn):
            thread=threading.Thread(target=lambda:(time.sleep(.01),endpoint.poll()))
            thread.start()
            try:return fn()
            finally:thread.join(1)
        try:
            item=exchange(lambda:client.list(kind=1))[1][0]
            fd=exchange(lambda:client.open_local(item[0],1))
            try:self.assertEqual(os.read(fd,8),b'music')
            finally:os.close(fd)
            self.catalog.refresh(dict(state='absent',generation=2,folders=[]))
            with self.assertRaises(RuntimeError):exchange(lambda:client.open_local(item[0],1))
        finally:endpoint.close()
    def test_playback_lease_excludes_other_process_owner(self):
        a=AudioLease(str(self.root/'lease'));b=AudioLease(str(self.root/'lease'))
        try:
            a.acquire()
            with self.assertRaises(ValueError):b.acquire()
            a.release();b.acquire()
        finally:a.release();b.release()
    def test_native_lifecycle_and_source_loss(self):
        service=Service();service.source=self.catalog;service.manager.source=self.catalog;service.admission.audio_lease=AudioLease(str(self.root/'lease'))
        service.engine=lambda:Engine()
        service.manager.engine_factory=service.engine
        status=dict(observed=time.monotonic(),output='selected',outputs=[dict(id='selected')],state='stopped',volume=20)
        item=self.catalog.list(after_media_id=None,limit=32,media_kind=1)[1][0]
        with patch('media_player_service.audio_status',lambda:status),patch('media_player_service.STATE',self.root):
            service.command(os.getpid(),dict(action='open',id=item[0].hex(),generation=1))
            self.assertTrue(service.active())
            service.command(os.getpid(),dict(action='pause'));self.assertEqual(service.status()['state'],'paused')
            service.command(os.getpid(),dict(action='seek',position=50))
            service.command(os.getpid(),dict(action='resume'))
            self.catalog.refresh(dict(state='absent',generation=2,folders=[]))
            service.tick();self.assertFalse(service.active());self.assertIsNone(service.admission.audio_lease.fd)
            self.assertTrue((self.root/'resume.json').is_file())
    def test_video_requires_shell_display_offer(self):
        service=Service();service.source=self.catalog;service.manager.source=self.catalog;service.admission.audio_lease=AudioLease(str(self.root/'lease'))
        item=self.catalog.list(after_media_id=None,limit=32,media_kind=2)[1][0]
        status=dict(output='selected',outputs=[dict(id='selected')],state='stopped',volume=20,inventory_observed=time.monotonic())
        with patch('media_player_service.audio_status',lambda:status):
            with self.assertRaisesRegex(RuntimeError,'Video requires shell display admission'):service.open(os.getpid(),dict(id=item[0].hex(),generation=1))
        self.assertFalse(service.active());self.assertIsNone(service.owner_fd)

    def test_missing_stale_or_invalid_inventory_cannot_acquire_output(self):
        for observed in (None,time.monotonic()-11,float('nan'),time.monotonic()+60,True,10**400):
            with self.subTest(observed=observed):
                service=Service();service.source=self.catalog;service.manager.source=self.catalog
                service.admission.audio_lease=AudioLease(str(self.root/'lease'))
                item=self.catalog.list(after_media_id=None,limit=32,media_kind=1)[1][0]
                status=dict(output='selected',outputs=[dict(id='selected')],state='stopped',volume=20,inventory_observed=observed)
                with patch('media_player_service.audio_status',lambda:status):
                    with self.assertRaisesRegex(RuntimeError,'Audio outputs are being checked'):service.open(os.getpid(),dict(id=item[0].hex(),generation=1))
                self.assertFalse(service.active());self.assertIsNone(service.owner_fd);self.assertIsNone(service.admission.audio_lease.fd)

if __name__=='__main__':unittest.main()
