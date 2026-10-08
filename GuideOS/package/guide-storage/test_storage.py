import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import storage_service as storage

MEDIA = Path(__file__).resolve().parent.parent/'guide-media'
if str(MEDIA) not in os.sys.path: os.sys.path.insert(0,str(MEDIA))
from storage_media_runtime import create_storage_media_host
from storage_media_runtime import MediaLibraryEndpoint

class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
    def folder(self, name):
        path = self.root/name; path.mkdir(parents=True,exist_ok=True); return path
    def test_ordinary_and_empty(self):
        self.assertEqual(storage.recognize(self.root)['state'], 'ordinary')
        self.folder('GUIDE')
        self.assertEqual(storage.recognize(self.root)['state'], 'incomplete')
    def test_host_cartridge_tool_minimal_layout(self):
        card = self.folder('GUIDE/CARTRIDGES')
        (card/'sample.guide').write_bytes(b'not a verified archive')
        (card/'sample.gde').write_text('not a trusted manifest')
        result = storage.recognize(self.root)
        self.assertEqual(result['state'], 'guide'); self.assertEqual(result['packages'], 1)
        self.assertNotIn('verified', result)
    def test_case_insensitive_canonical_folders_and_unicode(self):
        self.folder('guide/applications/games'); self.folder('guide/applications/BIOS')
        self.folder('guide/media/éŸ³æ¥½'); self.folder('guide/documents')
        result = storage.recognize(self.root)
        self.assertEqual(result['state'],'guide')
        self.assertIn('APPLICATIONS/GAMES',result['folders'])
        self.assertIn('APPLICATIONS/BIOS',result['folders'])
    def test_symlink_and_duplicate_roots_rejected(self):
        self.folder('other/CARTRIDGES'); (self.root/'GUIDE').symlink_to('other')
        self.assertEqual(storage.recognize(self.root)['state'],'invalid')
        (self.root/'GUIDE').unlink(); self.folder('GUIDE'); self.folder('guide')
        self.assertEqual(storage.recognize(self.root)['state'],'invalid')
    def test_symlink_child_and_file_rejected(self):
        self.folder('GUIDE'); (self.root/'GUIDE/MEDIA').symlink_to('/etc')
        self.assertEqual(storage.recognize(self.root)['state'],'invalid')
        (self.root/'GUIDE/MEDIA').unlink(); (self.root/'GUIDE/MEDIA').touch()
        self.assertEqual(storage.recognize(self.root)['state'],'invalid')
    def test_scan_is_bounded(self):
        self.folder('GUIDE')
        for i in range(storage.LIMIT+1): (self.root/'GUIDE'/str(i)).touch()
        self.assertEqual(storage.recognize(self.root)['state'],'invalid')
    def test_count_does_not_follow_links_or_walk_recursively(self):
        card=self.folder('GUIDE/CARTRIDGES'); self.folder('GUIDE/CARTRIDGES/nested.guide')
        (card/'link.guide').symlink_to('/etc/passwd')
        self.assertEqual(storage.recognize(self.root)['packages'],0)
    def test_recognition_does_not_write(self):
        self.folder('GUIDE/MEDIA'); before={str(x): x.stat().st_mtime_ns for x in self.root.rglob('*')}
        storage.recognize(self.root)
        self.assertEqual(before,{str(x):x.stat().st_mtime_ns for x in self.root.rglob('*')})

class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.base=self.root/'class/block';self.base.mkdir(parents=True)
    def disk(self, name, controller, cid='card', seq='1'):
        disk=self.root/'devices'/controller/name; (disk/'device').mkdir(parents=True)
        for key,value in {'device/type':'SD','device/cid':cid,'diskseq':seq,'dev':'179:8','size':'2048'}.items():
            (disk/key).write_text(value)
        (self.base/name).symlink_to(disk);return disk
    def test_controller_identity_ignores_device_number(self):
        self.disk('mmcblk1','4020000.mmc');self.disk('mmcblk2','4022000.mmc')
        self.assertEqual(storage.discover('4022000.mmc',self.base)['disk'],'mmcblk2')
    def test_absence_and_reinsertion_generation(self):
        self.assertIsNone(storage.discover('4022000.mmc',self.base))
        disk=self.disk('mmcblk3','4022000.mmc');before=storage.discover('4022000.mmc',self.base)
        (disk/'diskseq').write_text('2')
        self.assertNotEqual(before,storage.discover('4022000.mmc',self.base))
    def test_ambiguous_slot_is_rejected(self):
        self.disk('mmcblk1','4022000.mmc');self.disk('mmcblk2','4022000.mmc')
        with self.assertRaises(RuntimeError):storage.discover('4022000.mmc',self.base)
    def test_mounted_seed_refused_before_blkid(self):
        card=dict(disk='mmcblk0',devices=['mmcblk0p1'],identity=('cid','1','179:0','100'))
        with patch.object(storage,'discover',return_value=card), patch.object(storage,'device_number',return_value='179:0'), patch.object(storage.Path,'read_text',return_value='20 10 179:0 / / rw - ext4 /dev/mmcblk0 rw'), patch.object(storage,'command') as cmd:
            self.assertEqual(storage.probe('4022000.mmc')['state'],'busy');cmd.assert_not_called()
    def test_multiple_volumes_refused_before_mount(self):
        card=dict(disk='mmcblk1',devices=['mmcblk1p1','mmcblk1p2'],identity=('cid','1','179:8','100'))
        with patch.object(storage,'discover',return_value=card), patch.object(storage,'device_number',return_value='179:8'), patch.object(storage.Path,'read_text',return_value=''), patch.object(storage,'command',return_value='exfat') as cmd:
            self.assertEqual(storage.probe('4022000.mmc')['state'],'unsupported')
            self.assertTrue(all(call.args[0]=='/usr/sbin/blkid' for call in cmd.call_args_list))
    def test_read_only_mount_and_removal_discard(self):
        card=dict(disk='mmcblk1',devices=['mmcblk1p1'],identity=('cid','1','179:8','100'))
        mounts='20 10 179:8 / '+str(storage.MOUNT)+' ro,nodev,nosuid,noexec - exfat /dev/mmcblk1p1 ro'
        with patch.object(storage,'discover',side_effect=[card,card,None]), patch.object(storage,'device_number',return_value='179:8'), patch.object(storage.Path,'read_text',side_effect=['',mounts]), patch.object(storage,'command',side_effect=['exfat','']) as cmd, patch.object(storage,'recognize',return_value=dict(state='guide')):
            with self.assertRaises(RuntimeError):storage.probe('4022000.mmc')
            mount=cmd.call_args_list[1].args
            self.assertIn('ro,nodev,nosuid,noexec,noatime,iocharset=utf8',mount)


