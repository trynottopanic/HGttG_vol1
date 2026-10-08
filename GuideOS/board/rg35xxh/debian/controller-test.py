#!/usr/bin/python3
"""GuideOS guided RG35XX H input discovery. SPDX-License-Identifier: AGPL-3.0-or-later."""
import argparse
import array
import ctypes
import errno
import fcntl
import glob
import json
import math
import mmap
import os
from pathlib import Path
import select
import signal
import struct
import subprocess
import time
import wave

EV_SYN, EV_KEY, EV_ABS, EV_SW, EV_FF = 0, 1, 3, 5, 21
EXCLUDED = {315, 116, 0x198}  # Start, Power, Restart. Never map or use to navigate.
EVENT = struct.Struct('llHHi')
SESSION_SECONDS = 900
BUTTONS = ['A', 'B', 'X', 'Y', 'UP', 'RIGHT', 'DOWN', 'LEFT',
           'L1', 'R1', 'L2', 'R2', 'LEFT CLICK', 'RIGHT CLICK',
           'SELECT', 'MENU', 'VOL +', 'VOL -']
BG, PANEL, INK, MUTED, GOLD, GREEN = '#101c2c', '#203047', '#f1f5fa', '#9cacbf', '#ffd166', '#63e6b0'


def ioc(direction, number, size):
    return (direction << 30) | (size << 16) | (ord('E') << 8) | number


def read_ioctl(fd, number, size):
    buf = bytearray(size)
    fcntl.ioctl(fd, ioc(2, number, size), buf, True)
    return bytes(buf)


