"""System-owned radio observations and cancellable, explicit network jobs.

Discovery never pairs, joins, trusts a device or starts a port scan. The shell
consumes bounded snapshots; transport matches the current Wi-Fi system adapter.
"""
import copy
import ipaddress
import json
import os
from pathlib import Path
import re
import select
import signal
import socket
import struct
import subprocess
import tempfile
import threading
import time
import xml.etree.ElementTree as ET

MAX_ROWS = 64
MAX_OUTPUT = 128*1024
RUNTIME = Path('/run/guideos-nearby')
PROFILES = {'ports':'Nmap / Common TCP ports', 'services':'Nmap / Service details',
            'ping':'Ping', 'dns':'DNS lookup', 'route':'Route trace'}


def clean(value, limit=100):
    return ''.join(c if c.isprintable() else ' ' for c in str(value))[:limit]


def channel(frequency):
    if frequency == 2484: return 14
    if 2412 <= frequency <= 2472: return (frequency-2407)//5
    if 5000 <= frequency <= 5900: return (frequency-5000)//5
    if frequency == 5935: return 2
    if 5955 <= frequency <= 7115: return (frequency-5950)//5
    return None


def target_value(profile, value):
    if profile not in PROFILES or not isinstance(value,str): raise ValueError('Choose a tool and target.')
    value = value.strip()
    try: return str(ipaddress.ip_address(value))
    except ValueError:
        if profile != 'dns': raise ValueError('Enter one IPv4 or IPv6 address.')
    if len(value)>253 or not value or any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?',p)
                                         for p in value.rstrip('.').split('.')):
        raise ValueError('Enter an IP address or DNS name.')
    return value


def command_for(profile, target):
    target = target_value(profile,target)
    if profile in ('ports','services'):
        args = ['/usr/bin/nmap','--unprivileged','-sT','-n','-Pn','--top-ports','50',
                '--max-retries','1','--max-parallelism','4','--max-rate','10',
                '--host-timeout','30s','-oX','-']
        if ':' in target: args.append('-6')
        if profile == 'services': args += ['-sV','--version-light']
        return args+[target], 40
    if profile == 'ping': return ['/usr/bin/ping','-n','-c','3','-W','2',target], 10
    if profile == 'route': return ['/usr/bin/tracepath','-n','-m','8',target], 25
    try: ipaddress.ip_address(target); reverse=True
    except ValueError: reverse=False
    return ['/usr/bin/dig','+time=2','+tries=1','+short']+(['-x',target] if reverse else [target]), 8


def nmap_result(raw):
    if len(raw)>MAX_OUTPUT or b'<!ENTITY' in raw: raise ValueError('Scan report is too large or invalid.')
    root = ET.fromstring(raw)
    if root.tag != 'nmaprun': raise ValueError('Invalid Nmap report.')
    rows=[]
    for port in root.findall('./host/ports/port')[:128]:
        state=port.find('state'); service=port.find('service')
        rows.append(dict(port=int(port.attrib['portid']), protocol=clean(port.get('protocol'),8),
                         state=clean(state.get('state') if state is not None else 'unknown',16),
                         service=clean(service.get('name','') if service is not None else '',32),
                         reported=clean(' '.join(service.get(k,'') for k in ('product','version','extrainfo')).strip()
                                        if service is not None else '',160)))
    summary = [dict(state=clean(e.get('state'),16),count=int(e.get('count','0')))
               for e in root.findall('./host/ports/extraports')[:8]]
    finished=root.find('./runstats/finished')
    if finished is None or finished.get('exit') != 'success': raise ValueError('Nmap did not finish this scan.')
    lines=[str(s['count'])+' ports '+s['state'] for s in summary]
    lines += [f"{r['port']}/{r['protocol']}  {r['state']}  {r['service']} {r['reported']}".strip() for r in rows]
    return dict(ports=rows,summary=summary,lines=lines or ['No port results returned; the target may not have responded.'])


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try: process.wait(timeout=1)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=1)


