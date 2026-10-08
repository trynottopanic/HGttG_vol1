"""Display lease ordering and nonblocking observations; no physical VT claim."""
import time,threading,unittest
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock,patch
from guide_browser_frontend import BrowserSession

class ImmediateExecutor:
    def submit(self,work):
        f=Future()
        try:f.set_result(work())
        except Exception as e:f.set_exception(e)
        return f
    def shutdown(self,**kw):pass

class LeaseTests(unittest.TestCase):
    def setUp(self):
        self.pause=Mock(return_value=True);self.resume=Mock()
        self.session=BrowserSession(self.pause,self.resume,executor=ImmediateExecutor())
        self.controller=patch('guide_browser_frontend.Controller').start()
        self.run=patch('guide_browser_frontend.subprocess.run').start()
        self.run.return_value=SimpleNamespace(stdout=b'inactive\n')
        self.addCleanup(patch.stopall)
    def tick(self,n=1):
        for _ in range(n):self.session.next_poll=0;self.session.poll()
    def begin(self):
        self.session.start();self.tick() # Check then shell-owned lease and start.
        self.run.return_value=SimpleNamespace(stdout=b'activating\n');self.tick()
    def test_refused_lease_does_not_create_controller(self):
        self.pause.return_value=False;self.session.start();self.tick()
        self.assertEqual(self.session.state,'idle');self.controller.assert_not_called();self.resume.assert_not_called()
    def test_input_failure_restores_only_after_service_stops(self):
        self.controller.side_effect=OSError('uinput unavailable')
        self.session.start();self.tick()
        self.assertEqual(self.session.state,'stopping');self.resume.assert_not_called()
        self.run.return_value=SimpleNamespace(stdout=b'deactivating\n');self.tick(3)
        self.resume.assert_not_called()
        self.run.return_value=SimpleNamespace(stdout=b'failed\n');self.tick(2)
        self.resume.assert_called_once();self.assertIn('Browser controls unavailable',self.session.detail)
    def test_existing_service_does_not_take_new_lease(self):
        self.run.return_value=SimpleNamespace(stdout=b'active\n');self.session.start();self.tick()
        self.assertEqual(self.session.state,'idle');self.pause.assert_not_called()
    def test_startup_timeout_requests_stop_before_restore(self):
        self.begin();self.session.deadline=0;self.tick()
        self.assertEqual(self.session.state,'stopping');self.resume.assert_not_called()
        self.tick(3);self.resume.assert_not_called()
        self.run.return_value=SimpleNamespace(stdout=b'inactive\n');self.tick(2)
        self.resume.assert_called_once();self.assertEqual(self.session.state,'idle')
    def test_observation_failure_never_releases_live_display(self):
        self.begin();self.run.side_effect=TimeoutError();self.tick(3)
        self.resume.assert_not_called();self.assertTrue(self.session.leased)
        self.session.close();self.tick(3);self.resume.assert_not_called()
    def test_cancelled_preflight_cannot_launch_or_take_a_lease(self):
        self.session.start();self.session.close();self.tick(2)
        self.pause.assert_not_called();self.controller.assert_not_called();self.resume.assert_not_called()
        self.assertEqual(self.session.state,'idle')

class WorkerTests(unittest.TestCase):
    def test_idle_neutral_samples_do_not_fill_keyboard_queue_or_drop_cancel(self):
        session=BrowserSession(Mock(),Mock(),executor=ImmediateExecutor())
        session.state='running';session.controller=Mock();session.info=dict(keyboard=True,keyboard_token='focus')
        for _ in range(100):
            session.input(sticks=dict(left=[0,0],right=[0,0],generation=1))
        session.input(code=304,value=1)
        self.assertEqual(len(session.keyboard_events),1)
        self.assertEqual(session.keyboard_events[-1],dict(code=304,value=1))
        self.assertEqual(session.detail,'')

    def test_native_input_queues_hold_and_release_without_blocking_or_uinput(self):
        session=BrowserSession(Mock(),Mock(),executor=ImmediateExecutor())
        session.state='running';session.controller=Mock();session.info=dict(keyboard=True,keyboard_token='focus')
        session.input(sticks=dict(left=[0,0],right=[1,0],generation=1))
        session.input(sticks=dict(left=[0,0],right=[0,0],generation=1))
        self.assertEqual(len(session.keyboard_events),2)
        session.controller.input.assert_not_called()

    def test_native_packet_uses_focus_token_without_repeated_service_forks(self):
        with patch.object(BrowserSession,'_active') as active,patch('guide_browser_frontend.request',return_value=dict(keyboard=True,keyboard_token='new')) as send:
            BrowserSession._observe(True,None,None,dict(token='old',events=[dict(code=305,value=1)]))
            send.assert_called_once_with('keyboard-input',token='old',events=[dict(code=305,value=1)])
            active.assert_not_called()

    def test_admission_shortfall_never_takes_display(self):
        pause=Mock();resume=Mock()
        admission=Mock(side_effect=RuntimeError('Not enough memory to open Browser safely'))
        session=BrowserSession(pause,resume,executor=ImmediateExecutor(),admission=admission)
        self.assertTrue(session.start());session.poll()
        self.assertEqual(session.state,'idle');pause.assert_not_called()
        self.assertIn('Not enough memory',session.detail)

    def test_dead_launcher_cannot_release_live_session_display(self):
        with patch.object(BrowserSession,'_active',return_value='inactive'):
            active,info,opened=BrowserSession._observe(False,None,lambda:False)
        self.assertEqual(active,'deactivating');self.assertIsNone(info)

    def test_slow_service_observation_does_not_block_input_loop(self):
        gate=threading.Event();entered=threading.Event()
        def active():entered.set();gate.wait(1);return 'inactive'
        session=BrowserSession(Mock(return_value=True),Mock())
        with patch.object(session,'_active',active):
            try:
                start=time.monotonic();self.assertTrue(session.start());self.assertLess(time.monotonic()-start,.1)
                self.assertTrue(entered.wait(.5))
                for _ in range(20):
                    start=time.monotonic();session.poll();self.assertLess(time.monotonic()-start,.05)
                session.close();gate.set()
                end=time.monotonic()+1
                while session.state!='idle' and time.monotonic()<end:session.poll();time.sleep(.005)
                self.assertEqual(session.state,'idle')
            finally:gate.set();session.shutdown()

if __name__=='__main__':unittest.main()
