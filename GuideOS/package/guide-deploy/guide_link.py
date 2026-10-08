#!/usr/bin/python3
"""Paired-PC live diagnostics. Run in WSL; Ctrl+C closes the active connection."""
import argparse
import base64
import hashlib
import os
import platform
import sys
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import zipfile
from deploy_core import Rejected, require
from guide_deploy import Remote


def save(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2),encoding='utf-8')
    temporary.replace(path)


def stamp(): return datetime.now(timezone.utc).isoformat()


def connect(profile, host, port):
    remote=Remote(profile,host,port)
    try:
        status=remote.request('status')
        require(status['device']==profile['device'],'wrong-device')
        return remote,status
    except BaseException:
        remote.close()
        raise


def watch(profile,host,port,output,interval=10,duration=None):
    remote=None; last=None; retry=5; state=None; received=None
    deadline=time.monotonic()+duration if duration is not None else float('inf')
    try:
        while time.monotonic()<deadline:
            try:
                if remote is None:
                    remote,status=connect(profile,host,port)
                last=remote.request('health')
                require(last.get('protocol')=='GUIDE-LINK-1','unsupported-diagnostic-protocol')
                received=stamp()
                save(output,dict(connected=True,received_utc=received,device=profile['device'],
                                 host=host,health=last))
                if state!='connected': print('Deck connected. Live readings are being saved.',flush=True)
                state='connected'; retry=5
                time.sleep(min(interval,max(0,deadline-time.monotonic())))
            except (OSError,ValueError,KeyError,Rejected) as error:
                if remote is not None: remote.close(); remote=None
                reason=str(error) if isinstance(error,Rejected) else 'connection-unavailable'
                save(output,dict(connected=False,observed_utc=stamp(),device=profile['device'],
                                 host=host,reason=reason,last_health=last,last_received_utc=received))
                if reason in ('bad-request','wrong-device','unsupported-diagnostic-protocol'):
                    raise Rejected('Diagnostic bootstrap required or paired device mismatch.') from None
                if state!='disconnected': print('Deck disconnected. Waiting for the connection to return.',flush=True)
                state='disconnected'
                time.sleep(min(retry,max(0,deadline-time.monotonic())))
                retry=min(60,retry*2)
    finally:
        if remote is not None: remote.close()
        save(output,dict(connected=False,monitor_stopped=True,observed_utc=stamp(),
                         device=profile['device'],host=host,last_health=last,last_received_utc=received))


def compatibility_capture(remote, output, device, deployment, reason):
    """Save supported, bounded readings when an older Deck cannot export an archive."""
    reports = {operation: remote.request(operation) for operation in ('health', 'report', 'inspect')}
    metadata = dict(device=device, captured_utc=stamp(), capture_mode='compatibility',
                    full_export_unavailable=reason,
                    included=['live-health', 'diagnostic-event-tail', 'board-report', 'scoped-current-boot-journal',
                              'service-state', 'display', 'network', 'storage', 'audio'],
                    excluded=['complete-retained-log-files', 'raw-current-boot-journal'])
    temporary = output.with_name(output.name + '.compatibility.partial')
    try:
        with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('capture.json', json.dumps(metadata, indent=2))
            for name, report_value in reports.items():
                archive.writestr(name + '.json', json.dumps(report_value, separators=(',', ':')))
            archive.writestr('desktop-capture.json', json.dumps({'device': device, 'deployment': deployment}, indent=2))
        require(temporary.stat().st_size <= 24*1024*1024, 'capture-size-limit')
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    print('Compatibility diagnostic capture: complete retained logs and raw journal are unavailable.')
    print('Diagnostic capture saved: ' + str(output))


def capture(remote,output,device,deployment):
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    require(not output.exists(),'capture-output-exists')
    try:
        info=remote.request('capture-begin',_timeout=180)
    except Rejected as error:
        if str(error) not in ('invalid-request-or-local-failure', 'bad-request'):
            raise
        compatibility_capture(remote, output, device, deployment, str(error))
        return
    capture_id=info.get('id');expected=info.get('bytes');expected_hash=info.get('sha256')
    require(isinstance(capture_id,str) and len(capture_id)==32,'bad-capture-id')
    require(type(expected) is int and 0<expected<=24*1024*1024,'bad-capture-size')
    require(isinstance(expected_hash,str) and len(expected_hash)==64,'bad-capture-hash')
    chunk_size=info.get('chunk_bytes')
    require(type(chunk_size) is int and 0<chunk_size<=240000,'bad-capture-chunk-size')
    partial=output.with_name(output.name+'.'+capture_id+'.partial')
    try:
        with partial.open('xb') as stream:
            offset=0
            while offset<expected:
                result=remote.request('capture-chunk',_timeout=30,id=capture_id,offset=offset,
                                      length=min(chunk_size,expected-offset))
                require(result.get('offset')==offset,'capture-offset-mismatch')
                try:data=base64.b64decode(result.get('data',''),validate=True)
                except (ValueError,TypeError):raise Rejected('bad-capture-chunk') from None
                require(len(data)==result.get('bytes') and data,'bad-capture-chunk')
                stream.write(data);offset+=len(data)
            stream.flush();os.fsync(stream.fileno())
        digest=hashlib.sha256(partial.read_bytes()).hexdigest()
        require(partial.stat().st_size==expected and digest==expected_hash,'capture-integrity-failed')
        os.replace(partial,output)
        summary={key:deployment.get(key) for key in ('device','active','previous','enabled','highest_sequence','sequence','protocol','scope')}
        summary.update(captured_utc=stamp(),deck_archive_sha256=digest,desktop_host=platform.node(),
                       desktop_platform=platform.platform(),python_version=sys.version.split()[0])
        with zipfile.ZipFile(output,'a',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('desktop-capture.json',json.dumps({'device':device,'deployment':summary},indent=2))
        print('Full diagnostic capture saved: '+str(output))
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    finally:
        try:remote.request('capture-finish',_timeout=8,id=capture_id)
        except (Rejected,OSError,ValueError):pass


def main():
    parser=argparse.ArgumentParser(description='Guide live diagnostic connection to this PC')
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--host',required=True)
    parser.add_argument('--port',type=int)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--duration',type=float)
    parser.add_argument('action',choices=('watch','capture','health','report','inspect','speaker-probe','audio-path','probe-result','tone-internal','tone-s16','tone-s32','tone-s16-higher','tf2-observe','tf2-hold-awake','tf2-result'))
    args=parser.parse_args()
    profile=json.loads(args.profile.read_text())
    if args.action=='watch':
        watch(profile,args.host,args.port,args.output,duration=args.duration)
    else:
        remote,status=connect(profile,args.host,args.port)
        try:
            if args.action=='capture':
                capture(remote,args.output,profile['device'],status)
            else:
                result=remote.request(args.action)
                save(args.output,dict(received_utc=stamp(),device=profile['device'],deployment=status,report=result))
                print('Diagnostic report saved: '+str(args.output))
        finally: remote.close()


if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: print('Diagnostic connection closed.')
    except (Rejected,OSError,ValueError) as error:
        print(str(error) if isinstance(error,Rejected) else 'Connection or local file failure.')
        raise SystemExit(1)
