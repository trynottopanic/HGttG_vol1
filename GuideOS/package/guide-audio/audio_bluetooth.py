"""BlueZ adapter for explicit owner-initiated A2DP earbud pairing."""
import time
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from audio_errors import bluetooth_message, report
from guide_telemetry import emit

DBusGMainLoop(set_as_default=True)
A2DP_SINK = '0000110b-0000-1000-8000-00805f9b34fb'


class Rejected(dbus.DBusException):
    _dbus_error_name = 'org.bluez.Error.Rejected'


class Agent(dbus.service.Object):
    def __init__(self, bus, owner):
        super().__init__(bus, '/org/guideos/audio/agent')
        self.owner = owner

    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='')
    def RequestAuthorization(self, device):
        if str(device) != self.owner.pending:
            raise Rejected('No owner pairing request')

    @dbus.service.method('org.bluez.Agent1', in_signature='os', out_signature='')
    def AuthorizeService(self, device, uuid):
        if str(uuid).lower() != A2DP_SINK or str(device) != self.owner.pending:
            raise Rejected('Service not requested')

    @dbus.service.method('org.bluez.Agent1', in_signature='ou', out_signature='')
    def RequestConfirmation(self, device, passkey):
        raise Rejected('This first earbud flow does not support code confirmation')

    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='s')
    def RequestPinCode(self, device):
        raise Rejected('PIN entry is not supported by this earbud flow')

    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='u')
    def RequestPasskey(self, device):
        raise Rejected('Passkey entry is not supported by this earbud flow')

    @dbus.service.method('org.bluez.Agent1', in_signature='', out_signature='')
    def Cancel(self):
        pass

    @dbus.service.method('org.bluez.Agent1', in_signature='', out_signature='')
    def Release(self):
        self.owner.registered = False


