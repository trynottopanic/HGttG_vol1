import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from guide_application_runtime import request, load_policy
root=Path(sys.argv[1]);registry=Path('/var/lib/guideos/applications')
sys.path.insert(0,str(root.parent/'guide-installer'))
from guide_installer import policy,encode_record
ident='org.hhgtg.runtime-proof'
release=Path('/opt/guideos/applications')/ident/'releases'/'1.0.0'/'application'
release.mkdir(parents=True)
record=registry/'10001.policy'
def write_source(source,state='committed'):
    digest=hashlib.sha256(source).hexdigest();(release/'reference.py').write_bytes(source)
    package={'manifest':{'id':ident,'version':'1.0.0','entrypoint':{'module':'reference','callable':'application'}},'application':{'privateBytes':524288},'sourceHash':digest}
    r={'code':10001,'generation':1,'package':package,'agreement':{'revision':1,'granted':['storage.private','output.visual.surface','input.actions','input.text']},'state':state}
    r['runtime_policy']=policy(r);(registry/ident).mkdir(exist_ok=True)
    (registry/ident/'installation.json').write_bytes(encode_record(r));record.write_text(r['runtime_policy'])
    return digest
source=(root/'python/reference_application.py').read_bytes();digest=write_source(source)
load_policy(10001)

def rpc(path,op,args):
    with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as s:
        s.settimeout(1);s.connect(path);return request(s,op,args)
def supervisor(op,args):return rpc('/run/guideos/supervisor/control.sock',op,args)
def shell(op=1,args=None):return rpc('/run/guideos/apps/10001/shell.sock',op,args or {})
def wait(fn):
    end=time.monotonic()+5
    while time.monotonic()<end:
        try:
            result=fn()
            if result:return result
        except (OSError,PermissionError,EOFError):pass
        time.sleep(.05)
    subprocess.run(['journalctl','-u','guide-supervisor0.service','-u','guide-capability-broker0.service','-u','guide-app-*.service','--since','-1 minute','--no-pager'])
    raise AssertionError('bounded live check timed out')
def launch():
    identity=supervisor(1,{0:10001});wait(lambda:shell().get(0)==1)
    return identity
def stop(identity):
    supervisor(3,identity)
    status=wait(lambda:(s if s[0] in (7,8) else None) if (s:=supervisor(4,identity)) else None)
    assert status[1]==2,status
    return status
identity=launch();print('LIVE_INSTALLED_APPLICATION_READY',flush=True)
unit='guide-app-'+identity[0].hex()+'-g'+str(identity[1])+'.service'
properties=subprocess.check_output(['systemctl','show',unit,'-p','MainPID','-p','MemoryHigh','-p','MemoryMax','-p','TasksMax','-p','LimitNOFILE'],text=True)
props=dict(line.split('=',1) for line in properties.splitlines());pid=int(props['MainPID'])
assert os.stat('/proc/'+str(pid)).st_uid!=0
assert props['MemoryHigh']=='50331648' and props['MemoryMax']=='67108864' and props['TasksMax']=='5' and props['LimitNOFILE']=='32',props
children=Path(f'/proc/{pid}/task/{pid}/children').read_text().split();assert len(children)==1
child=children[0];assert os.stat('/proc/'+child).st_uid==os.stat('/proc/'+str(pid)).st_uid
assert 'Seccomp:\t2' in Path('/proc/'+child+'/status').read_text()
print('LIVE_KERNEL_LIMITS_PASS',json.dumps(props),flush=True)
try:supervisor(1,{0:10001})
except PermissionError:pass
else:raise AssertionError('duplicate application launch')
shell(2,{0:0});wait(lambda:shell().get(2) is not None);shell(3,{0:'synthetic checkpoint'})
wait(lambda:shell()[1][1]=='synthetic checkpoint')
# Supervisor restart must preserve running app identity and existing input/view.
subprocess.run(['systemctl','restart','guide-supervisor0.service'],check=True)
wait(lambda:shell()[1][1]=='synthetic checkpoint')
print('LIVE_SUPERVISOR_RECONCILIATION_PASS',flush=True)
stop(identity);print('LIVE_CHECKPOINT_STOP_PASS',flush=True)
identity=launch();assert shell()[1][1]=='synthetic checkpoint'
print('LIVE_PRIVATE_RELAUNCH_PASS',flush=True)
# Release presentation independently; private checkpoint must remain authorized.
shell(5,{0:3});assert shell()[1] is None
stop(identity);print('LIVE_INDEPENDENT_RELEASE_PASS',flush=True)
# Verify integrity denial before executing modified source.
(release/'reference.py').write_bytes(source+b'\n# tampered\n')
try:load_policy(10001)
except ValueError:pass
else:raise AssertionError('tampered payload accepted')
(release/'reference.py').write_bytes(source)
print('LIVE_RELEASE_INTEGRITY_PASS',flush=True)
# A ready app that ignores checkpoint must stop with an explicit failed save.
source=b"import time\ndef application(api):\n api.ready()\n while True: time.sleep(.01)\n"
digest=write_source(source)
identity=launch();supervisor(3,identity)
status=wait(lambda:(s if s[0] in (7,8) else None) if (s:=supervisor(4,identity)) else None)
assert status[1]==3,status
print('LIVE_UNACKNOWLEDGED_CHECKPOINT_FAILS_PASS',flush=True)
# A module that never reports ready fails without an automatic restart.
source=b"import time\ndef application(api):\n while True: time.sleep(.01)\n"
digest=write_source(source)
identity=supervisor(1,{0:10001});status=wait(lambda:supervisor(4,identity)[0]==8)
print('LIVE_READY_DEADLINE_PASS',flush=True)

