import unittest
from unittest.mock import Mock, patch
import dbus
from audio_bluetooth import Bluetooth, Agent, Rejected


class BluetoothTests(unittest.TestCase):
    def bare(self):
        bt = Bluetooth.__new__(Bluetooth)
        bt.pending, bt.generation, bt.scan_adapter = None, 0, None
        bt.registered = True
        bt.adapters, bt.devices = [], []
        bt.adapter_state=[];bt.last_inventory=None;bt.last_error=None;bt.message='Bluetooth idle'
        bt.inventory_pending=False;bt.inventory_generation=0;bt.closed=False;bt.registering=False
        bt.deadline=0;bt.scan_deadline=0
        bt.interface = Mock()
        managed=bt.interface.return_value.GetManagedObjects
        managed.side_effect=lambda *args,**kwargs:kwargs['reply_handler'](managed.return_value)
        bt.interface.return_value.RegisterAgent.side_effect=lambda *args,**kwargs:kwargs['reply_handler']()
        return bt

    def test_absent_controller_has_visible_error(self):
        bt = self.bare()
        bt.interface.return_value.GetManagedObjects.return_value = {}
        with self.assertRaisesRegex(ValueError, 'controller unavailable'):
            bt.scan()
        self.assertIn('No Bluetooth controller', bt.message)

    def test_empty_scan_result_and_stop_failure_are_distinct(self):
        bt = self.bare()
        bt.scan_adapter, bt.scan_deadline = '/adapter', 0
        bt.interface.return_value.GetManagedObjects.return_value = {
            '/adapter': {'org.bluez.Adapter1': {'Powered': True}}}
        bt.tick()
        self.assertIn('No devices found', bt.message)
        bt.scan_adapter = '/adapter'
        error = dbus.DBusException('private address', name='org.bluez.Error.NotReady')
        bt.interface.return_value.StopDiscovery.side_effect = error
        bt.tick()
        self.assertIn('not ready', bt.message)
        self.assertNotIn('private', bt.message)

    def test_synchronous_pair_failure_clears_busy_and_records_reason(self):
        bt = self.bare()
        bt.devices = [dict(id='/dev/test', paired=False)]
        bt.interface.return_value.Pair.side_effect = dbus.DBusException(
            'private address', name='org.freedesktop.DBus.Error.AccessDenied')
        with patch('audio_errors.emit') as event:
            bt.connect('/dev/test')
        self.assertIsNone(bt.pending)
        self.assertIn('permission denied', bt.message)
        self.assertEqual(event.call_args.kwargs['backend_error'],
                         'org.freedesktop.DBus.Error.AccessDenied')

    def test_cancelled_pairing_callback_cannot_connect(self):
        bt = Bluetooth.__new__(Bluetooth)
        bt.pending, bt.generation, bt.scan_adapter = None, 0, None
        bt.devices = [dict(id='/dev/test', paired=False)]
        interface = Mock()
        bt.interface = Mock(return_value=interface)
        bt.connect('/dev/test')
        callback = interface.Pair.call_args.kwargs['reply_handler']
        bt.cancel()
        callback()
        interface.ConnectProfile.assert_not_called()
        interface.CancelPairing.assert_called_once()

    def test_agent_rejects_unsolicited_pairing(self):
        agent = Agent.__new__(Agent)
        agent.owner = Mock(pending='/dev/selected')
        agent.RequestAuthorization('/dev/selected')
        with self.assertRaises(Rejected):
            agent.RequestAuthorization('/dev/unselected')

    def test_stale_device_cannot_be_connected(self):
        bt = Bluetooth.__new__(Bluetooth)
        bt.pending, bt.devices = None, []
        with self.assertRaises(ValueError):
            bt.connect('/dev/vanished')

    def test_registration_uses_declared_exported_agent_path(self):
        bt = self.bare()
        bt.registered = False
        manager = bt.interface.return_value
        manager.GetManagedObjects.return_value = {}
        bt.refresh()
        self.assertEqual(manager.RegisterAgent.call_args.args,('/org/guideos/audio/agent','NoInputNoOutput'))
        self.assertEqual(manager.RegisterAgent.call_args.kwargs['timeout'],2)
        self.assertEqual(manager.RegisterAgent.call_args.kwargs['signature'],'os')
        self.assertTrue(callable(manager.RegisterAgent.call_args.kwargs['reply_handler']))
        self.assertTrue(bt.registered)


if __name__ == '__main__':
    unittest.main()
