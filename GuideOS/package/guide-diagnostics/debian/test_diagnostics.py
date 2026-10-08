import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from diagnostics_core import Log,Sampler,parse_process,sanitize,journal_event
from guide_telemetry import Timings


def process(pid=42,parent=1,ticks=100,start=900,rss=10):
    fields=['S',str(parent)]+['0']*20
    fields[11],fields[12],fields[19],fields[21]=str(ticks),'0',str(start),str(rss)
    return f'{pid} (worker (audio)) '+' '.join(fields)


class DiagnosticsTests(unittest.TestCase):
    def test_bluetooth_failure_preserves_action_but_not_private_text(self):
        row=sanitize(dict(code='COMMAND_ERROR', action='scan',
                          backend_error='org.bluez.Error.NotReady', message='private device address'))
        self.assertEqual(row,dict(code='COMMAND_ERROR',action='scan',backend_error='org.bluez.Error.NotReady'))
        self.assertNotIn('backend_error',sanitize(dict(code='COMMAND_ERROR',backend_error='private data')))

    def test_process_names_parentheses_and_identity(self):
        row=parse_process(process(),4096)
        self.assertEqual(row['name'],'worker (audio)')
        self.assertEqual(row['id'],'42:900')
        self.assertEqual(row['rss_bytes'],40960)

    def test_cpu_delta_parent_tree_and_pid_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'meminfo').write_text('MemTotal: 1000 kB\nMemFree: 100 kB\nMemAvailable: 400 kB\n')
            (root/'stat').write_text('cpu 100 0 100 800 0 0 0 0\n')
            for pid in (1,42):(root/str(pid)).mkdir()
            (root/'1/stat').write_text(process(1,0))
            (root/'42/stat').write_text(process())
            sampler=Sampler(root)
            first=sampler.sample()
            self.assertEqual(first['memory']['used_bytes'],600*1024)
            self.assertIsNone(first['cpu_percent_total'])
            (root/'42/stat').write_text(process(ticks=200))
            with patch('diagnostics_core.time.monotonic',return_value=sampler.last+5):second=sampler.sample()
            child=next(r for r in second['processes'] if r['pid']==42)
            self.assertEqual(child['parent_id'],'1:900')
            self.assertAlmostEqual(child['cpu_percent_one_core'],100/sampler.hz/5*100)
            (root/'42/stat').write_text(process(ticks=9999,start=901))
            third=sampler.sample()
            self.assertIsNone(next(r for r in third['processes'] if r['pid']==42)['cpu_percent_one_core'])

    def test_event_schema_excludes_text_and_invalid_values(self):
        row=sanitize(dict(code='COMMAND_ERROR',error_number=28,password='secret',path='/private',component=['invalid'],max_ms=float('nan')))
        self.assertEqual(row,dict(code='COMMAND_ERROR',error_number=28,errno_name='ENOSPC'))
        self.assertIsNone(sanitize(dict(code='invented')))

    def test_recovery_failure_keeps_phase_and_errno_without_exception_text(self):
        row=sanitize(dict(code='CONTROL_ERROR',phase='force',backend_error='FileNotFoundError',
                          error_number=2,message='/private/group'))
        self.assertEqual(row,dict(code='CONTROL_ERROR',phase='force',backend_error='FileNotFoundError',
                                  error_number=2,errno_name='ENOENT'))
        self.assertNotIn('phase',sanitize(dict(code='CONTROL_ERROR',phase='/private/group')))

    def test_rotation_is_bounded_and_records_are_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=Log(tmp,limit=160)
            for i in range(50):log.add(dict(index=i))
            log.flush()
            files=list(Path(tmp).glob('*.jsonl'))
            self.assertLessEqual(len(files),4)
            self.assertLessEqual(sum(p.stat().st_size for p in files),640)
            for p in files:
                for line in p.read_text().splitlines():self.assertIn('index',json.loads(line))

    def test_journal_retains_codes_not_raw_messages(self):
        event=journal_event(dict(MESSAGE='private path ENOSPC password secret',PRIORITY='3'))
        self.assertEqual(event['errno_name'],'ENOSPC')
        self.assertNotIn('secret',json.dumps(event))
        event=journal_event(dict(MESSAGE='GUIDE_VIDEO_METRICS {"frames":42,"frame_max_ms":19}'))
        self.assertEqual(event['frames'],42)

    def test_timings_aggregate_without_individual_inputs(self):
        timings=Timings()
        timings.add('navigation_submit',.01)
        timings.add('navigation_submit',.2)
        with patch('guide_telemetry.emit') as emit:
            timings.flush(force=True)
        self.assertEqual(emit.call_args.kwargs['count'],2)
        self.assertEqual(emit.call_args.kwargs['mean_ms'],105)
        self.assertEqual(emit.call_args.kwargs['over_100_ms'],1)
        self.assertFalse(timings.rows)
