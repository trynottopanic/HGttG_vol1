"""Overlay display handoff and owner recovery, independent of the shell loop."""
import json
from pathlib import Path
import subprocess
import time
from control_core import Foreground
from resource_host import Host, browser_group, bounded, fields


def active_vt():
    name=bounded('/sys/class/tty/tty0/active',32).strip()
    if name not in ('tty1','tty2','tty3'):
        raise RuntimeError('Unknown foreground display owner')
    return int(name[-1])


def switch_vt(number):
    if number not in (1,2,3):raise ValueError('Unknown display target')
    subprocess.run(['chvt',str(number)],check=True,timeout=2)
    deadline=time.monotonic()+1
    while active_vt()!=number and time.monotonic()<deadline:time.sleep(.01)
    if active_vt()!=number:raise RuntimeError('Display owner did not release its surface')


class OverlayLease:
    def __init__(self,foreground=None):
        self.foreground=foreground or Foreground()
        self.original=None
        self.browser=None
        self.browser_inode=None

    def prepare(self,ack,checkpoint=None):
        self.original=active_vt()
        if checkpoint:checkpoint(self.original,None)
        if not ack.wait(.75):
            raise RuntimeError('Foreground did not acknowledge display pause')
        # Weston/mpv and the shell must handle VT release BEFORE freezing.
        switch_vt(3)
        self.foreground.freeze()
        group=browser_group()
        if group.exists() and fields(group/'cgroup.events').get('populated')=='1':
            self.browser=group;self.browser_inode=group.stat().st_ino
            # Persist recovery ownership before pausing: a control-service
            # crash between freeze and returning must still be recoverable.
            if checkpoint:checkpoint(self.original,self.browser_inode)
            (group/'cgroup.freeze').write_text('1\n')
            deadline=time.monotonic()+1
            while fields(group/'cgroup.events').get('frozen')!='1' and time.monotonic()<deadline:
                time.sleep(.01)
            if fields(group/'cgroup.events').get('frozen')!='1':
                raise RuntimeError('Browser pause was not acknowledged')
        return self.original

    def release(self,home=False):
        # Missing groups exited. A replacement group must never be thawed by
        # stale overlay ownership.
        if self.browser and self.browser.exists():
            if self.browser.stat().st_ino!=self.browser_inode:
                raise RuntimeError('Paused Browser instance was replaced')
            (self.browser/'cgroup.freeze').write_text('0\n')
        self.foreground.thaw()
        if self.original:switch_vt(1 if home else self.original)
        if home:Host().command('start','--no-block','guide-shell.service')


def recovery_workloads():
    return Host().workloads()


def force_home(records):
    return Host().force_home(records)


def crash_recover(marker):
    if not marker.exists():return
    info=json.loads(bounded(marker,2048))
    group=browser_group()
    if info.get('browser_inode') and group.exists() and group.stat().st_ino==info['browser_inode']:
        (group/'cgroup.freeze').write_text('0\n')
    Foreground().thaw()
    switch_vt(info.get('original',1))
    if info.get('home'):Host().command('start','--no-block','guide-shell.service')
    marker.unlink(missing_ok=True)
