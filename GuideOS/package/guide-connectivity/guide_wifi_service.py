#!/usr/bin/python3
"""Guide-owned Wi-Fi policy above NetworkManager; no display/input ownership.

Trusted local clients send bounded commands to a root-only Unix datagram socket.
Status contains no secrets. NetworkManager owns association, IP and keyfiles.
SPDX-License-Identifier: AGPL-3.0-or-later
"""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import select
import signal
import socket
import time
import uuid

from guide_wifi_discovery import Discovery, NM, BASE, network_row

RUNTIME = Path('/run/guideos-wifi')
POLICY = Path('/var/lib/guideos-wifi/policy.json')
SETTINGS = BASE + '/Settings'
SC = NM + '.Settings.Connection'
MIN_INTERVAL = 300
DBUS_CALL_LIMIT = 2.0
CLEANUP_WINDOW = 8.0
DBUS_TIMEOUT_ERRORS = frozenset('org.freedesktop.DBus.Error.' + name for name in
                                ('NoReply', 'Timeout', 'TimedOut', 'Disconnected'))
MISSING_OBJECT_ERRORS = frozenset('org.freedesktop.DBus.Error.' + name for name in
                                 ('UnknownObject', 'UnknownMethod'))
SAFE_DBUS_ERRORS = DBUS_TIMEOUT_ERRORS | frozenset((
    'org.freedesktop.DBus.Error.UnknownObject',
    'org.freedesktop.DBus.Error.UnknownMethod',
    'org.freedesktop.DBus.Error.ServiceUnknown',
    'org.freedesktop.DBus.Error.AccessDenied',
    NM + '.Settings.InvalidConnection', NM + '.Settings.PermissionDenied',
    NM + '.UnknownConnection', NM + '.UnknownDevice', NM + '.ConnectionNotAvailable',
    NM + '.PermissionDenied', NM + '.DependencyFailed', NM + '.ConnectionAlreadyActive',
    NM + '.ConnectionNotActive', NM + '.Device.NotActive',
))


def dbus_error_name(exc):
    """Only known protocol names, never exception bodies or arbitrary strings."""
    method = getattr(exc, 'get_dbus_name', None)
    name = method() if callable(method) else ''
    return name if name in SAFE_DBUS_ERRORS else ''


def transient_error(exc):
    return isinstance(exc, TimeoutError) or dbus_error_name(exc) in DBUS_TIMEOUT_ERRORS


def safe_error(exc):
    return dict(error_type='timeout' if transient_error(exc) else
                'dbus' if callable(getattr(exc, 'get_dbus_name', None)) else 'provider',
                dbus_error=dbus_error_name(exc))


class ActivationError(RuntimeError):
    def __init__(self, attempt, cause):
        super().__init__('Activation outcome requires reconciliation')
        self.attempt = attempt
        self.diagnostic = safe_error(cause)


class CleanupPending(RuntimeError):
    pass


def atomic_json(path, value, durable=False):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream)
        if durable:
            stream.flush()
            os.fsync(stream.fileno())
    temporary.replace(path)
    if durable:
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def security_kind(properties):
    rsn = int(properties.get('RsnFlags', 0))
    if rsn & 0x100:
        return 'wpa-psk'
    if rsn & 0x400:
        return 'sae'
    if not (int(properties.get('Flags', 0)) & 1 or rsn or int(properties.get('WpaFlags', 0))):
        return 'open'
    return 'unsupported'


def network_id(ssid, kind):
    return hashlib.sha256(bytes(ssid) + b'\0' + kind.encode('ascii')).hexdigest()[:24]


