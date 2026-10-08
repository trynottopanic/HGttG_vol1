"""Fixed board diagnostics and an explicit, idle-only speaker isolation probe."""
import fcntl
import hashlib
import json
import math
import os
import pwd
from itertools import islice
from pathlib import Path
import secrets
import struct
import subprocess
import tempfile
import time
import wave
import zipfile
from deploy_core import Rejected, require
from deploy_diagnostics import health, head, report
from audio_path_diagnostics import board_snapshot, test_signal, compact_graph

STATE=Path('/run/guideos-speaker-probe')
PUBLIC=Path('/run/guideos-tone-status.json')
EXPORTS=Path('/run/guideos-diagnostics/exports')
EXPORT_MAX_AGE=3600
EXPORT_CHUNK_MAX=240000
LOG_FILES=('diagnostics.jsonl','diagnostics.1.jsonl','diagnostics.2.jsonl','diagnostics.3.jsonl',
           'journal.jsonl','journal.1.jsonl','journal.2.jsonl','journal.3.jsonl')
TONES=('file-s16','file-s32','internal-sine','file-s16-higher')
SERVICES=('guide-pipewire.service','guide-wireplumber.service','guide-audio.service')

def command(argv, limit=24000, timeout=5):
    try:
        with tempfile.TemporaryFile() as output:
            run=subprocess.run(argv,stdout=output,stderr=subprocess.STDOUT,timeout=timeout)
            output.seek(0); raw=output.read(limit+1)
        return dict(available=run.returncode==0,returncode=run.returncode,truncated=len(raw)>limit,text=raw[:limit].decode(errors='replace'))
    except (OSError,subprocess.TimeoutExpired) as exc:
        return dict(available=False,reason=type(exc).__name__)

def browser_process_snapshot():
    roots=[Path('/sys/fs/cgroup/system.slice/guide-browser.service')]
    try:roots.append(Path('/sys/fs/cgroup/user.slice')/f'user-{pwd.getpwnam("guide-browser").pw_uid}.slice')
    except KeyError:pass
    pids=set()
    for root in roots:
        for path in ([root/'cgroup.procs']+list(islice(root.glob('**/cgroup.procs'),64))):
            try:pids.update(int(value) for value in path.read_text().split()[:256] if value.isdigit())
            except OSError:continue
    if not pids:return {'available':False,'processes':[]}
    rows=[]
    env_names={'DISPLAY','WAYLAND_DISPLAY','XDG_RUNTIME_DIR','XDG_SESSION_TYPE','GDK_BACKEND',
               'WEBKIT_DISABLE_DMABUF_RENDERER','WEBKIT_DISABLE_COMPOSITING_MODE','LD_LIBRARY_PATH',
               'DBUS_SESSION_BUS_ADDRESS','LANG','LC_ALL'}
    for pid in sorted(pids)[:256]:
        base=Path('/proc')/str(pid)
        try:
            comm=(base/'comm').read_text().strip()[:64]
            raw=(base/'cmdline').read_bytes()[:8192]
            argv=[part.decode(errors='replace') for part in raw.rstrip(b'\0').split(b'\0') if part]
            fields={}
            for line in (base/'status').read_text().splitlines():
                key,sep,value=line.partition(':')
                if sep and key in ('State','Uid','Gid','Groups','CapEff','NoNewPrivs',
                                   'VmRSS','RssAnon','RssFile','RssShmem','VmSwap','VmHWM'):fields[key]=value.strip()
            environment={}
            for item in (base/'environ').read_bytes()[:65536].split(b'\0'):
                key,sep,value=item.partition(b'=')
                if sep and key.decode(errors='ignore') in env_names:
                    environment[key.decode(errors='ignore')]=value.decode(errors='replace')[:512]
            fds=[]
            for fd in sorted((base/'fd').iterdir(),key=lambda path:int(path.name) if path.name.isdigit() else 999999)[:256]:
                try:target=os.readlink(fd)
                except OSError:continue
                if target.startswith(('/dev/dri/','/dev/fb','/dev/tty','/run/guideos-browser')) or target.startswith('socket:'):
                    fds.append({'fd':fd.name,'target':target[:256]})
            rows.append({'pid':pid,'comm':comm,'argv':argv,'status':fields,'environment':environment,'relevant_fds':fds})
        except (OSError,ValueError):continue
    return {'available':True,'cgroup':str(roots[0]),'cgroups':[str(root) for root in roots],'processes':rows}


