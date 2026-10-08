#!/usr/bin/python3
"""Minimal RG35XX H platform adapter for the Debian Guide Shell.

This is a board adapter, not application policy. It deliberately never opens
the dedicated power-key device. SPDX-License-Identifier: AGPL-3.0-or-later
"""
import array
import errno
import fcntl
import glob
import mmap
import os
from pathlib import Path
import select
import struct
import time
import signal

EVENT = struct.Struct("llHHi")
ABS_INFO = struct.Struct("6i")
EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
SYN_REPORT, SYN_DROPPED = 0, 3
ALLOWED_INPUTS = {"H700 Gamepad", "gpio-keys-volume"}
# Board profile: patches/linux/0140-rg35xx-2024-use-rocknix-joypad-driver.patch
# and 0144 enable ABS_X/Y (0/1) and ABS_RX/RY (3/4). Returned diagnostic-3
# EVIOCGABS evidence confirms these codes. The kernel applies the DTS inversion;
# normalized evdev coordinates already mean +x right, +y down. Do not invert twice.
STICK_AXES = {"left": (0, 1), "right": (3, 4)}
RIGHT_STICK_CLICK = 318
BTN_SELECT, KEY_SELECT = 314, 353


def _ioc(direction, number, size):
    return (direction << 30) | (size << 16) | (ord("E") << 8) | number


def _read_ioctl(fd, number, size):
    value = bytearray(size)
    fcntl.ioctl(fd, _ioc(2, number, size), value, True)
    return bytes(value)


