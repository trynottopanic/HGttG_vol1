"""Real IPC stream fixtures exercise the single-reader notification boundary."""
import json,socket,tempfile,threading,time,unittest
from pathlib import Path
from mpv_backend import MpvJsonBackend

class ObservationTests(unittest.TestCase):
    def test_track_inventory_notifications_reach_adapter_without_poll_requests(self):
        from mpv_video_adapter import MpvVideoAdapter
        self.event('track-list',[dict(type='audio',id=1,lang='eng',selected=True),
                                 dict(type='audio',id=2,lang='fra',selected=False),
                                 dict(type='sub',id=4,lang='eng',selected=False)])
        adapter=MpvVideoAdapter(self.backend);tracks=adapter.tracks()
        self.assertEqual(len(tracks['audio']),2);self.assertEqual(len(tracks['subtitle']),1)
        self.assertTrue(tracks['audio'][0]['selected'])
        self.assertIn('fra',tracks['audio'][1]['label'])
        self.assertEqual(len(tracks['subtitle'][0]['id']),16)
        self.server.setblocking(False)
        with self.assertRaises(BlockingIOError):self.server.recv(1)
    def setUp(self):
        self.backend=MpvJsonBackend(Path('/tmp/guide-notification-test'))
        self.client,self.server=socket.socketpair();self.client.settimeout(.25)
        self.backend.connection=self.client;self.backend.observing=True
        self.addCleanup(self.client.close);self.addCleanup(self.server.close)
    def event(self,name,data):
        self.server.sendall(json.dumps(dict(event='property-change',id=self.backend.PROPERTIES.index(name)+1,name=name,data=data)).encode()+b'\n')
    def test_notifications_coalesce_without_polling_requests(self):
        self.event('demuxer-cache-state',{'eof':True});self.event('eof-reached',False)
        self.event('duration',8);self.event('time-pos',1);self.event('time-pos',2)
        self.event('demuxer-cache-duration',3)
        result=self.backend.status();self.assertEqual(result['position_ms'],2000)
        self.assertEqual(result['buffered_ms'],3000);self.assertTrue(result['input_complete'])
        self.server.setblocking(False)
        with self.assertRaises(BlockingIOError):self.server.recv(1)
    def test_command_reply_preserves_interleaved_properties(self):
        def decoder():
            request=json.loads(self.server.recv(4096))
            self.event('time-pos',3.5)
            self.server.sendall(json.dumps(dict(request_id=request['request_id'],error='success')).encode()+b'\n')
        thread=threading.Thread(target=decoder);thread.start()
        self.backend.command('set_property','pause',True);thread.join(1)
        self.assertEqual(self.backend.status()['position_ms'],3500)
    def test_seek_cannot_reuse_old_end_and_buffer_until_restart(self):
        self.event('demuxer-cache-state',{'eof':True});self.event('eof-reached',True);self.event('demuxer-cache-duration',9)
        self.backend.status();self.backend.seek_pending=True
        result=self.backend.status();self.assertFalse(result['ended']);self.assertFalse(result['input_complete']);self.assertEqual(result['buffered_ms'],0)
        self.server.sendall(b'{"event":"playback-restart"}\n');self.event('eof-reached',False);self.event('demuxer-cache-duration',2)
        self.assertEqual(self.backend.status()['buffered_ms'],2000)
    def test_closed_decoder_cannot_report_cached_readiness(self):
        self.event('demuxer-cache-duration',4);self.backend.status();self.server.close()
        with self.assertRaises(RuntimeError):self.backend.status()
    def test_seek_restart_keeps_unchanged_observed_cache_properties(self):
        self.event('demuxer-cache-state',{'eof':True});self.event('eof-reached',False);self.event('demuxer-cache-duration',1.5)
        self.backend.status()
        self.backend._event({'event':'seek'})
        self.assertEqual(self.backend.status()['buffered_ms'],0)
        # mpv sends property changes, not snapshots. Unchanged complete-input
        # evidence must survive the seek barrier so a short clip can resume.
        self.backend._event({'event':'playback-restart'})
        result=self.backend.status();self.assertEqual(result['buffered_ms'],1500)
        self.assertTrue(result['input_complete']);self.assertFalse(result['ended'])
    def test_invalid_numbers_are_rejected(self):
        self.event('time-pos',float('nan'))
        with self.assertRaises(ValueError):self.backend.status()
    def test_runtime_rendering_evidence_distinguishes_gpu_and_decode(self):
        self.assertIsNone(self.backend.status()['rendering']['hardware_rendering'])
        self.event('current-vo','gpu')
        self.assertIsNone(self.backend.status()['rendering']['hardware_rendering'])
        self.event('current-gpu-context','drm');self.event('hwdec-current','no')
        evidence=self.backend.status()['rendering']
        self.assertTrue(evidence['hardware_rendering']);self.assertFalse(evidence['hardware_decoding'])
        self.event('current-vo','drm');self.event('current-gpu-context',None)
        self.assertFalse(self.backend.status()['rendering']['hardware_rendering'])
        self.server.setblocking(False)
        with self.assertRaises(BlockingIOError):self.server.recv(1)
    def test_unavailable_or_invalid_decoder_evidence_is_unknown(self):
        for value in (None,{},'x'*65,'untrusted\ntext'):
            self.event('hwdec-current',value)
            evidence=self.backend.status()['rendering']
            self.assertIsNone(evidence['decoder']);self.assertIsNone(evidence['hardware_decoding'])
        self.event('hwdec-current','drm')
        self.assertTrue(self.backend.status()['rendering']['hardware_decoding'])
    def test_hardware_admission_cannot_report_hardware_after_fallback(self):
        self.backend.decoder_policy=dict(executable='/private/mpv',hwdec='v4l2request-copy',reason='cedrus-admitted')
        self.event('hwdec-current','no')
        evidence=self.backend.status()['rendering']
        self.assertEqual(evidence['decoder_admission'],'cedrus-admitted')
        self.assertFalse(evidence['hardware_decoding'])
        self.event('hwdec-current','v4l2request-copy')
        self.assertTrue(self.backend.status()['rendering']['hardware_decoding'])

if __name__=='__main__':unittest.main()