def inspect():
    result={}
    browser_scope=['-u','guide-browser.service']
    try:browser_scope=['_SYSTEMD_UNIT=guide-browser.service','+',
                      'UNIT=guide-browser.service','+',
                      '_UID='+str(pwd.getpwnam('guide-browser').pw_uid)]
    except KeyError:pass
    scopes={'boot':['-u','guide-boot-animation.service'], 'kernel':['-k'],
            'audio':['-u',SERVICES[0],'-u',SERVICES[1],'-u',SERVICES[2]],
            'bluetooth':['-u','bluetooth.service','-u','hciuart.service'],
            'storage':['-u','guide-storage.service','-u','guide-media-library.socket'],
            'media_player':['-u','guide-media-player.service','-u','guide-media-player.socket'],
            'browser':browser_scope,
            'resources':['-u','guide-resources.service','-u','guide-zram.service'],
            'shell':['-u','guide-shell.service','-u','guide-control.service','-u','guide-diagnostics.service'],
            'network':['-u','NetworkManager.service','-u','wpa_supplicant.service'],
            'link':['-u','guide-deploy.service','-u','guide-deploy-ssh.service']}
    for name,scope in scopes.items():
        result[name]=command(['journalctl','-b','--no-pager','-o','short-monotonic','-n','300',*scope],limit=12000)
    units=['guide-browser.service','weston.service','guide-shell.service','guide-control.service',
           'guide-diagnostics.service','guide-resources.service','guide-zram.service','guide-boot-animation.service','guide-deploy.service',
           'guide-deploy-ssh.service','guide-storage.service','guide-media-library.socket',
           'guide-media-player.service','guide-media-player.socket',*SERVICES,
           'NetworkManager.service','wpa_supplicant.service','bluetooth.service']
    result['service_state']=command(['systemctl','show',*units,'-p','Id','-p','LoadState','-p','ActiveState',
        '-p','SubState','-p','Result','-p','ExecMainCode','-p','ExecMainStatus','-p','ConditionResult',
        '-p','NRestarts','-p','MainPID','-p','ActiveEnterTimestampMonotonic','-p','FragmentPath',
        '-p','DropInPaths','-p','ExecStart','-p','ExecStartPre','-p','ExecStopPost',
        '-p','ControlPID','-p','TimeoutStartUSec','-p','Environment',
        '-p','ControlGroup','-p','MemoryCurrent','-p','MemoryPeak','-p','MemoryHigh','-p','MemoryMax','-p','MemorySwapMax'],limit=32768)
    result['resource_status']=head('/run/guideos-resources/status.json',65536)
    result['failed_units']=command(['systemctl','--failed','--no-legend','--plain'],limit=8192)
    result['network_links']=command(['ip','-details','-statistics','link','show'],limit=16384)
    result['network_addresses']=command(['ip','-brief','address','show'],limit=8192)
    result['network_routes']=command(['ip','route','show','table','all'],limit=8192)
    result['wifi_radio']=command(['iw','dev'],limit=8192)
    result['rfkill']=command(['rfkill','list'],limit=8192)
    result['boot_launch']=command(['systemctl','show','guide-boot-animation.service','-p','FragmentPath','-p','DropInPaths','-p','ExecStart','-p','Result'])
    result['boot_world']=head('/var/lib/guideos-boot-world/counter.json',4096)
    result['gpio']=head('/sys/kernel/debug/gpio',12000)
    result['dapm']={str(p):head(p,2048) for p in sorted(Path('/sys/kernel/debug/asoc').glob('*/dapm/*'))[:24] if p.is_file()}
    result['controllers']=[p.name for p in Path('/sys/class/bluetooth').glob('hci*') if ':' not in p.name]
    result['drm']={}
    for connector in sorted(Path('/sys/class/drm').glob('card*-*'))[:32]:
        if not connector.is_dir():continue
        result['drm'][connector.name]={name:head(connector/name,4096) for name in ('status','enabled','dpms','modes') if (connector/name).exists()}
    result['drm_devices']=[dict(name=p.name,available=p.exists()) for p in sorted(Path('/dev/dri').glob('*'))[:32]]
    result['browser_processes']=browser_process_snapshot()
    runtime=Path('/run/guideos-browser')
    try:result['browser_runtime']=[dict(name=p.name,directory=p.is_dir(),socket=p.is_socket()) for p in sorted(runtime.iterdir())[:64]] if runtime.is_dir() else []
    except OSError:result['browser_runtime']=[]
    result['thermal']={p.parent.name:head(p,128) for p in sorted(Path('/sys/class/thermal').glob('thermal_zone*/temp'))[:16]}
    result['cpu_frequency']={p.parent.name:head(p,128) for p in sorted(Path('/sys/devices/system/cpu/cpufreq').glob('policy*/scaling_cur_freq'))[:8]}
    from tf2_probe import snapshot
    result['tf2']=snapshot()
    result['storage_status']=head('/run/guideos-storage/status.json',4096)
    clocks=head('/sys/kernel/debug/clk/clk_summary',65536)
    result['mmc_clocks']=[line for line in clocks.get('text','').splitlines() if line.split() and line.split()[0] in ('mmc0','mmc1','mmc2','bus-mmc0','bus-mmc1','bus-mmc2')]
    result['probe']={k:v for k,v in probe_status().items() if k in ('state','restored','returncode','reason')}
    result['probe']['details_operation']='probe-result'
    return result


