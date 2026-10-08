"""Early resource recovery for the Browser's explicit ephemeral-session policy."""
from pathlib import Path
import signal
import time
from resource_host import Host, RUNTIME, MIB, browser_group, bounded, fields, mem_available, atomic, set_oom_group


class Pressure:
    """PSI if provided; available RAM and direct reclaim on older board kernels."""
    def __init__(self):
        self.previous = None
        self.previous_high = None
        self.since = None

    def sample(self, available, reclaim, psi, now, high_events=0):
        growth = self.previous is not None and reclaim > self.previous
        self.previous = reclaim
        thrashing=self.previous_high is not None and high_events-self.previous_high>32
        self.previous_high=high_events
        threatened = thrashing or available < 96 * MIB or (available < 128 * MIB and (growth or psi >= .20))
        if not threatened:
            self.since = None
            return False
        if self.since is None:
            self.since = now
        return now - self.since >= 2


def pressure_counters(proc=Path('/proc')):
    counters = fields(proc / 'vmstat')
    reclaim = sum(int(value) for key, value in counters.items() if key.startswith('allocstall'))
    psi = 0.0
    try:
        for line in bounded(proc / 'pressure/memory').splitlines():
            if line.startswith('full '):
                psi = float(dict(item.split('=') for item in line.split()[1:])['avg10']) / 100
    except (OSError, ValueError, KeyError):
        pass
    return reclaim, psi


def main():
    host = Host()
    policy = Pressure()
    stopping = []
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: stopping.append(True))
    last = None
    previous_oom=None
    while not stopping:
        now = time.monotonic()
        status = dict(observed=now, headroom_bytes=128*MIB, state='ready', last_recovery=last)
        try:
            available = mem_available()
            reclaim, psi = pressure_counters()
            status.update(available_bytes=available, direct_reclaim=reclaim, memory_pressure=psi)
            group = browser_group()
            high_events=0
            oom_event=False
            if group.exists():
                set_oom_group(group)
                status['browser'] = dict(current=int(bounded(group/'memory.current')),
                    high=bounded(group/'memory.high').strip(), max=bounded(group/'memory.max').strip(),
                    events=fields(group/'memory.events'))
                high_events=int(status['browser']['events'].get('high',0))
                oom=(group.stat().st_ino,int(status['browser']['events'].get('oom_kill',0)))
                oom_event=previous_oom is not None and oom[0]==previous_oom[0] and oom[1]>previous_oom[1]
                previous_oom=oom
            else:raise RuntimeError('Browser resource group is unavailable')
            pressure=policy.sample(available, reclaim, psi, now,high_events)
            if pressure or oom_event:
                targets = host.workloads()
                browser = next((row for row in targets if row['unit']=='guide-browser.service'), None)
                if browser:
                    status['state']='recovering'
                    atomic(RUNTIME/'status.json', status)
                    print('GUIDE_RESOURCE_RECOVERY browser pressure; ephemeral page state may be lost', flush=True)
                    outcome = host.stop(browser)
                    last = dict(observed=time.monotonic(), unit=browser['unit'], invocation=browser['invocation'],
                                reason='memory limit' if oom_event else 'memory pressure', outcome=outcome)
                    atomic(RUNTIME/'browser-result.json', last)
                    policy.since = None
                elif oom_event:
                    last=dict(observed=time.monotonic(),unit='guide-browser.service',
                              reason='memory limit',outcome='session exited')
                    atomic(RUNTIME/'browser-result.json',last)
            status['last_recovery']=last
        except (OSError, ValueError, RuntimeError, KeyError) as error:
            status.update(state='unavailable', detail=str(error)[:160])
        atomic(RUNTIME/'status.json', status)
        time.sleep(.5)


if __name__ == '__main__':
    main()
