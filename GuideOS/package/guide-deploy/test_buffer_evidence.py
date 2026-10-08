import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock,patch
import audio_probe_sequence as seq
import deploy_board_diagnostics as board
import json

class BufferEvidenceTests(TestCase):
    def test_restore_normal_even_when_disarm_fails_and_no_service_restart(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(board,'STATE',Path(folder)):
            (Path(folder)/'restore.json').write_text(json.dumps(dict(active=['guide-audio.service'],diagnostic_source=True,buffer_probe=True)))
            command=Mock(side_effect=lambda argv,**kwargs:dict(available=argv[-2:]!=['name=DAC Buffer Probe','off']))
            with patch.object(board,'command',command):board.restore()
            self.assertEqual(command.call_args_list[0].args[0][-1],'Normal')
            self.assertEqual(command.call_count,2)
            self.assertFalse(board.probe_status()['restored'])
    def test_known_fnv_and_prefix_bound(self):
        self.assertEqual(seq.buffer_summary(b'hello')['fnv1a32'],0x4f9f2cab)
        self.assertEqual(seq.buffer_summary(b'\0'*5000),seq.buffer_summary(b'\0'*4096))
        self.assertEqual(seq.buffer_summary(b'\0\1')['nonzero_bytes'],1)
    def test_readback_match_and_mismatch(self):
        expected=seq.buffer_summary(b'hello');hash=expected['fnv1a32']
        values=f'1,5,5,{hash&65535},{hash>>16},16,2,84500512,48000,96000,2'
        command=Mock(return_value=dict(available=True,text='  : values='+values+'\n'))
        self.assertTrue(seq.buffer_evidence(command,expected)['matches'])
        self.assertFalse(seq.buffer_evidence(command,seq.buffer_summary(b'other'))['matches'])
    def test_missing_capture_not_success(self):
        command=Mock(return_value=dict(available=True,text=': values=0,0,0,0,0,0,0,0,0,0,0'))
        self.assertFalse(seq.buffer_evidence(command,{})['available'])
    def test_failed_disarm_still_restores_normal(self):
        calls=[]
        def command(argv):
            calls.append(argv)
            return dict(available=argv[-2:]!=['name=DAC Buffer Probe','off'],text='')
        with tempfile.TemporaryDirectory() as folder,patch.object(seq,'run_stage',return_value={'state':'complete'}):
            with self.assertRaisesRegex(RuntimeError,'disarm-failed'):
                seq.sequence(folder,command,lambda:{},lambda s:None,'file-s16',probe_buffer=True)
        self.assertEqual(calls[-1][-2:],['name=DAC Diagnostic Source','Normal'])
    def test_capture_arm_failure_prevents_player(self):
        command=Mock(side_effect=lambda argv:dict(available=argv[-2:]!=['name=DAC Buffer Probe','on']))
        with tempfile.TemporaryDirectory() as folder,patch.object(seq,'run_stage') as play:
            with self.assertRaisesRegex(RuntimeError,'arm-failed'):
                seq.sequence(folder,command,lambda:{},lambda s:None,'file-s16',probe_buffer=True)
        play.assert_not_called()