def _remove_expired_exports(now=None):
    now=time.time() if now is None else now
    EXPORTS.mkdir(mode=0o700,parents=True,exist_ok=True)
    for path in EXPORTS.glob('[0-9a-f]'*32+'.zip'):
        try:
            if now-path.stat().st_mtime>EXPORT_MAX_AGE:path.unlink()
        except OSError:pass


def begin_full_capture():
    """Freeze a broad, read-only Deck snapshot for chunked transfer to the paired PC."""
    now=time.time();_remove_expired_exports(now)
    capture_id=secrets.token_hex(16)
    path=EXPORTS/f'{capture_id}.zip'
    metadata={'capture_id':capture_id,'captured_unix':now,
              'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
              'capture_scope':'current-boot process, service, kernel, display, network, storage, audio and retained diagnostics'}
    status=head('/run/guideos-diagnostics/status.json',1048576)
    live_journal=command(['journalctl','-b','--no-pager','--all','-n','3000','-o','json'],limit=2*1024*1024,timeout=12)
    report_value=report();inspect_value=inspect()
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        archive.writestr('capture.json',json.dumps(metadata,indent=2))
        archive.writestr('report.json',json.dumps(report_value,separators=(',',':')))
        archive.writestr('inspect.json',json.dumps(inspect_value,separators=(',',':')))
        archive.writestr('diagnostics-status.json',json.dumps(status,separators=(',',':')))
        archive.writestr('current-boot-journal.json',json.dumps(live_journal,separators=(',',':')))
        data=Path('/data/guideos/diagnostics')
        for name in LOG_FILES:
            source=data/name
            try:
                if source.is_file() and not source.is_symlink() and source.stat().st_size<=2*1024*1024:
                    archive.write(source,'retained-logs/'+name)
            except OSError:pass
    size=path.stat().st_size
    require(size<=24*1024*1024,'capture-size-limit')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    os.chmod(path,0o600)
    return {'id':capture_id,'bytes':size,'sha256':digest,'expires_in_seconds':EXPORT_MAX_AGE,
            'chunk_bytes':EXPORT_CHUNK_MAX}


