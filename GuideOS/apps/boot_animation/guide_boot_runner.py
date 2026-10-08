"""Bound setup and playback independently; readiness means first frame presented."""
import argparse
import os
import select
import signal
import subprocess
import time
import json
import socket
import re
from pathlib import Path
import sys

RUNTIME = Path('/run/guideos-boot-animation')


def notify_ready():
    address = os.environ.get('NOTIFY_SOCKET')
    if address:
        if address.startswith('@'):
            address = '\0' + address[1:]
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as connection:
            connection.sendto(b'READY=1', address)


def supports_early_home():
    # A rollback to an older shell must retain the original serial handoff.
    try:
        active=json.loads(Path('/opt/guideos/deploy/active.json').read_text())
        release=active['release']
        if not re.fullmatch(r'[a-f0-9]{64}',release):return False
        shell=Path('/opt/guideos/deploy/releases')/release/'shell0/guide_shell.py'
        if shell.stat().st_size>512*1024:return False
        source=shell.read_bytes()
        return b'class BootFramebuffer:' in source and b'GUIDE_BOOT_HANDOFF' in source
    except (OSError,ValueError,KeyError,TypeError):
        return False


def emit(code, **fields):
    # Journal transport retains early-boot events before the collector starts.
    print('GUIDE_DIAGNOSTIC ' + json.dumps(dict(code=code, observed=time.monotonic(), **fields)), flush=True)


def run(command, initialization=12.0, playback=10.0, grace=2.0):
    run_started = time.monotonic()
    emit('VIDEO_START')
    read_fd, write_fd = os.pipe()
    child = None
    interrupted = []
    previous = {}
    early_home = supports_early_home()
    try:
        if RUNTIME.is_dir():
            for name in ('display-released', 'home-presented', 'early-home'):
                (RUNTIME / name).unlink(missing_ok=True)
            if early_home:(RUNTIME/'early-home').touch()
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous[sig] = signal.signal(sig, lambda signum, frame: interrupted.append(signum))
        child = subprocess.Popen(command, pass_fds=(write_fd,), start_new_session=True,
                                 env=dict(os.environ, GUIDE_BOOT_READY_FD=str(write_fd)))
        os.close(write_fd)
        write_fd = -1
        started = time.monotonic()
        deadline = started + initialization
        phase = 'initialization'
        ready = False
        while child.poll() is None:
            if interrupted:
                return 128 + interrupted[0]
            if time.monotonic() >= deadline:
                emit('VIDEO_TIMEOUT', phase=phase, elapsed_ms=(time.monotonic()-started)*1000)
                print('guide-boot-runner timeout=' + phase, flush=True)
                return 124
            if not ready:
                readable, _, _ = select.select([read_fd], [], [], .05)
                if readable:
                    value = os.read(read_fd, 1)
                    if value == b'R':
                        emit('VIDEO_READY', elapsed_ms=(time.monotonic()-started)*1000)
                        ready = True
                        if early_home:notify_ready()
                        phase = 'playback'
                        deadline = time.monotonic() + playback
                        print('guide-boot-runner first-frame initialization=%.3f' %
                              (time.monotonic() - started), flush=True)
                    elif value:
                        return 1
                    else:
                        # A renderer that closes readiness without producing a
                        # frame is not a successfully completed animation.
                        return child.wait(timeout=grace) or 1
            else:
                time.sleep(.05)
        if not ready and select.select([read_fd], [], [], 0)[0]:
            ready = os.read(read_fd, 1) == b'R'
        return (child.returncode or (0 if ready else 1))
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        # The child has restored DRM before Home may open the framebuffer.
        if RUNTIME.is_dir():
            (RUNTIME / 'display-released').touch()
        if not early_home:
            subprocess.run([sys.executable,str(Path(__file__).with_name('guide_boot_console.py')),'release'],check=False)
            notify_ready()
        os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        emit('VIDEO_EXIT', returncode=child.returncode if child is not None and child.returncode is not None else -1,
             elapsed_ms=(time.monotonic()-run_started)*1000)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--initialization', type=float, default=12)
    parser.add_argument('--playback', type=float, default=10)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not all(0 < n <= 60 for n in (args.initialization, args.playback)) or not args.command:
        parser.error('positive bounded phase times and a command are required')
    raise SystemExit(run(args.command, args.initialization, args.playback))
