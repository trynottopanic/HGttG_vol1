"""Bounded /proc sampling, rotating JSONL, and a fixed diagnostic vocabulary."""
import errno
import json
import math
import os
from pathlib import Path
import re
import time

CODES = {'BLUETOOTH_HARDWARE','BLUETOOTH_INVENTORY','AUDIO_ROUTE','AUDIO_MIXER','AUDIO_MIXER_ERROR','CONTROL_OPEN','CONTROL_CLOSE','CONTROL_ERROR','CONTROL_DEFERRED','TIMING', 'AUDIO_STATE', 'AUDIO_DECODE_ERROR', 'AUDIO_WORKER_TIMEOUT',
         'AUDIO_QUEUE', 'AUDIO_OUTPUT_LOST', 'VIDEO_START', 'VIDEO_READY',
         'VIDEO_EXIT', 'VIDEO_TIMEOUT', 'VIDEO_METRICS', 'VIDEO_ERROR', 'SHELL_ERROR',
         'COMMAND_ERROR', 'SYSTEM_ERROR', 'DIAGNOSTICS_STARTED', 'DIAGNOSTICS_STOPPED',
         'UI_NAVIGATION', 'BROWSER_ATTEMPT'}
METRICS = {'shell_draw','navigation_submit','input_handler','input_queue','audio_ack','wifi_ack','audio_command',
           'frame_interval','frame_layout','frame_compose','framebuffer_diff','framebuffer_convert','framebuffer_write',
           'poll_browser','poll_installer','poll_application','poll_statusbar','poll_storage','poll_operations',
           'poll_audio','poll_wifi','poll_bridge','poll_wifi_scan','file_request'}
NUMBERS = {'hci_count','radio_count','soft_blocked','hard_blocked','adapters','powered','discovering','devices','connected','muted','route_volume','output_present',
           'dac_gain','line_gain','speaker_on','headphone','dac_on','line_on','observed','count','mean_ms','max_ms','over_100_ms','error_number',
           'returncode','elapsed_ms','position','volume','buffer_ms','buffer_bytes','p50_ms','p95_ms',
           'queue_empty_events','underruns','frames','late_frames','frame_max_ms','frame_mean_ms','priority','pid','backend_code'}
TOKENS = {'state': {'stopped','starting','playing','paused','failed'},
          'backend_domain': {'gst-core-error-quark','gst-library-error-quark','gst-resource-error-quark','gst-stream-error-quark'},
          'metric': METRICS, 'phase': {'initialization','playback','prepare','workloads','force','release'},
          'component': {'audio','shell','wifi','video','kernel','systemd','browser','storage','media','other'},
          'page': {'home','settings','media','files','applications','installer','application','browser',
                   'storage','wifi','nodes','diagnostics','about','power','transfers','updates','unavailable'},
          'transition': {'open','back','home','attempt','ready','failed','exit'}}
TOKENS['action'] = {'refresh','output','play','resume','pause','stop','volume','scan','connect',
                    'disconnect','cancel','inventory','scan_stop','pair','unknown','navigate','launch'}
TOKENS['backend_error'] = {'ValueError','TimeoutError','FileNotFoundError','RuntimeError','OSError','other'} | {
    'org.bluez.Error.' + name for name in ('NotReady','Failed','InProgress','NotSupported',
        'AuthenticationFailed','AuthenticationCanceled','AuthenticationRejected','AuthenticationTimeout',
        'ConnectionAttemptFailed','NotConnected','AlreadyConnected','AlreadyExists')
} | {'org.freedesktop.DBus.Error.' + name for name in ('AccessDenied','NoReply','ServiceUnknown','UnknownObject')}


def sanitize(event):
    if not isinstance(event, dict) or event.get('code') not in CODES:
        return None
    clean = {'code': event['code']}
    for key, value in event.items():
        if key in NUMBERS and isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(value):
            clean[key] = value
        elif key in TOKENS and isinstance(value,str) and value in TOKENS[key]:
            clean[key] = value
    if 'error_number' in clean:
        clean['errno_name'] = errno.errorcode.get(abs(int(clean['error_number'])), 'UNKNOWN')
    return clean


def parse_process(text, page_size):
    left, right = text.index('('), text.rindex(')')
    fields = text[right+2:].split()
    pid, started = int(text[:left]), int(fields[19])
    return dict(id=f'{pid}:{started}', pid=pid, ppid=int(fields[1]),
                name=text[left+1:right][:32], ticks=int(fields[11])+int(fields[12]),
                rss_bytes=max(0,int(fields[21]))*page_size, state=fields[0])


