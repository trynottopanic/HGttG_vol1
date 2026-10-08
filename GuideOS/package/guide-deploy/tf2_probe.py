"""Fixed, bounded TF2 observation and temporary runtime-power comparison."""
import json
from pathlib import Path
import signal
import subprocess
import time
from deploy_core import Rejected, require, atomic_json
HOST=Path('/sys/bus/platform/devices/4022000.mmc')
STATE=Path('/run/guideos-tf2-probe')
UNIT='guide-tf2-probe.service'
SECONDS=120

def read(path):
    try:
        with path.open() as stream:return stream.read(4096).strip()
    except OSError:return None

def snapshot(host=HOST):
    value={name:read(host/'power'/name) for name in ('control','runtime_status','runtime_error','runtime_usage','autosuspend_delay_ms')}
    value.update(controller=host.name,observed=time.monotonic(),cards=sorted(p.name for p in (host/'mmc_host').glob('mmc*/mmc*:*'))[:4])
    return value

def result():
    try:
        with (STATE/'result.json').open() as stream:return json.loads(stream.read(131072))
    except (OSError,ValueError):return dict(state='not-run')

def media_idle():
    import socket
    from deploy_diagnostics import health
    audio=health()['audio']
    require(not audio.get('stale',True) and audio.get('state') in ('stopped','finished','failed'),'audio-must-be-idle')
    with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as connection:
        connection.settimeout(1);connection.connect('/run/guideos-player/control.sock')
        connection.send(b'{"action":"status"}')
        reply=json.loads(connection.recv(8193))
    require(reply.get('ok') and reply['result'].get('state')=='stopped','media-must-be-idle')

def validate_host(host=HOST):
    require(host.is_dir() and host.resolve().name=='4022000.mmc','tf2-unavailable')
    require((host/'driver').resolve().name=='sunxi-mmc','tf2-driver-mismatch')
    require(read(host/'power/control') in ('auto','on'),'tf2-power-policy-unavailable')

def start(hold_awake):
    validate_host();media_idle()
    require(subprocess.run(['systemctl','is-active','--quiet',UNIT],timeout=3).returncode!=0,'tf2-probe-busy')
    STATE.mkdir(mode=0o700,exist_ok=True)
    try:
        with (STATE/'request.json').open('x') as stream:json.dump(dict(hold_awake=hold_awake),stream)
    except FileExistsError:raise Rejected('tf2-probe-busy') from None
    atomic_json(STATE/'result.json',dict(state='queued',hold_awake=hold_awake))
    try:subprocess.run(['systemctl','start','--no-block',UNIT],check=True,timeout=3)
    except (OSError,subprocess.SubprocessError):
        (STATE/'request.json').unlink(missing_ok=True)
        raise Rejected('tf2-probe-start-failed') from None
    return dict(state='queued',hold_awake=hold_awake,seconds=SECONDS)

def run_probe(host=HOST,state=STATE,seconds=SECONDS,sleep=time.sleep):
    validate_host(host)
    request=json.loads((state/'request.json').read_text())
    require(set(request)=={'hold_awake'} and type(request['hold_awake']) is bool,'bad-tf2-request')
    original=read(host/'power/control');changed=False;stopped=False
    def stop(*_):
        nonlocal stopped
        stopped=True
    previous={sig:signal.signal(sig,stop) for sig in (signal.SIGINT,signal.SIGTERM)}
    report=dict(state='running',original_policy=original,hold_awake=request['hold_awake'],samples=[])
    try:
        if request['hold_awake']:
            changed=True;(host/'power/control').write_text('on\n')
            require(read(host/'power/control')=='on','tf2-policy-write-failed')
        deadline=time.monotonic()+seconds
        while not stopped and time.monotonic()<deadline:
            report['samples'].append(snapshot(host));atomic_json(state/'result.json',report)
            sleep(min(1,max(0,deadline-time.monotonic())))
        report['state']='interrupted' if stopped else 'complete'
    except Exception:
        report['state']='failed'
        raise
    finally:
        try:
            if changed:(host/'power/control').write_text(original+'\n')
            report['restored']=read(host/'power/control')==original
            if not report['restored']:report['state']='restoration-failed'
            atomic_json(state/'result.json',report)
        finally:
            (state/'request.json').unlink(missing_ok=True)
            for sig,handler in previous.items():signal.signal(sig,handler)

if __name__=='__main__':run_probe()
