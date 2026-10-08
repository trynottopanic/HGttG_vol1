"""Observation failure is distinct from confirmed pinned-output removal."""
import time,threading,unittest
from concurrent.futures import Future,ThreadPoolExecutor
from unittest.mock import Mock,patch
from audio_service import Service,read_inventory

class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.service=Service.__new__(Service);s=self.service
        s.outputs=[{'id':'speaker'}];s.selected='speaker';s.track='song';s.position=0
        s.player=Mock(state='playing',position=12);s.monitor=Mock();s.audio_test=Mock(active=False)
        s.inventory_state='ready';s.inventory_observed=time.monotonic();s.inventory_job=None;s.bluetooth=Mock()
    def complete(self,value=None,error=None):
        f=Future()
        if error:f.set_exception(error)
        else:f.set_result(value)
        self.service.inventory_job=f;self.service.reconcile_inventory()
    def test_timeout_keeps_last_output_without_stopping_playback(self):
        observed=self.service.inventory_observed
        self.complete(error=TimeoutError())
        self.assertEqual(self.service.outputs,[{'id':'speaker'}]);self.assertEqual(self.service.inventory_state,'unknown')
        self.assertEqual(self.service.inventory_observed,observed)
        self.service.player.pause.assert_not_called();self.service.player.stop_pipeline.assert_not_called()
        self.service.monitor.inventory.assert_not_called()
    def test_confirmed_removal_pauses_pinned_playback(self):
        self.complete([])
        self.assertEqual(self.service.outputs,[]);self.assertEqual(self.service.inventory_state,'ready')
        self.service.player.pause.assert_called_once();self.service.player.stop_pipeline.assert_called_once()
    def test_slow_inventory_is_coalesced_and_does_not_block_owner(self):
        gate=threading.Event();entered=threading.Event();s=self.service
        s.inventory_worker=ThreadPoolExecutor(max_workers=1)
        def inventory():entered.set();gate.wait(1);return []
        try:
            with patch('audio_service.read_inventory',side_effect=inventory) as work:
                start=time.monotonic();s.refresh();self.assertLess(time.monotonic()-start,.1)
                self.assertTrue(entered.wait(.5));job=s.inventory_job
                for _ in range(20):s.refresh();s.reconcile_inventory()
                self.assertIs(s.inventory_job,job);self.assertEqual(work.call_count,1)
                s.player.pause.assert_not_called()
        finally:gate.set();s.inventory_worker.shutdown()
    def test_unknown_inventory_rejects_new_play_without_taking_lease(self):
        s=self.service;s.inventory_state='unknown';s.playback_lease=Mock();s.notice='';s.next_refresh=5
        with self.assertRaisesRegex(ValueError,'being checked'):s.command({'action':'play','id':'song'})
        s.playback_lease.acquire.assert_not_called()

class BluetoothInventoryTests(unittest.TestCase):
    def setUp(self):
        from audio_bluetooth import Bluetooth
        b=self.bluetooth=Bluetooth.__new__(Bluetooth)
        b.inventory_pending=False;b.inventory_generation=0;b.closed=False;b.registering=False;b.registered=True
        b.adapters=['known'];b.devices=[{'id':'known'}];b.adapter_state=[];b.last_error=None;b.last_inventory=None
        b.message='idle';b.interface=Mock();b.failed=Mock();b.cancel=Mock()
    def test_async_inventory_coalesces_and_preserves_rows_on_failure(self):
        b=self.bluetooth;b.refresh();b.refresh()
        call=b.interface.return_value.GetManagedObjects
        self.assertEqual(call.call_count,1);kwargs=call.call_args.kwargs
        self.assertIn('reply_handler',kwargs);self.assertIn('error_handler',kwargs)
        error=Mock();error.get_dbus_name.return_value='org.bluez.Error.Failed';kwargs['error_handler'](error)
        self.assertEqual(b.adapters,['known']);self.assertEqual(b.devices,[{'id':'known'}]);self.assertFalse(b.inventory_pending)
    def test_callback_after_close_cannot_reintroduce_devices(self):
        b=self.bluetooth;b.refresh();reply=b.interface.return_value.GetManagedObjects.call_args.kwargs['reply_handler']
        b.close();reply({'/new':{'org.bluez.Adapter1':{'Powered':True}}})
        self.assertEqual(b.adapters,['known']);b.cancel.assert_called_once()

if __name__=='__main__':unittest.main()
