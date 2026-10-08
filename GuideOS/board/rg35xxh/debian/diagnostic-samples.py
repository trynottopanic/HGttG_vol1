#!/usr/bin/python3
"""Bounded passive snapshots; sensor exposure is not a claim of calibration."""
import json
from pathlib import Path
import signal
import sys
import time

running=True
def stop(*args):
    global running
    running=False

def read(path):
    try: return Path(path).read_text().strip()
    except OSError: return None

def sample():
    return {'monotonic_seconds':time.monotonic(), 'loadavg':read('/proc/loadavg'),
            'memory':{line.split(':')[0]:line.split(':',1)[1].strip()
                      for line in (read('/proc/meminfo') or '').splitlines()
                      if line.startswith(('MemTotal:','MemAvailable:','SwapFree:'))},
            'thermal':[{'zone':p.name,'type':read(p/'type'),'millidegrees_c':read(p/'temp')}
                       for p in Path('/sys/class/thermal').glob('thermal_zone*')],
            'power':[{'device':p.name,'properties':read(p/'uevent')}
                     for p in Path('/sys/class/power_supply').glob('*')]}

if __name__=='__main__':
    signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)
    end=time.monotonic()+1150
    with open(sys.argv[1],'w',buffering=1) as out:
        while running and time.monotonic()<end:
            out.write(json.dumps(sample())+'\n')
            for _ in range(50):
                if not running: break
                time.sleep(.1)