class Sampler:
    def __init__(self, proc='/proc'):
        self.proc = Path(proc)
        self.hz, self.page = os.sysconf('SC_CLK_TCK'), os.sysconf('SC_PAGE_SIZE')
        self.previous, self.last, self.cpu = {}, None, None

    def sample(self):
        started = time.monotonic()
        elapsed = started - self.last if self.last is not None else None
        memory = {}
        for line in (self.proc/'meminfo').read_text().splitlines():
            key, value = line.split(':',1)
            if key in ('MemTotal','MemFree','MemAvailable','SwapTotal','SwapFree'):
                memory[key] = int(value.split()[0])*1024
        memory['used_bytes'] = max(0,memory['MemTotal']-memory.get('MemAvailable',memory['MemFree']))
        values = list(map(int,(self.proc/'stat').read_text().splitlines()[0].split()[1:9]))
        total, idle = sum(values), values[3]+values[4]
        cpu = None if self.cpu is None or total==self.cpu[0] else round(100*(1-(idle-self.cpu[1])/(total-self.cpu[0])),2)
        self.cpu = total,idle
        rows, skipped, truncated = [], 0, False
        for entry in self.proc.iterdir():
            if not entry.name.isdigit():continue
            if len(rows)>=512:
                truncated=True
                break
            try:
                row = parse_process((entry/'stat').read_text(),self.page)
                old = self.previous.get(row['id'])
                row['cpu_percent_one_core'] = (round(max(0,row['ticks']-old)/self.hz/elapsed*100,2)
                    if old is not None and elapsed and elapsed>0 else None)
                row['cpu_time_seconds'] = round(row['ticks']/self.hz, 3)
                rows.append(row)
            except (OSError,ValueError,IndexError):
                skipped+=1
        identities = {row['pid']:row['id'] for row in rows}
        self.previous = {row['id']:row.pop('ticks') for row in rows}
        for row in rows:row['parent_id']=identities.get(row['ppid'])
        self.last = started
        return dict(kind='resources', observed=started, interval_seconds=elapsed,
                    cpu_percent_total=cpu, logical_cpus=os.cpu_count(), memory=memory,
                    processes=rows, skipped_processes=skipped, truncated=truncated,
                    sample_cost_ms=round((time.monotonic()-started)*1000,3))


class Log:
    def __init__(self, folder, limit=2*1024*1024, prefix='diagnostics'):
        self.folder=Path(folder)
        self.folder.mkdir(parents=True,exist_ok=True)
        self.limit=limit
        if prefix not in ('diagnostics','journal'):
            raise ValueError('unsupported diagnostic log')
        self.prefix=prefix
        self.path=self.folder/f'{prefix}.jsonl'
        self.pending=[]
        self.pending_bytes=0
        self.write_errors=0

    def add(self,row):
        encoded=json.dumps(row,separators=(',',':'),ensure_ascii=True)+'\n'
        if len(encoded)>self.limit:return
        self.pending.append(encoded)
        self.pending_bytes+=len(encoded)
        if self.pending_bytes>=64*1024:self.flush()

    def flush(self):
        try:
            for line in self.pending:
                if self.path.exists() and self.path.stat().st_size+len(line)>self.limit:
                    (self.folder/f'{self.prefix}.3.jsonl').unlink(missing_ok=True)
                    for i in (2,1):
                        old=self.folder/f'{self.prefix}.{i}.jsonl'
                        if old.exists():old.replace(self.folder/f'{self.prefix}.{i+1}.jsonl')
                    self.path.replace(self.folder/f'{self.prefix}.1.jsonl')
                with self.path.open('a',encoding='ascii') as f:f.write(line)
        except OSError:
            self.write_errors+=1
        finally:
            self.pending.clear()
            self.pending_bytes=0


def journal_event(row):
    # Raw messages, paths, SSIDs and arguments never enter the diagnostic log.
    message=row.get('MESSAGE','')
    if not isinstance(message,str):return None
    if message.startswith('GUIDE_DIAGNOSTIC '):
        try:return sanitize(json.loads(message.partition(' ')[2]))
        except (ValueError,TypeError):return None
    if message.startswith('guide-boot-animation error='):
        return dict(code='VIDEO_ERROR', component='video')
    if message.startswith('GUIDE_VIDEO_METRICS '):
        try:return sanitize(dict(code='VIDEO_METRICS',**json.loads(message.partition(' ')[2])))
        except (ValueError,TypeError):return None
    priority=int(row.get('PRIORITY',6))
    if priority>4:return None
    component='kernel' if row.get('_TRANSPORT')=='kernel' else 'systemd' if row.get('SYSLOG_IDENTIFIER')=='systemd' else 'other'
    number=row.get('ERRNO')
    if number is None:
        match=re.search(r'\b(EIO|ENOMEM|ENOSPC|EACCES|ENODEV|ETIMEDOUT|EPIPE|ECONNRESET)\b',message)
        number=getattr(errno,match[1]) if match else 0
    try:
        event=sanitize(dict(code='SYSTEM_ERROR',component=component,priority=priority,error_number=int(number)))
        unit=row.get('_SYSTEMD_UNIT','')
        if isinstance(unit,str) and re.fullmatch(r'[A-Za-z0-9_.@-]{1,80}',unit):event['unit']=unit
        if str(row.get('_PID','')).isdigit():event['pid']=int(row['_PID'])
        return event
    except (ValueError,TypeError):return None
