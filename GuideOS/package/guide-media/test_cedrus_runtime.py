"""Admission boundaries: incomplete builds and unrelated cameras stay software."""
import hashlib,json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from cedrus_runtime import select_decoder,REQUIRED_LIBRARIES
from mpv_backend import MpvJsonBackend

class CedrusAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.runtime=self.root/'runtime'
        (self.runtime/'bin').mkdir(parents=True)
        self.files={}
        for name in ('bin/mpv','bin/mpv-guide',*REQUIRED_LIBRARIES):
            target=self.runtime/name;target.parent.mkdir(exist_ok=True);target.write_bytes(name.encode())
            target.chmod(0o755);self.files[name]=hashlib.sha256(target.read_bytes()).hexdigest()
        self.manifest=dict(schema=1,hwdec='v4l2request-copy',codecs=['h264'],kernel_release='guide-test',files=self.files)
        self.save()
        self.sysfs=self.root/'sys';self.dev=self.root/'dev';self.dev.mkdir()
        self.platform=self.root/'platform';self.platform.mkdir()
        driver=self.root/'drivers/cedrus';driver.mkdir(parents=True)
        (self.platform/'driver').symlink_to(driver,target_is_directory=True)
        (self.platform/'of_node').mkdir();(self.platform/'of_node/compatible').write_bytes(b'allwinner,sun50i-h616-video-engine\0')
        for subsystem,name in [('media','media2'),('video4linux','video7')]:
            entry=self.sysfs/subsystem/name;entry.mkdir(parents=True)
            (entry/'device').symlink_to(self.platform,target_is_directory=True)
            (self.dev/name).symlink_to('/dev/null')
    def save(self):
        (self.runtime/'manifest.json').write_text(json.dumps(self.manifest))
    def select(self,**values):
        return select_decoder(runtime=self.runtime,sysfs=self.sysfs,dev=self.dev,kernel_release='guide-test',**values)
    def test_complete_matching_runtime_is_admitted(self):
        self.assertEqual(self.select()['hwdec'],'v4l2request-copy')
    def test_wrong_kernel_keeps_system_player(self):
        self.manifest['kernel_release']='old';self.save()
        self.assertEqual(self.select()['reason'],'kernel-mismatch')
        self.assertEqual(self.select()['executable'],'/usr/bin/mpv')
    def test_missing_or_corrupt_library_cannot_be_admitted(self):
        (self.runtime/'lib/libavcodec.so.63').write_bytes(b'partial build')
        self.assertEqual(self.select()['reason'],'runtime-incomplete')
        (self.runtime/'lib/libavcodec.so.63').unlink()
        self.assertEqual(self.select()['hwdec'],'no')
    def test_no_media_node_and_inaccessible_nodes_keep_software(self):
        self.assertEqual(self.select(access=lambda p,m: False if Path(p).parent==self.dev else os.access(p,m))['hwdec'],'no')
        (self.dev/'media2').unlink();self.assertEqual(self.select()['hwdec'],'no')
    def test_camera_or_different_device_pair_cannot_be_admitted(self):
        (self.platform/'of_node/compatible').write_bytes(b'camera\0')
        self.assertEqual(self.select()['hwdec'],'no')
        (self.platform/'of_node/compatible').write_bytes(b'allwinner,sun50i-h616-video-engine\0')
        entry=self.sysfs/'media/media2/device';entry.unlink()
        other=self.root/'other';other.mkdir();entry.symlink_to(other,target_is_directory=True)
        self.assertEqual(self.select()['hwdec'],'no')
    def test_manifest_path_escape_is_rejected(self):
        self.manifest['files']['../escape']='0'*64;self.save()
        self.assertEqual(self.select()['hwdec'],'no')
    def test_bad_symlink_and_bad_json_are_rejected(self):
        target=self.runtime/'bin/mpv';target.unlink();target.symlink_to('/bin/true')
        self.assertEqual(self.select()['hwdec'],'no')
        (self.runtime/'manifest.json').write_text('[]')
        self.assertEqual(self.select()['hwdec'],'no')
    def test_admitted_player_keeps_descriptor_clock_and_leases(self):
        calls=[]
        class Process:
            def poll(self):return 1
        def popen(args,**kw):calls.append((args,kw));return Process()
        backend=MpvJsonBackend(self.root/'ipc',popen=popen,device='selected-route',display=True,
                               decoder_selector=self.select)
        backend.display_device=lambda:'/dev/dri/card1'
        with self.assertRaises(RuntimeError):
            backend.spawn(9,0,max_buffer_bytes=1234,audio_clock=True,drop_late_video=True)
        args,options=calls[0]
        self.assertEqual(args[0],str(self.runtime/'bin/mpv-guide'))
        self.assertIn('--hwdec=v4l2request-copy',args);self.assertIn('--hwdec-codecs=h264',args)
        self.assertIn('--hwdec-software-fallback=3',args);self.assertIn('--video-sync=audio',args)
        self.assertIn('--audio-device=pipewire/selected-route',args);self.assertIn('--gpu-sw=no',args)
        self.assertEqual(options['pass_fds'],(9,));self.assertEqual(options['process_group'],0)
    def test_real_launcher_preserves_source_fd_and_scopes_library_path(self):
        launcher=self.runtime/'bin/mpv-guide'
        shutil.copyfile(Path(__file__).with_name('cedrus-mpv.sh'),launcher);launcher.chmod(0o755)
        child=self.runtime/'bin/mpv'
        child.write_text('#!/usr/bin/python3\nimport json,os,sys\nprint(json.dumps(dict(data=os.read(int(sys.argv[1]),64).decode(),library=os.environ["LD_LIBRARY_PATH"])))\n')
        child.chmod(0o755)
        source=self.root/'video';source.write_bytes(b'inherited media descriptor')
        with source.open('rb') as stream:
            env=dict(os.environ,LD_LIBRARY_PATH='/parent-only')
            result=subprocess.run([str(launcher),str(stream.fileno())],pass_fds=(stream.fileno(),),
                                  env=env,capture_output=True,text=True,timeout=3,check=True)
        self.assertEqual(json.loads(result.stdout),dict(data='inherited media descriptor',library=str(self.runtime/'lib')))
        self.assertEqual(env['LD_LIBRARY_PATH'],'/parent-only')

if __name__=='__main__':unittest.main()