def run_tool(profile, target, cancel, spawn=subprocess.Popen):
    args, seconds = command_for(profile,target)
    # File output cannot deadlock a pipe and is capped while the child runs.
    with tempfile.TemporaryFile() as output:
        try:
            child=spawn(args,stdout=output,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,
                        user=65534,group=65534,extra_groups=[],start_new_session=True)
        except FileNotFoundError: raise ValueError('This tool is not installed in the image.')
        deadline=time.monotonic()+seconds
        try:
            while child.poll() is None:
                if cancel.wait(.1): raise InterruptedError('Cancelled')
                if time.monotonic()>=deadline: raise TimeoutError('Tool timed out.')
                if os.fstat(output.fileno()).st_size>MAX_OUTPUT: raise ValueError('Tool output limit reached.')
            if cancel.is_set(): raise InterruptedError('Cancelled')
            output.seek(0); raw=output.read(MAX_OUTPUT+1)
            if len(raw)>MAX_OUTPUT: raise ValueError('Tool output limit reached.')
            if profile in ('ports','services'):
                if child.returncode: raise ValueError(clean(raw.decode(errors='replace'),180))
                return nmap_result(raw)
            lines=[clean(line,180) for line in raw.decode(errors='replace').splitlines()][:128]
            return dict(lines=lines or ['No answer returned.'],exitCode=child.returncode)
        finally: stop_process(child)


class Radios:
    """One private D-Bus connection, used only by the observation job thread."""
    def __init__(self):
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
        from gi.repository import GLib
        self.dbus=dbus; self.context=GLib.MainContext.default()
        self.bus=dbus.bus.BusConnection(dbus.bus.BUS_SYSTEM,mainloop=DBusGMainLoop())
        self.bt_seen={}; self.bt_session=None
        self.matches=[self.bus.add_signal_receiver(self.changed,signal_name='PropertiesChanged',
                         dbus_interface='org.freedesktop.DBus.Properties',bus_name='org.bluez',path_keyword='path'),
                      self.bus.add_signal_receiver(self.added,signal_name='InterfacesAdded',
                         dbus_interface='org.freedesktop.DBus.ObjectManager',bus_name='org.bluez')]

    def call(self, service, path, interface, method, *args):
        proxy=self.bus.get_object(service,path,introspect=False)
        return getattr(self.dbus.Interface(proxy,interface),method)(*args,timeout=1)

    def props(self,service,path,interface):
        return self.call(service,path,'org.freedesktop.DBus.Properties','GetAll',interface)

    def changed(self,interface,values,invalidated,path=None):
        if interface=='org.bluez.Device1' and any(k in values for k in ('RSSI','ManufacturerData','ServiceData')):
            self.record_seen(path)

    def record_seen(self,path):
        self.bt_seen[str(path)]=time.monotonic()
        while len(self.bt_seen)>128: self.bt_seen.pop(next(iter(self.bt_seen)))

    def added(self,path,interfaces):
        if 'org.bluez.Device1' in interfaces: self.record_seen(path)

    def wifi(self, rescan=False):
        from guide_wifi_discovery import NM, BASE, network_row
        manager=self.props(NM,BASE,NM)
        if not manager.get('WirelessHardwareEnabled'): return [],'Wi-Fi blocked by hardware'
        if not manager.get('WirelessEnabled'): return [],'Wi-Fi is off'
        devices=[]
        for path in self.call(NM,BASE,NM,'GetDevices'):
            if int(self.props(NM,path,NM+'.Device').get('DeviceType',0))==2: devices.append(path)
        if not devices: return [],'No Wi-Fi adapter detected'
        note='Wi-Fi observations'
        if rescan:
            try:
                busy=json.loads(Path('/run/guideos-wifi/status.json').read_text()).get('busy',False)
            except (OSError,ValueError): busy=False
            if busy: note='Wi-Fi is busy; showing previous observations'
            else:
                for path in devices:
                    try: self.call(NM,path,NM+'.Device.Wireless','RequestScan',self.dbus.Dictionary({},signature='sv'))
                    except self.dbus.DBusException: note='Scan unavailable; showing previous observations'
        return self._wifi_rows(devices,network_row),note

    def _wifi_rows(self,devices,network_row):
        from guide_wifi_discovery import NM
        rows=[]; until=time.monotonic()+3
        for path in devices:
            for ap in self.call(NM,path,NM+'.Device.Wireless','GetAllAccessPoints'):
                if len(rows)>=MAX_ROWS or time.monotonic()>=until: break
                p=self.props(NM,ap,NM+'.AccessPoint'); row=network_row(p)
                address=clean(p.get('HwAddress',''),32); frequency=int(p.get('Frequency',0))
                last=int(p.get('LastSeen',-1)); now=time.monotonic()
                seen=None if last<0 else now-max(0,time.clock_gettime(time.CLOCK_BOOTTIME)-last)
                row.update(id='wifi:'+address if address else 'wifi:'+str(ap),kind='wifi',name=clean(row.pop('ssid')),
                    address=address,frequency=frequency,channel=channel(frequency),seen=seen,unit='%',
                    signal=0 if seen is None else row['signal'])
                rows.append(row)
        return sorted(rows,key=lambda r:(r['seen'] is None,-r['signal'],r['name']))

    def bluetooth_start(self,power=False):
        values=self.call('org.bluez','/','org.freedesktop.DBus.ObjectManager','GetManagedObjects')
        adapters=[(p,v['org.bluez.Adapter1']) for p,v in values.items() if 'org.bluez.Adapter1' in v]
        if not adapters: return 'No Bluetooth adapter detected'
        path,properties=adapters[0]
        if not properties.get('Powered'):
            if not power: return 'Bluetooth is off; choose Enable Bluetooth and scan'
            self.call('org.bluez',path,'org.freedesktop.DBus.Properties','Set','org.bluez.Adapter1','Powered',self.dbus.Boolean(True))
        self.call('org.bluez',path,'org.bluez.Adapter1','SetDiscoveryFilter',
                  self.dbus.Dictionary({'Transport':self.dbus.String('auto'),'RSSI':self.dbus.Int16(-127),
                                        'DuplicateData':self.dbus.Boolean(True)},signature='sv'))
        self.call('org.bluez',path,'org.bluez.Adapter1','StartDiscovery')
        self.bt_session=path
        return 'Bluetooth discovery'

    def bluetooth(self):
        for _ in range(128):
            if not self.context.pending(): break
            self.context.iteration(False)
        values=self.call('org.bluez','/','org.freedesktop.DBus.ObjectManager','GetManagedObjects')
        rows=[]
        for path,value in values.items():
            p=value.get('org.bluez.Device1')
            if p is None: continue
            rows.append(dict(id='bt:'+str(path),kind='bluetooth',name=clean(p.get('Alias',p.get('Name','Unnamed device'))),
                type=clean(p.get('Icon','Unknown device type'),40).replace('-',' '),
                address=clean(p.get('Address',''),32),addressType=clean(p.get('AddressType',''),16),
                deviceClass=int(p.get('Class',0)),appearance=int(p.get('Appearance',0)),
                services=[clean(v,40) for v in p.get('UUIDs',[])][:16],
                manufacturers=[int(v) for v in p.get('ManufacturerData',{})][:8],
                paired=bool(p.get('Paired')),connected=bool(p.get('Connected')),
                signal=int(p['RSSI']) if 'RSSI' in p else None,unit='dBm',seen=self.bt_seen.get(str(path))))
        return sorted(rows,key=lambda r:(r['seen'] is None,-(r['signal'] if r['signal'] is not None else -128),r['name']))[:MAX_ROWS]

    def close(self):
        try:
            if self.bt_session: self.call('org.bluez',self.bt_session,'org.bluez.Adapter1','StopDiscovery')
        finally:
            for match in self.matches: match.remove()
            self.bus.close()


