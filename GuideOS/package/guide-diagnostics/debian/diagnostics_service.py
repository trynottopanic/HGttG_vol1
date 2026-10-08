import argparse
from collections import Counter,deque
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import struct
import subprocess
import time
from diagnostics_core import Log,Sampler,sanitize,journal_event,parse_process

RUNTIME=Path('/run/guideos-diagnostics')

RAW_UNITS={'guide-browser.service','weston.service','guide-shell.service','guide-control.service',
           'guide-diagnostics.service','guide-deploy.service','guide-deploy-ssh.service',
           'guide-storage.service','guide-media-player.service','guide-media-player.socket',
           'guide-pipewire.service','guide-wireplumber.service','guide-audio.service',
           'NetworkManager.service','wpa_supplicant.service','bluetooth.service','systemd-logind.service'}

def journal_record(row):
    unit=row.get('_SYSTEMD_UNIT','')
    transport=row.get('_TRANSPORT','')
    if unit not in RAW_UNITS and transport!='kernel':return None
    message=row.get('MESSAGE','')
    if not isinstance(message,str):return None
    try:priority=int(row.get('PRIORITY',6))
    except (TypeError,ValueError):priority=6
    if not 0<=priority<=7:return None
    result={'kind':'journal','priority':priority,'message':message[:4096]}
    for key,target in (('_SYSTEMD_UNIT','unit'),('SYSLOG_IDENTIFIER','identifier'),('_TRANSPORT','transport')):
        value=row.get(key)
        if isinstance(value,str) and len(value)<=100 and all(ch.isalnum() or ch in '._@- ' for ch in value):result[target]=value
    for key,target in (('_PID','pid'),('__REALTIME_TIMESTAMP','realtime_us'),('__MONOTONIC_TIMESTAMP','monotonic_us')):
        value=row.get(key)
        if str(value).isdigit():result[target]=int(value)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',action='store_true')
    args=parser.parse_args()
    if args.report:
        print((RUNTIME/'status.json').read_text())
        return
    stopping=[]
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stopping.append(True))
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    log=Log('/data/guideos/diagnostics')
    journal_log=Log('/data/guideos/diagnostics',prefix='journal')
    sampler=Sampler()
    counts=Counter()
    recent=deque(maxlen=20)
    latest_events={}
    socket_path=RUNTIME/'events.sock'
    socket_path.unlink(missing_ok=True)
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,1)
    sock.bind(str(socket_path))
    os.chmod(socket_path,0o666)
    sock.setblocking(False)
    selector=selectors.DefaultSelector()
    selector.register(sock,selectors.EVENT_READ,'events')
    journal=subprocess.Popen(['journalctl','-b','-f','--no-pager','-o','json','-n','all',
        '--output-fields=MESSAGE,PRIORITY,ERRNO,_TRANSPORT,SYSLOG_IDENTIFIER,_SYSTEMD_UNIT,_PID'],
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    os.set_blocking(journal.stdout.fileno(),False)
    selector.register(journal.stdout,selectors.EVENT_READ,'journal')
    journal_buffer=b''
    next_sample=next_flush=0
    rate_start=time.monotonic()
    rate_count=dropped=0
    latest={}
    def record(event):
        event=dict(event,boot_id=boot,recorded=time.monotonic(),wall_time=time.time())
        counts[event['code']]+=1
        recent.append(event)
        identity=event['code']+(':'+event['metric'] if event['code']=='TIMING' and 'metric' in event else '')
        latest_events[identity]=event
        log.add(event)
    record(dict(code='DIAGNOSTICS_STARTED'))
    try:
        while not stopping:
            now=time.monotonic()
            if now>=next_sample:
                latest=sampler.sample()
                log.add(dict(latest,boot_id=boot,wall_time=time.time()))
                status=dict(latest,boot_id=boot,counters=dict(counts),recent=list(recent),latest_events=latest_events.copy(),
                            dropped_events=dropped,log_write_errors=log.write_errors,
                            journal_log_write_errors=journal_log.write_errors,
                            journal_log_pending_bytes=journal_log.pending_bytes,
                            journal_running=journal.poll() is None)
                temporary=RUNTIME/'status.tmp'
                temporary.write_text(json.dumps(status,separators=(',',':')))
                temporary.replace(RUNTIME/'status.json')
                next_sample=time.monotonic()+5
            if now>=next_flush:
                log.flush()
                journal_log.flush()
                next_flush=now+2
            for key,_mask in selector.select(max(0,min(next_sample,next_flush)-time.monotonic())):
                if time.monotonic()-rate_start>=1:
                    rate_start=time.monotonic()
                    rate_count=0
                if key.data=='events':
                    for _ in range(32):
                        try:raw,credentials,_flags,_address=sock.recvmsg(2049,socket.CMSG_SPACE(12))
                        except BlockingIOError:break
                        if len(raw)>2048 or rate_count>=64:
                            dropped+=1
                            continue
                        try:event=sanitize(json.loads(raw))
                        except (ValueError,TypeError):event=None
                        if event:
                            for level,kind,value in credentials:
                                if level==socket.SOL_SOCKET and kind==socket.SCM_CREDENTIALS:
                                    pid,_uid,_gid=struct.unpack('3i',value[:12])
                                    event['pid']=pid
                                    try:event['process_id']=parse_process(Path(f'/proc/{pid}/stat').read_text(),sampler.page)['id']
                                    except (OSError,ValueError,IndexError):pass
                            record(event)
                            rate_count+=1
                else:
                    data=os.read(journal.stdout.fileno(),65536)
                    if not data:
                        selector.unregister(journal.stdout)
                        continue
                    journal_buffer+=data
                    lines=journal_buffer.split(b'\n')
                    journal_buffer=lines.pop()
                    if len(journal_buffer)>131072:
                        journal_buffer=b''
                        dropped+=1
                    for line in lines:
                        try:
                            journal_row=json.loads(line)
                            event=journal_event(journal_row)
                        except (ValueError,TypeError,AttributeError):event=None
                        if event:
                            try:
                                source_time=journal_row.get('__MONOTONIC_TIMESTAMP')
                                if str(source_time).isdigit():event.setdefault('observed',int(source_time)/1000000)
                                cursor=journal_row.get('__CURSOR')
                                if isinstance(cursor,str) and len(cursor)<=512:event['journal_cursor']=cursor
                            except (ValueError,TypeError):pass
                            if rate_count>=64:dropped+=1
                            else:
                                record(event)
                                rate_count+=1
                        raw_entry=journal_record(journal_row)
                        if raw_entry is not None:
                            raw_entry.update(boot_id=boot,recorded=time.monotonic(),wall_time=time.time())
                            journal_log.add(raw_entry)
                if rate_count>=64:time.sleep(.05)
    finally:
        record(dict(code='DIAGNOSTICS_STOPPED'))
        log.flush()
        journal_log.flush()
        journal.terminate()
        try:journal.wait(timeout=1)
        except subprocess.TimeoutExpired:
            journal.kill()
            journal.wait(timeout=1)
        selector.close()
        sock.close()
        socket_path.unlink(missing_ok=True)


if __name__=='__main__':main()
