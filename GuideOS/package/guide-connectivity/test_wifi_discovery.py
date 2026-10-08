import unittest
from unittest.mock import patch
from guide_wifi_discovery import Discovery, NM, BASE, network_row, summarize


class DiscoveryTests(unittest.TestCase):
    def row(self, **changes):
        p = dict(Ssid=b'Example', Strength=60, Flags=1, WpaFlags=0, RsnFlags=0x100)
        p.update(changes)
        return network_row(p)

    def test_security_labels(self):
        self.assertEqual(self.row()['security'], 'WPA2')
        self.assertEqual(self.row(RsnFlags=0x500)['security'], 'WPA2/3')
        self.assertEqual(self.row(RsnFlags=0x400)['security'], 'WPA3')
        self.assertEqual(self.row(RsnFlags=0x200)['security'], 'Enterprise')
        self.assertEqual(self.row(RsnFlags=0, Flags=0)['security'], 'Open')
        self.assertEqual(self.row(RsnFlags=0)['security'], 'Legacy secured')

    def test_names_and_signal(self):
        self.assertEqual(self.row(Ssid=b'')['ssid'], '(hidden network)')
        self.assertEqual(self.row(Ssid=b'a\nb')['ssid'], 'a?b')
        self.assertEqual(self.row(Strength=255)['signal'], 100)

    def test_duplicate_access_points_keep_strongest_and_distinct_security(self):
        rows = summarize([self.row(Strength=10), self.row(Strength=80), self.row(RsnFlags=0, Flags=0)])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['signal'], 80)

    def test_absent_off_and_blocked_do_not_request_scan(self):
        adapter = Discovery.__new__(Discovery)
        for radio, hardware, expected in [(False, True, 'off'), (True, False, 'blocked'), (True, True, 'no-adapter')]:
            adapter.props = lambda *_: dict(WirelessEnabled=radio, WirelessHardwareEnabled=hardware)
            adapter.call = lambda path, interface, method: [] if method == 'GetDevices' else self.fail('Unexpected mutation')
            self.assertEqual(adapter.scan()['state'], expected)

    def test_completed_scan_and_cached_failure_are_distinct(self):
        class BusError(Exception):
            pass
        class DBus:
            DBusException = BusError
            Dictionary = staticmethod(lambda value, **_: value)
        adapter = Discovery.__new__(Discovery)
        adapter.dbus = DBus
        scan_number = 10
        denied = False
        def props(path, interface):
            if path == BASE:
                return dict(WirelessEnabled=True, WirelessHardwareEnabled=True)
            if interface == NM + '.Device':
                return dict(DeviceType=2)
            if interface == NM + '.Device.Wireless':
                return dict(LastScan=scan_number)
            return dict(Ssid=b'Example', Strength=70, Flags=1, WpaFlags=0, RsnFlags=0x100)
        def call(path, interface, method, *args):
            nonlocal scan_number
            if method == 'GetDevices':
                return ['/device']
            if method == 'RequestScan':
                if denied:
                    raise BusError()
                scan_number += 1
                return None
            if method == 'GetAllAccessPoints':
                return ['/ap']
            self.fail('Unexpected operation: ' + method)
        adapter.props, adapter.call = props, call
        self.assertEqual(adapter.scan()['state'], 'ready')
        denied = True
        result = adapter.scan()
        self.assertEqual(result['state'], 'cached')
        self.assertEqual(result['networks'][0]['ssid'], 'Example')


if __name__ == '__main__':
    unittest.main()
