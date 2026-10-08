"""Keep tty1 covered through boot and transfer its original mode to Home."""
import array
import fcntl
import json
import os
from pathlib import Path
import sys
import time

STATE = Path('/run/guideos-boot-animation/console.json')
KDGETMODE, KDSETMODE, VT_ACTIVATE = 0x4B3B, 0x4B3A, 0x5606

def acquire():
    # Headless boot remains useful; the service normally skips without DRM.
    if not Path('/dev/dri').exists():
        return
    fd = os.open('/dev/tty1', os.O_RDWR | os.O_NOCTTY)
    try:
        mode = array.array('i', [0])
        fcntl.ioctl(fd, KDGETMODE, mode, True)
        STATE.write_text(json.dumps(dict(mode=mode[0])))
        fcntl.ioctl(fd, VT_ACTIVATE, 1)
        fcntl.ioctl(fd, KDSETMODE, 1)
    finally:
        os.close(fd)

def release():
    if not STATE.exists():
        return
    mode = json.loads(STATE.read_text())['mode']
    if mode not in (0, 1, 2):
        raise ValueError('invalid saved console mode')
    fd = os.open('/dev/tty1', os.O_RDWR | os.O_NOCTTY)
    try:
        fcntl.ioctl(fd, KDSETMODE, mode)
        STATE.unlink()
    finally:
        os.close(fd)


def handoff():
    if not (STATE.parent/'early-home').exists():
        release()
        return
    # Home copies the original mode into its framebuffer cleanup before it
    # acknowledges a presented frame. Never restore text between the two UIs.
    deadline = time.monotonic() + 10
    while STATE.exists() and time.monotonic() < deadline:
        if (STATE.parent / 'home-presented').exists():
            STATE.unlink(missing_ok=True)
            return
        time.sleep(.025)
    # Missing/failed Home must leave a usable console, including failed boots.
    release()

if __name__ == '__main__':
    try:
        {'acquire': acquire, 'release': release, 'handoff': handoff}[sys.argv[1]]()
    except Exception as exc:
        print('guide-boot-console error=' + type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
