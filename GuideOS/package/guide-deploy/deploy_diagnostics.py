"""Read-only diagnostic operations on the existing paired development transport."""
import json
from pathlib import Path
import subprocess
import time


def read_json(path, limit=131072):
    try:
        with Path(path).open('rb') as stream:
            raw=stream.read(limit+1)
        if len(raw)>limit: return {'available':False,'reason':'size-limit'}
        value=json.loads(raw)
        if not isinstance(value,dict): raise ValueError()
        return value
    except (OSError,ValueError):
        return {'available':False,'reason':'unavailable'}


def health(root=Path('/'), now=None):
    root=Path(root); now=time.monotonic() if now is None else now
    diagnostic=read_json(root/'run/guideos-diagnostics/status.json')
    audio=read_json(root/'run/guideos-audio/status.json')
    def cached(data, fields):
        result={k:data[k] for k in fields if k in data}
        stamp=data.get('observed')
        age=max(0,now-stamp) if type(stamp) in (int,float) and 0<=stamp<=now else None
        result.update(available=age is not None,age_seconds=round(age,2) if age is not None else None,
                      stale=age is None or age>15)
        return result
    stats=cached(diagnostic,('boot_id','memory','cpu_percent_total','logical_cpus','counters',
                            'latest_events','dropped_events','log_write_errors','sample_cost_ms',
                            'skipped_processes','truncated'))
    # Export bounded process CPU time only: no PID, command line, paths or environment.
    process_rows=diagnostic.get('processes',[])
    safe_processes=[]
    if isinstance(process_rows,list):
        for row in process_rows:
            if not isinstance(row,dict):continue
            name=row.get('name');cpu=row.get('cpu_percent_one_core')
            cpu_time=row.get('cpu_time_seconds');rss=row.get('rss_bytes')
            if (not isinstance(name,str) or not name.isascii() or len(name)>32 or
                    any(not (ch.isalnum() or ch in '._()-') for ch in name) or
                    type(cpu) not in (int,float) or not 0<=cpu<=10000 or
                    type(cpu_time) not in (int,float) or cpu_time<0 or
                    type(rss) is not int or rss<0):continue
            safe_processes.append(dict(name=name,cpu_percent_one_core=round(cpu,2),
                                       cpu_time_seconds=round(cpu_time,3),rss_bytes=rss))
    stats['top_processes']=sorted(safe_processes,key=lambda row:row['cpu_percent_one_core'],reverse=True)[:8]
    # Explicitly omit media filenames, SSIDs, device aliases and paired addresses.
    sound=cached(audio,('state','position','volume','busy','scanning','bluetooth_adapters'))
    output=audio.get('output') or ''
    sound['output_kind']='bluetooth' if output.startswith('bluez_output.') else 'local' if output.startswith('alsa_output.') else 'other' if output else 'none'
    sound['connected_devices']=sum(d.get('connected') is True for d in audio.get('devices',[]) if isinstance(d,dict))
    return dict(protocol='GUIDE-LINK-1',observed=now,diagnostics=stats,audio=sound,
                time_synchronized=(root/'run/systemd/timesync/synchronized').exists())


def tail(path, limit=65536):
    try:
        with Path(path).open('rb') as stream:
            stream.seek(0,2); size=stream.tell(); stream.seek(max(0,size-limit))
            raw=stream.read(limit)
        if size>limit: raw=raw.partition(b'\n')[2]
        return dict(available=True,truncated=size>limit,text=raw.decode('utf-8',errors='replace'))
    except OSError:
        return dict(available=False,truncated=False,text='')


def head(path,limit=2048):
    # /proc PCM status uses seq_file: seeking to EOF is not supported.
    try:
        with Path(path).open('rb') as stream:raw=stream.read(limit+1)
        return dict(available=True,truncated=len(raw)>limit,text=raw[:limit].decode(errors='replace'))
    except OSError:
        return dict(available=False,truncated=False,text='')


def report(root=Path('/')):
    root=Path(root)
    result=health(root)
    result['events']=tail(root/'data/guideos/diagnostics/diagnostics.jsonl')
    # Fixed, read-only board inspection; no caller-supplied paths or commands.
    result['pcm']={str(p.relative_to(root)):head(p,2048) for p in
                   sorted((root/'proc/asound').glob('card*/pcm*p/sub*/status'))[:16]}
    if root==Path('/'):
        try:
            # Store bounded output in a temporary file rather than an unbounded PIPE.
            import tempfile
            with tempfile.TemporaryFile() as output:
                run=subprocess.run(['amixer','-c','Codec','contents'],stdout=output,stderr=subprocess.DEVNULL,timeout=2)
                output.seek(0); raw=output.read(32769)
            result['mixer']=dict(available=run.returncode==0,truncated=len(raw)>32768,
                                 text=raw[:32768].decode(errors='replace'))
        except (OSError,subprocess.SubprocessError):
            result['mixer']=dict(available=False,text='')
    return result
