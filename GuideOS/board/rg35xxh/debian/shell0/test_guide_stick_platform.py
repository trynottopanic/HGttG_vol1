"""Linux evdev stick frames, ioctl state recovery and board normalization."""
import errno
import unittest
from unittest.mock import Mock, patch

import guide_platform_rg35xxh as platform


def bits(codes, size):
    result = bytearray(size)
    for code in codes:
        result[code // 8] |= 1 << (code % 8)
    return bytes(result)


def axis(value=0, low=-1800, high=1800, flat=32):
    return dict(value=value, minimum=low, maximum=high, fuzz=32, flat=flat, resolution=0)


def ioctl_state(values, keys=(), name='H700 Gamepad'):
    def read(_fd, number, size):
        if number == 6:
            return name.encode().ljust(size, b'\0')
        if number == 0x18:
            return bits(keys, size)
        if number == 0x23:
            return bits(values, size)
        code = number - 0x40
        if code in values:
            data = values[code]
            return platform.ABS_INFO.pack(*(data[k] for k in
                ('value', 'minimum', 'maximum', 'fuzz', 'flat', 'resolution')))
        raise OSError(errno.EINVAL, 'No such axis')
    return read


class StickPlatformTests(unittest.TestCase):
    def device(self, name='H700 Gamepad', values=None):
        device = platform.InputDevice.__new__(platform.InputDevice)
        device.path, device.fd, device.name = '/dev/input/fake', 10, name
        device.keys = {}
        device.axes = values if values is not None else {code: axis() for code in (0, 1, 3, 4)}
        device.pending_axes = {}
        device.connected, device.dropped, device.monotonic = True, False, True
        return device

    def deck(self, *devices):
        inputs = platform.DeckInputs.__new__(platform.DeckInputs)
        inputs.devices = list(devices)
        inputs.generation = 0
        inputs.event_log = Mock()
        return inputs

    def poll(self, inputs, rows):
        raw = b''.join(platform.EVENT.pack(123, index * 1000, *row)
                       for index, row in enumerate(rows))
        with patch.object(platform.select, 'select', return_value=([10], [], [])), \
                patch.object(platform.os, 'read', return_value=raw):
            return inputs.poll(0)

    def test_ioctl_open_reads_metadata_and_current_held_positions(self):
        values = {0: axis(900), 1: axis(-1800), 3: axis(0), 4: axis(450)}
        with patch.object(platform.os, 'open', return_value=10), \
                patch.object(platform, '_read_ioctl', side_effect=ioctl_state(values, keys=(318,))), \
                patch.object(platform.fcntl, 'ioctl') as ioctl:
            device = platform.InputDevice('/dev/input/fake')
        snapshot = self.deck(device).stick_snapshot()
        self.assertEqual(snapshot['left'], (.5, -1.0))
        self.assertEqual(snapshot['right'], (0.0, .25))
        self.assertTrue(snapshot['right_click'])
        self.assertEqual(device.axes[0]['flat'], 32)
        self.assertEqual(device.axes[0]['minimum'], -1800)
        self.assertEqual(device.axes[0]['maximum'], 1800)
        self.assertEqual(device.axes[0]['value'], 900)
        self.assertIn(unittest.mock.call(10, platform._ioc(1, 0x90, 4), 1), ioctl.call_args_list)

    def test_axis_updates_are_atomic_only_at_syn_report_across_reads(self):
        device = self.device()
        inputs = self.deck(device)
        self.assertEqual(self.poll(inputs, [(platform.EV_ABS, 0, 1800)]), [])
        self.assertEqual(inputs.stick_snapshot()['left'], (0.0, 0.0))
        events = self.poll(inputs, [(platform.EV_ABS, 1, 900),
                                   (platform.EV_KEY, 305, 1),
                                   (platform.EV_SYN, platform.SYN_REPORT, 0)])
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0], ('H700 Gamepad', platform.EV_KEY, 305, 1))
        self.assertEqual(events[1].sticks['left'], (1.0, .5))
        self.assertAlmostEqual(events[1].timestamp, 123.002)
        self.assertEqual(device.pending_axes, {})

    def test_fast_deflect_and_neutral_in_one_poll_preserve_each_frame(self):
        inputs = self.deck(self.device())
        events = self.poll(inputs, [(platform.EV_ABS, 0, 1800),
                                   (platform.EV_SYN, platform.SYN_REPORT, 0),
                                   (platform.EV_KEY, 305, 1),
                                   (platform.EV_ABS, 0, 0),
                                   (platform.EV_SYN, platform.SYN_REPORT, 0)])
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0].sticks['left'], (1.0, 0.0))
        self.assertEqual(events[1][1:], (platform.EV_KEY, 305, 1))
        self.assertEqual(events[2].sticks['left'], (0.0, 0.0))
        self.assertEqual(inputs.stick_snapshot()['left'], (0.0, 0.0))
        self.assertEqual(events[0].sticks['left'], (1.0, 0.0))

    def test_right_click_is_captured_in_frame_order(self):
        inputs = self.deck(self.device())
        events = self.poll(inputs, [(platform.EV_KEY, 318, 1),
                                   (platform.EV_ABS, 3, 1800),
                                   (platform.EV_SYN, platform.SYN_REPORT, 0),
                                   (platform.EV_KEY, 318, 0),
                                   (platform.EV_ABS, 3, 0),
                                   (platform.EV_SYN, platform.SYN_REPORT, 0)])
        frames = [event.sticks for event in events if hasattr(event, 'sticks')]
        self.assertEqual([(frame['right'], frame['right_click']) for frame in frames],
                         [((1.0, 0.0), True), ((0.0, 0.0), False)])

    def test_drop_discards_pending_axes_and_recovers_actual_ioctl_state(self):
        device = self.device()
        inputs = self.deck(device)
        recovered = {0: axis(-900), 1: axis(450), 3: axis(0), 4: axis(-1800)}
        with patch.object(platform, '_read_ioctl', side_effect=ioctl_state(recovered, keys=(318,))):
            events = self.poll(inputs, [(platform.EV_ABS, 0, 1800),
                                       (platform.EV_SYN, platform.SYN_DROPPED, 0),
                                       (platform.EV_ABS, 1, 1700),
                                       (platform.EV_KEY, 305, 1),
                                       (platform.EV_SYN, platform.SYN_REPORT, 0)])
        self.assertEqual(len(events), 2)
        self.assertIsNone(events[0].sticks['left'])
        self.assertIsNone(events[0].sticks['right'])
        self.assertEqual(events[0].sticks['generation'], 1)
        self.assertEqual(events[1].sticks['left'], (-.5, .25))
        self.assertEqual(events[1].sticks['right'], (0.0, -1.0))
        self.assertTrue(events[1].sticks['right_click'])
        self.assertEqual(device.pending_axes, {})
        self.assertFalse(device.dropped)
        self.assertNotIn(305, device.keys)

    def test_failed_resync_remains_unavailable_until_later_frame(self):
        device = self.device()
        inputs = self.deck(device)
        with patch.object(platform, '_read_ioctl', side_effect=OSError(errno.EIO, 'state unavailable')):
            events = self.poll(inputs, [(platform.EV_SYN, platform.SYN_DROPPED, 0),
                                       (platform.EV_SYN, platform.SYN_REPORT, 0)])
        self.assertEqual(len(events), 1)
        self.assertTrue(device.dropped)
        self.assertIsNone(inputs.stick_snapshot()['left'])
        with patch.object(platform, '_read_ioctl', side_effect=ioctl_state({0: axis(900), 1: axis()})):
            recovered = self.poll(inputs, [(platform.EV_SYN, platform.SYN_REPORT, 0)])
        self.assertEqual(recovered[0].sticks['left'], (.5, 0.0))
        self.assertIsNone(recovered[0].sticks['right'])

    def test_disconnect_invalidates_samples_and_changes_generation_once(self):
        device = self.device()
        inputs = self.deck(device)
        device.pending_axes[0] = 1800
        with patch.object(platform.select, 'select', return_value=([10], [], [])), \
                patch.object(platform.os, 'read', side_effect=OSError(errno.ENODEV, 'gone')):
            events = inputs.poll(0)
        self.assertFalse(device.connected)
        self.assertEqual(device.pending_axes, {})
        self.assertEqual(events[0].sticks['generation'], 1)
        self.assertIsNone(events[0].sticks['left'])
        with patch.object(platform.select, 'select', return_value=([], [], [])), \
                patch.object(platform.os, 'read') as read:
            self.assertEqual(inputs.poll(0), [])
            read.assert_not_called()
        self.assertEqual(inputs.generation, 1)

    def test_temporary_empty_queue_retains_last_complete_frame(self):
        device = self.device(values={0: axis(900), 1: axis(-900)})
        inputs = self.deck(device)
        with patch.object(platform.select, 'select', return_value=([10], [], [])), \
                patch.object(platform.os, 'read', side_effect=BlockingIOError(errno.EAGAIN, 'empty')):
            self.assertEqual(inputs.poll(0), [])
        self.assertTrue(device.connected)
        self.assertEqual(inputs.generation, 0)
        self.assertEqual(inputs.stick_snapshot()['left'], (.5, -.5))

    def test_normalization_uses_declared_midpoint_clamps_and_does_not_recenter(self):
        device = self.device(values={0: axis(25, 10, 30), 1: axis(15, 10, 30),
                                     3: axis(99, 10, 30), 4: axis(-99, 10, 30)})
        snapshot = self.deck(device).stick_snapshot()
        self.assertEqual(snapshot['left'], (.5, -.5))
        self.assertEqual(snapshot['right'], (1.0, -1.0))

    def test_missing_invalid_or_wrong_codes_are_unavailable_not_neutral(self):
        device = self.device(values={0: axis(), 2: axis(), 5: axis()})
        inputs = self.deck(device)
        self.assertIsNone(inputs.stick_snapshot()['left'])
        self.assertIsNone(inputs.stick_snapshot()['right'])
        device.axes[1] = axis(0, 0, 0)
        self.assertIsNone(inputs.stick_snapshot()['left'])
        device.axes[1] = axis(0, 1, -1)
        self.assertIsNone(inputs.stick_snapshot()['left'])
        device.axes[1] = axis(flat=-1)
        self.assertIsNone(inputs.stick_snapshot()['left'])
        device.axes[1] = axis()
        device.axes[0]['value'] = None
        self.assertIsNone(inputs.stick_snapshot()['left'])

    def test_duplicate_or_unrelated_devices_do_not_supply_invented_sticks(self):
        for devices in ((), (self.device('gpio-keys-volume'),), (self.device(), self.device())):
            with self.subTest(count=len(devices)):
                snapshot = self.deck(*devices).stick_snapshot()
                self.assertIsNone(snapshot['left'])
                self.assertIsNone(snapshot['right'])

    def test_key_events_preserve_existing_press_repeat_release_behavior(self):
        device = self.device()
        inputs = self.deck(device)
        events = self.poll(inputs, [(platform.EV_KEY, 305, 1), (platform.EV_KEY, 305, 2),
                                   (platform.EV_KEY, 305, 0),
                                   (platform.EV_SYN, platform.SYN_REPORT, 0)])
        self.assertEqual([event[3] for event in events], [1, 2, 0])
        self.assertFalse(any(hasattr(event, 'sticks') for event in events))
        self.assertFalse(device.keys[305])

    def test_keyboard_style_select_is_normalized_to_board_select(self):
        device = self.device()
        inputs = self.deck(device)
        events = self.poll(inputs, [(platform.EV_KEY, platform.KEY_SELECT, 1),
                                   (platform.EV_KEY, platform.KEY_SELECT, 0)])
        self.assertEqual([(event[2], event[3]) for event in events],
                         [(platform.BTN_SELECT, 1), (platform.BTN_SELECT, 0)])
        self.assertFalse(device.keys[platform.BTN_SELECT])
        self.assertNotIn(platform.KEY_SELECT, device.keys)

    def test_power_device_remains_excluded_before_any_grab(self):
        with patch.object(platform.os, 'open', return_value=10), \
                patch.object(platform.os, 'close') as close, \
                patch.object(platform, '_read_ioctl', side_effect=ioctl_state({}, name='axp20x-pek')), \
                patch.object(platform.fcntl, 'ioctl') as ioctl:
            with self.assertRaises(ValueError):
                platform.InputDevice('/dev/input/power')
        close.assert_called_once_with(10)
        ioctl.assert_not_called()


if __name__ == '__main__':
    unittest.main()
