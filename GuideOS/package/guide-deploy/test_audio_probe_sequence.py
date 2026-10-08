import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import subprocess
import audio_probe_sequence as seq


class FormatTests(unittest.TestCase):
    def test_sample_values_match_between_formats(self):
        with tempfile.TemporaryDirectory() as folder:
            a,b=Path(folder)/'a',Path(folder)/'b'
            x=seq.make_signal(a,'S16_LE');y=seq.make_signal(b,'S32_LE')
            s16=struct.unpack('<'+'h'*(x['frames']*2),a.read_bytes())
            s32=struct.unpack('<'+'i'*(y['frames']*2),b.read_bytes())
            self.assertTrue(all(wide==narrow<<16 for narrow,wide in zip(s16,s32)))
            self.assertGreater(x['normalized_peak'],0.11)
            self.assertEqual(x['normalized_peak'],y['normalized_peak'])
            self.assertEqual(s16[0],0);self.assertEqual(s16[-1],0)
            self.assertEqual(s16[::2],s16[1::2])
            seq.make_signal(a,'S16_LE',silent=True)
            self.assertEqual(set(a.read_bytes()),{0})

    def test_file_error_does_not_skip_other_format(self):
        calls=[]
        def command(argv):calls.append(('mixer',argv[-1]));return {'available':True}
        def play(path,fmt,label,snapshot):
            calls.append(('play',label));return {'label':label,'state':'failed' if label=='file-s16' else 'complete'}
        with tempfile.TemporaryDirectory() as folder,patch.object(seq,'run_stage',side_effect=play),patch.object(seq.time,'sleep'):
            stages=seq.sequence(Path(folder),command,lambda:{},lambda s:None)
        self.assertEqual([s['label'] for s in stages],['file-s16','file-s32','internal-sine'])
        self.assertEqual(calls[-1],('mixer','Normal'))
        self.assertLess(calls.index(('mixer','Sine')),calls.index(('play','internal-sine')))

    def test_source_reset_failure_stops_sequence(self):
        calls=[]
        def command(argv):
            calls.append(argv[-1]);return {'available':len(calls)!=3}
        with tempfile.TemporaryDirectory() as folder,patch.object(seq,'run_stage',return_value={'state':'complete'}) as play:
            with self.assertRaisesRegex(RuntimeError,'reset-failed'):
                seq.sequence(Path(folder),command,lambda:{},lambda s:None)
            self.assertEqual(play.call_count,1)

    def test_run_stage_records_io_failure_without_format_conversion(self):
        player=Mock();player.poll.return_value=1;player.wait.return_value=1
        with patch.object(seq.subprocess,'Popen',return_value=player) as popen,patch.object(seq.time,'sleep'):
            result=seq.run_stage('/fixed','S32_LE','file-s32',lambda:{'pcm':'closed'})
        argv=popen.call_args.args[0]
        self.assertIn('hw:CARD=Codec,DEV=0',argv);self.assertIn('S32_LE',argv)
        self.assertEqual(result['state'],'failed')
        self.assertEqual(result['snapshots'][0]['player_returncode'],1)
        self.assertIn('exit_observed_elapsed',result)

    def test_timeout_kills_and_reaps_player(self):
        player=Mock();player.poll.side_effect=[None,None,-9]
        player.wait.side_effect=[subprocess.TimeoutExpired('aplay',7),-9]
        with patch.object(seq.subprocess,'Popen',return_value=player),patch.object(seq.time,'sleep'):
            result=seq.run_stage('/fixed','S16_LE','file-s16',lambda:{})
        self.assertTrue(result['timed_out']);self.assertEqual(result['state'],'failed')
        player.kill.assert_called_once();self.assertEqual(player.wait.call_count,2)

    def test_snapshot_failure_still_reaps_player(self):
        player=Mock();player.poll.return_value=None
        with patch.object(seq.subprocess,'Popen',return_value=player),patch.object(seq.time,'sleep'):
            with self.assertRaises(RuntimeError):
                seq.run_stage('/fixed','S16_LE','file-s16',Mock(side_effect=RuntimeError('capture failed')))
        player.kill.assert_called_once();player.wait.assert_called_once()
