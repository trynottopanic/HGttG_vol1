"""Fixed Guide workload identities and kernel evidence, never arbitrary PID kills."""
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import time

MIB = 1024 ** 2
BROWSER_HIGH = 320 * MIB
BROWSER_MAX = 384 * MIB
HEADROOM = 128 * MIB
RUNTIME = Path('/run/guideos-resources')
CGROUP = Path('/sys/fs/cgroup')
APP_UNIT = re.compile(r'guide-app-[0-9a-f]{32}-g[1-9][0-9]{0,19}\.service')


def bounded(path, limit=16384):
    with Path(path).open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Oversized host evidence')
    return raw.decode('utf-8')


def fields(path):
    return dict(line.split(None, 1) for line in bounded(path).splitlines() if ' ' in line)


def mem_available(path=Path('/proc/meminfo')):
    rows = dict(line.split(':', 1) for line in bounded(path).splitlines())
    return int(rows['MemAvailable'].split()[0]) * 1024


def browser_group(root=CGROUP):
    uid = pwd.getpwnam('guide-browser').pw_uid
    if uid == 0:
        raise ValueError('Browser must have its own unprivileged account')
    return Path(root) / 'user.slice' / f'user-{uid}.slice'


def set_oom_group(group):
    # systemd has OOMPolicy=kill for services, but no corresponding slice
    # directive. Set the kernel attribute on the dedicated PAM parent itself.
    fd=os.open(group,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        attribute=os.open('memory.oom.group',os.O_WRONLY,dir_fd=fd)
        try:os.write(attribute,b'1\n')
        finally:os.close(attribute)
        attribute=os.open('memory.oom.group',os.O_RDONLY,dir_fd=fd)
        try:
            if os.read(attribute,32).strip()!=b'1':raise RuntimeError('Whole-session OOM policy unavailable')
        finally:os.close(attribute)
    finally:os.close(fd)


def verify_browser_limits(group=None):
    group = group or browser_group()
    for name, ceiling in (('memory.high', BROWSER_HIGH), ('memory.max', BROWSER_MAX),
                          ('memory.swap.max', 64 * MIB), ('pids.max', 256)):
        value = bounded(group / name).strip()
        if not value.isdigit() or int(value) > ceiling:
            raise RuntimeError('Browser session resource limits are not enforced')
    if bounded(group / 'memory.oom.group').strip() != '1':
        raise RuntimeError('Browser whole-session OOM policy is not enforced')
    own = bounded(Path('/proc/self/cgroup')).splitlines()
    relative = '/' + str(group.relative_to(CGROUP))
    if not any(row.startswith('0::' + relative + '/') for row in own):
        raise RuntimeError('Browser is outside its protected session group')
    if mem_available() < BROWSER_MAX + HEADROOM:
        raise RuntimeError('Not enough memory to open Browser safely; close another application')


def browser_admission():
    status = json.loads(bounded(RUNTIME/'status.json', 65536))
    if status.get('state') != 'ready' or not 0 <= time.monotonic()-status.get('observed', 0) <= 3:
        raise RuntimeError('Memory recovery service is unavailable; Browser was not opened')
    if mem_available() < BROWSER_MAX + HEADROOM:
        raise RuntimeError('Not enough memory to open Browser safely; close another application')


def browser_empty():
    group = browser_group()
    return not group.exists() or fields(group/'cgroup.events').get('populated') == '0'


def atomic(path, value):
    raw = json.dumps(value, separators=(',', ':')).encode()
    if len(raw) > 65536:
        raise ValueError('Oversized resource status')
    tmp = path.with_suffix('.tmp')
    with tmp.open('wb') as stream:
        stream.write(raw)
    tmp.chmod(0o644)
    tmp.replace(path)


class Host:
    """Trusted fixed units; invocation and cgroup inode bind each recovery request."""
    def __init__(self, root=CGROUP, runner=subprocess.run):
        self.root = Path(root)
        self.runner = runner

    def command(self, *args):
        result = self.runner(['systemctl', *args], timeout=2, check=False,
                             capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError('System service operation unavailable')
        if len(result.stdout) > 32768:
            raise RuntimeError('Oversized service evidence')
        return result.stdout

    def observe(self, unit, label, groups=None):
        if unit not in ('guide-browser.service', 'guide-media-player.service', 'guide-shell.service') and not APP_UNIT.fullmatch(unit):
            raise ValueError('Not an application recovery target')
        text = self.command('show', unit, '-p', 'InvocationID', '-p', 'ControlGroup',
                            '-p', 'ActiveState')
        info = dict(row.split('=', 1) for row in text.splitlines() if '=' in row)
        if info.get('ActiveState') not in ('active', 'activating'):
            return None
        invocation = info.get('InvocationID', '')
        if not re.fullmatch('[0-9a-f]{32}', invocation):
            raise RuntimeError('Workload has no live invocation identity')
        relative = Path(info.get('ControlGroup', '').lstrip('/'))
        if not relative.parts or '..' in relative.parts:
            raise RuntimeError('Invalid workload group')
        group = self.root / relative
        if groups is None:
            groups = [group]
        records = []
        memory = 0
        for path in groups:
            path = Path(path)
            if not path.exists():
                continue
            resolved = path.resolve(strict=True)
            if self.root.resolve() not in resolved.parents:
                raise RuntimeError('Workload escaped the group boundary')
            records.append((str(path), path.stat().st_ino))
            memory += int(bounded(path / 'memory.current').strip())
        return dict(unit=unit, label=label, invocation=invocation, groups=records,
                    memory=memory)

    def workloads(self):
        result = []
        browser = self.observe('guide-browser.service', 'Browser',
            [browser_group(self.root), self.root / 'system.slice/guide-browser.service'])
        if browser:
            result.append(browser)
        player = self.observe('guide-media-player.service', 'Music / Video')
        if player:
            result.append(player)
        ledger = Path('/run/guideos/supervisor')
        for path in sorted(ledger.glob('*.record'))[:32]:
            if path.is_symlink() or path.stat().st_uid != 0:
                continue
            info = dict(row.split('=', 1) for row in bounded(path, 2048).splitlines() if '=' in row)
            unit = info.get('unit', '')
            if not APP_UNIT.fullmatch(unit):
                continue
            record = self.observe(unit, 'Application ' + info.get('app', '?')[:16])
            if record and record['invocation'] == info.get('invocation'):
                result.append(record)
        return result

    def same(self, record):
        now = self.observe(record['unit'], record['label'],
                           [Path(path) for path, inode in record['groups']])
        return now is not None and now['invocation'] == record['invocation'] and now['groups'] == record['groups']

    def empty(self, record):
        for path, inode in record['groups']:
            try:
                directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            except FileNotFoundError:
                continue
            try:
                if os.fstat(directory).st_ino != inode:
                    raise RuntimeError('Recovery target was replaced')
                try:
                    event = os.open('cgroup.events', os.O_RDONLY | os.O_NOFOLLOW,
                                    dir_fd=directory)
                except FileNotFoundError:
                    # systemd can remove the old group after the directory was
                    # opened. Read only that pinned instance, never its replacement.
                    try:
                        remaining = os.stat(path, follow_symlinks=False)
                    except FileNotFoundError:
                        continue
                    if remaining.st_ino != inode:
                        raise RuntimeError('Recovery target was replaced')
                    raise RuntimeError('Recovery completion evidence unavailable')
                try:
                    raw = os.read(event, 16385)
                finally:
                    os.close(event)
                if len(raw) > 16384:
                    raise ValueError('Oversized host evidence')
                state = dict(line.split(None, 1) for line in raw.decode('utf-8').splitlines()
                             if ' ' in line)
                if state.get('populated') != '0':
                    return False
            finally:
                os.close(directory)
        return True

    def stop(self, record, force=False):
        # A vanished original is completion only if its old groups are empty.
        if not self.same(record):
            if self.empty(record):
                return 'already exited'
            raise RuntimeError('Recovery target changed; refresh diagnostics')
        handles = []
        try:
            # Pin kernel group directories across stop/removal; never reopen a
            # replacement group by path when escalating to cgroup.kill.
            for path, inode in record['groups']:
                fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                handles.append(fd)
                if os.fstat(fd).st_ino != inode:
                    raise RuntimeError('Recovery target changed')
            self.command('stop', '--no-block', record['unit'])
            deadline = time.monotonic() + (0.25 if force else 1.5)
            while not self.empty(record) and time.monotonic() < deadline:
                time.sleep(.025)
            if not self.empty(record):
                for fd in handles:
                    try:
                        frozen = os.open('cgroup.freeze', os.O_WRONLY, dir_fd=fd)
                        try: os.write(frozen, b'0\n')
                        finally: os.close(frozen)
                        kill = os.open('cgroup.kill', os.O_WRONLY, dir_fd=fd)
                        try: os.write(kill, b'1\n')
                        finally: os.close(kill)
                    except FileNotFoundError:
                        pass
                deadline = time.monotonic() + 2
                while not self.empty(record) and time.monotonic() < deadline:
                    time.sleep(.025)
            if not self.empty(record):
                raise RuntimeError('Application is still stopping; display has not been released')
            return 'closed; unsaved work may have been lost'
        finally:
            for fd in handles: os.close(fd)

    def force_home(self, records):
        # Owner action includes current managed application trees; never kill
        # unrelated system services or caller-supplied PIDs.
        for record in records:
            self.stop(record, force=True)
        # Restart only after applications/compositors are confirmed empty.
        shell = self.observe('guide-shell.service', 'Guide interface')
        if shell:
            self.stop(shell, force=True)
        self.command('reset-failed', 'guide-shell.service')
        return 'Applications closed. Unsaved work may have been lost.'
