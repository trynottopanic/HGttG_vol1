import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave
from audio_test import AudioTest, write_tone, RATE, SECONDS

LOCAL = 'alsa_output.platform-5096000.codec.stereo-fallback'


class AudioTestTests(unittest.TestCase):
    def test_five_second_stereo_wave_with_fades(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'tone.wav';write_tone(path)
            with wave.open(str(path)) as f:
                self.assertEqual((f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()), (2,2,RATE,RATE*5))
                samples=struct.unpack('<'+'h'*(RATE*5*2),f.readframes(f.getnframes()))
            self.assertEqual(samples[::2],samples[1::2])
            self.assertEqual((samples[0],samples[-1]),(0,0))
            self.assertLessEqual(max(samples),16384)
            self.assertGreater(max(samples),16000)
            # Confirm tone frequency over a steady one-second interval.
            channel=samples[2*RATE:4*RATE:2]
            crossings=sum(a<=0<b for a,b in zip(channel,channel[1:]))
            self.assertIn(crossings,(439,440,441))

    def test_current_volume_selected_output_and_stop(self):
        with tempfile.TemporaryDirectory() as d:
            player=Mock();player.state='starting';tone=AudioTest(player,d)
            prepare=Mock();tone.start([{'id':'bluez_output.test'}],'bluez_output.test',37,'paused',prepare)
            player.set_volume.assert_called_once_with(37)
            self.assertEqual(player.play.call_args.args[1],'bluez_output.test')
            prepare.assert_called_once_with('bluez_output.test')
            self.assertTrue(tone.active)
            tone.start([],None,100,'paused')
            self.assertFalse(tone.active);self.assertFalse(tone.path.exists())
            player.close.assert_called_once()

    def test_no_interruption_or_silent_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            tone=AudioTest(Mock(),d)
            for state in ('playing','starting'):
                with self.assertRaisesRegex(ValueError,'Pause music'):
                    tone.start([{'id':LOCAL}],None,20,state)
            with self.assertRaisesRegex(ValueError,'Selected output unavailable'):
                tone.start([{'id':LOCAL}],'bluez_output.gone',20,'paused')
            with self.assertRaisesRegex(ValueError,'No audio output'):
                tone.start([],None,20,'stopped')
            tone.player.play.assert_not_called()

    def test_completion_failure_and_deadline_release_worker(self):
        with tempfile.TemporaryDirectory() as d:
            for state,expected in [('stopped','complete'),('failed','failed'),('starting','timed out')]:
                player=Mock();tone=AudioTest(player,d)
                tone.start([{'id':LOCAL}],None,0,'stopped')
                player.set_volume.assert_called_once_with(0)
                player.state=state
                if state=='starting':tone.deadline=0
                tone.tick();self.assertFalse(tone.active)
                self.assertIn(expected,tone.message);self.assertFalse(tone.path.exists())
                player.close.assert_called_once()

    def test_prepare_failure_cleans_up(self):
        with tempfile.TemporaryDirectory() as d:
            tone=AudioTest(Mock(),d)
            with self.assertRaises(ValueError):
                tone.start([{'id':LOCAL}],None,20,'stopped',Mock(side_effect=ValueError('failed')))
            self.assertFalse(tone.active);self.assertFalse(tone.path.exists())

    def test_service_preserves_paused_media_and_controls_test_volume(self):
        from audio_service import Service
        with tempfile.TemporaryDirectory() as d:
            service=Service.__new__(Service);service.player=Mock();service.playback_lease=Mock()
            service.player.state='paused';service.player.volume=37;service.player.position=83
            service.outputs=[{'id':LOCAL,'node_id':1}];service.selected=LOCAL;service.track='original-track'
            import time
            service.inventory_state='ready';service.inventory_observed=time.monotonic()
            service.audio_test=AudioTest(Mock(),d);service.save=Mock();service.prepare_output=Mock()
            service.command({'action':'test'})
            self.assertEqual((service.track,service.player.position,service.selected),('original-track',83,LOCAL))
            service.player.play.assert_not_called();service.save.assert_not_called()
            with self.assertRaisesRegex(ValueError,'Stop the audio test'):
                service.command({'action':'resume'})
            service.command({'action':'volume','value':37})
            service.audio_test.player.set_volume.assert_called_with(37)
            service.command({'action':'test'})
            self.assertFalse(service.audio_test.active)


if __name__=='__main__':unittest.main()