class Backend(Discovery):
    """Synchronous D-Bus requests are short; association itself is asynchronous."""
    def __init__(self):
        super().__init__()
        self.until = float('inf')
        self.device = None
        self.aps = {}
        self.profiles = {}
        self.active = None
        self.diagnostic = {}

    def call(self, path, interface, method, *args):
        remaining = self.until - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Operation deadline')
        proxy = self.bus.get_object(NM, path, introspect=False)
        return getattr(self.dbus.Interface(proxy, interface), method)(*args, timeout=min(DBUS_CALL_LIMIT, remaining))

    def record_device_state(self, properties):
        state = int(properties.get('State', 0))
        reason = properties.get('StateReason', (state, 0))
        self.diagnostic = dict(device_state=state, device_reason=int(reason[1]))

    def ip_ready(self, properties):
        if int(properties.get('State', 0)) != 2:
            return False
        ip = str(properties.get('Ip4Config', '/'))
        return ip != '/' and bool(self.props(ip, NM + '.IP4Config').get('AddressData'))

    def ipv4_address(self, properties):
        path=str(properties.get('Ip4Config','/'))
        if path=='/':return None
        for row in self.props(path,NM+'.IP4Config').get('AddressData',[]):
            try:address=ipaddress.IPv4Address(str(row.get('address','')))
            except ipaddress.AddressValueError:continue
            if not (address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast):
                return str(address)
        return None

    def refresh(self):
        self.until = time.monotonic() + 2
        manager = self.props(BASE, NM)
        self.device = None
        for path in self.call(BASE, NM, 'GetDevices'):
            if int(self.props(path, NM + '.Device')['DeviceType']) == 2:
                self.device = str(path)
                break
        self.profiles = {}
        for path in list(self.call(SETTINGS, NM + '.Settings', 'ListConnections'))[:64]:
            settings = self.call(path, SC, 'GetSettings')
            connection = settings.get('connection', {})
            if not str(connection.get('id', '')).startswith('Guide Wi-Fi '):
                continue
            ssid = bytes(settings.get('802-11-wireless', {}).get('ssid', b''))
            kind = str(settings.get('802-11-wireless-security', {}).get('key-mgmt', 'open'))
            if ssid and kind in ('open', 'wpa-psk', 'sae'):
                saved = not bool(self.props(path, SC).get('Unsaved', True))
                self.profiles[network_id(ssid, kind)] = dict(path=str(path), ssid=ssid, kind=kind,
                                                           saved=saved, uuid=str(connection.get('uuid', '')))
        self.aps = {}
        self.active = None
        ipv4 = None
        if not self.device:
            return dict(state='no-adapter', message='No Wi-Fi adapter detected.', networks=[], connected=None, ipv4=None)
        dev = self.props(self.device, NM + '.Device')
        self.record_device_state(dev)
        wireless = self.props(self.device, NM + '.Device.Wireless')
        if int(dev['State']) == 100 and str(dev.get('ActiveConnection', '/')) != '/':
            active_path = str(dev.get('ActiveConnection', '/'))
            props = self.props(active_path, NM + '.Connection.Active')
            if self.ip_ready(props):
                self.active = dict(path=active_path, profile=str(props['Connection']))
                ipv4 = self.ipv4_address(props)
        active_ap = str(wireless.get('ActiveAccessPoint', '/'))
        rows = {}
        for path in list(self.call(self.device, NM + '.Device.Wireless', 'GetAllAccessPoints'))[:64]:
            if time.monotonic() >= self.until - .05:
                break
            p = self.props(path, NM + '.AccessPoint')
            ssid = bytes(p['Ssid'])
            if not ssid:
                continue
            # Do not offer stale sightings as currently in range.
            seen = int(p.get('LastSeen', -1))
            if seen < 0 or time.clock_gettime(time.CLOCK_BOOTTIME) - seen > 360:
                continue
            kind = security_kind(p)
            identity = network_id(ssid, kind)
            row = dict(network_row(p), id=identity, saved=self.profiles.get(identity, {}).get('saved', False),
                       supported=kind != 'unsupported', active=bool(self.active) and str(path) == active_ap,
                       seen=seen, available=True)
            if identity not in rows or row['active'] or (not rows[identity]['active'] and row['signal'] > rows[identity]['signal']):
                rows[identity] = row
                self.aps[identity] = dict(path=str(path), ssid=ssid, kind=kind)
        for identity, profile in self.profiles.items():
            if identity not in rows:
                name = bytes(profile['ssid']).decode('utf-8', 'replace')
                name = ''.join(c if c.isprintable() else '?' for c in name)
                rows[identity] = dict(id=identity, ssid=name, signal=0,
                                      security={'open':'Open', 'wpa-psk':'WPA2', 'sae':'WPA3'}[profile['kind']],
                                      saved=profile['saved'], supported=True, active=False, available=False, seen=-1)
        connected = next((r['id'] for r in rows.values() if r['active']), None)
        if self.active and connected is None:
            connected = next((k for k, p in self.profiles.items() if p['path'] == self.active['profile']), 'external')
        state = 'ready' if manager['WirelessEnabled'] else 'off'
        if not manager['WirelessHardwareEnabled']:
            state = 'blocked'
        return dict(state=state, message='Connected; internet not checked.' if self.active else 'Not connected.',
                    networks=sorted(rows.values(), key=lambda r: (not r['active'], not r['available'], -r['signal'], r['ssid'])),
                    connected=connected, ipv4=ipv4)

    def request_scan(self):
        self.until = time.monotonic() + .6
        if not self.device:
            raise ValueError('No adapter')
        before = int(self.props(self.device, NM + '.Device.Wireless')['LastScan'])
        self.call(self.device, NM + '.Device.Wireless', 'RequestScan', self.dbus.Dictionary({}, signature='sv'))
        return before

    def recover(self):
        """A crashed UI/service must not leave an unbounded initial activation."""
        self.refresh()
        if self.device:
            dev = self.props(self.device, NM + '.Device')
            if 40 <= int(dev['State']) < 100 and str(dev.get('ActiveConnection', '/')) != '/':
                active = self.props(str(dev['ActiveConnection']), NM + '.Connection.Active')
                if str(active['Connection']) in {p['path'] for p in self.profiles.values()}:
                    self.cancel()
        for profile in self.profiles.values():
            self.until = time.monotonic() + .6
            if self.props(profile['path'], SC).get('Unsaved'):
                self.call(profile['path'], SC, 'Delete')

    def scan_finished(self, before):
        self.until = time.monotonic() + .3
        return int(self.props(self.device, NM + '.Device.Wireless')['LastScan']) > before

    def start(self, identity, password, deadline):
        self.until = deadline
        ap = self.aps.get(identity)
        if not ap or ap['kind'] == 'unsupported':
            raise ValueError('Unavailable or unsupported network')
        # Re-read the selected AP. A removed/reused object must not change the target.
        p = self.props(ap['path'], NM + '.AccessPoint')
        if bytes(p['Ssid']) != ap['ssid'] or security_kind(p) != ap['kind']:
            raise ValueError('Network changed')
        profile = self.profiles.get(identity)
        fresh = profile is None
        attempt = dict(active=None, profile=profile['path'] if profile else None,
                       fresh=fresh or not profile.get('saved', True), id=identity,
                       uuid=str(uuid.uuid4()) if fresh else profile.get('uuid', ''), uncertain=False)
        if fresh:
            if ap['kind'] != 'open':
                valid = 8 <= len(password.encode('utf-8')) <= 63
                if not valid or any(ord(c) < 32 or ord(c) > 126 for c in password):
                    raise ValueError('Use an 8-63 character ASCII password')
            dbus = self.dbus
            settings = {
                'connection': {'id': 'Guide Wi-Fi ' + identity, 'uuid': attempt['uuid'],
                               'type': '802-11-wireless', 'autoconnect': dbus.Boolean(False)},
                '802-11-wireless': {'ssid': dbus.ByteArray(ap['ssid']), 'mode': 'infrastructure',
                                   'powersave': dbus.UInt32(3)},
                'ipv4': {'method': 'auto', 'may-fail': dbus.Boolean(False)},
                'ipv6': {'method': 'auto', 'may-fail': dbus.Boolean(True)},
            }
            if ap['kind'] != 'open':
                settings['802-11-wireless-security'] = {
                    'key-mgmt': ap['kind'], 'psk': password, 'psk-flags': dbus.UInt32(0),
                    'proto': dbus.Array(['rsn'], signature='s')}
        try:
            if fresh:
                attempt['profile'] = str(self.call(SETTINGS, NM + '.Settings', 'AddConnectionUnsaved',
                    dbus.Dictionary({k: dbus.Dictionary(v, signature='sv') for k, v in settings.items()}, signature='sa{sv}')))
            attempt['active'] = str(self.call(BASE, NM, 'ActivateConnection', self.dbus.ObjectPath(attempt['profile']),
                                             self.dbus.ObjectPath(self.device), self.dbus.ObjectPath(ap['path'])))
        except Exception as exc:
            # A timeout does not undo the remote method. Preserve its identity even
            # if no reply supplied the new object's path; never lose the cleanup job.
            attempt['uncertain'] = transient_error(exc)
            raise ActivationError(attempt, exc) from None
        return attempt

    def progress(self, attempt, deadline):
        self.until = deadline
        dev = self.props(self.device, NM + '.Device')
        self.record_device_state(dev)
        p = self.props(attempt['active'], NM + '.Connection.Active')
        state = int(p['State'])
        self.diagnostic['active_state'] = state
        if int(dev['State']) == 100 and self.ip_ready(p):
            return 'connected'
        if state in (3, 4):
            return 'failed'
        return 'waiting'

    def save(self, attempt, deadline=None):
        self.until = min(time.monotonic() + DBUS_CALL_LIMIT, deadline) if deadline is not None else time.monotonic() + DBUS_CALL_LIMIT
        if attempt['fresh']:
            self.call(attempt['profile'], SC, 'Save')

    def disconnect_device(self):
        if not self.device:
            return
        dev = self.props(self.device, NM + '.Device')
        self.record_device_state(dev)
        if 40 <= int(dev['State']) < 120 or str(dev.get('ActiveConnection', '/')) != '/':
            try:
                self.call(self.device, NM + '.Device', 'Disconnect')
            except Exception as exc:
                if dbus_error_name(exc) != NM + '.Device.NotActive':
                    raise

    def cancel(self, attempt=None, disconnect_all=False):
        self.until = time.monotonic() + .8
        if disconnect_all or not attempt:
            # Honour explicit disconnection before trying to find an uncertain
            # new profile; a slow/missing profile must not preserve an old link.
            self.disconnect_device()
        if attempt and attempt['fresh'] and not attempt.get('profile'):
            try:
                attempt['profile'] = str(self.call(SETTINGS, NM + '.Settings', 'GetConnectionByUuid', attempt['uuid']))
            except Exception as exc:
                if dbus_error_name(exc) != NM + '.Settings.InvalidConnection':
                    raise
                # The transaction remains uncertain, but an explicit Disconnect
                # must still stop any other link before reporting that uncertainty.
        # Deactivate only this transaction, including an activation whose reply was
        # lost. An explicit Disconnect (no transaction) applies to the whole device.
        matching = []
        if attempt and attempt.get('profile'):
            for path in self.props(BASE, NM).get('ActiveConnections', []):
                try:
                    active = self.props(path, NM + '.Connection.Active')
                except Exception as exc:
                    if dbus_error_name(exc) in MISSING_OBJECT_ERRORS:
                        continue
                    raise
                if str(active.get('Connection')) == attempt['profile'] and int(active['State']) != 4:
                    matching.append(str(path))
            for path in matching:
                attempt['observed_activation'] = True
                if not disconnect_all:
                    try:
                        self.call(BASE, NM, 'DeactivateConnection', self.dbus.ObjectPath(path))
                    except Exception as exc:
                        if dbus_error_name(exc) != NM + '.ConnectionNotActive':
                            raise
        if attempt and attempt['fresh'] and attempt.get('profile'):
            try:
                self.call(attempt['profile'], SC, 'Delete')
            except Exception as exc:
                if dbus_error_name(exc) not in MISSING_OBJECT_ERRORS:
                    raise
            # Removing this newly-created profile prevents a delayed activation
            # from using it. A saved profile is never deleted during cancellation.
            attempt['uncertain'] = False
        elif attempt and attempt.get('uncertain') and not attempt.get('observed_activation'):
            raise CleanupPending('Activation outcome is not confirmed')
        if self.device:
            dev = self.props(self.device, NM + '.Device')
            self.record_device_state(dev)
            active_path = str(dev.get('ActiveConnection', '/'))
            if active_path != '/':
                active = self.props(active_path, NM + '.Connection.Active')
                if (disconnect_all or not attempt or str(active.get('Connection')) == attempt.get('profile')
                        or active_path == attempt.get('active') or active_path in matching):
                    if int(active.get('State', 0)) != 4:
                        raise CleanupPending('Disconnection is not yet confirmed')
            elif (disconnect_all or not attempt) and 40 <= int(dev['State']) < 120:
                raise CleanupPending('Device disconnection is not yet confirmed')

    def forget(self, identity):
        self.until = time.monotonic() + .3
        self.call(self.profiles[identity]['path'], SC, 'Delete')


