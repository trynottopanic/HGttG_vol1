"""Shell-side restart handshake. Never serializes keys, text or network names."""
import json
import os
from pathlib import Path
import time

def status_line():
    """A local address helps the paired PC find the Deck; no radio scan."""
    try:
        import fcntl
        import socket
        import struct
        config = json.loads(Path('/opt/guideos/deploy/config.json').read_text())
        if not config.get('enabled'):
            return 'Network delivery: disabled'
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
            for interface in sorted(Path('/sys/class/net').iterdir()):
                if interface.name == 'lo':
                    continue
                try:
                    value = fcntl.ioctl(connection, 0x8915, struct.pack('256s', interface.name.encode()[:15]))
                    return 'Paired PC delivery: ' + socket.inet_ntoa(value[20:24])
                except OSError:
                    continue
        return 'Paired PC delivery: network needed'
    except (OSError, ValueError):
        return 'Network delivery: unavailable'

class ShellBridge:
    def __init__(self):
        self.root = Path(os.environ['GUIDE_DEPLOY_RUNTIME']) if 'GUIDE_DEPLOY_RUNTIME' in os.environ else None
        self.release = os.environ.get('GUIDE_RELEASE_ID', '')
        self.ready = False
        self.last = 0
        self.quiesced = None
        self.last_safe = None

    def publish(self, safe, stopped=False, clean=False):
        if self.root is None:
            return
        now = time.monotonic()
        if not stopped and now - self.last < 1 and safe == self.last_safe:
            return
        data = dict(pid=os.getpid(), release=self.release, monotonic=now, ready=self.ready,
                    can_restart=safe, quiesced=self.quiesced, stopped=stopped, clean=clean)
        try:
            temporary = self.root / 'shell.json.tmp'
            temporary.write_text(json.dumps(data))
            os.replace(temporary, self.root / 'shell.json')
        except OSError:
            # Missing handshake defers deployment; it must not crash ordinary use.
            return
        self.last, self.last_safe = now, safe

    def poll(self, safe):
        if self.root is None:
            return False
        token = None
        try:
            path = self.root / 'quiesce.json'
            if path.stat().st_size <= 256:
                token = json.loads(path.read_text())['token']
        except (OSError, ValueError, KeyError):
            pass
        if token != self.quiesced:
            self.quiesced = token if safe else None
            self.last = 0
        self.publish(safe)
        return self.quiesced is not None
