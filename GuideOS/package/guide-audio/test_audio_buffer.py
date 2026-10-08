import time
import unittest
from unittest.mock import Mock
from audio_player import Gst, GstPlayer, buffered_sink, BUFFER_TIME_NS, BUFFER_BYTES


class BufferTests(unittest.TestCase):
    def test_volume_change_keeps_position_restore_muted(self):
        player = GstPlayer()
        player.pipeline = Mock()
        player.seek_pending = 12
        player.set_volume(45)
        player.pipeline.set_property.assert_called_with('volume', 0)
        self.assertEqual(player.volume,45)

    def test_decode_ahead_is_bounded_when_output_is_paused(self):
        source = Gst.ElementFactory.make('audiotestsrc')
        source.set_property('samplesperbuffer', 441)  # 10 ms at default 44.1 kHz
        output = buffered_sink(Gst.ElementFactory.make('fakesink'))
        pipeline = Gst.Pipeline.new(None)
        pipeline.add(source)
        pipeline.add(output)
        self.assertTrue(source.link(output))
        try:
            pipeline.set_state(Gst.State.PAUSED)
            queue = output.get_by_name('guide-audio-buffer')
            deadline = time.monotonic() + 5
            while queue.get_property('current-level-time') < BUFFER_TIME_NS and time.monotonic() < deadline:
                time.sleep(.01)
            level = queue.get_property('current-level-time')
            self.assertGreaterEqual(level, BUFFER_TIME_NS)
            # Whole Gst buffers can cross a threshold by one buffer.
            self.assertLessEqual(level, BUFFER_TIME_NS + 10 * Gst.MSECOND)
            self.assertLessEqual(queue.get_property('current-level-bytes'), BUFFER_BYTES + 882)
        finally:
            pipeline.set_state(Gst.State.NULL)

    def test_short_clip_drains_every_sample_at_end(self):
        source = Gst.ElementFactory.make('audiotestsrc')
        source.set_property('num-buffers', 3)
        source.set_property('samplesperbuffer', 441)
        sink = Gst.ElementFactory.make('fakesink')
        sink.set_property('signal-handoffs', True)
        sizes = []
        sink.connect('handoff', lambda _sink, buf, _pad: sizes.append(buf.get_size()))
        output = buffered_sink(sink)
        pipeline = Gst.Pipeline.new(None)
        pipeline.add(source)
        pipeline.add(output)
        self.assertTrue(source.link(output))
        try:
            pipeline.set_state(Gst.State.PLAYING)
            event = pipeline.get_bus().timed_pop_filtered(5 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
            self.assertIsNotNone(event)
            self.assertEqual(event.type, Gst.MessageType.EOS)
            self.assertEqual(len(sizes), 3)
            self.assertTrue(all(size > 0 for size in sizes))
        finally:
            pipeline.set_state(Gst.State.NULL)

class PlaybackStateTests(unittest.TestCase):
    def player(self, result):
        from unittest.mock import Mock
        from audio_player import GstPlayer, Gst
        player=GstPlayer();player.state='starting';player.deadline=time.monotonic()+10
        pipeline=player.pipeline=Mock()
        pipeline.set_state.return_value=result
        pipeline.query_position.return_value=(True,0)
        event=Mock(type=Gst.MessageType.ASYNC_DONE)
        pipeline.get_bus.return_value.pop.side_effect=[event,None]
        return player,pipeline

    def test_async_done_does_not_claim_playing(self):
        from audio_player import Gst
        player,pipeline=self.player(Gst.StateChangeReturn.ASYNC)
        player.tick()
        self.assertEqual(player.state,'starting')
        event=Mock(type=Gst.MessageType.STATE_CHANGED,src=pipeline)
        event.parse_state_changed.return_value=(Gst.State.PAUSED,Gst.State.PLAYING,Gst.State.VOID_PENDING)
        pipeline.get_bus.return_value.pop.side_effect=[event,None]
        player.tick();self.assertEqual(player.state,'playing')

    def test_playing_transition_failure_is_reported(self):
        from audio_player import Gst
        player,pipeline=self.player(Gst.StateChangeReturn.FAILURE)
        player.tick()
        self.assertEqual(player.state,'failed');self.assertIsNone(player.pipeline)
