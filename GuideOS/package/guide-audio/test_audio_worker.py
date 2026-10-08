import time
import unittest
from unittest.mock import Mock
from audio_player import Player


class WorkerTests(unittest.TestCase):
    def test_output_release_discards_worker_and_retains_resume_position(self):
        player = Player()
        player.process, player.connection = Mock(), Mock()
        process = player.process
        process.is_alive.return_value = False
        player.position, player.state, player.pipeline = 19, 'paused', True
        player.stop_pipeline()
        process.terminate.assert_called_once()
        self.assertIsNone(player.process)
        self.assertFalse(player.pipeline)
        self.assertEqual((player.position, player.state), (19, 'paused'))

    def test_stalled_native_worker_is_terminated_without_losing_position(self):
        player = Player()
        process = player.process = Mock()
        process.is_alive.return_value = True
        connection = player.connection = Mock()
        connection.poll.return_value = False
        player.last_reply = time.monotonic() - 13
        player.position = 27
        player.tick()
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(player.position, 27)
        self.assertEqual(player.state, 'failed')
        self.assertIsNone(player.process)

    def test_worker_command_queue_is_bounded(self):
        player = Player()
        player.process, player.connection = Mock(), Mock()
        player.process.is_alive.return_value = True
        player.sequence, player.acknowledged = 8, 0
        with self.assertRaises(ValueError):
            player._send('stop')
        player.connection.send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
