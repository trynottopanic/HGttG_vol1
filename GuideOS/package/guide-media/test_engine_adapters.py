from pathlib import Path
import socket,sys,threading,unittest
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
IPC=HERE.parent/'guide-ipc';sys.path[:0]=[str(IPC/'python'),str(IPC/'generated')]
from buffer_policy import BufferController,LOCAL_AUDIO,LOCAL_VIDEO,policy
from gst_audio_adapter import GStreamerAudioAdapter
from mpv_video_adapter import MpvVideoAdapter
from mpv_backend import MpvJsonBackend, MpvCommandError
from provider_grants import ProviderGrantValidator
from guide_ipc import REPLY,encode_packet,recv_packet,send_packet
from types import SimpleNamespace

class Backend:
    def __init__(self):self.buffered=0;self.position=0;self.present=[];self.commands=[];self.stopped=False
    def open_descriptor(self,fd,pos,**kw):self.position=pos;self.open_options=kw
    def spawn(self,fd,pos,**kw):self.position=pos;self.open_options=kw
    def duration_ms(self):return 60_000
    def status(self):return {"position_ms":self.position,"buffered_ms":self.buffered,"dropped_frames":3,"av_offset_ms":12}
    def set_presenting(self,value):self.present.append(value)
    def command(self,*value):
        self.commands.append(value)
        if value and value[0]=="seek":self.buffered=0
    def seek(self,value):self.position=value
    def set_output(self,value):pass
    def stop(self,*a,**kw):self.stopped=True

class PolicyTests(unittest.TestCase):
    def test_low_and_high_water_prevent_catchup_start(self):
        c=BufferController(policy(LOCAL_VIDEO))
        self.assertFalse(c.update(1999,requested_play=True));self.assertTrue(c.update(2000,requested_play=True))
        self.assertFalse(c.update(749,requested_play=True));self.assertEqual(c.underruns,1)
        self.assertFalse(c.update(1999,requested_play=True));self.assertTrue(c.update(2000,requested_play=True))
    def test_resume_waits_for_high_water_after_pause(self):
        c=BufferController(policy(LOCAL_AUDIO))
        self.assertTrue(c.update(750,requested_play=True))
        self.assertFalse(c.update(400,requested_play=False))
        self.assertFalse(c.update(400,requested_play=True))
        self.assertTrue(c.update(750,requested_play=True))
        self.assertEqual(c.underruns,0)

    def test_complete_short_input_and_tail_drain_without_underrun(self):
        c=BufferController(policy(LOCAL_VIDEO))
        self.assertFalse(c.update(100,requested_play=True))
        self.assertTrue(c.update(100,requested_play=True,input_complete=True))
        self.assertTrue(c.update(0,requested_play=True,input_complete=True))
        self.assertEqual(c.underruns,0)
        self.assertFalse(c.update(100,requested_play=False,input_complete=True))

    def test_pause_does_not_count_underrun(self):
        c=BufferController(policy(LOCAL_AUDIO));c.update(750,requested_play=True)
        self.assertFalse(c.update(0,requested_play=False));self.assertEqual(c.underruns,0)

class AdapterTests(unittest.TestCase):
    def test_gstreamer_waits_for_audio_high_water(self):
        b=Backend();a=GStreamerAudioAdapter(b);a.open(4,100)
        b.buffered=749;self.assertFalse(a.play());b.buffered=750;self.assertTrue(a.poll()["ready"])
        self.assertEqual(b.present[-2:],[False,True])
    def test_mpv_owns_audio_clock_and_rebuffers(self):
        b=Backend();a=MpvVideoAdapter(b);a.open(4,0)
        self.assertTrue(b.open_options["audio_clock"]);self.assertTrue(b.open_options["drop_late_video"])
        b.buffered=2000;self.assertTrue(a.play());b.buffered=700
        report=a.poll();self.assertFalse(report["ready"]);self.assertEqual(report["underruns"],1)
        self.assertEqual(report["dropped_frames"],3);self.assertEqual(report["av_offset_ms"],12)
    def test_seek_resets_prebuffer_and_stop_is_bounded(self):
        b=Backend();a=MpvVideoAdapter(b);a.open(4,0);b.buffered=2000;a.play();a.seek(3000)
        self.assertFalse(a.ready);a.stop();self.assertTrue(b.stopped)

class ProviderValidationTests(unittest.TestCase):
    def test_provider_validation_binds_returned_peer_identity(self):
        client,server=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        identity="3"*32
        def serve():
            header,payload,fds=recv_packet(server)
            self.assertEqual(payload[1][1],8);self.assertEqual(payload[1][2],123)
            send_packet(server,encode_packet(REPLY,header.request_id,
                        {0:0,1:{0:1,1:bytes.fromhex(identity),2:4}},
                        interface_major=1,interface_minor=0));server.close()
        thread=threading.Thread(target=serve);thread.start()
        peer=SimpleNamespace(pid=123,uid=1000,gid=1000,
              context=SimpleNamespace(instance_id=identity,generation=4))
        self.assertTrue(ProviderGrantValidator(connector=lambda:client).validate_peer(
                        b"G"*16,peer,capability="media.session.control"))
        thread.join(1)

class MpvBackendTests(unittest.TestCase):
    def test_output_is_not_acknowledged_without_route_owner(self):
        backend=MpvJsonBackend(Path("/tmp/guide-mpv-test"))
        with self.assertRaises(ValueError):backend.set_output(b"O"*16)
        commands=[]
        backend.output_resolver=lambda value:"pipewire/selected-output"
        backend.command=lambda *values:commands.append(values)
        backend.set_output(b"O"*16)
        self.assertEqual(commands,[("set_property","audio-device","pipewire/selected-output")])
        backend.output_resolver=lambda value:"auto"
        with self.assertRaises(ValueError):backend.set_output(b"O"*16)

    def test_unavailable_status_is_distinct_from_decoder_failure(self):
        backend=MpvJsonBackend(Path("/tmp/guide-mpv-test"))
        def unavailable(*args):raise MpvCommandError("property unavailable")
        backend.command=unavailable
        self.assertIsNone(backend.duration_ms())
        def failure(*args):raise MpvCommandError("error")
        backend.command=failure
        with self.assertRaises(MpvCommandError):backend.duration_ms()
        backend.command=lambda *args:float("nan")
        with self.assertRaises(ValueError):backend.duration_ms()

    def test_spawn_arguments_keep_one_clock_and_inherited_source(self):
        calls=[]
        class Process:
            stderr=None
            def poll(self):return 1
        def popen(args,**kwargs):calls.append((args,kwargs));return Process()
        backend=MpvJsonBackend(Path("/tmp/guide-mpv-test"),popen=popen,headless=True)
        with self.assertRaises(RuntimeError):backend.spawn(9,1250,max_buffer_bytes=1234,
                                                           audio_clock=True,drop_late_video=True)
        args,kwargs=calls[0]
        self.assertIn("--video-sync=audio",args);self.assertIn("--framedrop=vo",args)
        self.assertIn("--demuxer-max-bytes=1234",args);self.assertIn("/proc/self/fd/9",args)
        self.assertEqual(kwargs["pass_fds"],(9,));self.assertTrue(kwargs["start_new_session"])

if __name__=='__main__':unittest.main()