class LifecycleTests(unittest.TestCase):
    def test_departed_filesystem_is_detached_even_when_ismount_is_false(self):
        mounts='20 10 179:8 / '+str(storage.MOUNT)+' ro,nodev,nosuid,noexec - exfat /dev/mmcblk1p1 ro'
        with patch.object(storage.Path,'read_text',return_value=mounts), patch.object(storage.os.path,'ismount',return_value=False) as stat_mount, patch.object(storage,'command') as command:
            storage.unmount()
        stat_mount.assert_not_called()
        command.assert_called_once_with('/usr/bin/umount','-l',str(storage.MOUNT))

    def test_unmount_only_detaches_storage_owned_path(self):
        mounts='20 10 179:8 / /other/card ro - exfat /dev/mmcblk1p1 ro'
        with patch.object(storage.Path,'read_text',return_value=mounts), patch.object(storage,'command') as command:
            storage.unmount()
        command.assert_not_called()

    def test_repeated_insertion_removal_refreshes_catalog(self):
        cards=[dict(disk='mmcblk1',devices=['mmcblk1p1'],identity=('cid',str(seq),'179:8','100')) for seq in (1,2,3)]
        sequence=[None,cards[0],None,cards[1],None,cards[2],None]
        step=[0];handlers={};snapshots=[];catalog=Mock();mount=[False]
        def wait(_):
            step[0]+=1
            if step[0]==len(sequence):handlers[storage.signal.SIGTERM]()
        def command(*args,**kwargs):
            if args[0]=='/usr/bin/umount':mount[0]=False;return ''
            self.assertFalse(mount[0], 'stale mount blocks reinsertion')
            mount[0]=True
            return json.dumps(dict(state='guide',folders=['CARTRIDGES']))
        def mountinfo(*_):
            return ('20 10 179:8 / '+str(storage.MOUNT)+' ro - exfat /dev/mmcblk1p1 ro') if mount[0] else ''
        with patch.object(storage.Path,'mkdir'), patch.object(storage.Path,'read_text',side_effect=mountinfo), patch.object(storage.os.path,'ismount',return_value=False), patch.object(storage.signal,'signal',side_effect=lambda sig,fn:handlers.update({sig:fn})), patch.object(storage,'discover',side_effect=lambda _:sequence[step[0]]), patch.object(storage,'command',side_effect=command), patch.object(storage,'publish',side_effect=lambda value:snapshots.append(value.copy())):
            storage.serve('4022000.mmc',catalog_factory=lambda *_:catalog,wait=wait)
        recognized=[s for s in snapshots if s['state']=='guide']
        self.assertEqual([s['generation'] for s in recognized],[1,3,5])
        self.assertEqual([call.args[0] for call in catalog.invalidate.call_args_list if call.args],cards)
        self.assertFalse(mount[0])

    def test_removal_releases_mount_and_clears_snapshot(self):
        card=dict(disk='mmcblk1',devices=['mmcblk1p1'],identity=('cid','1','179:8','100'))
        handlers={}; sleeps=[]; snapshots=[]
        def sleep(_):
            sleeps.append(1)
            if len(sleeps)==2: handlers[storage.signal.SIGTERM]()
        with patch.object(storage.Path,'mkdir'), patch.object(storage.signal,'signal',side_effect=lambda sig,fn:handlers.update({sig:fn})), patch.object(storage,'discover',side_effect=[card,card,None]), patch.object(storage,'command',return_value=json.dumps(dict(state='guide',message='Guide layout recognized',folders=['CARTRIDGES']))), patch.object(storage,'unmount') as unmount, patch.object(storage,'publish',side_effect=lambda value:snapshots.append(value.copy())), patch.object(storage.time,'sleep',side_effect=sleep):
            storage.serve('4022000.mmc',catalog_factory=lambda *_:Mock(),wait=lambda _:storage.time.sleep(1))
        self.assertEqual([s['state'] for s in snapshots],['checking','guide','absent','unavailable'])
        self.assertEqual(snapshots[2]['folders'],[])
        self.assertEqual([s['generation'] for s in snapshots],[1,1,2,2])
        self.assertEqual(unmount.call_count,4)

    def test_media_catalog_shares_storage_lifecycle_inside_service(self):
        card=dict(disk='mmcblk1',devices=['mmcblk1p1'],identity=('cid','1','179:8','100'))
        handlers={};sleeps=[];host=Mock();host.listener=None
        def sleep(_):
            sleeps.append(1)
            if len(sleeps)==2:handlers[storage.signal.SIGTERM]()
        with patch.object(storage.Path,'mkdir'), patch.object(storage.signal,'signal',side_effect=lambda sig,fn:handlers.update({sig:fn})), patch.object(storage,'discover',side_effect=[card,card,None]), patch.object(storage,'command',return_value=json.dumps(dict(state='guide',message='Guide layout recognized',folders=['MEDIA']))), patch.object(storage,'unmount'), patch.object(storage,'publish'), patch.object(storage.time,'sleep',side_effect=sleep):
            storage.serve('4022000.mmc',catalog_factory=lambda *_:Mock(),wait=lambda _:storage.time.sleep(1),media_factory=lambda mount:host)
        self.assertEqual(host.refresh.call_count,2)
        first=host.refresh.call_args_list[0].args[0]
        self.assertEqual(first['generation'],1)
        self.assertIn('MEDIA',first['folders'])
        self.assertEqual(host.refresh.call_args_list[1].args[0]['state'],'absent')
        self.assertGreaterEqual(host.invalidate.call_count,2)
        host.close.assert_called_once()

