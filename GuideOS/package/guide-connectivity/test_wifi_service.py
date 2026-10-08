import json
import io
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import guide_wifi_service as wifi


class Clock:
    now = 0
    def __call__(self):
        return self.now


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = Clock()
        self.backend = Mock()
        self.backend.device = '/device/1'
        self.backend.profiles = {'a' * 24: dict(path='/profile/1')}
        self.backend.aps = {'a' * 24: {}}
        self.backend.start.return_value = dict(active='/active/1', fresh=False, profile='/profile/1', id='a' * 24)
        self.backend.progress.return_value = 'waiting'
        self.backend.scan_finished.return_value = False
        self.backend.refresh.return_value = dict(state='ready', message='Not connected', connected=None, networks=[])
        self.controller = wifi.Controller(self.backend, Path(self.tmp.name) / 'policy.json', self.clock)
        self.controller.refresh()

    def connect(self):
        self.controller.command(dict(action='connect', id='a' * 24))

    def boot_controller(self):
        self.backend.profiles['a'*24]['saved']=True
        return wifi.Controller(self.backend,self.controller.policy_path,self.clock,
                               boot_marker=Path(self.tmp.name)/'boot-marker')

    def test_boot_reconnect_once_without_waiting_five_minutes(self):
        controller=self.boot_controller();controller.tick()
        self.backend.request_scan.assert_called_once()
        self.assertTrue(controller.scan['auto'])
        recreated=self.boot_controller();recreated.tick()
        self.backend.request_scan.assert_called_once()
        self.assertEqual(recreated.next_auto,300)

    def test_boot_scan_connects_saved_network_without_password_request(self):
        controller=self.boot_controller();controller.tick()
        self.backend.scan_finished.return_value=True
        self.backend.refresh.return_value['networks']=[dict(id='a'*24,saved=True,available=True,supported=True)]
        self.clock.now=1;controller.tick()
        self.assertEqual(self.backend.start.call_args.args[:2],('a'*24,''))

    def test_boot_reconnect_respects_persisted_disconnect(self):
        self.controller.command(dict(action='disconnect'))
        self.boot_controller().tick()
        self.backend.request_scan.assert_not_called()

    def test_boot_waits_for_device_and_skips_unsaved_profiles(self):
        controller=self.boot_controller();self.backend.device=None;controller.tick()
        self.backend.request_scan.assert_not_called()
        self.backend.device='/device/1';self.backend.profiles['a'*24]['saved']=False
        self.clock.now=10;controller.tick()
        self.backend.request_scan.assert_not_called()

    def test_manual_scan_consumes_boot_exception(self):
        controller=self.boot_controller();controller.command(dict(action='scan'))
        self.assertIsNone(controller.boot_marker)
        self.assertEqual(controller.next_auto,300)

    def test_missing_adapter_scan_keeps_specific_failure_and_skips_scan_call(self):
        self.backend.refresh.return_value = dict(state='no-adapter', message='No Wi-Fi adapter detected.', connected=None, networks=[])
        self.controller.command(dict(action='scan', token='a'*32))
        self.backend.request_scan.assert_not_called()
        self.assertEqual(self.controller.result, 'no-adapter')
        self.assertFalse(self.controller.snapshot()['busy'])
        self.assertEqual(self.controller.snapshot()['token'], 'a'*32)
        self.assertIn('did not initialize', self.controller.snapshot()['message'])

    def test_no_background_scan_before_five_minutes(self):
        for value in (0, 100, 299.999):
            self.clock.now = value
            self.controller.tick()
        self.backend.request_scan.assert_not_called()
        self.clock.now = 300
        self.controller.tick()
        self.backend.request_scan.assert_called_once()

    def test_manual_disconnect_survives_restart_and_time(self):
        self.controller.command(dict(action='disconnect'))
        recreated = wifi.Controller(self.backend, self.controller.policy_path, self.clock)
        self.assertTrue(recreated.hold)
        self.clock.now = 9000
        recreated.tick()
        self.backend.request_scan.assert_not_called()
        self.controller.command(dict(action='connect', id='a' * 24))
        self.assertFalse(json.loads(self.controller.policy_path.read_text())['hold'])

    def test_restart_never_bypasses_floor(self):
        self.clock.now = 1000
        other = wifi.Controller(self.backend, self.controller.policy_path, self.clock)
        self.assertEqual(other.next_auto, 1300)

    def test_connected_network_is_not_replaced_by_background(self):
        self.backend.refresh.return_value['connected'] = 'a' * 24
        self.clock.now = 1000
        self.controller.tick()
        self.backend.request_scan.assert_not_called()
        self.backend.start.assert_not_called()

    def test_absent_network_backs_off_and_never_connects(self):
        self.clock.now = 300
        self.controller.tick()
        self.backend.scan_finished.return_value = True
        self.clock.now = 301
        self.controller.tick()
        self.assertEqual(self.controller.next_auto, 901)
        self.backend.start.assert_not_called()

    def test_saved_visible_network_reconnects_without_password(self):
        self.backend.refresh.return_value['networks'] = [dict(id='a'*24, saved=True, available=True, supported=True)]
        self.clock.now = 300
        self.controller.tick()
        self.backend.scan_finished.return_value = True
        self.clock.now = 301
        self.controller.tick()
        self.backend.start.assert_called_once_with('a' * 24, '', 331)

    def test_switch_timeout_cancels_instead_of_late_success(self):
        self.controller.state['connected'] = 'b' * 24
        self.connect()
        self.assertLess(self.controller.deadline, 5)
        self.clock.now = 3.8
        self.backend.progress.return_value = 'connected'
        self.controller.tick()
        self.backend.cancel.assert_called_once()
        self.backend.save.assert_not_called()
        self.assertIsNone(self.controller.attempt)
        self.assertIn('timed out', self.controller.message)

    def test_success_saves_only_after_ip_ready(self):
        self.connect()
        self.controller.tick()
        self.backend.save.assert_not_called()
        self.backend.progress.return_value = 'connected'
        self.controller.tick()
        self.backend.save.assert_called_once()
        self.assertEqual(self.controller.result, 'connected')

    def test_failed_save_is_visible_not_false_saved(self):
        self.connect()
        self.backend.progress.return_value = 'connected'
        self.backend.save.side_effect = OSError('disk full')
        self.controller.tick()
        self.assertEqual(self.controller.result, 'not-saved')

    def test_cancel_holds_reconnect_and_retries_cleanup(self):
        self.connect()
        self.backend.cancel.side_effect = [OSError('busy'), None]
        self.controller.command(dict(action='cancel'))
        self.assertTrue(self.controller.hold)
        self.assertEqual(self.controller.result, 'cleanup-pending')
        self.clock.now = .5
        self.controller.tick()
        self.assertFalse(hasattr(self.controller, 'cleanup_attempt'))
        self.assertEqual(self.backend.cancel.call_count, 2)

    def test_password_never_enters_status_or_policy(self):
        self.controller.command(dict(action='connect', id='a' * 24, password='test-secret-123'))
        self.assertNotIn('test-secret-123', json.dumps(self.controller.snapshot()))
        self.assertNotIn('test-secret-123', self.controller.policy_path.read_text())
        self.assertEqual(self.controller.policy_path.stat().st_mode & 0o777, 0o600)

    def test_manual_scan_postpones_background(self):
        self.clock.now = 298
        self.controller.command(dict(action='scan'))
        self.assertGreaterEqual(self.controller.next_auto, 598)

    def test_forget_current_network_disables_reconnect(self):
        self.controller.state['connected'] = 'a' * 24
        self.controller.command(dict(action='forget', id='a' * 24))
        self.backend.cancel.assert_called_once()
        self.backend.forget.assert_called_once_with('a' * 24)
        self.assertTrue(self.controller.hold)

    def test_corrupt_policy_fails_to_manual_hold(self):
        self.controller.policy_path.write_text('broken')
        self.assertTrue(wifi.Controller(self.backend, self.controller.policy_path, self.clock).hold)

    def test_radio_loss_cannot_connect_unavailable_saved_network(self):
        self.controller.command(dict(action='connect', id='c' * 24))
        self.backend.start.assert_not_called()
        self.assertEqual(self.controller.result, 'unavailable')

    def test_disconnect_still_works_when_policy_disk_is_full(self):
        with patch.object(wifi, 'atomic_json', side_effect=OSError('full')):
            self.controller.command(dict(action='disconnect'))
        self.backend.cancel.assert_called_once()
        self.assertTrue(self.controller.hold)
        self.assertEqual(self.controller.result, 'not-saved')

    def test_link_loss_clears_stale_success_message(self):
        self.controller.state = dict(self.controller.state, connected='a'*24)
        self.controller.message = 'Connected and saved. Internet not checked.'
        self.controller.refresh()
        self.assertIn('Connection lost', self.controller.message)

    def test_queued_switch_uses_click_time_not_receipt_time(self):
        self.controller.state['connected'] = 'b'*24
        self.clock.now = 4
        self.controller.command(dict(action='connect', id='a'*24, requested_at=0))
        self.backend.start.assert_not_called()
        self.assertEqual(self.controller.result, 'timeout')

    def test_repeated_reconnect_does_not_rewrite_unchanged_policy(self):
        self.controller.set_hold(False)
        with patch.object(wifi, 'atomic_json') as write:
            self.controller.set_hold(False)
            write.assert_not_called()

    def test_changed_access_point_is_rejected_before_profile_creation(self):
        backend = wifi.Backend.__new__(wifi.Backend)
        backend.aps = {'a'*24: dict(path='/ap/1', ssid=b'Chosen', kind='wpa-psk')}
        backend.props = Mock(return_value=dict(Ssid=b'Different', Flags=1, RsnFlags=0x100))
        backend.call = Mock()
        with self.assertRaises(ValueError):
            backend.start('a'*24, 'not-a-real-secret', 100)
        backend.call.assert_not_called()

    def test_slow_progress_observation_retries_without_authentication_restart(self):
        self.connect()
        attempt = self.controller.attempt
        self.backend.progress.side_effect = [BusError('org.freedesktop.DBus.Error.NoReply'), 'connected']
        self.clock.now = .6
        self.controller.tick()
        self.assertIs(self.controller.attempt, attempt)
        self.backend.cancel.assert_not_called()
        self.backend.start.assert_called_once()
        self.clock.now = 1.3
        self.controller.tick()
        self.assertEqual(self.controller.result, 'connected')
        self.backend.save.assert_called_once_with(attempt, 30)

    def test_progress_timeouts_never_extend_switch_deadline(self):
        self.controller.state['connected'] = 'b' * 24
        self.connect()
        self.backend.progress.side_effect = TimeoutError()
        self.clock.now = 3.5
        self.controller.tick()
        self.assertEqual(self.controller.deadline, 3.6)
        self.clock.now = 3.6
        self.controller.tick()
        self.backend.cancel.assert_called_once()
        self.backend.save.assert_not_called()

    def test_uncertain_start_keeps_cleanup_transaction_and_manual_hold(self):
        attempt = dict(active=None, profile='/profile/new', fresh=True, id='a' * 24, uncertain=True)
        self.backend.start.side_effect = wifi.ActivationError(attempt, TimeoutError())
        self.backend.cancel.side_effect = [wifi.CleanupPending(), None]
        self.connect()
        self.assertIs(self.controller.cleanup_attempt, attempt)
        self.assertTrue(self.controller.hold)
        self.clock.now = .5
        self.controller.tick()
        self.assertEqual(self.controller.result, 'cancelled')
        self.assertTrue(self.controller.hold)
        self.backend.start.assert_called_once()

    def test_unconfirmed_cleanup_is_bounded_and_manual_disconnect_can_retry(self):
        self.connect()
        self.backend.cancel.side_effect = wifi.CleanupPending()
        self.controller.command(dict(action='cancel'))
        for now in (.1, .2, .4):
            self.clock.now = now
            self.controller.tick()
        self.assertEqual(self.backend.cancel.call_count, 1)
        self.clock.now = wifi.CLEANUP_WINDOW
        self.controller.tick()
        self.assertFalse(hasattr(self.controller, 'cleanup_attempt'))
        self.assertEqual(self.controller.result, 'cleanup-unconfirmed')
        self.assertTrue(self.controller.hold)
        self.controller.command(dict(action='connect', id='a' * 24))
        self.backend.start.assert_called_once()
        self.backend.cancel.side_effect = None
        self.controller.command(dict(action='disconnect'))
        self.assertFalse(hasattr(self.controller, 'uncertain_attempt'))
        self.assertEqual(self.controller.result, 'cancelled')

    def test_explicit_disconnect_keeps_device_wide_scope_during_cleanup_retry(self):
        self.connect()
        attempt = self.controller.attempt
        self.backend.cancel.side_effect = [wifi.CleanupPending(), None]
        self.controller.command(dict(action='disconnect'))
        self.backend.cancel.assert_called_with(attempt, disconnect_all=True)
        self.clock.now = .5
        self.controller.tick()
        self.backend.cancel.assert_called_with(attempt, disconnect_all=True)
        self.assertEqual(self.controller.result, 'cancelled')

    def test_shutdown_retries_pending_cleanup_once_without_extending_shutdown(self):
        self.connect()
        attempt = self.controller.attempt
        self.backend.cancel.side_effect = wifi.CleanupPending()
        self.controller.command(dict(action='disconnect'))
        self.backend.cancel.reset_mock()
        self.controller.stop()
        self.backend.cancel.assert_called_once_with(attempt, disconnect_all=True)
        self.assertTrue(self.controller.hold)

    def test_idle_provider_shutdown_preserves_completed_connection(self):
        self.controller.state['connected'] = 'a' * 24
        self.controller.stop()
        self.backend.cancel.assert_not_called()

    def test_diagnostics_include_safe_state_reason_but_no_exception_body(self):
        self.backend.diagnostic = dict(device_state=50, device_reason=39, active_state=1,
                                       ssid='private-network', password='private-password')
        output = io.StringIO()
        with redirect_stdout(output):
            self.controller.diagnose(BusError('org.freedesktop.DBus.Error.NoReply',
                                             'private-password private-network'))
            self.controller.diagnose(BusError('private-password'))
        entries = [json.loads(line[len('GUIDE_WIFI '):]) for line in output.getvalue().splitlines()]
        self.assertEqual(entries[0]['device_state'], 50)
        self.assertEqual(entries[0]['device_reason'], 39)
        self.assertEqual(entries[1]['dbus_error'], 'org.freedesktop.DBus.Error.NoReply')
        self.assertEqual(entries[2]['dbus_error'], '')
        self.assertNotIn('private-password', output.getvalue())
        self.assertNotIn('private-network', output.getvalue())


