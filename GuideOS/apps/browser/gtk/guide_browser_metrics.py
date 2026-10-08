"""Bounded address-free memory samples for Browser initialization and recovery."""
import json
import os
from pathlib import Path
import time


def memory_fields(path):
    result = {}
    try:
        for line in path.read_text()[:65536].splitlines():
            key, sep, value = line.partition(':')
            if sep and key in ('Rss', 'Pss', 'Pss_Anon', 'Pss_File', 'Pss_Shmem',
                              'Private_Clean', 'Private_Dirty', 'Swap', 'SwapPss'):
                parts = value.split()
                if len(parts) == 2 and parts[1] == 'kB':
                    result[key] = int(parts[0]) * 1024
    except (OSError, ValueError):
        pass
    return result


def emit(phase):
    # Callers supply fixed phase names, never addresses, field text or requests.
    allowed = {'before-toolkit', 'toolkit-imported', 'webview-created',
               'window-presented', 'keyboard-before', 'keyboard-after',
               'keyboard-closed', 'navigation-started', 'navigation-finished',
               'periodic', 'shutdown'}
    if phase not in allowed:
        raise ValueError('Unknown measurement phase')
    processes = []
    root = Path('/sys/fs/cgroup/user.slice') / f'user-{os.getuid()}.slice'
    pending = [os.getpid()]
    # WebKit can spawn from a non-main thread and reparent through its sandbox.
    # Membership in the dedicated slice, rather than one thread's children,
    # identifies the complete Browser session.
    try:
        for group in list(root.glob('**/cgroup.procs'))[:64]:
            pending.extend(int(value) for value in group.read_text().split()[:24])
    except (OSError, ValueError): pass
    seen = set()
    deadline = time.monotonic() + .05
    while pending and len(seen) < 24 and time.monotonic() < deadline:
        pid = pending.pop(0)
        if pid in seen: continue
        seen.add(pid)
        base = Path('/proc') / str(pid)
        values = memory_fields(base / 'smaps_rollup')
        processes.append({'pid': pid, 'available': bool(values), 'memory_bytes': values})
        try:
            pending.extend(int(value) for value in
                           (base / 'task' / str(pid) / 'children').read_text().split()[:24])
        except (OSError, ValueError): pass
    session = {}
    for name in ('memory.current', 'memory.peak', 'memory.swap.current',
                 'memory.high', 'memory.max', 'memory.events', 'memory.stat'):
        try:
            text = (root / name).read_text()[:16384]
            if name in ('memory.events', 'memory.stat'):
                session[name] = {key: int(value) for key, value in
                                 (line.split() for line in text.splitlines())}
            else: session[name] = int(text.strip()) if text.strip().isdigit() else text.strip()
        except (OSError, ValueError): pass
    print('GUIDE_BROWSER_MEMORY ' + json.dumps({
        'phase': phase, 'observed': time.monotonic(), 'pid': os.getpid(),
        'processes': processes, 'session': session,
        'process_samples_partial': bool(pending),
    }, separators=(',', ':')), flush=True)