class StartupRecoveryTests(unittest.TestCase):
    def test_transient_absent_probe_retries_without_physical_reinsertion(self):
        card=dict(disk='mmcblk1',devices=['mmcblk1p1'],identity=('cid','1','179:8','100'))
        handlers={};clock=[0];snapshots=[]
        def sleep(seconds):
            clock[0]+=seconds
            if clock[0]>=12:handlers[storage.signal.SIGTERM]()
        replies=[json.dumps(dict(state='absent',message='No card in external slot',folders=[])),
                 json.dumps(dict(state='guide',message='Guide layout recognized',folders=['MEDIA']))]
        with patch.object(storage.Path,'mkdir'), patch.object(storage.signal,'signal',side_effect=lambda sig,fn:handlers.update({sig:fn})), patch.object(storage,'discover',return_value=card), patch.object(storage,'command',side_effect=replies) as probe, patch.object(storage,'unmount'), patch.object(storage,'publish',side_effect=lambda value:snapshots.append(value.copy())), patch.object(storage.time,'monotonic',side_effect=lambda:clock[0]), patch.object(storage.time,'sleep',side_effect=sleep):
            storage.serve('4022000.mmc',catalog_factory=lambda *_:Mock(),wait=lambda _:storage.time.sleep(1))
        self.assertEqual(probe.call_count,2)
        self.assertEqual(snapshots[-2]['state'],'guide')
        self.assertEqual(snapshots[-2]['folders'],['MEDIA'])
        self.assertEqual(snapshots[-2]['generation'],1)

class MediaRuntimeTests(unittest.TestCase):
    def test_production_endpoint_uses_supplied_listener_and_provider_validator(self):
        listener=Mock();listener.accept.side_effect=BlockingIOError
        catalog=Mock();endpoint=MediaLibraryEndpoint(listener,catalog,grants=Mock())
        listener.setblocking.assert_called_once_with(False)
        self.assertIs(endpoint.listener,listener)
        self.assertIs(endpoint.broker.catalog,catalog)

    def test_persistent_private_identity_and_key(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);mount=root/'mount';state=root/'state'
            (mount/'GUIDE/MEDIA').mkdir(parents=True)
            first=create_storage_media_host(mount,state=state)
            second=create_storage_media_host(mount,state=state)
            self.assertEqual(first.catalog.source_id,second.catalog.source_id)
            self.assertEqual(len(first.catalog.source_id),16)
            self.assertEqual((state/'storage-source-id').stat().st_mode & 0o077,0)
            self.assertEqual((state/'storage-id-key').stat().st_mode & 0o077,0)

    def test_invalid_or_linked_state_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);mount=root/'mount';state=root/'state';state.mkdir()
            target=root/'outside';target.write_bytes(b'X'*16)
            (state/'storage-source-id').symlink_to(target)
            with self.assertRaises((OSError,RuntimeError)):
                create_storage_media_host(mount,state=state)

if __name__=='__main__':unittest.main()