class Controller:
    def __init__(self, backend, policy_path=POLICY, clock=time.monotonic, boot_marker=None):
        self.backend, self.policy_path, self.clock = backend, Path(policy_path), clock
        try:
            policy = json.loads(self.policy_path.read_text())
        except FileNotFoundError:
            policy = {'hold': False}
        except (OSError, ValueError):
            policy = {'hold': True}  # damaged policy must not undo a manual disconnect
        if not isinstance(policy, dict):
            policy = {'hold': True}
        self.hold = policy.get('hold', True) is not False
        self.persisted_hold = self.hold if self.policy_path.exists() and type(policy.get('hold')) is bool else None
        self.misses = 0
        # A restart or inaccurate board RTC never shortens the five-minute floor.
        self.next_auto = clock() + MIN_INTERVAL
        self.boot_marker = Path(boot_marker) if boot_marker is not None else None
        self.next_refresh = 0
        self.attempt = None
        self.scan = None
        self.deadline = 0
        self.state = dict(state='starting', message='Starting Wi-Fi...', networks=[], connected=None)
        self.message = ''
        self.result = ''
        self.generation = 0
        self.token = ''
        self.last_diagnostic = None

    def set_hold(self, value):
        self.hold = value
        if self.persisted_hold == value:
            return
        atomic_json(self.policy_path, {'hold': value}, durable=True)
        self.persisted_hold = value

    def boot_reconnect(self, allow=True):
        """One startup check per boot; subsequent checks retain normal backoff."""
        if self.boot_marker is None:return
        # Device discovery may finish after the service starts.
        if allow and not self.backend.device and not self.hold:return
        marker,self.boot_marker=self.boot_marker,None
        try:
            with marker.open('x') as stream:stream.write('startup check consumed\n')
        except FileExistsError:return
        except OSError:
            self.event('boot_reconnect_marker_unavailable')
            return
        if (allow and not self.hold and not self.state.get('connected') and
                any(p.get('saved',False) for p in self.backend.profiles.values())):
            self.next_auto=self.clock()
            self.event('boot_reconnect_ready')

    def snapshot(self):
        return dict(self.state, message=self.message or self.state['message'], hold=self.hold,
                    busy=bool(self.attempt or self.scan), operation='connect' if self.attempt else 'scan' if self.scan else '',
                    result=self.result, generation=self.generation, token=self.token,
                    next_check_seconds=max(0, int(self.next_auto - self.clock())), observed=self.clock())

    def interval(self):
        minimum = MIN_INTERVAL
        for capacity in Path('/sys/class/power_supply').glob('*/capacity'):
            try:
                if int(capacity.read_text()) < 20:
                    minimum = 900
            except (ValueError, OSError):
                pass
        return min(1800, minimum * (2 ** min(self.misses, 3)))

    def refresh(self):
        previous = self.state.get('connected')
        self.state = self.backend.refresh()
        if previous and not self.state.get('connected') and not self.attempt:
            self.message = 'Disconnected. Auto-reconnect paused.' if self.hold else 'Connection lost. Waiting for the next saved-network check.'
        self.next_refresh = self.clock() + 10

    def finish(self, result, message):
        self.result, self.message = result, message
        self.generation += 1
        self.next_refresh = 0
        self.event('result', result=result)

    def event(self, name, **fields):
        # Explicit safe fields only: never include requests, SSIDs or exceptions.
        try:
            print('GUIDE_WIFI ' + json.dumps(dict(event=name, monotonic=self.clock(), **fields)), flush=True)
        except OSError:
            pass

    def diagnose(self, exc=None):
        values = getattr(self.backend, 'diagnostic', {})
        values = values if isinstance(values, dict) else {}
        safe = {key: int(values[key]) for key in ('device_state', 'device_reason', 'active_state')
                if key in values and isinstance(values[key], int)}
        if safe and safe != self.last_diagnostic:
            self.event('nm_state', **safe)
            self.last_diagnostic = safe
        if exc is not None:
            self.event('provider_error', **safe_error(exc))

    def hold_after_uncertain(self):
        try:
            self.set_hold(True)
        except OSError:
            pass  # Keep the in-memory hold even if the card cannot persist it.

    def link_status(self, identity=None, saved=False):
        self.state['connected'] = identity
        for row in self.state['networks']:
            row['active'] = row['id'] == identity
            if row['active'] and saved:
                row['saved'] = True

    def abort(self, message='Connection cancelled.', disconnect_all=False):
        attempt = self.attempt or getattr(self, 'cleanup_attempt', None) or getattr(self, 'uncertain_attempt', None)
        disconnect_all = disconnect_all or getattr(self, 'cleanup_all', False) or getattr(self, 'uncertain_all', False)
        self.attempt = None
        self.scan = None
        if hasattr(self, 'uncertain_attempt'):
            del self.uncertain_attempt
            self.__dict__.pop('uncertain_all', None)
        try:
            self.backend.cancel(attempt, disconnect_all=disconnect_all)
        except Exception as exc:
            self.diagnose(exc)
            self.hold_after_uncertain()
            self.finish('cleanup-pending', 'Disconnect not confirmed. Retrying cleanup...')
            self.cleanup_attempt = attempt
            self.cleanup_all = disconnect_all
            self.cleanup_deadline = self.clock() + CLEANUP_WINDOW
            self.cleanup_retry = self.clock() + .5
            return
        if hasattr(self, 'cleanup_attempt'):
            del self.cleanup_attempt
            del self.cleanup_all
        self.diagnose()
        self.link_status()
        self.finish('cancelled', message)

    def stop(self):
        """One bounded cleanup pass on shutdown, including incomplete cleanup.

        Completed connections survive a provider restart. An unfinished attempt
        receives at most one 0.8-second backend cleanup pass; shutdown never waits
        for the multi-tick reconciliation window.
        """
        self.scan = None
        if not (self.attempt or hasattr(self, 'cleanup_attempt') or hasattr(self, 'uncertain_attempt')):
            return
        attempt = self.attempt or getattr(self, 'cleanup_attempt', None) or getattr(self, 'uncertain_attempt', None)
        disconnect_all = getattr(self, 'cleanup_all', False) or getattr(self, 'uncertain_all', False)
        try:
            self.backend.cancel(attempt, disconnect_all=disconnect_all)
        except Exception as exc:
            self.diagnose(exc)
            self.hold_after_uncertain()
            self.event('shutdown_cleanup', confirmed=False)
        else:
            self.diagnose()
            self.event('shutdown_cleanup', confirmed=True)

    def command(self, command):
        action = command.get('action')
        token = command.get('token', '')
        if not isinstance(token, str) or len(token) > 32:
            raise ValueError('Invalid request token')
        if action in ('connect','disconnect','scan','forget','cancel'):
            self.boot_reconnect(allow=False)
        self.token = token
        self.result = ''
        if action == 'disconnect':
            self.event('disconnect_requested')
            persisted = True
            try:
                self.set_hold(True)
            except OSError:
                persisted = False
            self.next_auto = self.clock() + self.interval()
            self.abort('Disconnected. Auto-reconnect paused until Connect.', disconnect_all=True)
            if not persisted and not hasattr(self, 'cleanup_attempt'):
                self.finish('not-saved', 'Disconnected; hold could not be saved for the next boot.')
            return
        if action == 'cancel':
            self.event('cancel_requested')
            if self.attempt or hasattr(self, 'cleanup_attempt') or hasattr(self, 'uncertain_attempt'):
                try:
                    self.set_hold(True)
                except OSError:
                    pass  # in-memory hold still applies; cancellation must proceed
                self.abort()
            else:
                self.scan = None
                self.finish('cancelled', 'Scan cancelled; connection unchanged.')
            return
        if self.attempt or self.scan or hasattr(self, 'cleanup_attempt'):
            self.finish('busy', 'An operation is running. Cancel it first.')
            return
        if action == 'scan':
            self.refresh()
            if self.state.get('state') == 'no-adapter':
                self.finish('no-adapter', 'Wi-Fi adapter did not initialize. Restart the Deck to retry.')
                return
            self.scan = dict(before=self.backend.request_scan(), auto=False)
            self.event('scan_started', automatic=False)
            self.deadline = self.clock() + 8
            self.message = 'Scanning nearby networks...'
            # Manual discovery also postpones background work to avoid duplicate scans.
            self.next_auto = self.clock() + self.interval()
        elif action == 'connect':
            if hasattr(self, 'uncertain_attempt'):
                self.finish('cleanup-unconfirmed', 'Previous attempt is unconfirmed. Select Disconnect to retry cleanup.')
                return
            identity = command.get('id')
            password = command.get('password', '')
            if not isinstance(identity, str) or len(identity) != 24 or not isinstance(password, str) or len(password) > 63:
                raise ValueError('Invalid connection request')
            if identity not in self.backend.aps:
                self.finish('unavailable', 'Network unavailable. Rescan and select it again.')
                return
            switching = bool(self.state.get('connected'))
            # Reserve time for cancellation before the five-second switching outcome.
            requested = command.get('requested_at', self.clock())
            if type(requested) not in (int, float) or not self.clock() - 30 <= requested <= self.clock() + .1:
                raise ValueError('Stale request')
            self.deadline = requested + (3.6 if switching else 30)
            if self.clock() >= self.deadline:
                self.finish('timeout', 'Request expired before activation. Connection unchanged.')
                return
            self.set_hold(False)
            self.next_auto = self.clock() + self.interval()
            try:
                self.attempt = self.backend.start(identity, password, self.deadline)
            except ActivationError as exc:
                self.event('activation_error', **exc.diagnostic)
                self.attempt = exc.attempt
                self.hold_after_uncertain()
                self.abort('Connection did not start; attempt stopped. Select Connect to retry.')
                return
            self.event('connect_started', switching=switching, deadline=self.deadline)
            self.message = 'Switching (5-second limit)...' if switching else 'Connecting (up to 30 seconds)...'
        elif action == 'forget':
            identity = command.get('id')
            if identity == self.state.get('connected'):
                self.set_hold(True)
                self.backend.cancel()
            self.backend.forget(identity)
            self.finish('forgotten', 'Saved network removed.')
        else:
            raise ValueError('Unknown command')

    def tick(self):
        now = self.clock()
        if hasattr(self, 'cleanup_attempt'):
            if now >= self.cleanup_deadline:
                self.uncertain_attempt = self.cleanup_attempt
                self.uncertain_all = self.cleanup_all
                del self.cleanup_attempt
                del self.cleanup_all
                self.finish('cleanup-unconfirmed', 'Connection state is unconfirmed. Select Disconnect to retry cleanup.')
                return
            if now < self.cleanup_retry:
                return
            self.cleanup_retry = now + .5
            try:
                self.backend.cancel(self.cleanup_attempt, disconnect_all=self.cleanup_all)
            except Exception as exc:
                self.diagnose(exc)
                return
            del self.cleanup_attempt
            del self.cleanup_all
            self.diagnose()
            self.link_status()
            self.finish('cancelled', 'Disconnected; connection attempt stopped.')
            return
        if self.attempt:
            if now >= self.deadline:
                self.abort('Connection timed out; attempt stopped. Select Connect to retry.')
                return
            try:
                progress = self.backend.progress(self.attempt, self.deadline)
            except Exception as exc:
                self.diagnose(exc)
                if transient_error(exc):
                    # A delayed observation is not an authentication failure. The
                    # next tick retries only the read, inside the original budget.
                    return
                raise
            self.diagnose()
            if progress == 'connected':
                try:
                    self.backend.save(self.attempt, self.deadline)
                except Exception as exc:
                    self.diagnose(exc)
                    self.link_status(self.attempt['id'])
                    self.attempt = None
                    self.finish('not-saved', 'Connected; saving was not confirmed. Reconnection is not assured.')
                    return
                self.link_status(self.attempt['id'], saved=True)
                self.attempt = None
                self.misses = 0
                self.finish('connected', 'Connected and saved. Internet not checked.')
            elif progress == 'failed':
                self.abort('Connection failed. Network state was recorded for diagnosis.')
            return
        if self.scan:
            if self.backend.scan_finished(self.scan['before']) or now >= self.deadline:
                auto = self.scan['auto']
                self.scan = None
                self.refresh()
                self.finish('scan-complete', 'Nearby networks updated.')
                if auto and not self.hold and not self.state.get('connected'):
                    candidates = [r for r in self.state['networks'] if r['saved'] and r['available'] and r['supported']]
                    if candidates:
                        self.command(dict(action='connect', id=candidates[0]['id']))
                    else:
                        self.misses += 1
                        self.next_auto = now + self.interval()
            return
        if now >= self.next_refresh:
            self.refresh()
        self.boot_reconnect()
        if now >= self.next_auto:
            self.next_auto = now + self.interval()
            if not self.hold and not self.state.get('connected') and self.backend.profiles and self.backend.device:
                self.scan = dict(before=self.backend.request_scan(), auto=True)
                self.event('scan_started', automatic=True, next_interval=self.interval())
                self.deadline = now + 8
                self.message = 'Checking for saved networks...'