class Bluetooth:
    def __init__(self):
        self.bus = dbus.SystemBus()
        self.agent = Agent(self.bus, self)
        self.registered = False
        self.pending = None
        self.generation = 0
        self.deadline = 0
        self.scan_adapter = None
        self.scan_deadline = 0
        self.devices = []
        self.adapters = []
        self.adapter_state = []
        self.last_inventory = None
        self.last_error = None
        self.message = 'Bluetooth idle'
        self.inventory_pending=False;self.inventory_generation=0;self.closed=False
        self.registering=False

    def failed(self, action, error):
        self.message = bluetooth_message(action, error)

    def interface(self, path, interface):
        return dbus.Interface(self.bus.get_object('org.bluez', path, introspect=False,
                              follow_name_owner_changes=True), interface)

    def refresh(self):
        if self.inventory_pending or self.closed:return
        self.inventory_pending=True;self.inventory_generation+=1
        generation=self.inventory_generation
        def failed(error):
            if self.closed or generation!=self.inventory_generation:return
            self.inventory_pending=False
            self.registered=False
            # Retain last known rows; a failed observation is not device removal.
            name=error.get_dbus_name()
            if name!=self.last_error:self.failed('inventory',error);self.last_error=name
        def received(values):
            if self.closed or generation!=self.inventory_generation:return
            self.inventory_pending=False
            self._inventory(values)
        try:
            self.interface('/','org.freedesktop.DBus.ObjectManager').GetManagedObjects(
                reply_handler=received,error_handler=failed,timeout=2)
        except dbus.DBusException as error:failed(error)

    def _inventory(self,values):
        self.adapters = [str(p) for p, v in values.items() if 'org.bluez.Adapter1' in v][:8]
        self.adapter_state = [dict(powered=bool(v['org.bluez.Adapter1'].get('Powered')),
                                   discovering=bool(v['org.bluez.Adapter1'].get('Discovering')))
                              for v in values.values() if 'org.bluez.Adapter1' in v][:8]
        self.devices = []
        for p, v in values.items():
            if len(self.devices)>=64:break
            d = v.get('org.bluez.Device1')
            if not d:
                continue
            # During discovery the UUIDs may not have arrived yet. Pairing
            # remains a request for this explicitly selected device only.
            self.devices.append(dict(id=str(p), title=str(d.get('Alias', 'Bluetooth device'))[:100],
                                     paired=bool(d.get('Paired')), connected=bool(d.get('Connected'))))
        self.devices = self.devices[:64]
        if not self.registered and not self.registering:
            self.registering=True
            def registered():
                self.registering=False
                if not self.closed:self.registered=True
            def registration_failed(error):
                self.registering=False
                if not self.closed:
                    if error.get_dbus_name()=='org.bluez.Error.AlreadyExists':self.registered=True
                    else:self.failed('inventory',error)
            try:
                self.interface('/org/bluez','org.bluez.AgentManager1').RegisterAgent(
                    '/org/guideos/audio/agent','NoInputNoOutput',reply_handler=registered,
                    error_handler=registration_failed,signature='os',timeout=2)
            except dbus.DBusException as error:registration_failed(error)
        snapshot = (len(self.adapters), sum(r['powered'] for r in self.adapter_state),
                    sum(r['discovering'] for r in self.adapter_state), len(self.devices),
                    sum(r['connected'] for r in self.devices))
        if snapshot != getattr(self, 'last_inventory', None):
            emit('BLUETOOTH_INVENTORY', adapters=snapshot[0], powered=snapshot[1],
                 discovering=snapshot[2], devices=snapshot[3], connected=snapshot[4])
            self.last_inventory = snapshot
        self.last_error = None
        if not self.adapters:
            self.message = 'No Bluetooth controller detected. Diagnostic recorded.'

    def scan(self):
        if self.pending or self.scan_adapter:
            raise ValueError('Bluetooth is busy. Cancel before scanning again.')
        self.refresh()
        if not self.adapters:
            raise ValueError('Bluetooth controller unavailable')
        adapter = self.adapters[0]
        self.generation+=1;generation=self.generation
        def failed(error):
            if generation==self.generation:self.scan_adapter=None;self.failed('scan',error)
        def powered():
            if generation!=self.generation:return
            try:self.interface(adapter,'org.bluez.Adapter1').StartDiscovery(
                reply_handler=lambda:None,error_handler=failed,timeout=2)
            except dbus.DBusException as error:failed(error)
        self.interface(adapter,'org.freedesktop.DBus.Properties').Set(
            'org.bluez.Adapter1','Powered',True,reply_handler=powered,error_handler=failed,signature='ssv',timeout=2)
        self.scan_adapter, self.scan_deadline = adapter, time.monotonic() + 20
        self.message = 'Finding earbuds for 20 seconds. Put yours in pairing mode.'

    def connect(self, identity):
        if self.pending:
            raise ValueError('Another Bluetooth operation is running')
        row = next((d for d in self.devices if d['id'] == identity), None)
        if row is None:
            raise ValueError('Device no longer available')
        if getattr(self, 'scan_adapter', None):
            self.cancel()
        self.generation += 1
        generation = self.generation
        self.pending, self.deadline = identity, time.monotonic() + 30
        self.message = 'Pairing / connecting...'
        device = self.interface(identity, 'org.bluez.Device1')

        def done(*args):
            if generation != self.generation:
                return
            self.pending = None
            self.message = 'Connected. Choose the earbud in Audio outputs.'

        def failed(error):
            if generation != self.generation:
                return
            self.pending = None
            self.failed('connect', error)

        def paired():
            if generation != self.generation:
                return
            try:
                def trusted():
                    if generation==self.generation:
                        try:device.ConnectProfile(A2DP_SINK,reply_handler=done,error_handler=failed,timeout=20)
                        except dbus.DBusException as error:failed(error)
                self.interface(identity,'org.freedesktop.DBus.Properties').Set(
                    'org.bluez.Device1','Trusted',True,reply_handler=trusted,error_handler=failed,signature='ssv',timeout=2)
            except dbus.DBusException as error:
                failed(error)
        try:
            if row['paired']:
                paired()
            else:
                device.Pair(reply_handler=paired, error_handler=failed, timeout=25)
        except dbus.DBusException as error:
            failed(error)

    def cancel(self):
        self.generation += 1
        if self.pending:
            identity, self.pending = self.pending, None
            device = self.interface(identity, 'org.bluez.Device1')
            for operation in ('CancelPairing', 'Disconnect'):
                try:
                    getattr(device, operation)(reply_handler=lambda:None,error_handler=lambda error:None,timeout=2)
                except dbus.DBusException:
                    pass
        if self.scan_adapter:
            adapter, self.scan_adapter = self.scan_adapter, None
            try:
                self.interface(adapter, 'org.bluez.Adapter1').StopDiscovery(reply_handler=lambda:None,error_handler=lambda error:self.failed('scan_stop',error),timeout=2)
            except dbus.DBusException:
                pass
        self.message = 'Bluetooth operation cancelled'

    def disconnect(self, identity):
        if identity not in {d['id'] for d in self.devices}:
            raise ValueError('Device no longer available')
        self.message='Disconnecting...'
        generation=self.generation
        def done():
            if generation==self.generation and not self.closed:self.message='Disconnected';self.refresh()
        def failed(error):
            if generation==self.generation and not self.closed:self.failed('disconnect',error)
        self.interface(identity,'org.bluez.Device1').Disconnect(
            reply_handler=done,error_handler=failed,timeout=3)

    def tick(self):
        if self.pending and time.monotonic() >= self.deadline:
            self.cancel()
            self.message = 'Bluetooth operation timed out'
            report('connect', TimeoutError())
        if self.scan_adapter and time.monotonic() >= self.scan_deadline:
            adapter, self.scan_adapter = self.scan_adapter, None
            try:
                self.interface(adapter, 'org.bluez.Adapter1').StopDiscovery(reply_handler=lambda:None,error_handler=lambda error:self.failed('scan_stop',error),timeout=2)
            except dbus.DBusException as error:
                self.failed('scan_stop', error)
                return
            self.refresh()
            if not self.adapters:
                return
            self.message = (f'Discovery finished: {len(self.devices)} known / found devices.' if self.devices
                            else 'No devices found. Check pairing mode, then Find earbuds again.')

    def close(self):
        self.closed=True;self.inventory_generation+=1
        self.cancel()
