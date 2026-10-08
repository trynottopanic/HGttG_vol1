#!/usr/bin/python3
"""Bounded Wi-Fi discovery through NetworkManager. Does not connect or save secrets."""
import json
import time

NM = 'org.freedesktop.NetworkManager'
BASE = '/org/freedesktop/NetworkManager'


def network_row(properties):
    ssid = bytes(properties['Ssid']).decode('utf-8', errors='replace')
    ssid = ''.join(c if c.isprintable() else '?' for c in ssid) or '(hidden network)'
    wpa, rsn = int(properties['WpaFlags']), int(properties['RsnFlags'])
    if rsn & 0x400:  # key management SAE
        security = 'WPA2/3' if rsn & 0x100 else 'WPA3'
    elif (wpa | rsn) & 0x200:
        security = 'Enterprise'
    elif rsn & (0x800 | 0x1000):
        security = 'Enhanced open'
    elif rsn:
        security = 'WPA2'
    elif wpa:
        security = 'WPA'
    elif int(properties['Flags']) & 1:
        security = 'Legacy secured'
    else:
        security = 'Open'
    return dict(ssid=ssid, signal=max(0, min(100, int(properties['Strength']))), security=security)


def summarize(rows):
    # Multiple access points with the same name/security appear as one network.
    networks = {}
    for row in rows:
        key = (row['ssid'], row['security'])
        if key not in networks or networks[key]['signal'] < row['signal']:
            networks[key] = row
    return sorted(networks.values(), key=lambda row: (-row['signal'], row['ssid']))


class Discovery:
    def __init__(self):
        import dbus
        self.dbus = dbus
        self.bus = dbus.SystemBus()

    def call(self, path, interface, method, *args):
        proxy = self.bus.get_object(NM, path, introspect=False)
        return getattr(self.dbus.Interface(proxy, interface), method)(*args, timeout=2)

    def props(self, path, interface):
        return self.call(path, 'org.freedesktop.DBus.Properties', 'GetAll', interface)

    def scan(self):
        manager = self.props(BASE, NM)
        if not manager['WirelessHardwareEnabled']:
            return dict(state='blocked', message='Wi-Fi is blocked by hardware.', networks=[])
        if not manager['WirelessEnabled']:
            return dict(state='off', message='Wi-Fi is off.', networks=[])
        devices = self.call(BASE, NM, 'GetDevices')
        wireless = []
        for path in devices:
            device = self.props(path, NM + '.Device')
            if int(device['DeviceType']) == 2:
                wireless.append(path)
        if not wireless:
            return dict(state='no-adapter', message='No Wi-Fi adapter detected.', networks=[])
        deadline = time.monotonic() + 7
        scans = []
        for path in wireless:
            before = int(self.props(path, NM + '.Device.Wireless').get('LastScan', -1))
            try:
                self.call(path, NM + '.Device.Wireless', 'RequestScan', self.dbus.Dictionary({}, signature='sv'))
                scans.append((path, before, True))
            except self.dbus.DBusException:
                scans.append((path, before, False))
        fresh = set()
        while time.monotonic() < deadline:
            for path, previous, requested in scans:
                if requested and int(self.props(path, NM + '.Device.Wireless').get('LastScan', -1)) > previous:
                    fresh.add(path)
            if len(fresh) == len(scans) or not any(requested for _, _, requested in scans):
                break
            time.sleep(0.2)
        rows = []
        # Parent shell enforces a total operation deadline, including D-Bus calls.
        for path, _, _ in scans:
            for ap in list(self.call(path, NM + '.Device.Wireless', 'GetAllAccessPoints'))[:64]:
                rows.append(network_row(self.props(ap, NM + '.AccessPoint')))
        cached = len(fresh) != len(scans)
        return dict(state='cached' if cached else 'ready',
                    message='Previous scan results; press A to retry.' if cached else 'Nearby networks',
                    networks=summarize(rows), observed_monotonic=time.monotonic())


def main():
    try:
        result = Discovery().scan()
    except Exception:
        result = dict(state='unavailable', message='Wi-Fi discovery is unavailable. Press A to retry.', networks=[])
    print(json.dumps(result))


if __name__ == '__main__':
    main()