class BusError(Exception):
    def __init__(self, name, message='Fixture error'):
        super().__init__(message)
        self.name = name

    def get_dbus_name(self):
        return self.name


def backend_fixture():
    backend = wifi.Backend.__new__(wifi.Backend)
    backend.until = 100
    backend.device = '/device/1'
    backend.aps = {'a' * 24: dict(path='/ap/1', ssid=b'Fixture', kind='wpa-psk')}
    backend.profiles = {}
    backend.active = None
    backend.diagnostic = {}
    backend.dbus = SimpleNamespace(Boolean=bool, UInt32=int, ByteArray=bytes, ObjectPath=str,
                                   Dictionary=lambda value, **kwargs: value,
                                   Array=lambda value, **kwargs: value)
    return backend


class BackendRegressionTests(unittest.TestCase):
    def test_reply_taking_six_tenths_is_allowed_within_initial_deadline(self):
        backend = backend_fixture()
        proxy = Mock()
        def reply(**kwargs):
            if kwargs['timeout'] < .6:
                raise BusError('org.freedesktop.DBus.Error.NoReply')
            return 'reply'
        proxy.Method.side_effect = reply
        backend.bus = Mock()
        backend.dbus.Interface = Mock(return_value=proxy)
        with patch.object(wifi.time, 'monotonic', return_value=70):
            self.assertEqual(backend.call('/object', 'interface', 'Method'), 'reply')
        self.assertEqual(proxy.Method.call_args.kwargs['timeout'], 2)
        with patch.object(wifi.time, 'monotonic', return_value=99.8):
            with self.assertRaises(BusError):
                backend.call('/object', 'interface', 'Method')
        self.assertLessEqual(proxy.Method.call_args.kwargs['timeout'], .201)

    def test_active_access_point_is_not_connection_success(self):
        for device_state, active_state, addresses, expected in (
                (40, 1, [], False), (70, 1, [], False),
                (100, 1, [], False), (100, 2, [], False),
                (100, 2, [dict(address='192.0.2.2', prefix=24)], True)):
            with self.subTest(device_state=device_state, active_state=active_state, addresses=addresses):
                backend = backend_fixture()
                def properties(path, interface):
                    if path == wifi.BASE:
                        return dict(WirelessEnabled=True, WirelessHardwareEnabled=True)
                    if path == '/device/1' and interface == wifi.NM + '.Device':
                        return dict(DeviceType=2, State=device_state, StateReason=(device_state, 0),
                                    ActiveConnection='/active/1')
                    if path == '/device/1':
                        return dict(ActiveAccessPoint='/ap/1')
                    if path == '/active/1':
                        return dict(State=active_state, Connection='/profile/1', Ip4Config='/ip4/1')
                    if path == '/ip4/1':
                        return dict(AddressData=addresses)
                    if path == '/ap/1':
                        return dict(Ssid=b'Fixture', Flags=1, RsnFlags=0x100, WpaFlags=0,
                                    Strength=80, LastSeen=100)
                    raise AssertionError('Unexpected property path')
                backend.props = Mock(side_effect=properties)
                backend.call = Mock(side_effect=lambda path, interface, method, *args:
                                    {'GetDevices': ['/device/1'], 'ListConnections': [],
                                     'GetAllAccessPoints': ['/ap/1']}[method])
                with patch.object(wifi.time, 'clock_gettime', return_value=100, create=True), \
                     patch.object(wifi.time, 'CLOCK_BOOTTIME', 7, create=True):
                    state = backend.refresh()
                self.assertEqual(bool(state['connected']), expected)
                self.assertEqual(state['networks'][0]['active'], expected)
                self.assertEqual(backend.diagnostic['device_state'], device_state)

    def test_profile_creation_timeout_preserves_uuid_for_cleanup_without_secret(self):
        backend = backend_fixture()
        backend.props = Mock(return_value=dict(Ssid=b'Fixture', Flags=1, RsnFlags=0x100))
        backend.call = Mock(side_effect=BusError('org.freedesktop.DBus.Error.NoReply'))
        with self.assertRaises(wifi.ActivationError) as caught:
            backend.start('a' * 24, 'fixture-password', 100)
        attempt = caught.exception.attempt
        self.assertTrue(attempt['uncertain'])
        self.assertIsNone(attempt['profile'])
        self.assertTrue(attempt['uuid'])
        self.assertNotIn('fixture-password', repr(attempt))
        backend.call = Mock(side_effect=lambda path, interface, method, *args:
                            '/profile/new' if method == 'GetConnectionByUuid' else None)
        backend.props = Mock(side_effect=lambda path, interface:
                             dict(ActiveConnections=[]) if path == wifi.BASE else
                             dict(State=30, StateReason=(30, 0), ActiveConnection='/'))
        backend.cancel(attempt)
        self.assertEqual(attempt['profile'], '/profile/new')
        self.assertFalse(attempt['uncertain'])
        self.assertEqual([call.args[2] for call in backend.call.call_args_list],
                         ['GetConnectionByUuid', 'Delete'])

    def test_missing_profile_after_uncertain_creation_is_not_false_cleanup_success(self):
        backend = backend_fixture()
        backend.call = Mock(side_effect=BusError(wifi.NM + '.Settings.InvalidConnection'))
        attempt = dict(profile=None, uuid='fixture-uuid', fresh=True, uncertain=True)
        with self.assertRaises(wifi.CleanupPending):
            backend.cancel(attempt)

    def test_uncertain_saved_activation_is_deactivated_without_deleting_credentials(self):
        backend = backend_fixture()
        backend.profiles = {'a' * 24: dict(path='/profile/saved', saved=True, uuid='fixture-uuid')}
        backend.props = Mock(return_value=dict(Ssid=b'Fixture', Flags=1, RsnFlags=0x100))
        backend.call = Mock(side_effect=BusError('org.freedesktop.DBus.Error.NoReply'))
        with self.assertRaises(wifi.ActivationError) as caught:
            backend.start('a' * 24, '', 100)
        attempt = caught.exception.attempt
        self.assertFalse(attempt['fresh'])
        backend.props = Mock(side_effect=lambda path, interface:
                             dict(ActiveConnections=['/active/1']) if path == wifi.BASE else
                             dict(Connection='/profile/saved', State=1) if path == '/active/1' else
                             dict(State=30, StateReason=(30, 39), ActiveConnection='/'))
        backend.call = Mock()
        backend.cancel(attempt)
        self.assertEqual([call.args[2] for call in backend.call.call_args_list], ['DeactivateConnection'])
        self.assertTrue(attempt['observed_activation'])

    def test_cleanup_waits_for_device_deactivation_not_method_acknowledgment(self):
        backend = backend_fixture()
        backend.props = Mock(side_effect=lambda path, interface:
                             dict(State=3) if path == '/active/1' else
                             dict(State=110, StateReason=(110, 39), ActiveConnection='/active/1'))
        backend.call = Mock()
        with self.assertRaises(wifi.CleanupPending):
            backend.cancel()
        self.assertEqual(backend.call.call_args.args[2], 'Disconnect')

    def test_cleanup_is_idempotent_when_a_temporary_profile_is_already_removed(self):
        for name in wifi.MISSING_OBJECT_ERRORS:
            with self.subTest(name=name):
                backend = backend_fixture()
                backend.props = Mock(side_effect=lambda path, interface:
                                     dict(ActiveConnections=[]) if path == wifi.BASE else
                                     dict(State=30, StateReason=(30, 0), ActiveConnection='/'))
                backend.call = Mock(side_effect=BusError(name))
                attempt = dict(active='/active/old', profile='/profile/removed', fresh=True, uncertain=True)
                backend.cancel(attempt)
                self.assertFalse(attempt['uncertain'])

    def test_uncertain_saved_attempt_does_not_disconnect_another_profile(self):
        backend = backend_fixture()
        backend.props = Mock(side_effect=lambda path, interface:
                             dict(ActiveConnections=['/active/other']) if path == wifi.BASE else
                             dict(Connection='/profile/other', State=2))
        backend.call = Mock()
        attempt = dict(active=None, profile='/profile/saved', fresh=False, uncertain=True)
        with self.assertRaises(wifi.CleanupPending):
            backend.cancel(attempt)
        backend.call.assert_not_called()

    def test_disconnect_all_removes_pending_profile_and_stops_another_active_link(self):
        for disconnect_all in (False, True):
            with self.subTest(disconnect_all=disconnect_all):
                backend = backend_fixture()
                disconnected = False
                def properties(path, interface):
                    if path == wifi.BASE:
                        return dict(ActiveConnections=['/active/other'])
                    if path == '/active/other':
                        return dict(Connection='/profile/other', State=2)
                    return dict(State=30 if disconnected else 100, StateReason=(30, 0),
                                ActiveConnection='/' if disconnected else '/active/other')
                def call(path, interface, method, *args):
                    nonlocal disconnected
                    if method == 'Disconnect':
                        disconnected = True
                backend.props = Mock(side_effect=properties)
                backend.call = Mock(side_effect=call)
                attempt = dict(active=None, profile='/profile/pending', fresh=True, uncertain=False)
                backend.cancel(attempt, disconnect_all=disconnect_all)
                self.assertEqual(disconnected, disconnect_all)
                methods = [call.args[2] for call in backend.call.call_args_list]
                self.assertEqual(methods, ['Disconnect', 'Delete'] if disconnect_all else ['Delete'])

    def test_disappeared_activation_does_not_prevent_temporary_profile_cleanup(self):
        backend = backend_fixture()
        backend.props = Mock(side_effect=lambda path, interface:
                             dict(ActiveConnections=['/active/1']) if path == wifi.BASE else
                             dict(Connection='/profile/new', State=1) if path == '/active/1' else
                             dict(State=30, StateReason=(30, 0), ActiveConnection='/'))
        backend.call = Mock(side_effect=[BusError(wifi.NM + '.ConnectionNotActive'), None])
        attempt = dict(active='/active/1', profile='/profile/new', fresh=True, uncertain=False)
        backend.cancel(attempt)
        self.assertEqual([call.args[2] for call in backend.call.call_args_list],
                         ['DeactivateConnection', 'Delete'])

    def test_save_uses_remaining_connection_deadline(self):
        backend = backend_fixture()
        backend.call = Mock()
        with patch.object(wifi.time, 'monotonic', return_value=10):
            backend.save(dict(fresh=True, profile='/profile/new'), deadline=10.6)
        self.assertEqual(backend.until, 10.6)
        self.assertEqual(backend.call.call_args.args[2], 'Save')

    def test_failure_state_reason_survives_active_object_disappearance(self):
        backend = backend_fixture()
        backend.props = Mock(side_effect=[dict(State=120, StateReason=(120, 7)),
                                         BusError('org.freedesktop.DBus.Error.UnknownObject')])
        with self.assertRaises(BusError):
            backend.progress(dict(active='/active/old'), 100)
        self.assertEqual(backend.diagnostic, dict(device_state=120, device_reason=7))


class IdentityTests(unittest.TestCase):
    def test_raw_ssid_and_security_are_separate_identities(self):
        self.assertNotEqual(wifi.network_id(b'bad\xff', 'open'), wifi.network_id(b'bad\xfe', 'open'))
        self.assertNotEqual(wifi.network_id(b'name', 'open'), wifi.network_id(b'name', 'wpa-psk'))

    def test_no_enterprise_or_legacy_downgrade_to_open(self):
        self.assertEqual(wifi.security_kind(dict(Flags=1, RsnFlags=0x200)), 'unsupported')
        self.assertEqual(wifi.security_kind(dict(Flags=1, WpaFlags=0x100)), 'unsupported')
        self.assertEqual(wifi.security_kind(dict(Flags=1, RsnFlags=0x100)), 'wpa-psk')
        self.assertEqual(wifi.security_kind(dict(Flags=1, RsnFlags=0x400)), 'sae')
        self.assertEqual(wifi.security_kind(dict(Flags=0)), 'open')


if __name__ == '__main__':
    unittest.main()
