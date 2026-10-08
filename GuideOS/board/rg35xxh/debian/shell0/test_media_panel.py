import time,unittest
from unittest.mock import patch
from guide_media_panel import MediaPanel
from guide_shell import ShellState, MENU

class MediaPanelTests(unittest.TestCase):
    def test_dpad_and_a_b_route_only_to_options_while_playing_or_paused(self):
        for playback in ('playing','paused'):
            with self.subTest(playback=playback):
                state=ShellState();state.audio_panel=self.panel();panel=state.audio_panel
                state.page='media';panel.video_busy=True;panel.video_options=True
                panel.playback=dict(state=playback,position=12345,video=True)
                for code in (544,545,546,547,305,304):
                    self.assertTrue(state.key(code,1));self.assertEqual(state.page,'media')
                    self.assertEqual(panel.playback['state'],playback)
                    self.assertEqual(panel.playback['position'],12345)
                    self.assertFalse(panel.cleanup_pending)
                    request=panel.tasks.pop()
                    self.assertEqual(request['action'],'video-options')
                    self.assertEqual(request['key'],{544:'up',545:'down',546:'up',547:'down',305:'choose',304:'back'}[code])
    def test_a_b_are_consumed_while_close_is_waiting_and_queue_is_full(self):
        state=ShellState();panel=self.panel();state.audio_panel=panel;state.page='media'
        panel.video_busy=True;panel.video_options=True
        state.key(314,1);self.assertFalse(panel.video_options)
        state.key(305,1);state.key(304,1)
        self.assertEqual(state.page,'media')
        self.assertEqual([r['action'] for r in panel.tasks],['video-options']*3)
        panel.queue('video-options',key='down')
        self.assertEqual(len(panel.tasks),4)
        state.key(305,1);state.key(304,1)
        self.assertEqual(len(panel.tasks),4);self.assertEqual(state.page,'media')
        self.assertFalse(any(r['action'] in ('pause','resume','stop','seek') for r in panel.tasks))
    def test_release_and_kernel_repeat_do_not_duplicate_a_b_menu_actions(self):
        state=ShellState();panel=self.panel();state.audio_panel=panel;state.page='media'
        panel.video_busy=True;panel.video_options=True
        for code in (305,304):
            state.key(code,1)
            self.assertFalse(state.key(code,0));self.assertFalse(state.key(code,2))
        self.assertEqual([r['key'] for r in panel.tasks],['choose','back'])
        self.assertEqual(state.page,'media')
    def test_open_reply_does_not_reopen_options_after_queued_close(self):
        from concurrent.futures import Future
        panel=self.panel();panel.video_busy=True
        panel.video_key(314)
        panel.inflight=panel.tasks.popleft();panel.future=Future()
        panel.video_key(314);self.assertFalse(panel.video_options)
        panel.future.set_result(dict(state='playing',video=True,position=0,options_view='options'))
        panel.next_media=float('inf');panel.poll()
        self.assertFalse(panel.video_options)
    def test_failed_menu_request_keeps_playback_and_display(self):
        from concurrent.futures import Future
        panel=self.panel();panel.video_busy=True;panel.video_options=True
        panel.inflight=dict(action='video-options',key='open');panel.future=Future()
        panel.future.set_exception(RuntimeError('inventory unavailable'))
        panel.poll();self.assertTrue(panel.video_busy)
        self.assertTrue(panel.video_options);self.assertFalse(panel.cleanup_pending)
        self.assertIn('options unavailable',panel.notice)
        panel.video_key(305);panel.video_key(304)
        self.assertEqual([r['action'] for r in panel.tasks],['video-options','video-options'])
    def test_select_opens_options_and_back_does_not_exit_video(self):
        state=ShellState();state.audio_panel=self.panel();state.audio_panel.video_busy=True
        state.page='media'
        self.assertTrue(state.key(314,1))
        self.assertTrue(state.audio_panel.video_options)
        state.key(304,1);self.assertEqual(state.page,'media')
        self.assertEqual(list(state.audio_panel.tasks),[
            dict(action='video-options',key='open',_video_generation=0),
            dict(action='video-options',key='back',_video_generation=0)])
        state.key(MENU,1);self.assertEqual(state.page,'home')
        self.assertEqual(list(state.audio_panel.tasks),[dict(action='stop')])
    def panel(self):
        panel=MediaPanel('/nonexistent');panel.request=lambda request:dict(state='stopped',position=0,video=False)
        self.addCleanup(panel.close);return panel
    def test_video_reserves_display_before_request_and_menu_stops(self):
        panel=self.panel();panel.view='video';panel.items=[dict(id='a'*32,title='clip',kind=2,generation=1)]
        panel.activate('media:'+'a'*32)
        self.assertTrue(panel.video_busy)
        panel.video_key(MENU)
        self.assertEqual(list(panel.tasks),[dict(action='stop')])
    def test_pending_request_does_not_block_ui_poll(self):
        panel=self.panel()
        def slow(request):time.sleep(.15);return dict(state='stopped',video=False,position=0)
        panel.request=slow;panel.queue('status')
        begin=time.monotonic();panel.poll()
        self.assertLess(time.monotonic()-begin,.1)
        time.sleep(.2);panel.poll();self.assertFalse(panel.video_busy)
    def test_menu_and_power_recover_global_navigation_from_video(self):
        state=ShellState();state.audio_panel=self.panel();state.audio_panel.video_busy=True
        state.page='media';self.assertTrue(state.key(MENU,1));self.assertEqual(state.page,'home')
        state.audio_panel.video_busy=True;self.assertTrue(state.key(116,1));self.assertEqual(state.page,'power')
        self.assertFalse(state.shutdown_requested)

    def test_older_status_reply_cannot_release_queued_video_display(self):
        from concurrent.futures import Future
        panel=self.panel();panel.display_pending=True;panel.video_busy=True
        panel.inflight=dict(action='status');panel.future=Future()
        panel.future.set_result(dict(state='stopped',position=0,video=False))
        panel.next_media=float('inf');panel.poll()
        self.assertTrue(panel.video_busy)