def serve():
    os.umask(0o077)
    RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
    endpoint = RUNTIME / 'control.sock'
    endpoint.unlink(missing_ok=True)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(str(endpoint))
    sock.setblocking(False)
    controller = Controller(Backend(),boot_marker=RUNTIME/'boot-reconnect')
    try:
        controller.backend.recover()
    except Exception:
        # Retry recovery before processing commands if NetworkManager starts late.
        controller.recovery_pending = True
    running = True
    def stop(_signum, _frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    wake_read, wake_write = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
    previous_wakeup = signal.set_wakeup_fd(wake_write)
    last_status = 0
    try:
        while running:
            ready = []
            generation = controller.generation
            try:
                wait = .1 if controller.attempt or controller.scan else 1 if hasattr(controller, 'cleanup_attempt') else min(10, max(0, controller.next_refresh - time.monotonic()))
                ready, _, _ = select.select([sock, wake_read], [], [], wait)
                if not running:
                    break
                if getattr(controller, 'recovery_pending', False):
                    controller.backend.recover()
                    controller.recovery_pending = False
                if sock in ready:
                    payload = sock.recv(4097)
                    if len(payload) > 4096:
                        raise ValueError('Oversized request')
                    request = json.loads(payload)
                    if not isinstance(request, dict):
                        raise ValueError('Invalid request')
                    try:
                        controller.command(request)
                    finally:
                        request.clear()
                        payload = b''
                controller.tick()
            except Exception as exc:
                # Never log exception bodies from D-Bus or commands: may contain secrets.
                controller.diagnose(exc)
                if controller.attempt:
                    controller.abort('Connection failed; attempt stopped.')
                else:
                    controller.scan = None
                    controller.finish('unavailable', 'Wi-Fi operation unavailable. Retry or rescan.')
                    controller.next_refresh = time.monotonic() + 10
            if ready or controller.attempt or controller.scan or controller.generation != generation or time.monotonic() - last_status >= 1:
                atomic_json(RUNTIME / 'status.json', controller.snapshot())
                last_status = time.monotonic()
    finally:
        signal.set_wakeup_fd(previous_wakeup)
        os.close(wake_read)
        os.close(wake_write)
        controller.stop()
        sock.close()
        endpoint.unlink(missing_ok=True)


if __name__ == '__main__':
    serve()