# Exercise the actual asynchronous shell adapter and shared keyboard.
source=(root/'python/reference_application.py').read_bytes();digest=hashlib.sha256(source).hexdigest()
write_source(source)
project=root.parents[1]
sys.path[:0]=[str(project/'board/rg35xxh/debian/shell0'),str(project/'package/guide-ui')]
from guide_application_panel import ApplicationPanel
from guide_input import TextEntryManager
from guide_field_ui import FieldUI
panel=ApplicationPanel(10001,TextEntryManager())
try:
    wait(lambda:panel.view is not None if not panel.poll() else panel.view is not None)
    panel.action(0)
    wait(lambda:panel.editor is not None if not panel.poll() else panel.editor is not None)
    panel.editor.handle('insert',text=' shell');panel.editor.handle('submit');panel.finish_editor()
    wait(lambda:panel.view and panel.view[1].endswith(' shell') if not panel.poll() else panel.view and panel.view[1].endswith(' shell'))
    ui=FieldUI(project/'package/guide-ui')
    result=ui.render(panel.model());assert result.regions
    out=project/'build/application-host-0';out.mkdir(exist_ok=True)
    result.image.save(out/'reference-shell.png')
    panel.close();wait(lambda:panel.finished if not panel.poll() else panel.finished)
    assert not panel.failed
finally:panel.shutdown()
print('LIVE_SHELL_KEYBOARD_PRESENTATION_STOP_PASS',flush=True)

# Isolated health: ordinary launch denied; no foreground socket; owner state exact.
private=Path('/var/lib/guideos/applications')/ident/'private'/'objects'
before={p.name:p.read_bytes() for p in private.iterdir()}
write_source((root/'python/reference_application.py').read_bytes(),'testing')
try:supervisor(1,{0:10001})
except PermissionError:pass
else:raise AssertionError('testing release normal-launchable')
health=supervisor(5,{0:10001})
status=wait(lambda:(v if v[0] in (7,8) else None) if (v:=supervisor(4,health)) else None)
assert status=={0:7,1:2},status
assert not Path('/run/guideos/health/10001/shell.sock').exists()
assert before=={p.name:p.read_bytes() for p in private.iterdir()}
print('LIVE_ISOLATED_HEALTH_PRIVATE_PRESERVATION_PASS',flush=True)

# More distinct IDs than the broker cache: terminal identities must be reclaimed.
reference=(root/'python/reference_application.py').read_bytes()
for number in range(36):
    code=20000+number;app_id='org.hhgtg.cache-proof-'+str(number)
    folder=Path('/opt/guideos/applications')/app_id/'releases/1.0.0/application';folder.mkdir(parents=True);(folder/'reference.py').write_bytes(reference)
    package={'manifest':{'id':app_id,'version':'1.0.0','entrypoint':{'module':'reference','callable':'application'}},'application':{'privateBytes':524288},'sourceHash':hashlib.sha256(reference).hexdigest()}
    r={'code':code,'generation':1,'package':package,'agreement':{'revision':1,'granted':['storage.private','output.visual.surface','input.actions','input.text']},'state':'testing'};r['runtime_policy']=policy(r)
    (registry/app_id).mkdir();(registry/app_id/'installation.json').write_bytes(encode_record(r));(registry/(str(code)+'.policy')).write_text(r['runtime_policy'])
    identity=supervisor(5,{0:code});status=wait(lambda:(v if v[0] in (7,8) else None) if (v:=supervisor(4,identity)) else None)
    assert status=={0:7,1:2},(code,status)
print('LIVE_36_DISTINCT_APPLICATION_IDENTITIES_PASS',flush=True)
