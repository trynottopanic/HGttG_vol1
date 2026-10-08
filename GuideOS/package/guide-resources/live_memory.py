"""Opt-in host proof: disposable PAM workload, real cap, unrelated heartbeat.

Run as root on a Linux systemd host. It creates and removes only a uniquely named
test account, test units and their runtime slice drop-in. No Deck hardware claim.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import subprocess
import tempfile
import time
import uuid
from browser_cleanup import cleanup_group
from resource_host import set_oom_group


WORKER='''
import json,os,pathlib,time
p=pathlib.Path(__import__('sys').argv[1])
(p/'ready').write_text(json.dumps(dict(pid=os.getpid(),group=pathlib.Path('/proc/self/cgroup').read_text())))
while not (p/'go').exists():time.sleep(.02)
child=os.fork()
if child==0:
 pages=[]
 while True:
  pages.append(bytearray(1024*1024))
  time.sleep(.01)
else:
 (p/'child').write_text(str(child))
 while True:time.sleep(.02)
'''


def main(output):
    if os.geteuid()!=0:raise RuntimeError('Disposable systemd fixture requires root')
    token=uuid.uuid4().hex[:10]
    user='guide-mem-'+token;unit='guide-memory-test-'+token+'.service'
    command=lambda *args:subprocess.run(args,check=True,timeout=10,capture_output=True,text=True)
    uid=None;dropin=None
    with tempfile.TemporaryDirectory(prefix='guide-memory-fixture-') as directory:
        path=Path(directory);path.chmod(0o777)
        try:
            command('useradd','--system','--no-create-home','--shell','/usr/sbin/nologin',user)
            uid=pwd.getpwnam(user).pw_uid
            dropin=Path(f'/run/systemd/system/user-{uid}.slice.d/90-guide-memory-fixture.conf')
            dropin.parent.mkdir(parents=True,exist_ok=True)
            # Exercise the final ceiling independently of soft-limit reclaim;
            # sustained memory.high throttling is covered by the guard tests.
            dropin.write_text('[Slice]\nMemoryAccounting=yes\nMemoryHigh=infinity\nMemoryMax=64M\nMemorySwapMax=0\nTasksMax=64\n')
            command('systemctl','daemon-reload')
            command('systemctl','start',f'user-{uid}.slice')
            command('systemd-run','--unit='+unit,'-p','User='+user,'-p','PAMName=login',
                    '-p','Restart=no','-p','OOMPolicy=kill','-p','OOMScoreAdjust=300','/usr/bin/python3','-c',WORKER,directory)
            deadline=time.monotonic()+10
            while not (path/'ready').exists() and time.monotonic()<deadline:time.sleep(.02)
            ready=json.loads((path/'ready').read_text())
            expected=f'/user.slice/user-{uid}.slice/'
            assert '0::'+expected in ready['group'],ready
            group=Path('/sys/fs/cgroup/user.slice')/f'user-{uid}.slice'
            set_oom_group(group)
            assert int((group/'memory.max').read_text())==64*1024**2
            assert (group/'memory.oom.group').read_text().strip()=='1'
            score_before=Path(f'/proc/{ready["pid"]}/oom_score_adj').read_text().strip()
            (path/'go').touch()
            deadline=time.monotonic()+10;beats=0;maximum_gap=0;previous=time.monotonic()
            while time.monotonic()<deadline:
                now=time.monotonic();maximum_gap=max(maximum_gap,now-previous);previous=now;beats+=1
                events=dict(line.split() for line in (group/'memory.events').read_text().splitlines())
                populated='populated 1' in (group/'cgroup.events').read_text()
                if int(events.get('oom_kill',0))>0:break
                time.sleep(.02)
            assert int(events.get('oom_kill',0))>0,events
            child=int((path/'child').read_text())
            def alive(pid):
                try:return Path(f'/proc/{pid}/stat').read_text().split()[2]!='Z'
                except FileNotFoundError:return False
            deadline=time.monotonic()+3
            while (alive(ready['pid']) or alive(child)) and time.monotonic()<deadline:time.sleep(.02)
            oom_survivors=[pid for pid in (ready['pid'],child) if alive(pid)]
            # PAM may keep its dedicated user manager alive after the page
            # exits. Exercise the production cleanup, after stopping the
            # launcher so it cannot create another session during cleanup.
            command('systemctl','stop',unit)
            cleanup_group(group)
            populated=group.exists() and 'populated 1' in (group/'cgroup.events').read_text()
            assert not populated,'Dedicated session helpers survived cleanup'
            assert not alive(ready['pid']) and not alive(child),'Application survived production cleanup'
            assert maximum_gap<1,'Unrelated host heartbeat stalled'
            result=dict(status='LIVE_PAM_SESSION_MEMORY_CONTAINMENT_PASS',pamScope=ready['group'].strip(),
                memoryMax=64*1024**2,memoryEvents=events,wholeGroupEmpty=True,
                parentAndChildKilled=True,productionCleanupExercised=True,
                survivorsBeforeCleanup=oom_survivors,
                fixtureParentOOMScoreAdj=score_before,
                unrelatedHeartbeatSamples=beats,maximumHeartbeatGapMs=round(maximum_gap*1000,2),
                deckPhysicalEvidence=False)
            Path(output).write_text(json.dumps(result,indent=2));print(json.dumps(result))
        finally:
            for target in [unit]+([f'user@{uid}.service',f'user-{uid}.slice'] if uid is not None else []):
                subprocess.run(['systemctl','stop',target],timeout=10,capture_output=True)
                subprocess.run(['systemctl','reset-failed',target],timeout=10,capture_output=True)
            if dropin:
                dropin.unlink(missing_ok=True)
                try:dropin.parent.rmdir()
                except OSError:pass
            subprocess.run(['systemctl','daemon-reload'],timeout=10,capture_output=True)
            subprocess.run(['userdel',user],timeout=10,capture_output=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output')
    main(parser.parse_args().output)
