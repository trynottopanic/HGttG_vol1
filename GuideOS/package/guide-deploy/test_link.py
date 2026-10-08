import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch,Mock
from deploy_core import Rejected
from deploy_diagnostics import health,report,tail,head
from deploy_server import dispatch
from guide_deploy import Remote
from guide_link import watch


class LinkTests(unittest.TestCase):
    def test_proc_status_read_does_not_require_seek_to_eof(self):
        result=head('/proc/self/status',128)
        self.assertTrue(result['available'])
        self.assertTrue(result['truncated'])
        self.assertIn('Name:',result['text'])

    def test_health_does_not_export_passwords_media_names_or_addresses(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('guideos-audio','guideos-diagnostics'):(root/'run'/name).mkdir(parents=True)
            (root/'run/guideos-audio/status.json').write_text(json.dumps(dict(observed=8,state='playing',
                volume=20,output='bluez_output.private-address',files=['private file'],password='secret',
                devices=[dict(connected=True,title='private alias')],message='private text')))
            (root/'run/guideos-diagnostics/status.json').write_text(json.dumps(dict(observed=1,memory={'MemAvailable':100})))
            value=health(root,now=10)
            self.assertEqual(value['audio']['output_kind'],'bluetooth')
            self.assertEqual(value['audio']['connected_devices'],1)
            self.assertFalse(value['audio']['stale'])
            self.assertNotIn('private',json.dumps(value)); self.assertNotIn('secret',json.dumps(value))
            self.assertTrue(health(root,now=30)['audio']['stale'])

    def test_tail_is_bounded_and_reports_truncation(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'events'; path.write_bytes(b'{"a":1}\n'*10000)
            result=tail(path,64)
            self.assertTrue(result['truncated']); self.assertLessEqual(len(result['text']),64)
            for line in result['text'].splitlines(): self.assertEqual(json.loads(line),{'a':1})

    def test_report_refuses_arbitrary_command_or_path(self):
        for field in ('path','command'):
            with self.assertRaises(Rejected):dispatch(None,dict(op='report',**{field:'/etc/shadow'}))
        with patch('deploy_diagnostics.health',return_value={'test':True}):
            self.assertEqual(dispatch(None,dict(op='health')),{'test':True})

    def test_unresponsive_authenticated_peer_has_request_deadline(self):
        remote=Remote.__new__(Remote)
        remote.process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
        try:
            with self.assertRaisesRegex(Rejected,'connection-timeout'):remote.request('health',_timeout=.05)
        finally:remote.close()

    def test_monitor_marks_stopped_state_not_live(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'live.json'
            remote=Mock(); remote.request.return_value={'protocol':'GUIDE-LINK-1'}
            with patch('guide_link.connect',return_value=(remote,{})):
                watch({'device':'test'},'127.0.0.1',None,output,interval=.01,duration=.025)
            state=json.loads(output.read_text())
            self.assertFalse(state['connected']); self.assertTrue(state['monitor_stopped'])
            remote.close.assert_called_once()

    def test_monitor_reconnects_after_lost_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            failed,healthy=Mock(),Mock()
            failed.request.side_effect=OSError('connection lost')
            healthy.request.return_value={'protocol':'GUIDE-LINK-1'}
            clock={'now':0}
            def sleep(seconds):clock['now']+=seconds
            with patch('guide_link.connect',side_effect=[(failed,{}),(healthy,{})]) as connect, \
                 patch('guide_link.time.monotonic',side_effect=lambda:clock['now']), \
                 patch('guide_link.time.sleep',side_effect=sleep):
                watch({'device':'test'},'127.0.0.1',None,Path(folder)/'live.json',interval=2,duration=12)
            self.assertEqual(connect.call_count,2)
            failed.close.assert_called_once(); healthy.close.assert_called_once()
