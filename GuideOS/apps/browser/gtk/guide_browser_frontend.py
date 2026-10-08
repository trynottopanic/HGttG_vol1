"""Import into the trusted shell; never import into a webpage process.

The GUI grants the exclusive display lease before start and keeps polling input.
Pass RG35XX H normalized stick samples and ordinary key events to input().
"""
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

UNIT = 'guide-browser.service'
CONTROL = '/run/guideos-browser/control.sock'


def request(action, **values):
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as conn:
        conn.settimeout(.25)
        conn.connect(CONTROL)
        payload = json.dumps(dict(action=action, **values)).encode()
        if len(payload) > 8192:
            raise ValueError('Browser request is too large')
        conn.sendall(payload)
        raw, _anc, flags, _addr = conn.recvmsg(8192)
        if flags & socket.MSG_TRUNC:
            raise ValueError('Browser response is too large')
        return json.loads(raw)


class Controller:
    """Translate shell-owned controls into a normal compositor mouse/keyboard."""
    def __init__(self):
        from evdev import UInput, ecodes as E
        candidate = Path('/usr/lib/guideos/input')
        if not candidate.exists():
            candidate = Path(__file__).resolve().parents[3] / 'package/guide-input'
        if str(candidate) not in sys.path: sys.path.insert(0, str(candidate))
        from guide_pointer_input import PointerController
        self.E = E
        self.keys = {305:E.BTN_LEFT, 304:E.KEY_ESC, 307:E.KEY_F6, 308:E.KEY_F4,
                     316:E.KEY_F10, 544:E.KEY_UP, 545:E.KEY_DOWN,
                     546:E.KEY_LEFT, 547:E.KEY_RIGHT, 312:E.KEY_PAGEUP,
                     313:E.KEY_PAGEDOWN, 310:E.KEY_TAB, 311:E.KEY_ENTER}
        self.device = UInput({E.EV_KEY:sorted(set(range(1,256)) | set(self.keys.values())),
                             E.EV_REL:[E.REL_X,E.REL_Y]}, name='Guide Browser Controls')
        self.pointer = PointerController(width=100000, height=100000)
        self.position = self.pointer.position
        self.held = set()
        self.generation = None

    def release(self):
        for key in self.held:
            self.device.write(self.E.EV_KEY, key, 0)
        self.device.syn()
        self.held.clear()

    def input(self, code=None, value=0, sticks=None):
        if sticks is not None:
            if self.generation != sticks.get('generation'):
                self.release()
                self.generation = sticks.get('generation')
            self.pointer.update(left=sticks.get('left'), generation=self.generation)
            x,y = self.pointer.position
            dx,dy = round(x-self.position[0]),round(y-self.position[1])
            if dx or dy:
                self.device.write(self.E.EV_REL, self.E.REL_X, dx)
                self.device.write(self.E.EV_REL, self.E.REL_Y, dy)
                self.position = self.position[0]+dx,self.position[1]+dy
                self.device.syn()
        elif code in self.keys and value in (0,1,2):
            key = self.keys[code]
            if value: self.held.add(key)
            else: self.held.discard(key)
            self.device.write(self.E.EV_KEY, key, value)
            self.device.syn()

    def close(self):
        self.release()
        self.device.close()