class Provider:
    def __init__(self, radios=Radios, tool=run_tool):
        self.radios,self.tool=radios,tool
        self.lock=threading.Lock(); self.cancel=threading.Event(); self.thread=None
        self.pending=None
        self.active=False; self.last_contact=time.monotonic()
        self.state=dict(generation=0,busy=False,operation='',message='Choose a survey or tool.',rows=[],history=[],result={},token='')

    def update(self, **values):
        with self.lock:
            self.state.update(values); self.state['generation']+=1

    def snapshot(self):
        with self.lock: value=copy.deepcopy(self.state)
        value['observed']=time.monotonic(); return value

    def command(self, request):
        action=request.get('action')
        if action=='keepalive': self.last_contact=time.monotonic(); return
        if action=='cancel': self.cancel.set(); self.pending=None; self.active=False; return
        if action not in ('survey','watch','tool'): raise ValueError('Unknown action.')
        kind=request.get('kind','wifi')
        if action != 'tool' and kind not in ('wifi','bluetooth'): raise ValueError('Choose Wi-Fi or Bluetooth.')
        if action=='watch' and (not isinstance(request.get('id'),str) or len(request['id'])>180): raise ValueError('Select an observation.')
        if action=='tool': request=dict(request,target=target_value(request.get('profile'),request.get('target')))
        if self.thread is not None and self.thread.is_alive():
            self.pending=dict(request); self.cancel.set(); self.last_contact=time.monotonic()
            self.update(message='Switching operations...',token=clean(request.get('token',''),40))
            return
        self.cancel=threading.Event(); self.last_contact=time.monotonic(); self.active=True
        self.update(busy=True,operation=action,message='Working...',history=[],result={},token=clean(request.get('token',''),40))
        self.thread=threading.Thread(target=self.work,args=(dict(request),),daemon=True); self.thread.start()

    def work(self, request):
        radio=None
        try:
            if request['action']=='tool':
                result=self.tool(request['profile'],request['target'],self.cancel)
                self.update(result=result,message='Finished: '+PROFILES[request['profile']]); return
            radio=self.radios(); kind=request.get('kind','wifi')
            note=radio.bluetooth_start(power=request.get('power') is True) if kind=='bluetooth' else 'Wi-Fi survey'
            if kind=='bluetooth' and not radio.bt_session:
                self.update(rows=radio.bluetooth(),message=note); return
            deadline=time.monotonic()+(60 if request['action']=='watch' else 20 if kind=='bluetooth' else 8)
            rows=[]; history=[]; sampled=None; next_scan=0
            while not self.cancel.is_set() and time.monotonic()<deadline:
                now=time.monotonic()
                if now-self.last_contact>5: raise InterruptedError('Stopped after leaving the page.')
                if kind=='wifi':
                    rows,note=radio.wifi(rescan=now>=next_scan); next_scan=now+10 if now>=next_scan else next_scan
                else: rows=radio.bluetooth()
                if request['action']=='watch':
                    row=next((r for r in rows if r['id']==request['id']),None)
                    if row and row['seen'] is not None and row['seen'] != sampled and row['signal'] is not None:
                        sampled=row['seen']; history.append(dict(at=sampled,value=row['signal'],unit=row['unit']))
                        history=history[-60:]
                self.update(rows=rows,history=history,message=note)
                self.cancel.wait(1)
            self.update(message='Stopped.' if self.cancel.is_set() else 'Survey complete.' if request['action']=='survey' else 'Signal watch complete.')
        except InterruptedError: self.update(message='Cancelled.')
        except (Exception,) as error: self.update(message=clean(str(error),180) or 'Observation unavailable.')
        finally:
            if radio:
                try: radio.close()
                except Exception: self.update(message='Bluetooth discovery cleanup failed; check adapter state.')
            self.update(busy=False); self.active=False

    def close(self):
        self.cancel.set(); self.pending=None
        if self.thread: self.thread.join(timeout=4)

    def tick(self):
        if time.monotonic()-self.last_contact>5:
            self.cancel.set(); self.pending=None
        elif self.pending is not None and (self.thread is None or not self.thread.is_alive()):
            request=self.pending; self.pending=None; self.command(request)