def full_capture_chunk(capture_id,offset,length):
    require(isinstance(capture_id,str) and len(capture_id)==32 and all(c in '0123456789abcdef' for c in capture_id),'bad-capture-id')
    require(type(offset) is int and offset>=0 and type(length) is int and 0<length<=EXPORT_CHUNK_MAX,'bad-capture-range')
    path=EXPORTS/f'{capture_id}.zip'
    require(path.is_file() and not path.is_symlink(),'capture-unavailable')
    require(time.time()-path.stat().st_mtime<=EXPORT_MAX_AGE,'capture-expired')
    size=path.stat().st_size
    require(offset<=size,'bad-capture-range')
    with path.open('rb') as stream:stream.seek(offset);data=stream.read(min(length,size-offset))
    import base64
    return {'offset':offset,'bytes':len(data),'data':base64.b64encode(data).decode('ascii')}


def finish_full_capture(capture_id):
    require(isinstance(capture_id,str) and len(capture_id)==32 and all(c in '0123456789abcdef' for c in capture_id),'bad-capture-id')
    (EXPORTS/f'{capture_id}.zip').unlink(missing_ok=True)
    return {'released':True}

def audio_path():
    raw=command(['runuser','-u','guide-audio','--','env','XDG_RUNTIME_DIR=/run/guide-audio','pw-dump'],limit=1048576)
    graph=dict(available=False,reason='graph-unavailable-or-oversized')
    if raw.get('available') and not raw.get('truncated'):
        try:graph=compact_graph(json.loads(raw['text']))
        except (ValueError,TypeError,AttributeError):pass
    return dict(board=board_snapshot(),mixer=command(['amixer','-c','Codec','contents'],limit=8192),
        graph=graph,source=test_signal('/data/guideos/media/Guide-audio-test.wav'))

def probe_status():
    try:return json.loads((STATE/'result.json').read_text())
    except (OSError,ValueError):return {'state':'not-run'}

def save(value):
    STATE.mkdir(mode=0o700,exist_ok=True)
    path=STATE/'result.tmp'; path.write_text(json.dumps(value)); path.replace(STATE/'result.json')

def idle():
    audio=health()['audio']
    return not audio.get('stale',True) and audio.get('state') in ('stopped','failed','finished')

def publish(tone, phase, seconds=0):
    temporary=PUBLIC.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(tone=tone,phase=phase,seconds=seconds,
        expires=time.monotonic()+(20 if phase in ('finished','failed') else 60))))
    temporary.chmod(0o644)
    temporary.replace(PUBLIC)

def announce(tone):
    for seconds in range(5,0,-1):
        publish(tone,'countdown',seconds)
        time.sleep(1)
    publish(tone,'playing')

def start_probe(selected=None):
    require(selected in (None,*TONES),'unsupported-tone')
    require(idle(),'audio-must-be-idle')
    require(subprocess.run(['systemctl','is-active','--quiet','guide-speaker-probe.service']).returncode!=0,'probe-busy')
    STATE.mkdir(mode=0o700,exist_ok=True)
    try:
        with (STATE/'request.json').open('x') as stream:json.dump({'selected':selected},stream)
    except FileExistsError:raise Rejected('probe-busy') from None
    save(dict(state='queued',selected=selected,audibility='unreported'))
    result=command(['systemctl','start','--no-block','guide-speaker-probe.service'])
    if not result['available']:(STATE/'request.json').unlink(missing_ok=True)
    require(result['available'],'probe-start-failed')
    return {'state':'queued','result_operation':'inspect'}

