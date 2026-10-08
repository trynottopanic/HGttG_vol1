import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import resource_host as host
from resource_guard import Pressure, pressure_counters
from stage import stage


class ResourceTests(unittest.TestCase):
    def test_available_memory_and_reclaim_trigger_before_exhaustion(self):
        policy=Pressure()
        self.assertFalse(policy.sample(120*host.MIB,10,0,0))
        self.assertFalse(policy.sample(120*host.MIB,11,0,1))
        self.assertTrue(policy.sample(120*host.MIB,12,0,3))
        self.assertFalse(policy.sample(200*host.MIB,13,0,4))
        self.assertFalse(policy.sample(70*host.MIB,13,0,5))
        self.assertTrue(policy.sample(70*host.MIB,13,0,7))

    def test_low_memory_without_stalls_does_not_kill_at_soft_threshold(self):
        policy=Pressure()
        for t in range(10):self.assertFalse(policy.sample(120*host.MIB,5,0,t))

    def test_browser_reclaim_livelock_triggers_even_with_global_headroom(self):
        policy=Pressure()
        self.assertFalse(policy.sample(300*host.MIB,0,0,0,0))
        self.assertFalse(policy.sample(300*host.MIB,0,0,1,100))
        self.assertTrue(policy.sample(300*host.MIB,0,0,3,200))

    def test_pressure_interface_absent_uses_reclaim_counters(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'vmstat').write_text('allocstall_normal 7\nallocstall_movable 2\n')
            self.assertEqual(pressure_counters(path),(9,0))

    def test_real_session_limits_required_even_when_launcher_has_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);group=root/'user.slice/user-987.slice';group.mkdir(parents=True)
            for key,value in {'memory.high':host.BROWSER_HIGH,'memory.max':host.BROWSER_MAX,
                              'memory.swap.max':64*host.MIB,'pids.max':256,'memory.oom.group':1}.items():
                (group/key).write_text(str(value))
            read=host.bounded
            def own(path,limit=16384):
                if Path(path)==Path('/proc/self/cgroup'):return '0::/user.slice/user-987.slice/session-3.scope\n'
                return read(path,limit)
            with patch.object(host,'CGROUP',root),patch.object(host,'bounded',side_effect=own),patch.object(host,'mem_available',return_value=600*host.MIB):
                host.verify_browser_limits(group)
                (group/'memory.max').write_text('max')
                with self.assertRaisesRegex(RuntimeError,'not enforced'):host.verify_browser_limits(group)

    def test_wrong_group_membership_is_rejected(self):
        with patch.object(host,'bounded',side_effect=['320','384','64','256','1','0::/system.slice/launcher.service']),patch.object(host,'mem_available',return_value=1000*host.MIB):
            with self.assertRaisesRegex(RuntimeError,'outside'):host.verify_browser_limits(host.CGROUP/'user.slice/user-987.slice')

    def test_missing_guard_and_insufficient_headroom_prevent_launch(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(host,'RUNTIME',Path(tmp)):
            with self.assertRaises(OSError):host.browser_admission()
            (Path(tmp)/'status.json').write_text(json.dumps(dict(state='ready',observed=100)))
            with patch.object(host.time,'monotonic',return_value=101),patch.object(host,'mem_available',return_value=400*host.MIB):
                with self.assertRaisesRegex(RuntimeError,'Not enough'):host.browser_admission()
            with patch.object(host.time,'monotonic',return_value=110):
                with self.assertRaisesRegex(RuntimeError,'unavailable'):host.browser_admission()

    def test_cannot_target_system_services_or_arbitrary_pids(self):
        runtime=host.Host(runner=Mock())
        for unit in ('systemd-logind.service','dbus.service','guide-app-foo.service','123'):
            with self.assertRaises(ValueError):runtime.observe(unit,'bad')
        runtime.runner.assert_not_called()

    def test_replaced_invocation_is_never_stopped(self):
        runtime=host.Host()
        runtime.same=Mock(return_value=False);runtime.empty=Mock(return_value=False)
        runtime.command=Mock()
        with self.assertRaisesRegex(RuntimeError,'changed'):runtime.stop({'unit':'guide-browser.service'},True)
        runtime.command.assert_not_called()

    def test_force_close_observes_all_released_before_shell_restart(self):
        runtime=host.Host();runtime.stop=Mock(side_effect=RuntimeError('still stopping'))
        runtime.command=Mock();runtime.observe=Mock()
        with self.assertRaisesRegex(RuntimeError,'still stopping'):runtime.force_home([{'unit':'guide-browser.service'}])
        runtime.command.assert_not_called();runtime.observe.assert_not_called()

    def test_group_removed_during_completion_check_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            group=Path(tmp)/'old';group.mkdir()
            (group/'cgroup.events').write_text('populated 0\n')
            record={'groups':[(str(group),group.stat().st_ino)]}
            open_real=os.open
            def disappearing(path,flags,**kwargs):
                fd=open_real(path,flags,**kwargs)
                if str(path)==str(group):
                    (group/'cgroup.events').unlink();group.rmdir()
                return fd
            with patch.object(host.os,'open',side_effect=disappearing):
                self.assertTrue(host.Host().empty(record))

    def test_replacement_group_is_rejected_and_live_group_is_not_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            group=Path(tmp)/'group';group.mkdir()
            (group/'cgroup.events').write_text('populated 1\n')
            inode=group.stat().st_ino
            runtime=host.Host()
            self.assertFalse(runtime.empty({'groups':[(str(group),inode)]}))
            with self.assertRaisesRegex(RuntimeError,'replaced'):
                runtime.empty({'groups':[(str(group),inode+1)]})
            (group/'cgroup.events').unlink()
            with self.assertRaisesRegex(RuntimeError,'evidence unavailable'):
                runtime.empty({'groups':[(str(group),inode)]})

    def test_offline_stage_resolves_uid_and_preserves_account_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'etc').mkdir();(root/'etc/debian_version').touch()
            passwd='root:x:0:0::/root:/bin/sh\nguide-browser:x:987:987::/nonexistent:/usr/sbin/nologin\n'
            (root/'etc/passwd').write_text(passwd)
            files=stage(root)
            self.assertEqual((root/'etc/passwd').read_text(),passwd)
            config=root/'etc/systemd/system/user-987.slice.d/50-guide-browser-resources.conf'
            self.assertIn('MemoryMax=384M',config.read_text())
            self.assertNotIn('MemoryOOMGroup=',config.read_text())
            self.assertEqual((root/'etc/systemd/system/autovt@tty3.service').readlink(),Path('/dev/null'))
            self.assertGreater(len(files),10)

    def test_oversized_evidence_is_not_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'status';path.write_bytes(b'x'*100)
            with self.assertRaises(ValueError):host.bounded(path,32)


if __name__=='__main__':unittest.main()