class BrowserSession:
    """Bounded start/stop with a display lease held through complete unit exit.

pause_display must reject video, editors, updates or other display owners.
resume_display must invalidate/redraw Home and reset held input state.
Neither callback may silently discard work. Power/volume remain shell-owned.
"""
    def __init__(self, pause_display, resume_display, probe_display=False, *, executor=None, admission=None, released=None):
        self.pause_display,self.resume_display=pause_display,resume_display
        self.probe_display=probe_display
        self.state='idle';self.controller=None;self.next_poll=0
        self.detail='';self.info={};self.address=None
        self.executor=executor or ThreadPoolExecutor(max_workers=1,thread_name_prefix='guide-browser-observer')
        self.job=None;self.job_kind=None;self.generation=0;self.leased=False
        self.stop_sent=False;self.deadline=0
        self.attempt_observed=0
        self.keyboard_events=[]
        self.last_neutral = None
        self.keyboard_sequence = 0
        self.admission=admission;self.released=released
        if probe_display and admission is None:
            sys.path.insert(0, '/usr/lib/guideos/resources')
            from resource_host import browser_admission, browser_empty
            self.admission=browser_admission;self.released=browser_empty

    def _check(self):
        if self.admission:self.admission()
        return self._active()

    def _submit(self,kind,work):
        if self.job is not None:raise RuntimeError('Browser observation already pending')
        self.job_kind=kind;self.job_generation=self.generation
        self.job=self.executor.submit(work)

    @staticmethod
    def _active():
        result=subprocess.run(['systemctl','is-active',UNIT],capture_output=True,timeout=2)
        return result.stdout.strip().decode()

    def start(self,address=None):
        if self.state!='idle' or self.job is not None:return False
        if address is not None:
            from urllib.parse import urlsplit
            parsed=urlsplit(address)
            if parsed.scheme not in ('http','https') or not parsed.hostname or len(address)>4096:
                raise ValueError('Expected an HTTP or HTTPS address')
        if self.probe_display:
            from guide_browser_drm import find_display_card
            find_display_card()
        self.generation+=1;self.detail='';self.address=address;self.info={}
        self.attempt_observed=time.monotonic()
        self.state='checking';self.deadline=time.monotonic()+25;self.stop_sent=False
        self._submit('check',self._check)
        return True

    def _begin(self):
        # Only this shell thread may acquire DRM or create/release uinput.
        if not self.pause_display():self.state='idle';self.detail=self.detail or 'Display unavailable';return
        self.leased=True;self.state='starting'
        try:self.controller=Controller()
        except Exception as error:
            self.detail='Browser controls unavailable: '+type(error).__name__
            self.close();return
        self._submit('start',lambda:subprocess.run(['systemctl','start','--no-block',UNIT],check=True,timeout=2))

    @staticmethod
    def _observe(with_status,address,released=None,keyboard_packet=None):
        if with_status and keyboard_packet and address is None:
            # The private response provides current keyboard focus. Its token
            # is checked by Browser; no systemctl fork per stick frame.
            try:return 'active',request('keyboard-input',**keyboard_packet),False
            except (OSError,ValueError):pass
        active=BrowserSession._active();info=None;opened=False
        if active in ('inactive','failed','unknown') and released and not released():
            # The launcher can exit while its PAM session still owns DRM.
            active='deactivating'
        if with_status and active not in ('inactive','failed','unknown'):
            try:
                info=request('status')
                if keyboard_packet and info.get('keyboard_token')==keyboard_packet['token']:
                    info=request('keyboard-input',**keyboard_packet)
                if address:request('open',uri=address);opened=True
            except (OSError,ValueError):pass
        return active,info,opened

    def poll(self):
        if self.job is not None and self.job.done():
            job,kind,generation=self.job,self.job_kind,self.job_generation
            self.job=None;self.job_kind=None
            if generation==self.generation:
                try:result=job.result()
                except Exception as error:
                    self.detail=str(error)[:180] if kind=='check' else 'Browser observation unavailable: '+type(error).__name__
                    if kind=='check':self.state='idle'
                    elif kind in ('start','stop'):
                        self.state='stopping';self.stop_sent=False
                    # A timeout never proves that the display owner exited.
                else:
                    if kind=='check':
                        if self.state=='checking':
                            if result in ('inactive','failed','unknown'):self._begin()
                            else:self.state='idle';self.detail='Browser session already exists'
                    elif kind=='stop':self.stop_sent=True
                    elif kind=='observe':
                        active,info,opened=result
                        if active in ('inactive','failed','unknown'):
                            if self.probe_display:
                                self._resource_detail()
                            if not self.detail:self.detail='Browser stopped' if self.state!='starting' and active=='inactive' else 'Browser service failed'
                            self._restore()
                        elif self.state!='stopping' and info is not None:
                            if self.info.get('keyboard_token')!=info.get('keyboard_token'):
                                self.keyboard_events.clear()
                                self.last_neutral = None
                                if self.controller:self.controller.release()
                            self.info=info
                            if opened:self.address=None
                            if self.state=='starting':self.state='running'
        if self.state=='idle':return self.state
        if self.state in ('checking','starting') and time.monotonic()>self.deadline:
            self.detail='Browser startup timed out';self.close()
        if self.job is not None:return self.state
        if self.state=='stopping' and not self.leased:
            self._restore();return self.state
        if self.state=='stopping' and not self.stop_sent:
            self._submit('stop',lambda:subprocess.run(['systemctl','stop','--no-block',UNIT],check=True,timeout=2))
        elif time.monotonic()>=self.next_poll:
            self.next_poll=time.monotonic()+(.02 if self.keyboard_events else .5)
            packet=None
            if self.keyboard_events:
                packet=dict(token=self.info.get('keyboard_token'),events=self.keyboard_events,
                            sequence=self.keyboard_sequence)
                self.keyboard_sequence += 1
                self.keyboard_events=[]
            self._submit('observe',lambda with_status=self.state!='stopping',address=self.address,packet=packet:self._observe(with_status,address,self.released,packet))
        return self.state

    def close(self):
        if self.state=='idle':return
        self.state='stopping'
        if self.controller:self.controller.release()
        # Stop is queued ahead of the next observation, after the one in flight.
        self.stop_sent=False;self.next_poll=0

    def _restore(self):
        try:
            if self.controller:self.controller.close()
        finally:
            self.controller=None;self.state='idle';self.address=None;self.generation+=1
            if self.leased:self.leased=False;self.resume_display()

    def _resource_detail(self):
        try:
            from resource_host import bounded
            result=json.loads(bounded('/run/guideos-resources/browser-result.json',4096))
            if (result.get('unit')==UNIT and result.get('observed',0)>=self.attempt_observed
                    and result.get('reason') in ('memory pressure','memory limit')):
                self.detail='Browser closed to keep the system responsive: '+result['reason']+'.'
        except (OSError,ValueError,TypeError):pass

    def shutdown(self):
        self.executor.shutdown(wait=True,cancel_futures=True)

    def input(self, **event):
        if self.state == 'running' and self.controller:
            if self.info.get('keyboard') and (event.get('sticks') is not None or
                    event.get('code') in (544,545,546,547,305,304,307,308,317,318,310,311)):
                # Preserve every RS neutral transition; never coalesce a hold
                # and release into a different gesture. Keep waits on observer.
                if event.get('code') == 304 and event.get('value') == 1:
                    # Owner cancellation supersedes queued edits/repeats.
                    self.keyboard_events = [event]
                    self.last_neutral = None
                    self.next_poll = 0
                    return
                sticks = event.get('sticks')
                if sticks is not None:
                    neutral = all(sticks.get(name) is None or
                                  all(abs(part) <= .01 for part in sticks.get(name))
                                  for name in ('left','right'))
                    signature = (self.info.get('keyboard_token'), sticks.get('generation'),
                                 tuple(sticks.get('left') or ()), tuple(sticks.get('right') or ()))
                    if neutral and self.last_neutral == signature: return
                    self.last_neutral = signature if neutral else None
                if len(self.keyboard_events)<32:self.keyboard_events.append(event)
                else:
                    self.keyboard_events=[]
                    self.keyboard_events.append(dict(sticks=dict(left=None,right=None,generation=0)))
                    self.detail='Keyboard input fell behind; release the controls and retry.'
                self.next_poll=0
                return
            self.controller.input(**event)
