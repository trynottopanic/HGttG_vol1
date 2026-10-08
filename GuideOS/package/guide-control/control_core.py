"""Global chord and foreground freeze policy, separate from the renderer."""
from pathlib import Path
import fcntl
import json
import time


def deployment_guard(base=Path('/opt/guideos/deploy')):
    """Share the existing deployment lock; never freeze its health trial."""
    path=base/'lock'
    if not path.exists():return None
    handle=path.open('r')
    try:
        fcntl.flock(handle,fcntl.LOCK_SH | fcntl.LOCK_NB)
        transaction=base/'transaction.json'
        if transaction.exists():
            if transaction.stat().st_size>65536:raise BlockingIOError('Deployment state unavailable')
            state=json.loads(transaction.read_text()).get('state')
            if state in ('queued','activating','trial','recovering'):
                raise BlockingIOError('Deployment transition in progress')
        return handle
    except Exception:
        handle.close()
        raise

SELECT,START=314,315


class Chord:
    def __init__(self):
        self.held=set()
        self.latched=False

    def update(self, code, value):
        if code not in (SELECT,START):return False
        if value==0:self.held.discard(code)
        elif value==1:self.held.add(code)
        if not self.held:self.latched=False
        if self.held=={SELECT,START} and not self.latched:
            self.latched=True
            return True
        return False


class Foreground:
    unit='guide-shell.service'
    events=Path('/sys/fs/cgroup/system.slice/guide-shell.service/cgroup.events')

    def frozen(self):
        try:return 'frozen 1' in self.events.read_text().splitlines()
        except OSError:return False

    def freeze(self):
        self._set_frozen(True)

    def thaw(self):
        if not self.events.exists():return  # the foreground has already exited
        self._set_frozen(False)

    def _set_frozen(self,wanted):
        # Use one source of freeze state throughout the lifecycle. systemd's
        # Freeze/Thaw API refuses Thaw once a stop job is queued, and mixing
        # that API with direct recovery leaves its cached state inconsistent.
        # The fixed unit is still started/stopped and limited by systemd.
        self.events.with_name('cgroup.freeze').write_text('1\n' if wanted else '0\n')
        deadline=time.monotonic()+2
        while self.frozen()!=wanted and time.monotonic()<deadline:time.sleep(.01)
        if self.frozen()!=wanted:raise RuntimeError('Foreground freeze transition not acknowledged')

    def owns(self,pid):
        try:return any(line.endswith('/system.slice/'+self.unit) for line in Path(f'/proc/{pid}/cgroup').read_text().splitlines())
        except OSError:return False
