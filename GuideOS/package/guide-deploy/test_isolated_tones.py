import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import audio_probe_sequence as seq
import deploy_board_diagnostics as board
from deploy_server import dispatch
from deploy_core import Rejected

class IsolatedTones(unittest.TestCase):
    def test_each_selection_runs_only_itself_and_resets(self):
        for selected in board.TONES:
            with tempfile.TemporaryDirectory() as folder,patch.object(seq,'run_stage',return_value={'state':'complete'}) as play,patch.object(seq.time,'sleep'):
                command=Mock(return_value={'available':True});announce=Mock()
                result=seq.sequence(folder,command,lambda:{},lambda x:None,selected,announce)
                self.assertEqual(len(result),1)
                self.assertEqual(play.call_args.args[2],selected)
                announce.assert_called_once_with(selected)
                self.assertEqual(command.call_args.args[0][-1],'Normal')
    def test_fixed_protocol_mapping_and_no_extra_arguments(self):
        for op,selected in [('tone-internal','internal-sine'),('tone-s16','file-s16'),('tone-s32','file-s32'),('tone-s16-higher','file-s16-higher')]:
            with patch.object(board,'start_probe') as start:
                dispatch(None,{'op':op});start.assert_called_once_with(selected)
            with self.assertRaises(Rejected):dispatch(None,{'op':op,'command':'anything'})
    def test_queued_request_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(board,'STATE',Path(folder)),patch.object(board,'idle',return_value=True),patch.object(board.subprocess,'run',return_value=Mock(returncode=3)),patch.object(board,'command',return_value={'available':True}):
            board.start_probe('internal-sine')
            with self.assertRaises(Rejected):board.start_probe('file-s16')
            self.assertEqual(json.loads((Path(folder)/'request.json').read_text())['selected'],'internal-sine')
    def test_countdown_is_before_playing_and_public_readable(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(board,'PUBLIC',Path(folder)/'status.json'),patch.object(board.time,'sleep') as sleep:
            board.announce('internal-sine')
            value=json.loads(board.PUBLIC.read_text());self.assertEqual(value['phase'],'playing')
            self.assertEqual(sleep.call_count,5)
            self.assertEqual(board.PUBLIC.stat().st_mode & 0o777,0o644)
    def test_internal_pcm_failure_still_has_bounded_listening_window(self):
        player=Mock();player.poll.return_value=1;player.wait.return_value=1
        with patch.object(seq.subprocess,'Popen',return_value=player),patch.object(seq.time,'monotonic',return_value=10),patch.object(seq.time,'sleep') as sleep:
            result=seq.run_stage('/fixed','S16_LE','internal-sine',lambda:{})
        self.assertEqual(result['state'],'failed')
        self.assertEqual([c.args[0] for c in sleep.call_args_list],[1.5,2.5,4])

    def test_higher_waveform_doubles_amplitude_without_clipping_or_duration_change(self):
        import struct
        with tempfile.TemporaryDirectory() as folder:
            a=Path(folder)/'normal'; b=Path(folder)/'higher'
            normal=seq.make_signal(a,'S16_LE'); higher=seq.make_signal(b,'S16_LE',higher=True)
            self.assertEqual(normal['bytes'],higher['bytes'])
            self.assertEqual(normal['frames'],higher['frames'])
            self.assertAlmostEqual(higher['normalized_peak']/normal['normalized_peak'],2,places=3)
            self.assertLess(higher['normalized_peak'],0.241)
            samples=struct.unpack('<'+'h'*(b.stat().st_size//2),b.read_bytes())
            self.assertEqual(samples[:2],(0,0));self.assertEqual(samples[-2:],(0,0))
