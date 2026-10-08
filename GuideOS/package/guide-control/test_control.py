import json
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
import unittest
import threading
from concurrent.futures import Future
from unittest.mock import Mock,patch
from control_core import Chord,Foreground,START,SELECT,deployment_guard
from control_service import Control
from control_view import capture,View
from guide_control_client import RemoteDeckInputs


class ControlTests(unittest.TestCase):
    def test_chord_fires_once_until_both_buttons_are_released(self):
        chord=Chord()
        self.assertFalse(chord.update(SELECT,1))
        self.assertTrue(chord.update(START,1))
        self.assertFalse(chord.update(START,2))
        chord.update(SELECT,0)
        self.assertFalse(chord.update(SELECT,1))
        chord.update(START,0)
        chord.update(SELECT,0)
        chord.update(START,1)
        self.assertTrue(chord.update(SELECT,1))

    def test_other_buttons_do_not_trigger_the_chord(self):
        chord=Chord()
        for code in (304,305,316,317,318):self.assertFalse(chord.update(code,1))
        self.assertFalse(chord.held)

    def test_freeze_requires_kernel_acknowledgement(self):
        target=Foreground()
        target.events=Mock()
        target.events.read_text.return_value='populated 1\nfrozen 0\n'
        with patch('control_core.time.monotonic',side_effect=[0,3]):
            with self.assertRaises(RuntimeError):target.freeze()
        target.events.read_text.return_value='populated 1\nfrozen 1\n'
        target.freeze()

    def test_thaw_uses_kernel_state_even_with_stop_pending(self):
        target=Foreground()
        with tempfile.TemporaryDirectory() as tmp:
            target.events=Path(tmp)/'cgroup.events'
            target.events.write_text('populated 1\nfrozen 0\n')
            with patch.object(target,'frozen',side_effect=[False,False]):
                target.thaw()
            self.assertEqual((Path(tmp)/'cgroup.freeze').read_text(),'0\n')

    def fixture(self):
        control=Control.__new__(Control)
        control.client=Mock()
        control.foreground=Mock()
        control.foreground.unit='guide-shell.service'
        control.inputs=SimpleNamespace(devices=[])
        control.framebuffer=control.background=control.view=None
        control.active=False
        control.pending_open=False
        control.deploy_lock=None
        control.job=None;control.job_kind=None;control.preparing=False
        control.lease=None;control.ack=threading.Event();control.prepare_token=0
        control.workloads=[];control.confirm_close=False;control.notice=''
        control.force_failed=False;control.force_records=[]
        control.next_workloads=10000000;control.warm_view=Mock()
        control.pending_action=None
        control.send=Mock()
        class Immediate:
            def submit(self,work):
                future=Future()
                try:future.set_result(work())
                except Exception as error:future.set_exception(error)
                return future
        control.executor=Immediate()
        control.status=Mock()
        control.disconnect=Mock()
        return control

    def chord_fixture(self):
        control=Control.__new__(Control)
        control.chord=Chord();control.chord_pending=[]
        control.chord_deadline=0;control.chord_consumed=False
        return control

    def test_lone_select_is_forwarded_without_waiting_for_release(self):
        control=self.chord_fixture()
        # Event tuples are sufficient for the routing contract.
        event=('H700 Gamepad',1,SELECT,1)
        self.assertEqual(control.route_chord_event(event,1.0),([],False))
        self.assertEqual(control.flush_chord_events(1.11),[])
        self.assertEqual(control.flush_chord_events(1.12),[event])

    def test_select_start_chord_is_consumed(self):
        control=self.chord_fixture()
        select=('H700 Gamepad',1,SELECT,1);start=('H700 Gamepad',1,START,1)
        self.assertEqual(control.route_chord_event(select,2.0),([],False))
        self.assertEqual(control.route_chord_event(start,2.04),([],True))
        self.assertEqual(control.flush_chord_events(3.0),[])
        self.assertEqual(control.route_chord_event(('H700 Gamepad',1,SELECT,0),2.1),([],False))
        self.assertEqual(control.route_chord_event(('H700 Gamepad',1,START,0),2.11),([],False))

    def test_failed_display_acquisition_always_thaws(self):
        control=self.fixture()
        control.foreground.frozen.return_value=False
        control.framebuffer_factory=Mock(side_effect=OSError('no display'))
        lease=Mock();lease.prepare.return_value=1
        with tempfile.TemporaryDirectory() as tmp,patch('control_service.MARKER',Path(tmp)/'paused.json'),patch('control_service.OverlayLease',return_value=lease):
            lease.browser_inode=None
            control.open()
            control.poll_recovery()
            control.poll_recovery()
            lease.release.assert_called_once()
            self.assertFalse(control.active)

    def test_display_preparation_failure_releases_lease(self):
        control=self.fixture();control.foreground.frozen.return_value=False
        lease=Mock();lease.prepare.side_effect=RuntimeError('pause unavailable')
        with tempfile.TemporaryDirectory() as tmp,patch('control_service.MARKER',Path(tmp)/'paused.json'),patch('control_service.OverlayLease',return_value=lease):
            control.open();control.poll_recovery();control.poll_recovery()
            lease.release.assert_called_once()
            self.assertFalse(control.active)
            self.assertIn('pause unavailable',control.notice)

    def test_physical_a_confirms_force_and_b_cancels(self):
        control=self.fixture();control.active=True;control.preparing=False
        control.blocked=set();control.page=2;control.route_chord_event=lambda event,now:([event],False)
        control.flush_chord_events=lambda now:[];control.inputs.poll=Mock()
        control.start_force=Mock();control.resume=Mock()
        control.inputs.poll.return_value=[('H700 Gamepad',1,305,1)]
        control.events();self.assertTrue(control.confirm_close);control.start_force.assert_not_called()
        control.inputs.poll.return_value=[('H700 Gamepad',1,304,1)]
        control.events();self.assertFalse(control.confirm_close);control.resume.assert_not_called()
        control.inputs.poll.return_value=[('H700 Gamepad',1,305,1)]
        control.events();control.events();control.start_force.assert_called_once()

    def test_release_failure_requires_service_recovery(self):
        control=self.fixture();control.job_kind='release'
        control.job=Future();control.job.set_exception(RuntimeError('VT busy'))
        with self.assertRaisesRegex(RuntimeError,'recovering control'):control.poll_recovery()

    def test_partial_force_failure_keeps_overlay_and_original_targets(self):
        control=self.fixture();control.active=True;control.page=0
        original=[{'unit':'guide-browser.service','invocation':'original'}]
        control.workloads=original
        control.foreground.frozen.return_value=False
        control.lease=Mock()
        with patch('control_service.force_home',side_effect=FileNotFoundError(2,'group vanished')) as close,patch('control_service.emit') as emit:
            control.start_force();control.poll_recovery()
            self.assertTrue(control.force_failed)
            self.assertTrue(control.active)
            self.assertEqual(control.page,2)
            emit.assert_called_with('CONTROL_ERROR',phase='force',backend_error='FileNotFoundError',error_number=2)
            control.resume()
            control.lease.release.assert_not_called()
            control.workloads=[]
            control.start_force()
            self.assertEqual(close.call_args.args[0],original)

    def test_successful_force_retry_switches_to_home(self):
        control=self.fixture();control.active=True;control.force_failed=True
        control.force_records=[{'unit':'guide-browser.service'}]
        control.lease=Mock();control.lease.release.return_value=None
        with tempfile.TemporaryDirectory() as tmp,patch('control_service.MARKER',Path(tmp)/'paused.json'),patch('control_service.force_home',return_value='closed'):
            control.start_force();control.poll_recovery()
            self.assertFalse(control.force_failed)
            self.assertEqual(control.force_records,[])
            control.lease.release.assert_called_once_with(home=True)

    def test_shell_acknowledges_display_yield_over_real_channel(self):
        with tempfile.TemporaryDirectory() as tmp:
            server=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET)
            path=str(Path(tmp)/'input.sock');server.bind(path);server.listen(1)
            client=RemoteDeckInputs(path=path);peer,_=server.accept()
            try:
                peer.send(b'{"type":"overlay","token":42}')
                event=client.poll(.1)[0]
                self.assertEqual(event.control_prepare,42)
                client.display_yielded(42)
                self.assertEqual(json.loads(peer.recv(1024)),{'type':'display-yielded','token':42})
            finally:client.close();peer.close();server.close()

    def test_restore_happens_before_thaw(self):
        control=self.fixture()
        control.active=True
        control.framebuffer=Mock()
        control.background=object()
        control.foreground.frozen.return_value=True
        order=[]
        control.framebuffer.show.side_effect=lambda _:order.append('restore')
        control.foreground.thaw.side_effect=lambda:order.append('thaw')
        with tempfile.TemporaryDirectory() as tmp:
            marker=Path(tmp)/'paused.json'
            marker.write_text('{}')
            with patch('control_service.MARKER',marker):control.resume()
        self.assertEqual(order,['restore','thaw'])
        self.assertFalse(control.active)

    def test_remote_input_reset_and_forwarded_button(self):
        with tempfile.TemporaryDirectory() as tmp:
            server=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET)
            path=str(Path(tmp)/'input.sock')
            server.bind(path)
            server.listen(1)
            client=RemoteDeckInputs(path=path)
            peer,_=server.accept()
            try:
                peer.send(json.dumps(dict(type='reset',devices=['H700 Gamepad'],snapshot=dict(left=None,right=None,generation=2,right_click=False))).encode())
                events=client.poll(.1)
                self.assertTrue(events[0].control_resume)
                self.assertEqual(client.devices[0].name,'H700 Gamepad')
                peer.send(json.dumps(dict(type='events',events=[dict(values=['H700 Gamepad',1,305,1],timestamp=12.5)])).encode())
                self.assertEqual(tuple(client.poll(.1)[0]),('H700 Gamepad',1,305,1))
            finally:client.close();peer.close();server.close()

    def test_capture_honors_framebuffer_offsets(self):
        framebuffer=SimpleNamespace(width=2,height=1,bpp=32,xoff=1,yoff=1,stride=16,
            fields=[(16,8,0),(8,8,0),(0,8,0)],mem=b'\0'*20+b'\x00\x00\xff\0\x00\xff\x00\0'+b'\0'*4)
        image=capture(framebuffer)
        self.assertEqual(list(image.getdata()),[(255,0,0),(0,255,0)])

    def test_update_trial_defers_overlay_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            (base/'lock').touch()
            (base/'transaction.json').write_text('{"state":"trial"}')
            with self.assertRaises(BlockingIOError):deployment_guard(base)
            (base/'transaction.json').write_text('{"state":"committed"}')
            lock=deployment_guard(base)
            self.assertIsNotNone(lock)
            lock.close()
