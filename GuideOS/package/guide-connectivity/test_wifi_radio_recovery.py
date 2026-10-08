import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
import guide_wifi_radio_recovery as recovery


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now
    def sleep(self, duration): self.now += duration


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.radio = Mock()
        self.radio.supported.return_value = True
        self.radio.interface_ready.return_value = False
        self.radio.target.return_value = Path('/radio/mmc2:0001:1')
        self.radio.bound.return_value = False
        self.radio.failed_probe.return_value = True
        self.radio.retry.return_value = True
        self.claim = Mock(return_value=True)

    def run_recovery(self):
        return recovery.recover(self.radio, self.claim, self.clock, self.clock.sleep)

    def test_working_radio_is_untouched(self):
        self.radio.interface_ready.return_value = True
        self.assertEqual(self.run_recovery(), 'already-ready')
        self.radio.retry.assert_not_called(); self.claim.assert_not_called()

    def test_bound_radio_without_interface_is_untouched(self):
        self.radio.bound.return_value = True
        self.assertEqual(self.run_recovery(), 'already-bound')
        self.radio.retry.assert_not_called()
        self.assertEqual(self.clock.now, recovery.STARTUP_WAIT)

    def test_in_progress_probe_failure_is_not_mistaken_for_healthy_binding(self):
        self.radio.bound.side_effect = lambda _: self.clock.now < 1
        self.radio.retry.side_effect = OSError('probe timeout')
        self.assertEqual(self.run_recovery(), 'initialization-failed')
        self.assertEqual(self.radio.retry.call_count, 2)
        self.assertEqual(self.clock.now, 7)

    def test_no_recorded_probe_failure_is_not_guessed(self):
        self.radio.failed_probe.return_value = False
        self.assertEqual(self.run_recovery(), 'no-matching-probe-failure')
        self.assertEqual(self.clock.now, recovery.STARTUP_WAIT)
        self.radio.retry.assert_not_called()

    def test_successful_retry_stops_immediately(self):
        def bind(_):
            self.radio.bound.return_value = True
            return True
        self.radio.retry.side_effect = bind
        self.assertEqual(self.run_recovery(), 'recovered')
        self.radio.retry.assert_called_once()

    def test_failed_retries_are_bounded_and_not_repeated_on_restart(self):
        self.radio.retry.side_effect = OSError('probe timeout')
        self.assertEqual(self.run_recovery(), 'initialization-failed')
        self.assertEqual(self.radio.retry.call_count, 2)
        self.assertEqual(self.clock.now, 6)
        self.radio.retry.reset_mock(); self.claim.return_value = False
        self.assertEqual(self.run_recovery(), 'already-attempted-this-boot')
        self.radio.retry.assert_not_called()

    def test_changed_target_is_refused(self):
        self.radio.target.side_effect = [Path('/radio/mmc2:0001:1'), None]
        self.assertEqual(self.run_recovery(), 'target-changed')
        self.radio.retry.assert_not_called()

    def test_other_board_is_untouched(self):
        self.radio.supported.return_value = False
        self.assertEqual(self.run_recovery(), 'unsupported-board')
        self.radio.retry.assert_not_called()


class IdentityTests(unittest.TestCase):
    def test_exact_controller_vendor_and_device_required_for_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'class/net').mkdir(parents=True)
            actual = root/'devices/platform/soc/4021000.mmc/mmc_host/mmc2/mmc2:0001/mmc2:0001:1'
            actual.mkdir(parents=True)
            (actual/'vendor').write_text('0x024c'); (actual/'device').write_text('0xc821')
            devices = root/'bus/sdio/devices'; devices.mkdir(parents=True)
            link = devices/'mmc2:0001:1'; link.symlink_to(actual, target_is_directory=True)
            bind = root/'bus/sdio/drivers/rtw88_8821cs/bind'; bind.parent.mkdir(parents=True); bind.write_text('')
            radio = recovery.Radio(root)
            self.assertEqual(radio.target(), link)
            self.assertTrue(radio.retry(link)); self.assertEqual(bind.read_text(), link.name)
            bind.write_text(''); (actual/'device').write_text('0x1234')
            self.assertIsNone(radio.target()); self.assertFalse(radio.retry(link)); self.assertEqual(bind.read_text(), '')

    def test_new_interface_prevents_write_after_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'class/net/wlan0/wireless').mkdir(parents=True)
            radio = recovery.Radio(root)
            self.assertFalse(radio.retry(Path('/radio/mmc2:0001:1')))


if __name__ == '__main__': unittest.main()