def bits(buf):
    return [n for n in range(len(buf)*8) if buf[n//8] & (1 << (n % 8))]


class Device:
    def __init__(self, path):
        self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        self.path = path
        self.name = read_ioctl(self.fd, 6, 256).split(b'\0')[0].decode(errors='replace')
        self.keys, self.axes, self.sw = {}, {}, {}
        self.dropped = False
        self.connected = True
        self.caps = {str(kind): bits(read_ioctl(self.fd, 0x20+kind, size))
                     for kind, size in [(0, 4), (1, 96), (3, 8), (5, 4), (21, 16)]}
        self.identity = {'path': path, 'name': self.name,
                         'id': list(struct.unpack('HHHH', read_ioctl(self.fd, 2, 8))),
                         'capabilities': self.caps}
        for code in self.caps['3']:
            value, low, high, fuzz, flat, resolution = struct.unpack('iiiiii', read_ioctl(self.fd, 0x40+code, 24))
            self.axes[code] = dict(value=value, minimum=low, maximum=high, fuzz=fuzz,
                                   flat=flat, resolution=resolution, center=value,
                                   observed_min=value, observed_max=value)
        self.identity['axes'] = self.axes
        try:
            fcntl.ioctl(self.fd, ioc(1, 0xa0, 4), struct.pack('i', 1))  # CLOCK_MONOTONIC
            self.monotonic_events=True
        except OSError:
            self.monotonic_events=False
        self.identity['monotonic_event_timestamps']=self.monotonic_events
        self.resync()

    def resync(self):
        self.keys = {code: 1 for code in bits(read_ioctl(self.fd, 0x18, 96))}
        self.sw = {code: 1 for code in bits(read_ioctl(self.fd, 0x1b, 8))}
        for code, axis in self.axes.items():
            axis['value'] = struct.unpack('iiiiii', read_ioctl(self.fd, 0x40+code, 24))[0]

    def close(self):
        try:
            fcntl.ioctl(self.fd, ioc(1, 0x90, 4), 0)  # release optional grab
        except OSError:
            pass
        os.close(self.fd)


class TimedEvent(tuple):
    def __new__(cls,values,timestamp):
        event=super().__new__(cls,values)
        event.timestamp=timestamp
        return event


class Inputs:
    def __init__(self, log):
        self.devices, self.log, self.generation = [], log, 0
        for path in sorted(glob.glob('/dev/input/event*')):
            # Never open/grab the dedicated power-key device.
            name = Path('/sys/class/input', Path(path).name, 'device/name').read_text().strip()
            if name not in ('H700 Gamepad', 'gpio-keys-volume', 'H616 Audio Codec Headphone Jack'):
                continue
            dev = Device(path)
            if name != 'H616 Audio Codec Headphone Jack':
                fcntl.ioctl(dev.fd, ioc(1, 0x90, 4), 1)
            self.devices.append(dev)

    def poll(self, delay=.05):
        live = [d for d in self.devices if d.connected]
        ready, _, _ = select.select([d.fd for d in live], [], [], delay)
        events = []
        for index, dev in enumerate(self.devices):
            if dev.fd not in ready:
                continue
            try:
                raw = os.read(dev.fd, EVENT.size*128)
                if not raw:
                    raise OSError(errno.ENODEV, 'disconnected')
            except OSError as exc:
                if exc.errno == errno.EAGAIN:
                    continue
                dev.connected = False
                self.generation += 1
                self.log.write(json.dumps({'time': time.monotonic(), 'device': index, 'disconnect': str(exc)})+'\n')
                continue
            for offset in range(0, len(raw), EVENT.size):
                sec, usec, kind, code, value = EVENT.unpack_from(raw, offset)
                event = TimedEvent((index, kind, code, value),sec+usec/1e6 if getattr(dev,'monotonic_events',False) else time.monotonic())
                self.log.write(json.dumps({'time': time.monotonic(), 'kernel_time': sec+usec/1e6,
                                          'device': index, 'type': kind, 'code': code, 'value': value})+'\n')
                if kind == EV_SYN and code == 3:
                    dev.dropped = True
                    self.generation += 1
                    continue
                if dev.dropped:
                    if kind == EV_SYN and code == 0:
                        dev.resync()
                        dev.dropped = False
                    continue
                if kind == EV_KEY:
                    dev.keys[code] = value != 0
                elif kind == EV_ABS and code in dev.axes:
                    axis = dev.axes[code]
                    axis['value'] = value
                    axis['observed_min'] = min(axis['observed_min'], value)
                    axis['observed_max'] = max(axis['observed_max'], value)
                elif kind == EV_SW:
                    dev.sw[code] = value
                events.append(event)
        return events

    def released(self):
        return all(not value for d in self.devices if d.connected for code, value in d.keys.items() if code not in EXCLUDED)

    def down(self, mapping):
        return bool(mapping and self.devices[mapping[0]].connected and self.devices[mapping[0]].keys.get(mapping[1], 0))

    def close(self):
        for dev in self.devices:
            dev.close()


class Framebuffer:
    def __init__(self):
        self.fd = os.open('/dev/fb0', os.O_RDWR)
        var = bytearray(160)
        fix = bytearray(80)
        fcntl.ioctl(self.fd, 0x4600, var, True)
        fcntl.ioctl(self.fd, 0x4602, fix, True)
        self.width, self.height, _, _, self.xoff, self.yoff, self.bpp = struct.unpack_from('7I', var)
        self.stride = struct.unpack_from('I', fix, 48)[0]
        self.length = struct.unpack_from('I', fix, 24)[0]
        self.fields = [struct.unpack_from('III', var, pos) for pos in (32, 44, 56)]
        if self.bpp not in (16, 32) or self.width < 320 or self.height < 240:
            raise RuntimeError('Unsupported framebuffer layout')
        if any(reverse for _, _, reverse in self.fields):
            raise RuntimeError('Unsupported reversed pixel channels')
        if (self.yoff+self.height)*self.stride > self.length:
            raise RuntimeError('Framebuffer bounds invalid')
        self.mem = mmap.mmap(self.fd, self.length)
        self.tty = os.open('/dev/tty1', os.O_RDWR)
        mode = array.array('i', [0])
        fcntl.ioctl(self.tty, 0x4b3b, mode, True)
        self.old_mode = mode[0]
        fcntl.ioctl(self.tty, 0x5606, 1)
        fcntl.ioctl(self.tty, 0x4b3a, 1)

    def show(self, image):
        image = image.resize((self.width, self.height))
        if self.bpp == 32 and self.fields == [(16, 8, 0), (8, 8, 0), (0, 8, 0)]:
            pixels = image.tobytes('raw', 'BGRX')
        else:
            values = array.array('H' if self.bpp == 16 else 'I',
                (sum((channel >> (8-length)) << offset for channel, (offset, length, _) in zip(rgb, self.fields))
                 for rgb in image.getdata()))
            pixels = values.tobytes()
        count = self.width*self.bpp//8
        for y in range(self.height):
            start = (y+self.yoff)*self.stride + self.xoff*self.bpp//8
            self.mem[start:start+count] = pixels[y*count:(y+1)*count]

    def close(self):
        fcntl.ioctl(self.tty, 0x4b3a, self.old_mode)
        os.close(self.tty)
        self.mem.close()
        os.close(self.fd)


class Screen:
    def __init__(self, sink):
        from PIL import Image, ImageDraw, ImageFont
        self.Image, self.Draw = Image, ImageDraw
        self.fonts = {s: ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', s)
                      for s in (14, 16, 20, 26, 30)}
        self.sink, self.completed = sink, set()
        self.remaining = SESSION_SECONDS

    def draw(self, title, instruction, detail='', target='', fraction=1, stick=None, lines=None, direction=None):
        im = self.Image.new('RGB', (640, 480), BG)
        d = self.Draw.Draw(im)
        def text(x, y, value, size=20, color=INK):
            d.text((x, y), value, font=self.fonts[size], fill=color)
        text(24, 12, 'GUIDEOS  /  CONTROLLER CHECK', 14, MUTED)
        text(475, 12, f'{max(0,math.ceil(self.remaining))}s in session', 14, MUTED)
        text(24, 38, title, 26)
        text(24, 78, instruction, 20, GOLD)
        if lines is not None:
            for n, line in enumerate(lines[:9]):
                text(28, 128+n*27, line, 16)
        elif stick is not None:
            x, y, seen = stick
            d.ellipse((204, 142, 436, 374), outline=MUTED, width=2)
            d.line((320, 146, 320, 370), fill=PANEL, width=2)
            d.line((208, 258, 432, 258), fill=PANEL, width=2)
            for i, (tx, ty) in enumerate([(418,258),(320,160),(222,258),(320,356)]):
                if direction and i != (0 if direction=='right' else 1): continue
                d.ellipse((tx-12,ty-12,tx+12,ty+12), fill=GREEN if i in seen else GOLD)
            px, py = 320+int(max(-1,min(1,x))*98), 258-int(max(-1,min(1,y))*98)
            d.ellipse((px-9,py-9,px+9,py+9), fill=INK)
        else:
            d.rounded_rectangle((56,170,584,354), radius=35, fill=PANEL, outline=MUTED, width=2)
            d.rounded_rectangle((230,201,410,296), radius=8, fill=BG)
            text(243,235,'WATCH HIGHLIGHT',14,MUTED)
            locations = {'UP':(131,212),'RIGHT':(166,246),'DOWN':(131,280),'LEFT':(96,246),
                         'A':(546,246),'B':(511,280),'X':(511,212),'Y':(476,246),
                         'LEFT CLICK':(204,318),'RIGHT CLICK':(436,318),
                         'SELECT':(276,328),'MENU':(320,181),'START':(367,328)}
            for label, (x,y) in locations.items():
                color = GOLD if label == target else GREEN if label in self.completed else MUTED
                if label == 'START':
                    color = '#546174'
                d.ellipse((x-16,y-16,x+16,y+16), fill=color)
                short = {'LEFT CLICK':'L3','RIGHT CLICK':'R3','SELECT':'SEL','MENU':'M','START':'--',
                         'UP':'U','RIGHT':'R','DOWN':'D','LEFT':'L'}.get(label,label)
                d.text((x,y),short,anchor='mm',font=self.fonts[14],fill=BG)
            for label,x in [('L2',80),('L1',170),('R1',380),('R2',470)]:
                color = GOLD if label == target else GREEN if label in self.completed else MUTED
                d.rounded_rectangle((x,132,x+70,162),radius=6,fill=color)
                d.text((x+35,147),label,anchor='mm',font=self.fonts[16],fill=BG)
            text(270,138,'TOP EDGE',14,MUTED)
            for label,y in [('VOL +',223),('VOL -',272)]:
                color = GOLD if label == target else GREEN if label in self.completed else MUTED
                d.rectangle((590,y,635,y+32),fill=color)
                d.text((612,y+16),label[-1],anchor='mm',font=self.fonts[20],fill=BG)
            text(74,366,'Front view   /   shoulder row shown above',14,MUTED)
        text(24,407,detail[:65],16, GREEN if detail.startswith('Complete') else INK)
        d.rounded_rectangle((24,439,616,447),radius=4,fill=PANEL)
        if fraction > 0:
            d.rounded_rectangle((24,439,24+int(592*min(1,fraction)),447),radius=4,fill=GOLD)
        text(24,457,'START, POWER AND RESET ARE EXCLUDED',14,MUTED)
        self.sink.show(im)


class SessionExpired(Exception):
    pass


class Test:
    def __init__(self, inputs, screen, folders):
        self.inputs, self.screen, self.folders = inputs, screen, folders
        self.started = time.monotonic()
        self.mapping, self.sticks = {}, {}
        self.audio_gain = .034
        self.results = []
        self.summary = {'version': 'guide-controller-3', 'excluded': ['Start','Power','Reset'],
                        'devices': [d.identity for d in inputs.devices], 'results': self.results,
                        'mapping': self.mapping, 'sticks': self.sticks}

    def save(self):
        self.summary['elapsed_seconds'] = time.monotonic()-self.started
        for folder in self.folders:
            temp = folder/'controller-summary.json.tmp'
            with temp.open('w') as f:
                json.dump(self.summary, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            temp.replace(folder/'controller-summary.json')
        self.inputs.log.flush()
        os.fsync(self.inputs.log.fileno())
        # Raw events are mirrored at every checkpoint, not only at shutdown.
        import shutil
        for folder in self.folders[1:]:
            shutil.copyfile(self.inputs.log.name, folder/'controller-events.jsonl')
        os.sync()

    def record(self, phase, label, outcome, **details):
        self.results.append(dict(phase=phase, label=label, outcome=outcome,
                                 end=time.monotonic(), **details))
        self.save()

    def tick(self):
        self.screen.remaining = SESSION_SECONDS-(time.monotonic()-self.started)
        if self.screen.remaining <= 0:
            raise SessionExpired()
        return self.inputs.poll()

    def hold_screen(self, title, instruction, seconds=2, **kwargs):
        start = time.monotonic()
        while time.monotonic()-start < seconds:
            self.tick()
            self.screen.draw(title, instruction, fraction=1-(time.monotonic()-start)/seconds, **kwargs)

    def neutral(self, target='', axes=False):
        start, stable = time.monotonic(), None
        while time.monotonic()-start < 5:
            self.tick()
            quiet = self.inputs.released()
            if axes:
                quiet &= all(abs(a['value']-a['center']) <= max(a['flat'], (a['maximum']-a['minimum'])*.12)
                             for d in self.inputs.devices if getattr(d,'connected',True) for a in d.axes.values())
            stable = (stable or time.monotonic()) if quiet else None
            if stable and time.monotonic()-stable > .35:
                return True
            self.screen.draw('GET READY', 'Release all controls', 'Waiting for a clean starting state', target)
        return False

    def button(self, label, exercise=False):
        phase = 'exercise' if exercise else 'discover'
        if not self.neutral(label):
            self.record(phase,label,'not observed',reason='Controls not released')
            return False
        mapping = self.mapping.get(label) if exercise else None
        if mapping and not getattr(self.inputs.devices[mapping[0]],'connected',True):
            self.record(phase,label,'unavailable',reason='Device disconnected'); return False
        if exercise and mapping and not getattr(self.inputs.devices[mapping[0]],'monotonic_events',True):
            self.record(phase,label,'unavailable',reason='Kernel event timing unavailable; hold duration cannot be trusted'); return False
        if not exercise:
            expected='gpio-keys-volume' if label.startswith('VOL') else 'H700 Gamepad'
            if not any(getattr(d,'name','H700 Gamepad')==expected and getattr(d,'connected',True) for d in self.inputs.devices):
                self.record(phase,label,'unavailable',reason='Input device absent or disconnected'); return False
        if exercise and not mapping:
            self.record(phase,label,'unavailable',reason='No discovered mapping')
            return False
        generation = self.inputs.generation
        start = time.monotonic()
        detector = ButtonTrial(mapping, list(self.mapping.values()) if not exercise else [], exercise,
                               required_taps=1 if exercise else 2)
        while time.monotonic()-start < 20:
            for event in self.tick():
                device,kind,code,value=event
                stamp=getattr(event,'timestamp',time.monotonic())
                if stamp<start: continue
                if kind == EV_KEY:
                    detector.event((device,code),value,stamp)
            if self.inputs.generation != generation:
                self.record(phase,label,'ambiguous',reason='Lost events or disconnected device')
                return False
            if detector.ambiguous:
                self.record(phase,label,'ambiguous',reason=detector.ambiguous)
                self.hold_screen('TRY AGAIN LATER', 'Only use the highlighted control', 1, target=label)
                return False
            if detector.complete:
                if not exercise:
                    self.mapping[label] = list(detector.mapping)
                    self.screen.completed.add(label)
                self.record(phase,label,'complete',mapping=list(detector.mapping),start=start,
                            transitions=detector.transitions)
                self.hold_screen(label, 'Complete - released', .45, detail='Complete', target=label)
                return True
            instruction = ('Tap the same control again to confirm' if detector.taps else 'Press once, then release') if not exercise else detector.instruction(time.monotonic())
            if not exercise and detector.down_at is not None: instruction='Press detected - let go'
            latest={r['label']:r for r in self.results if r['phase']==phase}
            completed=sum(r['outcome']=='complete' for r in latest.values())
            self.screen.draw(f'{phase.upper()}  /  {label}', instruction,
                             f'{completed} of 18 {phase} complete  |  {math.ceil(20-(time.monotonic()-start))}s left',
                             label, 1-(time.monotonic()-start)/20)
        self.record(phase,label,'not observed',start=start,transitions=detector.transitions)
        return False

    def discover_axis(self, label, direction):
        if not self.neutral(axes=True):
            self.record('axis discovery',label+direction,'not observed',reason='Not neutral')
            return None
        origin = {(i,c):a['value'] for i,d in enumerate(self.inputs.devices) for c,a in d.axes.items()}
        peaks = {key:0 for key in origin}
        start, generation = time.monotonic(), self.inputs.generation
        chosen, sign = None, 0
        while time.monotonic()-start < 12:
            self.tick()
            if generation != self.inputs.generation:
                break
            for (i,c), base in origin.items():
                axis = self.inputs.devices[i].axes[c]
                delta = (axis['value']-base)/max(1,axis['maximum']-axis['minimum'])
                if abs(delta)>abs(peaks[i,c]):
                    peaks[i,c] = delta
            ranked = sorted(peaks, key=lambda k:abs(peaks[k]), reverse=True)
            if chosen and any(abs(value)>max(.15,abs(peaks[chosen])*.55) for key,value in peaks.items() if key!=chosen):
                self.record('axis discovery',label+direction,'ambiguous',reason='Another axis moved after selection')
                return None
            if chosen is None and ranked and abs(peaks[ranked[0]]) > .28:
                if len(ranked)>1 and abs(peaks[ranked[1]]) > abs(peaks[ranked[0]])*.55:
                    self.record('axis discovery',label+direction,'ambiguous',reason='Multiple axes moved')
                    return None
                chosen = ranked[0]
                sign = 1 if peaks[chosen]>0 else -1
                used = [(a['device'],a['code']) for stick in self.sticks.values() for a in stick.values()]
                if chosen in used:
                    self.record('axis discovery',label+direction,'ambiguous',reason='Axis already mapped')
                    return None
            centered = chosen and abs(self.inputs.devices[chosen[0]].axes[chosen[1]]['value']-origin[chosen]) < max(1, (self.inputs.devices[chosen[0]].axes[chosen[1]]['maximum']-self.inputs.devices[chosen[0]].axes[chosen[1]]['minimum'])*.12)
            if centered:
                result = dict(device=chosen[0],code=chosen[1],sign=sign,center=origin[chosen])
                self.record('axis discovery',label+direction,'complete',mapping=result,start=start)
                return result
            self.screen.draw('DISCOVER  /  '+label, f'Move {direction}, then let go' if not chosen else 'Let the stick return to center',
                             'Move only the named stick in one direction', fraction=1-(time.monotonic()-start)/12,
                             stick=(0,0,set()),direction=direction)
        self.record('axis discovery',label+direction,'not observed',start=start)
        return None

    def axis_xy(self, stick):
        result=[]
        for key in ('right','up'):
            m=stick[key]
            a=self.inputs.devices[m['device']].axes[m['code']]
            result.append((a['value']-m['center'])*m['sign']/max(1,(a['maximum']-a['minimum'])/2))
        return result

    def exercise_stick(self,label):
        stick=self.sticks.get(label,{})
        if len(stick)!=2:
            self.record('stick exercise',label,'unavailable')
            return
        if not self.neutral(axes=True):
            self.record('stick exercise',label,'not observed',reason='Not neutral')
            return
        start=time.monotonic(); seen=set(); sectors=set(); centered=None
        generation=self.inputs.generation
        extremes={'x':[0,0],'y':[0,0]}
        while time.monotonic()-start<24:
            self.tick()
            if generation!=self.inputs.generation:
                break
            x,y=self.axis_xy(stick)
            for key,value in [('x',x),('y',y)]:
                extremes[key][0]=min(extremes[key][0],value); extremes[key][1]=max(extremes[key][1],value)
            for i,condition in enumerate([x>.65,y>.65,x<-.65,y<-.65]):
                if condition: seen.add(i)
            if math.hypot(x,y)>.65:
                sectors.add(int((math.atan2(y,x)+math.pi)*8/(2*math.pi))%8)
            ready=len(seen)==4 and len(sectors)==8
            centered=(centered or time.monotonic()) if ready and abs(x)<.15 and abs(y)<.15 else None
            if centered and time.monotonic()-centered>.6:
                self.record('stick exercise',label,'complete',start=start,normalized_extremes=extremes,
                            sectors=sorted(sectors),returned_center=[x,y],note='Coverage screen, not precision calibration')
                return
            self.screen.draw('EXERCISE  /  '+label, 'Slow circle around the edge, then let go',
                             'Let go and center' if ready else f'{len(seen)}/4 edges   {len(sectors)}/8 directions',
                             fraction=1-(time.monotonic()-start)/24,stick=(x,y,seen))
        self.record('stick exercise',label,'not observed',start=start,normalized_extremes=extremes,
                    sectors=sorted(sectors),reason='Incomplete coverage/center or lost events; not a hardware verdict')

    def combination(self, first, second, label):
        a,b=self.mapping.get(first),self.mapping.get(second)
        if not a or not b:
            self.record('combination',label,'unavailable'); return
        if not self.neutral():
            self.record('combination',label,'not observed',reason='Controls not released'); return
        start=time.monotonic(); overlap=False; independent=False; generation=self.inputs.generation
        av=bv=False
        while time.monotonic()-start<12:
            events=self.tick()
            if generation!=self.inputs.generation: break
            for i,t,c,v in events:
                if t!=EV_KEY or v not in (0,1): continue
                if [i,c]==a: av=bool(v)
                if [i,c]==b: bv=bool(v)
                overlap |= av and bv
                independent |= overlap and av and not bv
                if independent and not av and not bv:
                    self.record('combination',label,'complete',start=start); return
            self.screen.draw('TOGETHER  /  '+label, f'Hold {first}; tap {second}; release both',
                             'Overlap detected' if overlap else 'Waiting for both controls',target=first,
                             fraction=1-(time.monotonic()-start)/12)
        self.record('combination',label,'not observed',overlap=overlap,independent=independent)

    def stick_click(self,label):
        stick=self.sticks.get(label,{})
        click=self.mapping.get('LEFT CLICK' if label=='LEFT STICK' else 'RIGHT CLICK')
        if len(stick)!=2 or not click:
            self.record('stick click with movement',label,'unavailable'); return
        if not self.neutral(axes=True):
            self.record('stick click with movement',label,'not observed',reason='Not neutral'); return
        start=time.monotonic(); seen=False; generation=self.inputs.generation
        while time.monotonic()-start<12:
            self.tick()
            if generation!=self.inputs.generation: break
            x,y=self.axis_xy(stick)
            seen |= self.inputs.down(click) and math.hypot(x,y)>.4
            if seen and not self.inputs.down(click) and math.hypot(x,y)<.2:
                self.record('stick click with movement',label,'complete'); return
            self.screen.draw('CLICK + MOVE  /  '+label,'Hold stick click and move, then release',
                             'Now release and center' if seen else 'Press the stick down while moving it',
                             fraction=1-(time.monotonic()-start)/12,stick=(x,y,set()))
        self.record('stick click with movement',label,'not observed')

    def choice(self,title,instruction,yes='A',no='B',seconds=12,lines=None):
        self.last_choice_reason='no answer'
        if yes not in self.mapping or no not in self.mapping:
            self.last_choice_reason='navigation controls unavailable'
            return None
        if not self.neutral(): return None
        start=time.monotonic(); generation=self.inputs.generation
        while time.monotonic()-start<seconds:
            events=self.tick()
            if self.inputs.generation!=generation:
                self.last_choice_reason='input interrupted'
                return None
            for i,t,c,v in events:
                if t==EV_KEY and v==1 and c not in EXCLUDED:
                    if title=='AUDIO':
                        if self.mapping.get('VOL +')==[i,c]: self.audio_gain=min(.15,self.audio_gain+.015)
                        if self.mapping.get('VOL -')==[i,c]: self.audio_gain=max(.005,self.audio_gain-.015)
                    if self.mapping.get(yes)==[i,c]:
                        self.last_choice_reason='explicit yes'; return True
                    if self.mapping.get(no)==[i,c]:
                        self.last_choice_reason='explicit no'; return False
            body=lines or []
            if title=='AUDIO': body=body+[f'Volume +/-: test level {round(self.audio_gain/.15*100)}% of quiet range']
            self.screen.draw(title,instruction,f'{yes}: YES / RUN    {no}: NO / SKIP    Timeout: skip',
                             fraction=1-(time.monotonic()-start)/seconds,lines=body)
        return None

    def observation(self,phase,label,answer,**extra):
        outcome='user-confirmed' if answer is True else 'user-reported issue' if answer is False else 'unanswered'
        self.record(phase,label,outcome,answer=answer,answer_reason=self.last_choice_reason,**extra)

    def skipped(self,phase,label):
        self.record(phase,label,'user-skipped' if self.last_choice_reason=='explicit no' else 'unanswered',
                    answer_reason=self.last_choice_reason)

    def stage_gate(self,title):
        if not all(label in self.mapping for label in ('A','B')): return
        answer=self.choice(title,'Ready for the next stage?',seconds=30,
                           lines=['A: continue    B: pause / finish', 'No button press: save and finish.',
                                  'Controls only navigate on these menu screens.'])
        if answer is True: return
        if answer is False:
            answer=self.choice('PAUSED','Resume the test?',seconds=120,
                               lines=['A: resume    B: save and finish', 'You have up to two minutes on this screen.',
                                      'The session countdown still applies.'])
            if answer is True: return
        raise SessionExpired('finished or paused by user; partial results saved')

    def outputs(self):
        if not all(x in self.mapping for x in ('A','B')):
            self.record('outputs','optional checks','unavailable',reason='A/B navigation not discovered'); return
        if self.choice('OPTIONAL OUTPUTS','Run display, rumble and sound checks?') is not True:
            self.skipped('outputs','optional checks'); return
        # Color fields plus moving dot, rendered through the same framebuffer.
        start=time.monotonic()
        while time.monotonic()-start<3:
            self.tick()
            im=self.screen.Image.new('RGB',(640,480),BG); d=self.screen.Draw.Draw(im)
            for n,color in enumerate(['red','green','blue','white']): d.rectangle((n*160,80,(n+1)*160,350),fill=color)
            x=int((time.monotonic()-start)*150)%600
            d.ellipse((x,375,x+30,405),fill=INK)
            d.text((20,20),'DISPLAY: RED / GREEN / BLUE / WHITE',font=self.screen.fonts[20],fill=INK)
            self.screen.sink.show(im)
        answer=self.choice('DISPLAY','Were all colors and motion visible?')
        self.observation('output','display',answer)
        gamepad=next((d for d in self.inputs.devices if 80 in d.caps.get('21',[])),None)
        if not gamepad:
            self.record('output','rumble','unavailable')
        else:
            for strength,name in [(0x3000,'gentle'),(0x8000,'stronger')]:
                if self.choice('RUMBLE',f'Run a brief {name} pulse?') is not True:
                    self.skipped('output','rumble '+name); continue
                try:
                    # Linux ff_effect on 64-bit ARM/x86: union at offset 16, total 48.
                    effect=bytearray(48)
                    struct.pack_into('HhHHHHH',effect,0,80,-1,0,0,0,500,0)
                    struct.pack_into('HH',effect,16,strength,strength)
                    fcntl.ioctl(gamepad.fd,ioc(1,0x80,48),effect,True)
                    eid=struct.unpack_from('h',effect,2)[0]
                    try:
                        os.write(gamepad.fd,EVENT.pack(0,0,EV_FF,eid,1))
                        until=time.monotonic()+.6
                        while time.monotonic()<until:
                            events=self.tick()
                            self.screen.draw('RUMBLE','Brief pulse','B: STOP',lines=[])
                            if any(t==EV_KEY and v==1 and self.mapping.get('B')==[i,c] for i,t,c,v in events): break
                    finally:
                        os.write(gamepad.fd,EVENT.pack(0,0,EV_FF,eid,0))
                        fcntl.ioctl(gamepad.fd,ioc(1,0x81,4),eid)
                    answer=self.choice('RUMBLE',f'Did you feel the {name} pulse?')
                    self.observation('output','rumble '+name,answer)
                except OSError as exc:
                    self.record('output','rumble '+name,'unavailable',error=str(exc))
        for channel,name in [(0,'left'),(1,'right')]:
            if self.choice('AUDIO',f'Play a quiet {name}-channel tone?') is not True:
                self.skipped('output','audio '+name); continue
            path=Path('/run/guide-test-tone.wav')
            samples=array.array('h')
            for n in range(24000):
                value=int(32767*self.audio_gain*math.sin(2*math.pi*440*n/24000)*min(1,n/240,(23999-n)/240))
                samples.extend((value,0) if channel==0 else (0,value))
            with wave.open(str(path),'wb') as wav:
                wav.setparams((2,2,24000,0,'NONE','not compressed')); wav.writeframes(samples.tobytes())
            with (self.folders[0]/'controller-audio.txt').open('a') as log:
                player=subprocess.Popen(['aplay','-q',str(path)],stdout=log,stderr=log)
                try:
                    start=time.monotonic()
                    while player.poll() is None and time.monotonic()-start<3:
                        events=self.tick()
                        self.screen.draw('AUDIO  /  '+name.upper(),'Quiet tone playing','B: STOP',lines=[])
                        if any(t==EV_KEY and v==1 and self.mapping.get('B')==[i,c] for i,t,c,v in events): break
                finally:
                    if player.poll() is None: player.terminate()
                    try: player.wait(timeout=1)
                    except subprocess.TimeoutExpired: player.kill(); player.wait()
            answer=self.choice('AUDIO',f'Did you hear the {name}-channel tone?')
            self.observation('output','audio '+name,answer,player_exit=player.returncode)
        jack=next((d for d in self.inputs.devices if 2 in d.caps.get('5',[])),None)
        if jack and self.choice('HEADPHONES','Have headphones ready to insert/remove?') is True:
            start=time.monotonic(); initial=int(jack.sw.get(2,0)); sequence=[[start,initial]]
            generation=self.inputs.generation
            jack_index=self.inputs.devices.index(jack)
            unplugged=not initial; inserted=False; removed=False
            while time.monotonic()-start<20:
                events=self.tick()
                if generation!=self.inputs.generation: break
                for i,t,c,value in events:
                    if i!=jack_index or t!=EV_SW or c!=2: continue
                    if sequence[-1][1]!=value: sequence.append([time.monotonic(),value])
                    if not unplugged and not value: unplugged=True
                    elif unplugged and not inserted and value: inserted=True
                    elif inserted and not value: removed=True
                value=int(jack.sw.get(2,0))
                instruction='Remove headphones to begin' if not unplugged else 'Insert headphones' if not inserted else 'Remove headphones'
                self.screen.draw('HEADPHONE DETECTION',instruction,
                                 'Plugged in' if value else 'Unplugged',lines=[],fraction=1-(time.monotonic()-start)/20)
                if removed: break
            self.record('accessory','headphone switch','ambiguous' if generation!=self.inputs.generation else 'complete' if removed else 'not observed',initial=initial,sequence=sequence,
                        note='Full insert/remove sequence; switch detection only, routing remains untested')
        elif jack: self.skipped('accessory','headphone switch')
        else: self.record('accessory','headphone switch','unavailable')

    def run(self):
        start=time.monotonic()
        while time.monotonic()-start<60:
            events=self.tick()
            self.screen.draw('WELCOME','Press any game button when ready',
                         'Auto-finish after inactivity; never press Start/Power/Reset',
                         lines=['First: tap each highlighted control twice.', 'Next: hold, release and exercise the sticks.',
                                'Start, Power and Reset are never requested.', 'Missed steps get a retry; they are not failures.',
                                'Progress is saved as you go.'])
            if any(t==EV_KEY and v==1 and c not in EXCLUDED for _,t,c,v in events): break
        else:
            self.summary['session']='not started; welcome timed out'; self.save(); return
        self.hold_screen('BASELINE','Leave all controls untouched',2,lines=[])
        self.summary['baseline']=[{'keys':d.keys.copy(),'axes':{c:a['value'] for c,a in d.axes.items()}} for d in self.inputs.devices]
        self.save()
        if not any(d.name=='H700 Gamepad' for d in self.inputs.devices):
            self.record('inventory','gamepad','unavailable')
            self.hold_screen('GAMEPAD NOT FOUND','Reports saved - reconnect and retry',5,lines=[])
            return
        missed=[label for label in BUTTONS if not self.button(label)]
        if missed:
            self.hold_screen('DISCOVERY RETRY','Try the controls we have not identified',2,lines=missed[:9])
            for label in missed: self.button(label)
        if self.choice('MAPPING REVIEW','Did the highlights match what you pressed?',seconds=20,
                       lines=['A: matches   B: redo discovery', 'If you pressed the wrong control, choose B.',
                              'The test cannot infer physical intent.']) is False:
            self.summary.setdefault('superseded_mappings',[]).append(dict(self.mapping))
            for label in list(self.mapping): self.record('discover',label,'superseded')
            self.mapping.clear(); self.screen.completed.clear()
            for label in BUTTONS: self.button(label)
        for label in ('LEFT STICK','RIGHT STICK'):
            self.sticks[label]={}
            for direction in ('right','up'):
                result=self.discover_axis(label,direction)
                if result is None: result=self.discover_axis(label,direction)
                if result: self.sticks[label][direction]=result
            self.save()
        self.stage_gate('DISCOVERY SAVED')
        self.hold_screen('EXERCISE','Now check hold, release and another tap',2,lines=[])
        missed=[label for label in BUTTONS if label in self.mapping and not self.button(label,True)]
        for label in missed: self.button(label,True)
        for a,b in [('UP','RIGHT'),('RIGHT','DOWN'),('DOWN','LEFT'),('LEFT','UP'),('L1','A'),('R1','B')]:
            self.combination(a,b,a+' + '+b)
        for label in ('LEFT STICK','RIGHT STICK'):
            self.exercise_stick(label); self.stick_click(label)
        latest={(r['phase'],r['label']):r for r in self.results}
        missing=[r['label'] for r in latest.values() if r['outcome'] not in ('complete','user-confirmed')]
        self.hold_screen('CONTROLS SUMMARY',f'{len(self.mapping)} of 18 digital controls discovered',5,
                         lines=['Needs review: '+str(len(missing))]+missing[:7])
        if missing and self.choice('RETRY','Retry incomplete exercises?',lines=missing[:7]) is True:
            for r in latest.values():
                if r['outcome']=='complete': continue
                if r['phase']=='discover' and r['label'] not in self.mapping:
                    if self.button(r['label']): self.button(r['label'],True)
                elif r['phase']=='axis discovery':
                    for label in ('LEFT STICK','RIGHT STICK'):
                        for direction in ('right','up'):
                            if r['label']==label+direction and direction not in self.sticks[label]:
                                value=self.discover_axis(label,direction)
                                if value: self.sticks[label][direction]=value
                elif r['phase']=='exercise': self.button(r['label'],True)
                elif r['phase']=='stick exercise': self.exercise_stick(r['label'])
                elif r['phase']=='stick click with movement': self.stick_click(r['label'])
                elif r['phase']=='combination':
                    a,b=r['label'].split(' + '); self.combination(a,b,r['label'])
        self.stage_gate('EXERCISES SAVED')
        for label,prompt in [('readability','Was the text easy to read?'),('instructions','Were the instructions clear?'),
                             ('pacing','Did you have enough time for each step?'),('control feel','Did the controls feel comfortable?'),
                             ('stick response','Did the stick dot move smoothly?'),('results clarity','Could you tell what needed another try?')]:
            answer=self.choice('YOUR EXPERIENCE',prompt,seconds=15,lines=['A: yes   B: no', 'No answer is recorded separately.',
                                        'Tell us details after reconnecting the card.'])
            self.observation('experience',label,answer)
        self.outputs()
        self.summary['session']='finished'
        self.save()
        self.hold_screen('CONTROLS SAVED','Graphics test next - no buttons needed',4,lines=[])


class ButtonTrial:
    """Pure event recognizer shared by real input and regression tests."""
    def __init__(self,mapping=None,used=(),exercise=False,required_taps=1):
        self.mapping=tuple(mapping) if mapping else None
        self.used={tuple(x) for x in used}
        self.exercise=exercise
        self.required_taps=required_taps; self.taps=0
        self.state=0; self.down_at=None; self.complete=False; self.ambiguous=''; self.transitions=[]

    def event(self,key,value,now):
        if key[1] in EXCLUDED or value==2: return
        if self.complete or self.ambiguous: return
        if self.mapping is None and value==1:
            if key in self.used:
                self.ambiguous='This event already belongs to another physical control'; return
            self.mapping=key
        if key!=self.mapping:
            if value==1: self.ambiguous='Multiple different buttons pressed'
            return
        if value not in (0,1): return
        self.transitions.append([now,value])
        if value==1 and self.down_at is None:
            self.down_at=now
        elif value==0 and self.down_at is not None:
            held=now-self.down_at; self.down_at=None
            if not self.exercise:
                self.taps+=1
                self.complete=self.taps>=self.required_taps
            elif self.state==0 and held>=1: self.state=1
            elif self.state==1: self.complete=True

    def instruction(self,now):
        if self.state==1: return 'Tap once more, then release'
        if self.down_at is None: return 'Hold this control for one second'
        if now-self.down_at>=1: return 'Hold complete - release now'
        return f'Keep holding... {int((now-self.down_at)*100)}%'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',type=Path)
    parser.add_argument('--mirror',type=Path)
    parser.add_argument('--preview',type=Path)
    args=parser.parse_args()
    if args.preview:
        args.preview.mkdir(parents=True,exist_ok=True)
        class Preview:
            def show(self,image): self.image=image
        sink=Preview(); screen=Screen(sink)
        for name,kwargs in [('button',dict(title='DISCOVER  /  A',instruction='Press once, then release',detail='0 of 18 discovered  |  12s left',target='A')),
                            ('shoulder',dict(title='EXERCISE  /  L2',instruction='Hold complete - release now',target='L2',fraction=.6)),
                            ('stick',dict(title='EXERCISE  /  LEFT STICK',instruction='Slow circle around the edge, then let go',detail='2/4 edges   4/8 directions',stick=(.7,.6,{0,1})))]:
            screen.draw(**kwargs); sink.image.save(args.preview/(name+'.png'))
        return
    if not args.report or not args.mirror: parser.error('report and mirror required')
    for folder in (args.report,args.mirror): folder.mkdir(parents=True,exist_ok=True)
    def stop(signum,frame): raise SessionExpired('interrupted by service or user signal')
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    inputs=fb=test=None
    with (args.report/'controller-events.jsonl').open('w',buffering=1) as log:
        try:
            inputs=Inputs(log); fb=Framebuffer()
            test=Test(inputs,Screen(fb),[args.report,args.mirror]); test.run()
        except SessionExpired as exc:
            if test:
                test.summary['session']=str(exc) or 'session time limit; partial results saved'; test.save()
                test.screen.draw('PARTIAL RESULTS SAVED','Session ended - graphics test next',lines=[])
                time.sleep(2)
        except Exception as exc:
            if test:
                test.summary['session']='error'; test.summary['error']=repr(exc); test.save()
            raise
        finally:
            if fb: fb.close()
            if inputs: inputs.close()


if __name__=='__main__': main()