def restore():
    path=STATE/'restore.json'
    if not path.exists():return
    plan=json.loads(path.read_text())
    results=[]
    if (STATE/'mixer.state').exists():
        results.append(command(['alsactl','-f',str(STATE/'mixer.state'),'restore','Codec']))
    if plan.get('diagnostic_source'):
        normal=command(['amixer','-c','Codec','cset','name=DAC Diagnostic Source','Normal'])
        results.append(normal)
        if not normal['available']:
            # Do not restart user playback with a possibly latched test source.
            result=probe_status();result.update(state='failed',restored=False,
                reason='diagnostic-source-reset-failed',restoration=results)
            save(result)
            return
    if plan.get('buffer_probe'):
        disarmed=command(['amixer','-c','Codec','cset','name=DAC Buffer Probe','off'])
        results.append(disarmed)
        if not disarmed['available']:
            result=probe_status();result.update(state='failed',restored=False,
                reason='buffer-probe-disarm-failed',restoration=results)
            save(result)
            return
    for unit in plan['active']:
        results.append(command(['systemctl','start',unit],timeout=8))
    result=probe_status()
    result['after']=board_snapshot()
    result['restoration']=results
    result['restored']=all(r['available'] for r in results)
    if result.get('state')=='running':result['state']='interrupted'
    save(result)
    if result['restored']:path.unlink()

def probe():
    STATE.mkdir(mode=0o700,exist_ok=True)
    with open('/opt/guideos/deploy/lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(idle(),'audio-must-be-idle')
        require(not (STATE/'restore.json').exists(),'previous-restoration-incomplete')
        request=STATE/'request.json'
        selected=json.loads(request.read_text())['selected'] if request.exists() else None
        require(selected in (None,*TONES),'unsupported-tone')
        active=[u for u in SERVICES if subprocess.run(['systemctl','is-active','--quiet',u]).returncode==0]
        result={'state':'running','selected':selected,'audibility':'unreported','started_monotonic':time.monotonic(),'before':board_snapshot()}
        save(result)
        stored=command(['alsactl','-f',str(STATE/'mixer.state'),'store','Codec'])
        require(stored['available'],'mixer-backup-failed')
        (STATE/'restore.json').write_text(json.dumps({'active':active}))
        try:
            for unit in reversed(active):
                require(command(['systemctl','stop',unit],timeout=8)['available'],'audio-stop-failed')
            require(command(['amixer','-c','Codec','cset','name=DAC Diagnostic Source','Normal'])['available'],'diagnostic-source-unavailable')
            (STATE/'restore.json').write_text(json.dumps({'active':active,'diagnostic_source':True,'buffer_probe':True}))
            for control,value in [('DAC Playback Volume','58'),('Line Out Playback Volume','27'),('DAC Playback Switch','on'),('Line Out Playback Switch','on'),('DAC Reversed Playback Switch','off'),('Line Out Source Playback Route','Stereo'),('Speaker Switch','on')]:
                require(command(['amixer','-c','Codec','cset','name='+control,value])['available'],'mixer-set-failed')
            from audio_probe_sequence import sequence
            def progress(stages):
                result['stages']=stages
                save(result)
            result['stages']=sequence(STATE,command,board_snapshot,progress,selected,announce,probe_buffer=True)
            result['state']='complete' if all(s['state']=='complete' for s in result['stages']) else 'failed'
        except Exception as exc:
            result.update(state='failed',reason=str(exc))
        finally:
            publish(selected or 'sequence','restoring')
            save(result)
            restore()
            restored=probe_status().get('restored',False)
            publish(selected or 'sequence','finished' if restored else 'failed')

if __name__=='__main__':
    import sys
    if sys.argv[1:]==['restore']:
        restore()
        (STATE/'request.json').unlink(missing_ok=True)
        result=probe_status()
        publish(result.get('selected') or 'sequence','finished' if result.get('restored') else 'failed')
    elif sys.argv[1:]==['probe']:
        try:probe()
        except Exception as exc:
            result=probe_status();result.update(state='failed',reason=str(exc));save(result)
            raise