def _bits(value):
    return [n for n in range(len(value) * 8)
            if value[n // 8] & (1 << (n % 8))]


class InputEvent(tuple):
    def __new__(cls, values, timestamp):
        result = super().__new__(cls, values)
        result.timestamp = timestamp
        return result


class InputDevice:
    def __init__(self, path):
        self.path = path
        self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        self.name = _read_ioctl(self.fd, 6, 256).split(b"\0")[0].decode(errors="replace")
        if self.name not in ALLOWED_INPUTS:
            os.close(self.fd)
            raise ValueError("input device is not owned by the Guide Shell")
        self.keys = {}
        self.axes = {}
        self.pending_axes = {}
        self.dropped = False
        self.connected = True
        self.monotonic = False
        try:
            fcntl.ioctl(self.fd, _ioc(1, 0xA0, 4), struct.pack("i", 1))
            self.monotonic = True
        except OSError:
            pass
        fcntl.ioctl(self.fd, _ioc(1, 0x90, 4), 1)  # exclusive shell grab
        self.resync()

    def resync(self):
        self.keys = {code: True for code in _bits(_read_ioctl(self.fd, 0x18, 96))}
        axes = {}
        try:
            supported = _bits(_read_ioctl(self.fd, 0x20 + EV_ABS, 8))
        except OSError:
            supported = []
        for code in supported:
            try:
                value, low, high, fuzz, flat, resolution = ABS_INFO.unpack(
                    _read_ioctl(self.fd, 0x40 + code, ABS_INFO.size))
            except OSError:
                continue
            axes[code] = dict(value=value, minimum=low, maximum=high,
                              fuzz=fuzz, flat=flat, resolution=resolution)
        # Query actual held positions on open/recovery. Missing metadata must not
        # retain a stale previous value or invent a neutral axis.
        self.axes = axes
        self.pending_axes = {}

    def commit_axes(self):
        changed = bool(self.pending_axes)
        for code, value in self.pending_axes.items():
            if code in self.axes:
                self.axes[code]['value'] = value
        self.pending_axes.clear()
        return changed

    def close(self):
        errors = []
        try:
            fcntl.ioctl(self.fd, _ioc(1, 0x90, 4), 0)
        except OSError as exc:
            errors.append("release input grab: " + str(exc))
        try:
            os.close(self.fd)
        except OSError as exc:
            errors.append("close input: " + str(exc))
        self.connected = False
        self.pending_axes.clear()
        return errors


class DeckInputs:
    """Exclusive game/volume input owner. Power remains system-owned."""
    def __init__(self, event_log=None):
        self.event_log = event_log or (lambda _row: None)
        self.devices = []
        self.generation = 0
        for path in sorted(glob.glob("/dev/input/event*")):
            name_path = Path("/sys/class/input") / Path(path).name / "device/name"
            try:
                name = name_path.read_text().strip()
            except OSError:
                continue
            if name in ALLOWED_INPUTS:
                self.devices.append(InputDevice(path))

    def poll(self, delay=0.05):
        live = [device for device in self.devices if device.connected]
        ready, _, _ = select.select([device.fd for device in live], [], [], delay)
        events = []
        for index, device in enumerate(self.devices):
            if not device.connected or device.fd not in ready:
                continue
            try:
                raw = os.read(device.fd, EVENT.size * 128)
                if not raw:
                    raise OSError(errno.ENODEV, "input disconnected")
            except OSError as exc:
                if exc.errno == errno.EAGAIN:
                    continue
                device.connected = False
                device.pending_axes.clear()
                self.generation += 1
                self.event_log({"event": "disconnect", "device": device.name,
                                "detail": str(exc), "time": time.monotonic()})
                events.append(self._stick_event(device, SYN_DROPPED, time.monotonic()))
                continue
            for offset in range(0, len(raw), EVENT.size):
                sec, usec, kind, code, value = EVENT.unpack_from(raw, offset)
                timestamp = sec + usec / 1e6 if device.monotonic else time.monotonic()
                self.event_log({"event": "input", "device": device.name,
                                "type": kind, "code": code, "value": value,
                                "time": timestamp})
                if kind == EV_SYN and code == SYN_DROPPED:
                    device.dropped = True
                    device.pending_axes.clear()
                    self.generation += 1
                    events.append(self._stick_event(device, SYN_DROPPED, timestamp))
                    continue
                if device.dropped:
                    if kind == EV_SYN and code == SYN_REPORT:
                        try:
                            device.resync()
                        except OSError:
                            # Keep samples unavailable and retry at a later frame.
                            continue
                        device.dropped = False
                        events.append(self._stick_event(device, SYN_REPORT, timestamp))
                    continue
                if kind == EV_ABS and code in device.axes:
                    device.pending_axes[code] = value
                elif kind == EV_SYN and code == SYN_REPORT:
                    if device.commit_axes() and device.name == 'H700 Gamepad':
                        events.append(self._stick_event(device, SYN_REPORT, timestamp))
                if kind == EV_KEY:
                    # The board normally reports BTN_SELECT. Some compatible
                    # input profiles expose that physical control as the
                    # keyboard-style KEY_SELECT. Normalize it before shell
                    # policy sees the event.
                    if code == KEY_SELECT:
                        code = BTN_SELECT
                    device.keys[code] = value != 0
                    events.append(InputEvent((device.name, kind, code, value), timestamp))
        return events

    def _stick_event(self, device, code, timestamp):
        event = InputEvent((device.name, EV_SYN, code, 0), timestamp)
        event.sticks = self.stick_snapshot()
        return event

    def stick_snapshot(self):
        """Completed-frame positions; an unavailable pair is None, never center.

        Reported flat/fuzz are retained as metadata. Normalization uses the full
        declared range around its midpoint; temporal controls own their deadzone.
        Snapshot copies survive later frames, preserving deflect/neutral flicks.
        """
        snapshot = dict(left=None, right=None, generation=self.generation,
                        right_click=False)
        devices = [device for device in self.devices if device.name == 'H700 Gamepad'
                   and device.connected and not device.dropped]
        if len(devices) != 1:
            return snapshot
        device = devices[0]
        snapshot['right_click'] = bool(device.keys.get(RIGHT_STICK_CLICK, False))
        for name, pair in STICK_AXES.items():
            normalized = []
            for code in pair:
                axis = device.axes.get(code)
                if axis is None or any(type(axis.get(key)) is not int
                                       for key in ('value', 'minimum', 'maximum', 'flat')):
                    break
                low, high = axis['minimum'], axis['maximum']
                if high <= low or axis['flat'] < 0:
                    break
                midpoint = low + (high - low) / 2
                normalized.append(max(-1.0, min(1.0, (axis['value'] - midpoint) / ((high - low) / 2))))
            if len(normalized) == 2:
                snapshot[name] = tuple(normalized)
        return snapshot

    def close(self):
        errors = []
        for device in self.devices:
            errors.extend(device.close())
        return errors


class Framebuffer:
    """Single-owner framebuffer surface with non-throwing, idempotent cleanup."""
    def __init__(self, tty_path='/dev/tty1'):
        if tty_path not in ('/dev/tty1','/dev/tty3'):
            raise ValueError('Unknown Guide display surface')
        self.tty_path=tty_path
        self.vt_number=int(tty_path[-1])
        self.closed = False
        self.fd = os.open("/dev/fb0", os.O_RDWR)
        var, fix = bytearray(160), bytearray(80)
        fcntl.ioctl(self.fd, 0x4600, var, True)
        fcntl.ioctl(self.fd, 0x4602, fix, True)
        self.width, self.height, self.virtual_width, self.virtual_height, self.xoff, self.yoff, self.bpp = struct.unpack_from("7I", var)
        self.stride = struct.unpack_from("I", fix, 48)[0]
        self.length = struct.unpack_from("I", fix, 24)[0]
        self.fields = [struct.unpack_from("III", var, pos) for pos in (32, 44, 56)]
        if self.bpp not in (16, 32) or self.width < 320 or self.height < 240:
            raise RuntimeError("unsupported framebuffer layout")
        if any(reverse for _, _, reverse in self.fields):
            raise RuntimeError("reversed framebuffer channels are unsupported")
        if (self.yoff + self.height) * self.stride > self.length:
            raise RuntimeError("framebuffer bounds are invalid")
        self.mem = mmap.mmap(self.fd, self.length)
        self.last_metrics = {}
        try:
            from guide_telemetry import emit
            emit('FRAMEBUFFER_MODE',width=self.width,height=self.height,bpp=self.bpp,
                 stride=self.stride,virtual_height=self.virtual_height,
                 fields=[list(field) for field in self.fields],
                 pan_candidate=int(self.virtual_height >= self.height*2))
        except ImportError:
            pass
        self.tty = os.open(self.tty_path, os.O_RDWR | os.O_NOCTTY)
        mode = array.array("i", [0])
        fcntl.ioctl(self.tty, 0x4B3B, mode, True)  # KDGETMODE
        self.old_mode = mode[0]
        self.suspended = False
        self.old_vt_mode = self._get_vt_mode()
        self.old_vt_signals = {number:signal.getsignal(number) for number in (signal.SIGUSR1,signal.SIGUSR2)}
        signal.signal(signal.SIGUSR1,self._vt_release)
        signal.signal(signal.SIGUSR2,self._vt_acquire)
        self._own_vt()
        fcntl.ioctl(self.tty, 0x5606, self.vt_number)  # VT_ACTIVATE
        fcntl.ioctl(self.tty, 0x4B3A, 1)           # KD_GRAPHICS

    def _get_vt_mode(self):
        mode=bytearray(8)
        fcntl.ioctl(self.tty,0x5601,mode,True)  # VT_GETMODE
        return bytes(mode)

    def _own_vt(self):
        fcntl.ioctl(self.tty,0x5602,struct.pack('BBhhh',1,0,signal.SIGUSR1,signal.SIGUSR2,0))

    def _vt_release(self,*_):
        # An actual display lease must precede an external VT switch.
        try:fcntl.ioctl(self.tty,0x5605,1 if self.suspended else 0)
        except OSError:pass

    def _vt_acquire(self,*_):
        try:fcntl.ioctl(self.tty,0x5605,2)  # VT_ACKACQ
        except OSError:pass

    def suspend(self,image=None):
        if image is not None:self.show(image)
        self.suspended=True
        return True

    def resume(self):
        # A controlling-terminal owner can revoke old descriptors on exit.
        fresh=os.open(self.tty_path,os.O_RDWR|os.O_NOCTTY)
        old,self.tty=self.tty,fresh
        os.close(old)
        self._own_vt()
        fcntl.ioctl(self.tty,0x5606,self.vt_number)
        self.suspended=False
        fcntl.ioctl(self.tty,0x4B3A,1)
        self.invalidate()

    def invalidate(self):
        self._previous_image = None

    def show(self, image, dirty=None):
        if self.closed:
            raise RuntimeError("framebuffer is closed")
        from PIL import ImageChops
        started = time.monotonic()
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height))
        previous = getattr(self, '_previous_image', None)
        explicit = dirty is not None and previous is not None
        if explicit:
            boxes=[]
            for left,top,right,bottom in dirty:
                box=(max(0,int(left)),max(0,int(top)),min(self.width,int(right)),min(self.height,int(bottom)))
                if box[0]<box[2] and box[1]<box[3]:boxes.append(box)
        else:
            box = ImageChops.difference(previous, image).getbbox() if previous is not None else (0, 0, self.width, self.height)
            boxes=[] if box is None else [box]
        diff_done=time.monotonic()
        if not boxes:
            self.last_metrics=dict(diff_ms=(diff_done-started)*1000,convert_ms=0,write_ms=0,
                                   dirty_pixels=0,boxes=0,explicit=int(explicit))
            return
        convert_ms=write_ms=0.;dirty_pixels=0
        for box in boxes:
            tile = image.crop(box);conversion=time.monotonic()
            if self.bpp == 32 and self.fields == [(16, 8, 0), (8, 8, 0), (0, 8, 0)]:
                pixels = tile.tobytes("raw", "BGRX")
            else:
                code = "H" if self.bpp == 16 else "I"
                values = array.array(code,
                    (sum((channel >> (8 - length)) << offset
                         for channel, (offset, length, _) in zip(rgb, self.fields))
                     for rgb in tile.getdata()))
                pixels = values.tobytes()
            converted=time.monotonic();convert_ms+=(converted-conversion)*1000
            left, top, right, bottom = box
            dirty_pixels+=(right-left)*(bottom-top)
            pixel_bytes = self.bpp // 8
            row_bytes = (right-left) * pixel_bytes
            first = (self.yoff+top) * self.stride + (self.xoff+left) * pixel_bytes
            if self.xoff+left == 0 and row_bytes == self.stride:
                self.mem[first:first + row_bytes * (bottom-top)] = pixels
            else:
                for row in range(bottom-top):
                    offset = first + row*self.stride
                    self.mem[offset:offset+row_bytes] = pixels[row*row_bytes:(row+1)*row_bytes]
            write_ms+=(time.monotonic()-converted)*1000
        self._previous_image = image.copy()
        self.last_metrics=dict(diff_ms=(diff_done-started)*1000,convert_ms=convert_ms,
                               write_ms=write_ms,dirty_pixels=dirty_pixels,
                               boxes=len(boxes),explicit=int(explicit))

    def close(self):
        if self.closed:
            return []
        self.closed = True
        errors = []
        try:
            # Refresh before restoration if a player/service hung up tty1.
            fresh=os.open(self.tty_path,os.O_RDWR|os.O_NOCTTY)
            old,self.tty=self.tty,fresh;os.close(old)
            fcntl.ioctl(self.tty,0x5602,self.old_vt_mode)
            fcntl.ioctl(self.tty, 0x4B3A, self.old_mode)
        except OSError as exc:
            errors.append("restore terminal mode: " + str(exc))
        for number,handler in self.old_vt_signals.items():signal.signal(number,handler)
        for label, action in (("close terminal", lambda: os.close(self.tty)),
                              ("close framebuffer map", self.mem.close),
                              ("close framebuffer", lambda: os.close(self.fd))):
            try:
                action()
            except OSError as exc:
                errors.append(label + ": " + str(exc))
        return errors
