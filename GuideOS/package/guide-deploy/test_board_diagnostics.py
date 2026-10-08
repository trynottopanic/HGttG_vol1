import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import deploy_board_diagnostics as board
from deploy_core import Rejected
from deploy_server import dispatch

class BoardTests(unittest.TestCase):
    def test_internal_source_reset_precedes_service_restart(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(board,'STATE',Path(folder)),patch.object(board,'command',return_value={'available':True}) as command:
            (Path(folder)/'restore.json').write_text(json.dumps({'active':['guide-audio.service'],'diagnostic_source':True}))
            board.save({'state':'running'});board.restore()
            self.assertEqual(command.call_args_list[0].args[0][-1],'Normal')
            self.assertEqual(command.call_args_list[1].args[0],['systemctl','start','guide-audio.service'])
    def test_failed_source_reset_prevents_service_restart(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(board,'STATE',Path(folder)),patch.object(board,'command',return_value={'available':False}) as command:
            (Path(folder)/'restore.json').write_text(json.dumps({'active':['guide-audio.service'],'diagnostic_source':True}))
            board.save({'state':'running'});board.restore()
            self.assertEqual(command.call_count,1)
            self.assertFalse(board.probe_status()['restored'])
            self.assertTrue((Path(folder)/'restore.json').exists())
    def test_only_fixed_operations(self):
        for op in ('inspect','speaker-probe'):
            with self.assertRaises(Rejected): dispatch(None,dict(op=op,command='anything'))
    def test_playing_and_stale_refused(self):
        for status in ({'state':'playing','stale':False},{'state':'stopped','stale':True}):
            with patch.object(board,'health',return_value={'audio':status}),self.assertRaises(Rejected):board.start_probe()
    def test_probe_start_is_asynchronous(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(board,'STATE',Path(folder)),patch.object(board,'idle',return_value=True),patch.object(board.subprocess,'run',return_value=Mock(returncode=3)),patch.object(board,'command',return_value={'available':True}) as command:
            self.assertEqual(board.start_probe()['state'],'queued')
            command.assert_called_once_with(['systemctl','start','--no-block','guide-speaker-probe.service'])
    def test_restore_after_interruption_and_idempotent(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(board,'STATE',Path(folder)),patch.object(board,'command',return_value={'available':True}) as command:
            (Path(folder)/'restore.json').write_text(json.dumps({'active':['guide-pipewire.service','guide-audio.service']}))
            (Path(folder)/'mixer.state').touch();board.save({'state':'running'})
            board.restore();result=board.probe_status()
            self.assertTrue(result['restored']);self.assertEqual(result['state'],'interrupted')
            self.assertEqual(command.call_count,3)
            board.restore();self.assertEqual(command.call_count,3)
    def test_failed_restoration_retains_plan(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(board,'STATE',Path(folder)),patch.object(board,'command',return_value={'available':False}):
            (Path(folder)/'restore.json').write_text(json.dumps({'active':['guide-audio.service']}))
            board.restore();self.assertFalse(board.probe_status()['restored']);self.assertTrue((Path(folder)/'restore.json').exists())
    def test_command_timeout_reported(self):
        with patch.object(board.subprocess,'run',side_effect=board.subprocess.TimeoutExpired('test',1)):
            self.assertFalse(board.command(['test'])['available'])
    def test_command_output_capped(self):
        result=board.command(['python3','-c','print("x"*2000)'],limit=100)
        self.assertTrue(result['truncated']);self.assertEqual(len(result['text']),100)
    def test_probe_restores_after_stop_failure(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(board,'STATE',Path(folder)),patch.object(board,'idle',return_value=True),patch.object(board.subprocess,'run',return_value=Mock(returncode=0)):
            lock=open(Path(folder)/'lock','a')
            calls=[]
            def command(argv,**kwargs):
                calls.append(argv)
                if argv[0]=='alsactl' and 'store' in argv:(Path(folder)/'mixer.state').touch()
                return {'available':not (argv[:2]==['systemctl','stop'])}
            with patch('builtins.open',return_value=lock),patch.object(board,'publish'),patch.object(board,'command',side_effect=command):board.probe()
            result=board.probe_status()
            self.assertEqual(result['state'],'failed');self.assertTrue(result['restored'])
            self.assertEqual([c[2] for c in calls if c[:2]==['systemctl','start']],list(board.SERVICES))

class PathEvidenceTests(unittest.TestCase):
    def test_late_speaker_gpio_is_not_lost(self):
        from audio_path_diagnostics import board_snapshot
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            p=root/'sys/kernel/debug/gpio';p.parent.mkdir(parents=True)
            p.write_text('unrelated input pin\n'*140+' gpio-261 ( |pa ) out hi\n')
            result=board_snapshot(root)
            self.assertIn('gpio-261',result['files']['sys/kernel/debug/gpio']['text'])
            self.assertFalse(result['files']['sys/kernel/debug/gpio']['truncated'])

    def test_component_dapm_and_pcm_are_collected(self):
        from audio_path_diagnostics import board_snapshot
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('sys/kernel/debug/asoc/Card/Codec/dapm/Left DAC','sys/kernel/debug/asoc/Card/dapm/Speaker','proc/asound/card0/pcm0p/sub0/hw_params'):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('On\n')
            result=board_snapshot(root)
            self.assertIn('sys/kernel/debug/asoc/Card/Codec/dapm/Left DAC',result['files'])
            self.assertIn('proc/asound/card0/pcm0p/sub0/hw_params',result['files'])
    def test_global_read_budget(self):
        from audio_path_diagnostics import board_snapshot
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            p=root/'sys/kernel/debug/gpio';p.parent.mkdir(parents=True);p.write_text('x'*10000)
            result=board_snapshot(root,budget=100)
            self.assertLessEqual(sum(len(v.get('text','').encode()) for v in result['files'].values()),100)
            self.assertTrue(result['budget_exhausted'])
    def test_test_signal_detects_silence_and_channel_content(self):
        from audio_path_diagnostics import test_signal
        import wave,struct
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'tone.wav'
            with wave.open(str(p),'wb') as w:
                w.setparams((2,2,48000,0,'NONE','not compressed'));w.writeframes(struct.pack('<hh',1000,0)*100)
            result=test_signal(p)
            self.assertEqual(result['levels'][0]['peak'],1000);self.assertEqual(result['levels'][1]['peak'],0)
    def test_compact_graph_preserves_links_and_enforces_budget(self):
        from audio_path_diagnostics import compact_graph
        rows=[{'id':1,'type':'PipeWire:Interface:Node','info':{'state':'running','props':{'node.name':'sink','unrelated':'omit'},'params':{'Props':[{'mute':False}]}}},
              {'id':2,'type':'PipeWire:Interface:Link','info':{'output-node-id':1,'input-node-id':3,'state':'active'}}]
        value=compact_graph(rows)
        self.assertEqual(value['objects'][1]['input-node-id'],3)
        self.assertNotIn('unrelated',value['objects'][0]['props'])
        self.assertTrue(compact_graph(rows,budget=1)['truncated'])
