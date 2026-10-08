"""Resident input owner and diagnostic overlay, outside the frozen shell."""
import argparse
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import struct
import time
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from control_core import Chord,Foreground,START,SELECT,deployment_guard
from control_recovery import OverlayLease, recovery_workloads, force_home, crash_recover
from resource_host import atomic, bounded
from guide_platform_rg35xxh import DeckInputs,Framebuffer,EV_KEY
from guide_telemetry import emit

RUNTIME=Path('/run/guideos-control')
MARKER=RUNTIME/'paused.json'
A,B=305,304


def recover():
    if MARKER.exists():
        crash_recover(MARKER)


class Control:
    def __init__(self,inputs=None,foreground=None,framebuffer_factory=Framebuffer):
        self.inputs=inputs if inputs is not None else DeckInputs()
        self.foreground=foreground or Foreground()
        self.framebuffer_factory=framebuffer_factory
        self.chord=Chord()
        self.chord_pending=[]
        self.chord_deadline=0
        self.chord_consumed=False
        self.selector=selectors.DefaultSelector()
        self.client=None
        self.framebuffer=self.background=self.view=None
        self.active=False
        self.pending_open=False
        self.deploy_lock=None
        self.page=0
        self.generation=0
        self.blocked=set()
        self.next_draw=0
        self.next_probe=time.monotonic()+5
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='guide-recovery')
        self.job=None;self.job_kind=None;self.preparing=False
        self.lease=None;self.ack=threading.Event();self.prepare_token=0
        self.workloads=[];self.confirm_close=False;self.notice=''
        self.force_failed=False;self.force_records=[]
        self.next_workloads=0
        self.pending_action=None
        # Load fonts before an overloaded page can consume the remaining RAM.
        from control_view import View
        self.warm_view=View(None)
        self.register_inputs()
        self.server=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        path=RUNTIME/'input.sock'
        path.unlink(missing_ok=True)
        self.server.bind(str(path))
        os.chmod(path,0o600)
        self.server.listen(2)
        self.server.setblocking(False)
        self.selector.register(self.server,selectors.EVENT_READ,'accept')
        self.status()

    def register_inputs(self):
        for device in self.inputs.devices:
            if device.connected:self.selector.register(device.fd,selectors.EVENT_READ,'input')

    def status(self):
        temporary=RUNTIME/'status.tmp'
        temporary.write_text(json.dumps(dict(active=self.active,observed=time.monotonic(),
            pending=self.pending_open,
            recovery_phase=self.job_kind,recovery_failed=self.force_failed,
            foreground=self.foreground.unit,connected=bool(self.client),page=self.page,
            input_devices=len([d for d in self.inputs.devices if d.connected]))))
        temporary.replace(RUNTIME/'status.json')

    def disconnect(self):
        if self.client:
            try:self.selector.unregister(self.client)
            except (KeyError,ValueError):pass
            self.client.close()
            self.client=None

    def send(self,packet):
        if not self.client:return
        try:self.client.send(json.dumps(packet,separators=(',',':')).encode())
        except OSError:self.disconnect()

    def accept(self):
        connection,_=self.server.accept()
        pid,uid,_gid=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        if uid!=0 or not self.foreground.owns(pid) or self.active:
            connection.close()
            return
        self.disconnect()
        self.client=connection
        connection.setblocking(False)
        self.selector.register(connection,selectors.EVENT_READ,'client')
        self.generation+=1
        self.send(dict(type='reset',devices=[d.name for d in self.inputs.devices if d.connected],
            snapshot=dict(left=None,right=None,generation=self.generation,right_click=False)))
        self.status()

    def open(self):
        if not self.client or self.foreground.frozen() or self.job is not None:return
        try:self.deploy_lock=deployment_guard()
        except (OSError,ValueError):
            if not self.pending_open:emit('CONTROL_DEFERRED')
            self.pending_open=True
            self.status()
            return
        self.pending_open=False
        self.open_started=time.monotonic()
        self.lease=OverlayLease(self.foreground)
        self.ack.clear();self.prepare_token+=1;self.preparing=True
        self.notice='';self.confirm_close=False
        self.force_failed=False;self.force_records=[]
        self.checkpoint(1,None)
        self.send(dict(type='overlay',token=self.prepare_token))
        self._submit('prepare',lambda:self.lease.prepare(self.ack,self.checkpoint))
        self.status()

    def _submit(self,kind,work):
        if self.job is not None:raise RuntimeError('Recovery already pending')
        self.job_kind=kind;self.job=self.executor.submit(work)

    def checkpoint(self,original,browser_inode,home=False):
        atomic(MARKER,dict(unit=self.foreground.unit,original=original,
                          browser_inode=browser_inode,home=home))

    def receive(self):
        if not self.client:return
        try:
            raw=self.client.recv(1025)
            packet=json.loads(raw)
            if len(raw)>1024:raise ValueError('Oversized acknowledgement')
            if (self.preparing and packet.get('type')=='display-yielded' and
                    packet.get('token')==self.prepare_token):self.ack.set()
            else:raise ValueError('Unexpected foreground request')
        except (OSError,ValueError,TypeError):self.disconnect()

    def poll_recovery(self):
        if self.job is not None and self.job.done():
            job,kind=self.job,self.job_kind
            self.job=None;self.job_kind=None
            try:result=job.result()
            except Exception as error:
                self.notice=str(error)[:150]
                name=type(error).__name__
                emit('CONTROL_ERROR',phase=kind,
                     backend_error=name if name in ('ValueError','TimeoutError','FileNotFoundError','RuntimeError','OSError') else 'other',
                     error_number=getattr(error,'errno',None))
                if kind=='prepare':
                    self.preparing=False
                    self._submit('release',lambda:self.lease.release())
                elif kind=='workloads':
                    action=self.pending_action;self.pending_action=None
                    if action=='resume':self.resume()
                elif kind=='release':
                    # Restart through ExecStopPost recovery instead of leaving
                    # the resident input owner alive with no usable display.
                    raise RuntimeError('Overlay release failed; recovering control service') from error
                elif kind=='force':
                    # A failed close may already have stopped Home. Keep the
                    # resident display and inputs until a retry proves release.
                    self.force_failed=True
                    self.page=2
                    self.notice='Recovery incomplete. A: retry close + Home.'
                self.next_draw=0
            else:
                if kind=='prepare':
                    self.preparing=False
                    self.checkpoint(result,self.lease.browser_inode)
                    self.disconnect()
                    try:
                        self.framebuffer=self.framebuffer_factory()
                        self.background=None;self.view=self.warm_view
                        self.active=True;self.next_draw=0
                        self.draw()
                        emit('CONTROL_OPEN',elapsed_ms=(time.monotonic()-self.open_started)*1000)
                    except Exception:
                        self.resume(restore=False)
                elif kind=='workloads':
                    self.workloads=result;self.next_draw=0
                    action=self.pending_action;self.pending_action=None
                    if action=='resume':self.resume()
                    elif action=='force':self.start_force()
                elif kind=='force':
                    self.force_failed=False;self.force_records=[]
                    self.notice=result
                    self.checkpoint(1,None,home=True)
                    self.resume(restore=False,home=True)
                elif kind=='release':
                    MARKER.unlink(missing_ok=True)
                    self.active=False;self.preparing=False;self.lease=None
                    if self.deploy_lock:self.deploy_lock.close()
                    self.deploy_lock=None;self.disconnect()
                    self.blocked={code for d in self.inputs.devices for code,held in d.keys.items() if held}
                    emit('CONTROL_CLOSE')
                self.status()
        if self.active and self.job is None and time.monotonic()>=self.next_workloads:
            self.next_workloads=time.monotonic()+2
            self._submit('workloads',recovery_workloads)

    def resume(self,restore=True,home=False):
        if getattr(self,'force_failed',False) and not home:
            self.notice='Recovery incomplete. A: retry close + Home.'
            self.page=2;self.next_draw=0
            return
        if getattr(self,'lease',None) is not None:
            if self.job is not None:return
            if self.framebuffer:self.framebuffer.close()
            self.framebuffer=self.background=self.view=None
            self.active=False;self.preparing=True
            self._submit('release',lambda:self.lease.release(home=home))
            return
        started=time.monotonic()
        try:
            if self.framebuffer:
                try:
                    if restore and self.background is not None and self.foreground.frozen():
                        self.framebuffer.show(self.background)
                finally:self.framebuffer.close()
        finally:
            self.framebuffer=self.background=self.view=None
            if MARKER.exists():
                self.foreground.thaw()
                MARKER.unlink(missing_ok=True)
            self.active=False
            if self.deploy_lock:self.deploy_lock.close()
            self.deploy_lock=None
            self.blocked={code for d in self.inputs.devices for code,held in d.keys.items() if held}
            self.disconnect()
            emit('CONTROL_CLOSE',elapsed_ms=(time.monotonic()-started)*1000)
            self.status()

    def draw(self):
        if not self.active:return
        if not self.foreground.frozen() and self.job_kind!='force' and not self.force_failed:
            self.resume(restore=False)
            return
        try:
            path=Path('/run/guideos-diagnostics/status.json')
            status=json.loads(bounded(path,512*1024))
        except (OSError,ValueError):status={}
        status=dict(status,workloads=self.workloads,confirm_close=self.confirm_close,
                    recovery_notice=self.notice,recovery_busy=self.job_kind=='force',
                    recovery_failed=self.force_failed)
        self.framebuffer.show(self.view.render(status,self.page))
        self.next_draw=time.monotonic()+(.05 if self.view.statusbar.volume_alpha() else 1)
        self.status()

    def start_force(self):
        records=list(self.force_records if self.force_failed else self.workloads)
        self.force_records=records
        self.confirm_close=False
        self.notice='Closing active applications…'
        self._submit('force',lambda:force_home(records))

    def volume(self,code):
        try:
            status=json.loads(bounded('/run/guideos-audio/status.json',128*1024))
            if not 0<=time.monotonic()-status['observed']<=12:raise ValueError('Stale audio status')
            value=max(0,min(100,status['volume']+(-5 if code==114 else 5)))
            with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as connection:
                connection.settimeout(.03)
                connection.sendto(json.dumps(dict(action='volume',value=value,token=uuid.uuid4().hex)).encode(),
                                  '/run/guideos-audio/control.sock')
        except (OSError,ValueError,KeyError,TypeError):self.notice='Volume service unavailable'
        self.next_draw=0

    def route_chord_event(self,event,now):
        """Delay a lone Select/Start just long enough to distinguish the chord."""
        name,kind,code,value=event
        if kind!=EV_KEY or name!='H700 Gamepad' or code not in (START,SELECT):
            return [event],False
        triggered=self.chord.update(code,value)
        if self.chord_consumed:
            if not self.chord.held:self.chord_consumed=False
            return [],False
        if triggered:
            self.chord_pending.clear();self.chord_deadline=0;self.chord_consumed=True
            return [],True
        self.chord_pending.append(event)
        if not self.chord_deadline:self.chord_deadline=now+.12
        if value==0 and not self.chord.held:
            ready=self.chord_pending;self.chord_pending=[];self.chord_deadline=0
            return ready,False
        return [],False

    def flush_chord_events(self,now):
        if not self.chord_pending or now<self.chord_deadline:return []
        ready=self.chord_pending;self.chord_pending=[];self.chord_deadline=0
        return ready

    def events(self):
        forwarded=[]
        routed=[];open_overlay=False;now=time.monotonic()
        for event in self.inputs.poll(0):
            ready,triggered=self.route_chord_event(event,now)
            routed.extend(ready);open_overlay|=triggered
        routed.extend(self.flush_chord_events(now))
        if open_overlay and not self.preparing:
            if self.active and self.job is None:self.resume()
            elif self.active and self.job_kind=='workloads':self.pending_action='resume'
            elif self.pending_open:
                self.pending_open=False
                self.status()
            else:self.open()
        for event in routed:
            name,kind,code,value=event
            if code in self.blocked and kind==EV_KEY:
                if value==0:self.blocked.discard(code)
                continue
            if self.active:
                if kind==EV_KEY and value==1:
                    if code in (114,115):self.volume(code)
                    elif code in (546,547):
                        self.page=(self.page+(1 if code==547 else -1))%3
                        self.confirm_close=False
                        self.next_draw=0
                    elif code==B:
                        if self.confirm_close:self.confirm_close=False;self.next_draw=0
                        elif self.job is None:self.resume()
                        elif self.job_kind=='workloads':self.pending_action='resume'
                    elif code==A and self.page==2 and self.job_kind!='force':
                        if self.confirm_close:
                            if self.job is None:self.start_force()
                            elif self.job_kind=='workloads':self.pending_action='force'
                        else:self.confirm_close=True
                        self.next_draw=0
                continue
            if self.preparing:continue
            item=dict(values=list(event),timestamp=event.timestamp)
            if hasattr(event,'sticks'):
                item['sticks']=dict(event.sticks,generation=self.generation+event.sticks['generation'])
            forwarded.append(item)
        for offset in range(0,len(forwarded),16):
            self.send(dict(type='events',events=forwarded[offset:offset+16]))

    def tick(self):
        self.poll_recovery()
        now=time.monotonic()
        deadline=min(self.next_probe,self.next_draw if self.active else now+5)
        if self.pending_open:deadline=min(deadline,now+.5)
        if self.job is not None or self.preparing:deadline=min(deadline,now+.02)
        if self.chord_pending:deadline=min(deadline,self.chord_deadline)
        for key,_mask in self.selector.select(max(0,deadline-now)):
            if key.data=='accept':self.accept()
            elif key.data=='client':self.receive()
            elif key.data=='input':self.events()
        if self.chord_pending and time.monotonic()>=self.chord_deadline:self.events()
        if self.active and time.monotonic()>=self.next_draw:self.draw()
        if self.pending_open:self.open()
        if time.monotonic()>=self.next_probe:
            # Reopen only after disconnection; no recurring device enumeration
            # while the established input devices are healthy.
            if not self.inputs.devices or not all(d.connected for d in self.inputs.devices):
                for d in self.inputs.devices:
                    try:self.selector.unregister(d.fd)
                    except (KeyError,ValueError):pass
                self.inputs.close()
                self.inputs=DeckInputs()
                self.chord=Chord()
                self.generation+=1
                self.register_inputs()
                self.disconnect()
            self.next_probe=time.monotonic()+5
            self.status()

    def close(self):
        try:
            if self.job is not None:
                try:self.job.result(timeout=8)
                except Exception:pass
                self.job=None
            if self.framebuffer:self.framebuffer.close()
            if self.lease:self.lease.release()
            if MARKER.exists():recover()
        finally:
            if self.deploy_lock:self.deploy_lock.close()
            self.disconnect()
            self.inputs.close()
            self.selector.close()
            self.server.close()
            self.executor.shutdown(wait=False,cancel_futures=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--recover',action='store_true')
    args=parser.parse_args()
    recover()
    if args.recover:return
    stopping=[]
    control=Control(framebuffer_factory=lambda:Framebuffer('/dev/tty3'))
    wake_read,wake_write=os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
    control.selector.register(wake_read,selectors.EVENT_READ,'wake')
    def stop(*_):
        stopping.append(True)
        try:os.write(wake_write,b'x')
        except OSError:pass
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop)
    try:
        while not stopping:control.tick()
    finally:
        try:control.close()
        finally:
            os.close(wake_read)
            os.close(wake_write)


if __name__=='__main__':main()
