import sys
import time
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import guide_boot_runner as runner
from guide_boot_runner import run


class PhaseTests(unittest.TestCase):
    def child(self, code, initialization=2, playback=.5):
        return run([sys.executable, '-c', code], initialization, playback, grace=.1)

    def test_setup_does_not_consume_playback(self):
        code = 'import os,time;time.sleep(.6);os.write(int(os.environ["GUIDE_BOOT_READY_FD"]),b"R");time.sleep(.7)'
        self.assertEqual(self.child(code, 2, 1), 0)

    def test_hung_initialization(self):
        self.assertEqual(self.child('import time;time.sleep(5)'), 124)

    def test_hung_playback(self):
        code = 'import os,time;os.write(int(os.environ["GUIDE_BOOT_READY_FD"]),b"R");time.sleep(5)'
        self.assertEqual(self.child(code), 124)

    def test_success_without_a_frame_is_failure(self):
        self.assertEqual(self.child('pass'), 1)

    def test_child_failure_is_preserved(self):
        self.assertEqual(self.child('raise SystemExit(7)'), 7)

    def test_ignored_term_is_killed(self):
        started = time.monotonic()
        self.assertEqual(self.child('import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(5)'), 124)
        self.assertLess(time.monotonic() - started, 3)

    def test_first_frame_starts_home_before_exit_and_release_follows_exit(self):
        with tempfile.TemporaryDirectory() as d:
            runtime=Path(d);completed=runtime/'child-completed';ack=runtime/'home-started';notifications=[]
            def ready():
                notifications.append('ready')
                self.assertFalse(completed.exists())
                self.assertFalse((runtime/'display-released').exists())
                ack.touch()
            code=('import os,time\nfrom pathlib import Path\n'
                  'os.write(int(os.environ["GUIDE_BOOT_READY_FD"]),b"R")\n'
                  'deadline=time.monotonic()+2\n'
                  'while not Path('+repr(str(ack))+').exists():\n'
                  ' if time.monotonic()>=deadline: raise SystemExit(9)\n'
                  ' time.sleep(.005)\n'
                  'Path('+repr(str(completed))+').touch()\n')
            with patch.object(runner,'RUNTIME',runtime),patch.object(runner,'supports_early_home',return_value=True),patch.object(runner,'notify_ready',side_effect=ready):
                self.assertEqual(self.child(code,initialization=2,playback=2),0)
            self.assertEqual(notifications,['ready'])
            self.assertTrue(completed.exists())
            self.assertTrue((runtime/'display-released').exists())
            self.assertTrue((runtime/'early-home').exists())


if __name__ == '__main__':
    unittest.main()