def main(runtime=RUNTIME):
    runtime=Path(runtime); runtime.mkdir(mode=0o700,parents=True,exist_ok=True)
    control=runtime/'control.sock'; control.unlink(missing_ok=True)
    stop=threading.Event(); provider=Provider()
    for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig,lambda *_:stop.set())
    with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as server:
        server.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,1); server.bind(str(control)); control.chmod(0o600)
        try:
            while not stop.is_set():
                provider.tick()
                if select.select([server],[],[],.2)[0]:
                    raw,ancillary,flags,_=server.recvmsg(2048,socket.CMSG_SPACE(struct.calcsize('3i')))
                    uid=None
                    for level,kind,data in ancillary:
                        if level==socket.SOL_SOCKET and kind==socket.SCM_CREDENTIALS: _,uid,_=struct.unpack('3i',data)
                    if uid!=0 or flags & (socket.MSG_TRUNC|socket.MSG_CTRUNC): continue
                    try: provider.command(json.loads(raw))
                    except (ValueError,TypeError,KeyError,AttributeError) as error: provider.update(message=clean(str(error),180))
                raw=json.dumps(provider.snapshot(),ensure_ascii=True).encode()
                if len(raw)>MAX_OUTPUT: raise ValueError('Observation snapshot limit reached.')
                temporary=runtime/'status.tmp'; temporary.write_bytes(raw); temporary.chmod(0o600)
                temporary.replace(runtime/'status.json')
        finally: provider.close(); control.unlink(missing_ok=True)


if __name__=='__main__': main()
