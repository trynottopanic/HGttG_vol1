"""Shared keyboard stick behavior through the actual shell and Wi-Fi owner."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import guide_platform_rg35xxh as platform
import guide_input  # Resolve the shared modules through the production adapter.
from guide_stick_input import INITIAL_REPEAT_DELAY, REPEAT_INTERVAL


def sample(left=(0, 0), right=(0, 0), generation=0, right_click=False):
    return dict(left=left, right=right, generation=generation, right_click=right_click)


class StickIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        spec = importlib.util.spec_from_file_location('stick_test_shell', Path(__file__).with_name('guide_shell.py'))
        self.shell = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {'GUIDE_WIFI_DISCOVERY': '1', 'GUIDE_WIFI_CONTROL': '1'}):
            spec.loader.exec_module(self.shell)
        self.state = self.shell.ShellState()
        self.addCleanup(self.state.text_entries.teardown)
        self.state.page = 'wifi'
        self.state.selection = self.shell.PAGES.index('wifi')
        self.ui = self.state.wifi_panel
        self.ui.runtime = Path(self.tmp.name)
        self.ui.status['networks'] = [dict(id='a' * 24, ssid='Example', security='WPA2',
            saved=False, available=True, active=False, supported=True, signal=80)]
        self.ui.target = 'a' * 24
        self.ui.view = 'detail'
        self.state.menu_input.sync_focus()
        self.state.key(self.shell.A, 1)
        self.editor = self.ui.editor

    def update(self, now, **values):
        return self.state.sticks(sample(**values), now=now)

    def test_sticks_held_on_open_require_independent_neutral(self):
        original = self.editor.focus
        self.assertFalse(self.update(0, left=(1, 0), right=(1, 0)))
        self.assertFalse(self.update(2, left=(1, 0), right=(1, 0)))
        self.assertEqual(self.editor.focus, original)
        self.assertEqual(self.editor.session.text, '')
        self.update(3, left=(0, 0), right=(1, 0))
        self.update(3.1, left=(1, 0), right=(1, 0))
        self.assertEqual(self.editor.focus, (0, 1))
        self.assertEqual(self.editor.session.text, '')
        self.update(3.2, left=(0, 0), right=(0, 0))
        self.update(3.3, left=(0, 0), right=(1, 0))
        self.assertEqual(self.editor.session.text, '')
        self.update(3.4)
        self.assertEqual(self.editor.session.text, 'e')

    def test_left_hold_moves_selection_then_repeats_without_typing(self):
        self.update(0)
        self.update(.1, left=(1, 0))
        self.assertEqual(self.editor.focus, (0, 1))
        self.update(.1 + INITIAL_REPEAT_DELAY - .001, left=(1, 0))
        self.assertEqual(self.editor.focus, (0, 1))
        self.update(.1 + INITIAL_REPEAT_DELAY + .001, left=(1, 0))
        self.assertEqual(self.editor.focus, (0, 2))
        self.update(.1 + INITIAL_REPEAT_DELAY + REPEAT_INTERVAL + .002, left=(1, 0))
        self.assertEqual(self.editor.focus, (0, 3))
        self.assertEqual(self.editor.session.text, '')

    def test_right_sweep_highlights_and_release_types_last_neighbor(self):
        self.editor.focus = (1, 4)  # g, with h immediately to its right
        self.update(0)
        self.update(.1, right=(1, 0))
        self.update(5, right=(1, 0))
        self.update(6, right=(-1, 0))
        self.assertEqual(self.editor.session.text, '')
        self.assertEqual(self.editor.stick_highlight, (1, 3))
        self.assertEqual(self.editor.focus, (1, 4))
        self.update(7)
        self.assertEqual(self.editor.session.text, 'f')
        self.update(7.1, right=(-1, 0))
        self.update(7.2)
        self.assertEqual(self.editor.session.text, 'ff')
        self.assertEqual(self.editor.focus, (1, 4))

    def test_right_neighbor_can_submit_once_and_releases_focus(self):
        self.editor.handle('insert', text='valid-password')
        self.editor.focus = (4, 3)  # DEL, whose right neighbor is JOIN
        self.update(0)
        with patch.object(self.ui, 'send') as send:
            self.update(.1, right=(1, 0))
            self.update(.2, right=(1, 0))
            send.assert_not_called()
            self.update(.3)
            send.assert_called_once_with('connect', id='a' * 24, password='valid-password')
        self.assertIsNone(self.ui.editor)
        self.assertIsNone(self.ui.stick_input)
        self.assertIsNone(self.state.text_entries.active)
        self.assertEqual(self.editor.session.text, '')

    def test_right_neighbor_can_cancel_without_connecting(self):
        self.editor.handle('insert', text='cancelled-password')
        self.editor.focus = (4, 4)  # JOIN, whose right neighbor is CANCEL
        self.update(0)
        with patch.object(self.ui, 'send') as send:
            self.update(.1, right=(1, 0))
            self.update(.2)
            send.assert_not_called()
        self.assertEqual(self.ui.view, 'detail')
        self.assertIsNone(self.ui.editor)
        self.assertIsNone(self.ui.stick_input)
        self.assertEqual(self.editor.session.text, '')

    def test_case_click_suppresses_right_flick_until_neutral(self):
        self.editor.focus = (1, 4)
        self.update(0)
        self.state.key(317, 1)
        self.assertEqual(self.editor.page, 1)
        self.update(.1, right=(1, 0), right_click=True)
        self.update(.2, right=(1, 0), right_click=False)
        self.assertEqual(self.editor.session.text, '')
        self.assertFalse(self.state.key(317, 2))
        self.assertEqual(self.editor.page, 1)
        self.update(.3)
        self.update(.4, right=(1, 0))
        self.update(.5)
        self.assertEqual(self.editor.session.text, 'H')
        self.assertEqual(self.editor.focus, (1, 4))

    def test_shoulder_buttons_switch_layers_and_disarm_held_sticks(self):
        self.update(0)
        self.editor.handle('insert', text='kept')
        self.state.key(311, 1)
        self.assertEqual(self.editor.page, 2)
        self.assertFalse(self.state.key(311, 2))
        self.update(.1, right=(1, 0), left=(1, 0))
        self.assertEqual(self.editor.session.text, 'kept')
        self.state.key(310, 1)
        self.assertEqual(self.editor.page, 0)
        self.assertEqual(self.editor.session.text, 'kept')

    def test_right_click_selects_primary_and_cancels_pending_neighbor(self):
        self.editor.focus = (1, 4)
        self.update(0)
        self.update(.1, right=(1, 0))
        self.assertEqual(self.editor.stick_highlight, (1, 5))
        self.state.key(318, 1)
        self.assertEqual(self.editor.session.text, 'g')
        self.assertEqual(self.editor.page, 0)
        self.assertIsNone(self.editor.stick_highlight)
        self.update(.2, right=(1, 0), right_click=True)
        self.update(.3)
        self.assertEqual(self.editor.session.text, 'g')
        self.assertFalse(self.state.key(318, 2))

    def test_left_click_changes_case_without_committing_preview(self):
        self.editor.focus = (1, 4)
        self.update(0)
        self.update(.1, right=(1, 0))
        self.state.key(317, 1)
        self.assertEqual(self.editor.page, 1)
        self.update(.2)
        self.assertEqual(self.editor.session.text, '')

    def test_anchor_change_or_input_loss_cancels_preview(self):
        self.editor.focus = (1, 4)
        self.update(0)
        self.update(.1, right=(1, 0))
        self.update(.2, left=(1, 0), right=(1, 0))
        self.update(.3)
        self.assertEqual(self.editor.session.text, '')
        self.update(.4, right=(1, 0))
        self.update(.5, right=None)
        self.update(.6)
        self.assertEqual(self.editor.session.text, '')

    def test_missing_and_new_generation_samples_disarm_until_neutral(self):
        self.editor.focus = (1, 4)
        self.update(0)
        self.update(.1, left=(1, 0), right=(1, 0), generation=1)
        self.assertEqual(self.editor.focus, (1, 4))
        self.assertEqual(self.editor.session.text, '')
        self.update(.2, left=None, right=None, generation=1)
        self.update(.3, left=(1, 0), right=(1, 0), generation=1)
        self.assertEqual(self.editor.session.text, '')
        self.update(.4, generation=1)
        self.update(.5, right=(1, 0), generation=1)
        self.update(.6, generation=1)
        self.assertEqual(self.editor.session.text, 'h')

    def test_menu_tears_down_editor_and_stick_state(self):
        self.editor.handle('insert', text='unsubmitted-secret')
        self.update(0)
        self.update(.1, left=(1, 0))
        self.state.key(self.shell.MENU, 1)
        self.assertEqual(self.state.page, 'home')
        self.assertIsNone(self.ui.editor)
        self.assertIsNone(self.ui.stick_input)
        self.assertIsNone(self.state.text_entries.active)
        self.assertEqual(self.editor.session.text, '')

    def test_shell_preserves_fast_frame_order_and_excludes_axes_from_reports(self):
        self.editor.focus = (1, 4)
        self.editor.handle('insert', text='private-prefix')
        self.ui.stick_input.clock = lambda: 100.0
        observed = []
        frames = []
        for number, right in enumerate(((0, 0), (.871234, 0), (0, 0))):
            event = platform.InputEvent(('H700 Gamepad', platform.EV_SYN, platform.SYN_REPORT, 0), 100 + number * .01)
            event.sticks = sample(right=right)
            frames.append(event)
        exit_events = [('H700 Gamepad', platform.EV_KEY, code, 1) for code in
                       (self.shell.MENU, self.shell.DOWN, self.shell.A, self.shell.A)]
        inputs = Mock()
        inputs.devices = []
        inputs.close.return_value = []
        inputs.stick_snapshot.return_value = sample()
        batches = iter((frames, exit_events))

        def poll(_delay):
            if observed:
                self.fail('Shell failed to finish the bounded input sequence')
            batch = next(batches)
            if batch is exit_events:
                observed.append((self.editor.session.text, self.editor.focus))
            return batch

        inputs.poll.side_effect = poll
        framebuffer = Mock()
        framebuffer.close.return_value = []
        report = self.shell.Report(Path(self.tmp.name) / 'data', Path(self.tmp.name) / 'boot')

        def hardware(event_log):
            event_log(dict(event='input', type=platform.EV_ABS, code=3, value=.871234))
            return inputs

        with patch.object(self.shell, 'ShellState', return_value=self.state), \
                patch.object(self.shell, 'Screen'), patch.object(self.ui, 'poll', return_value=False):
            poweroff = Mock()
            self.shell.run(report, input_factory=hardware,
                           framebuffer_factory=lambda: framebuffer, poweroff=poweroff)
        self.assertEqual(observed, [('private-prefixh', (1, 4))])
        poweroff.assert_called_once()
        serialized = json.dumps(report.events)
        self.assertNotIn('private-prefix', serialized)
        self.assertNotIn('.871234', serialized)
        self.assertFalse(any(set(row) & {'sticks', 'axes', 'cursor', 'text'} for row in report.events))
        self.assertEqual(self.editor.session.text, '')


class MenuIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        spec = importlib.util.spec_from_file_location('menu_test_shell', Path(__file__).with_name('guide_shell.py'))
        self.shell = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {'GUIDE_WIFI_DISCOVERY': '1', 'GUIDE_WIFI_CONTROL': '1'}):
            spec.loader.exec_module(self.shell)
        self.state = self.shell.ShellState()
        self.addCleanup(self.state.text_entries.teardown)
        self.menu = self.state.menu_input
        self.ui = self.state.wifi_panel
        self.ui.runtime = Path(self.tmp.name)
        self.network = dict(id='a' * 24, ssid='Example', security='WPA2', saved=True,
                            available=True, active=False, supported=True, signal=80)
        self.other = dict(self.network, id='b' * 24, ssid='Other', signal=60)
        self.ui.status['networks'] = [self.network, self.other]

    def point_at(self, identity):
        target = next(target for target in self.menu.targets() if target.identity == identity)
        left, top, right, bottom = target.rect
        self.menu.pointer.move_to((left + right) / 2, (top + bottom) / 2)

    def open_wifi(self):
        self.point_at('home:wifi')
        self.state.key(self.shell.A, 1)
        self.assertEqual(self.state.page, 'wifi')

    def choose_context(self, action):
        context = self.menu.pointer.context
        if context.items:
            for _ in range(len(context.options)):
                self.state.key(self.shell.DOWN, 1)
                if context.options[context.highlight]['id'] == action:
                    return self.state.key(self.shell.A, 1)
            self.fail('Action not in current context page: ' + action)
        direction = next(key for key, row in context.options.items() if row['id'] == action)
        return self.state.key({'up': 544, 'down': 545, 'left': 546, 'right': 547}[direction], 1)

    def refresh_networks(self, networks, synchronize=True):
        status = dict(self.ui.status, networks=networks, observed=time.monotonic())
        (self.ui.runtime / 'status.json').write_text(json.dumps(status))
        self.ui.poll()
        return self.menu.refresh_targets() if synchronize else False

    def test_left_cursor_and_primary_click_use_hovered_target(self):
        for button in (self.shell.A, 317):
            with self.subTest(button=button):
                self.state.page, self.state.selection = 'home', 0
                self.menu.sync_focus()
                self.state.sticks(sample(), now=0)
                for number in range(1, 5):
                    self.state.sticks(sample(left=(0, 1)), now=number * .05)
                self.assertEqual(self.state.selection, 0)
                self.assertEqual(self.menu.hovered().identity, 'home:status')
                self.state.key(button, 1)
                self.assertEqual(self.state.page, 'status')

    def test_context_expands_and_filters_unavailable_or_unsaved_network_actions(self):
        self.open_wifi()
        self.point_at('wifi:row:' + self.network['id'])
        self.state.key(308, 1)
        context = self.menu.pointer.context
        self.assertEqual(len(context.options), 5)
        self.assertTrue(context.items)
        self.choose_context('network:forget:' + self.network['id'])
        self.assertEqual(self.ui.view, 'forget')
        self.assertFalse(self.ui.pending_token)
        self.ui.view = 'detail'
        self.network.update(saved=False, supported=False)
        self.menu.sync_focus()
        self.state.key(308, 1)
        labels = {row['label'] for row in self.menu.pointer.context.options.values()}
        self.assertFalse({'Connect', 'Disconnect', 'Forget'} & labels)
        self.assertLess(len(labels), 5)

    def test_context_direct_connect_uses_captured_network_and_does_not_retarget(self):
        self.open_wifi()
        self.point_at('wifi:row:' + self.network['id'])
        self.state.key(308, 1)
        self.refresh_networks([self.other, self.network])
        with patch.object(self.ui, 'send') as send:
            self.choose_context('network:connect:' + self.network['id'])
            send.assert_called_once_with('connect', id=self.network['id'])

    def test_expanded_context_rejects_connect_after_status_changes_to_active(self):
        self.open_wifi()
        self.point_at('wifi:row:' + self.network['id'])
        self.state.key(308, 1)
        self.network['active'] = True
        with patch.object(self.ui, 'send') as send:
            self.choose_context('network:connect:' + self.network['id'])
            send.assert_not_called()
        self.assertIsNone(self.menu.pointer.context)

    def test_dpad_focus_moves_pointer_and_primary_click_follows_it(self):
        self.state.key(self.shell.DOWN, 1)
        self.assertEqual(self.state.selection, 1)
        self.assertEqual(self.menu.hovered().identity, 'home:status')
        self.state.key(self.shell.A, 1)
        self.assertEqual(self.state.page, 'status')

    def test_secondary_buttons_open_context_and_dpad_selects_immediately(self):
        for button in (308, 318):
            with self.subTest(button=button):
                self.state.page, self.state.selection = 'home', 0
                self.menu.sync_focus()
                self.point_at('home:status')
                self.state.key(button, 1)
                self.assertIsNotNone(self.menu.pointer.context)
                self.assertEqual(self.state.page, 'home')
                self.state.key(self.shell.UP, 1)
                self.assertEqual(self.state.page, 'status')
                self.assertIsNone(self.menu.pointer.context)

    def test_right_stick_highlights_while_held_and_confirms_once_on_release(self):
        self.point_at('home:status')
        self.state.key(308, 1)
        self.state.sticks(sample(), now=0)
        self.state.sticks(sample(right=(0, -1)), now=.1)
        self.assertEqual(self.menu.pointer.context.highlight, 'up')
        self.assertEqual(self.state.page, 'home')
        self.state.sticks(sample(right=(0, -1)), now=100)
        self.assertEqual(self.state.page, 'home')
        self.state.sticks(sample(), now=101)
        self.assertEqual(self.state.page, 'status')
        self.assertIsNone(self.menu.pointer.context)
        self.state.sticks(sample(), now=102)
        self.assertEqual(self.state.page, 'status')

    def test_context_back_home_and_close_directions_have_separate_effects(self):
        self.open_wifi()
        self.point_at('wifi:row:' + self.network['id'])
        self.state.key(self.shell.A, 1)
        self.assertEqual(self.ui.view, 'detail')
        with patch.object(self.ui, 'send') as send:
            self.state.key(308, 1)
            self.assertTrue({'select', 'back', 'home', 'close'} <=
                            {value['id'] for value in self.menu.pointer.context.options.values()})
            self.choose_context('close')
            self.assertEqual(self.ui.view, 'detail')
            self.state.key(308, 1)
            self.choose_context('back')
            self.assertEqual((self.state.page, self.ui.view), ('wifi', 'list'))
            self.state.key(308, 1)
            self.choose_context('home')
            self.assertEqual(self.state.page, 'home')
            send.assert_not_called()

    def test_back_and_menu_cancel_context_without_activating_underlying_network(self):
        self.open_wifi()
        self.point_at('wifi:row:' + self.network['id'])
        self.state.key(self.shell.A, 1)
        with patch.object(self.ui, 'send') as send:
            self.state.key(308, 1)
            self.state.key(self.shell.B, 1)
            self.assertEqual((self.state.page, self.ui.view), ('wifi', 'detail'))
            self.assertIsNone(self.menu.pointer.context)
            self.state.key(308, 1)
            self.state.key(self.shell.MENU, 1)
            self.assertEqual(self.state.page, 'home')
            self.assertIsNone(self.menu.pointer.context)
            send.assert_not_called()

    def test_power_target_still_requires_a_separate_confirmation(self):
        self.point_at('home:power')
        self.state.key(317, 1)
        self.assertEqual(self.state.page, 'power')
        self.assertFalse(self.state.shutdown_requested)
        self.state.key(self.shell.A, 2)
        self.assertFalse(self.state.shutdown_requested)
        self.state.key(self.shell.A, 1)
        self.assertTrue(self.state.shutdown_requested)

    def test_context_target_survives_network_reordering_without_connecting_other(self):
        self.open_wifi()
        self.point_at('wifi:row:' + self.network['id'])
        self.state.key(308, 1)
        self.refresh_networks([self.other, self.network])
        with patch.object(self.ui, 'send') as send:
            self.choose_context('select')
            self.assertEqual(self.ui.target, self.network['id'])
            self.assertEqual(self.ui.view, 'detail')
            send.assert_not_called()
            self.state.key(self.shell.A, 1)
            send.assert_called_once_with('connect', id=self.network['id'])

    def test_disappeared_context_target_does_not_fall_through_to_another_network(self):
        self.open_wifi()
        self.point_at('wifi:row:' + self.network['id'])
        self.state.key(308, 1)
        self.refresh_networks([self.other])
        with patch.object(self.ui, 'send') as send:
            if self.menu.pointer.context is not None:
                self.choose_context('select')
            self.assertEqual(self.ui.view, 'list')
            self.assertIsNone(self.ui.target)
            send.assert_not_called()
        self.assertIsNone(self.menu.pointer.context)

    def test_keyboard_keeps_pointer_inactive_and_text_shortcuts_keep_their_meaning(self):
        self.network['saved'] = False
        self.open_wifi()
        self.point_at('wifi:row:' + self.network['id'])
        self.state.key(self.shell.A, 1)
        self.state.key(self.shell.A, 1)
        self.assertTrue(self.state.keyboard_active)
        editor = self.ui.editor
        editor.handle('insert', text='ab')
        position = self.menu.pointer.position
        self.state.sticks(sample(), now=0)
        self.state.sticks(sample(left=(1, 0)), now=.1)
        self.assertEqual(self.menu.pointer.position, position)
        self.assertEqual(editor.focus, (0, 1))
        self.state.key(308, 1)
        self.assertEqual(editor.session.text, 'a')
        self.state.key(317, 1)
        self.assertEqual(editor.page, 1)
        self.assertIsNone(self.menu.pointer.context)
        self.assertTrue(self.state.keyboard_active)

    def test_dpad_network_focus_follows_reordered_rows_before_primary_click(self):
        self.open_wifi()
        self.state.key(self.shell.DOWN, 1)
        self.state.key(self.shell.DOWN, 1)
        self.assertEqual(self.ui.rows()[self.ui.cursor][0], self.network['id'])
        before = self.menu.pointer.position
        self.assertTrue(self.refresh_networks([self.other, self.network]))
        self.assertNotEqual(self.menu.pointer.position, before)
        self.assertEqual(self.menu.hovered().identity, 'wifi:row:' + self.network['id'])
        self.state.key(self.shell.A, 1)
        self.assertEqual(self.ui.target, self.network['id'])
        self.assertEqual(self.ui.view, 'detail')

    def test_freely_moved_pointer_stays_physical_when_network_rows_reorder(self):
        self.open_wifi()
        self.state.key(self.shell.DOWN, 1)
        self.state.key(self.shell.DOWN, 1)
        self.state.sticks(sample(), now=0)
        self.state.sticks(sample(left=(1, 0)), now=.05)
        before = self.menu.pointer.position
        self.assertIsNone(self.menu.focus_anchor)
        self.refresh_networks([self.other, self.network])
        self.assertEqual(self.menu.pointer.position, before)
        self.assertEqual(self.ui.rows()[self.ui.cursor][0], self.network['id'])
        self.assertEqual(self.menu.hovered().identity, 'wifi:row:' + self.other['id'])
        self.state.key(self.shell.A, 1)
        self.assertEqual(self.ui.target, self.other['id'])

    def test_captured_connect_action_cannot_turn_into_disconnect_before_refresh_sync(self):
        self.open_wifi()
        self.point_at('wifi:row:' + self.network['id'])
        self.state.key(self.shell.A, 1)
        self.state.key(308, 1)
        self.assertEqual(next(row['label'] for row in self.menu.pointer.context.options.values()
                              if row['id'] == 'select'), 'Connect')
        active = dict(self.network, active=True)
        self.refresh_networks([active, self.other], synchronize=False)
        with patch.object(self.ui, 'send') as send:
            self.assertTrue(self.choose_context('select'))
            send.assert_not_called()
        self.assertIsNone(self.menu.pointer.context)
        self.assertEqual(self.ui.view, 'detail')
        self.assertTrue(any(target.identity == 'wifi:disconnect:' + self.network['id']
                            for target in self.menu.targets()))

    def test_provider_refresh_invalidates_popup_when_connect_changes_to_disconnect(self):
        self.open_wifi()
        self.point_at('wifi:row:' + self.network['id'])
        self.state.key(self.shell.A, 1)
        self.state.key(308, 1)
        with patch.object(self.ui, 'send') as send:
            changed = self.refresh_networks([dict(self.network, active=True), self.other])
            self.assertTrue(changed)
            self.assertIsNone(self.menu.pointer.context)
            self.assertIsNone(self.menu.context_target)
            send.assert_not_called()

    def test_rejected_stale_popup_confirmation_still_requests_redraw(self):
        self.open_wifi()
        self.point_at('wifi:row:' + self.network['id'])
        self.state.key(308, 1)
        self.refresh_networks([self.other], synchronize=False)
        before = self.state.revision
        with patch.object(self.ui, 'send') as send:
            self.assertTrue(self.choose_context('select'))
            send.assert_not_called()
        self.assertGreater(self.state.revision, before)
        self.assertIsNone(self.menu.pointer.context)
        self.assertEqual(self.ui.view, 'list')
        self.assertIsNone(self.ui.target)

    def test_busy_page_initial_cursor_does_not_cancel_but_dpad_can_focus_cancel(self):
        self.open_wifi()
        self.point_at('wifi:row:' + self.network['id'])
        self.state.key(self.shell.A, 1)

        def provider(action, **_values):
            self.ui.status['busy'] = action == 'connect'
            self.ui.pending_token = 'pending' if action == 'connect' else ''

        with patch.object(self.ui, 'send', side_effect=provider) as send:
            self.state.key(self.shell.A, 1)
            self.assertEqual(self.ui.view, 'working')
            self.assertIsNone(self.menu.hovered())
            self.assertFalse(self.state.key(self.shell.A, 1))
            self.assertFalse(self.state.key(317, 1))
            send.assert_called_once_with('connect', id=self.network['id'])
            self.state.key(self.shell.UP, 1)
            self.assertEqual(self.menu.hovered().label, 'Cancel')
            self.state.key(self.shell.A, 1)
            self.assertEqual([call.args[0] for call in send.call_args_list], ['connect', 'cancel'])
        self.assertEqual(self.ui.view, 'list')

    def test_primary_click_selects_context_wedge_without_underlying_fallthrough(self):
        for button in (self.shell.A, 317):
            with self.subTest(button=button):
                self.state.page, self.state.selection = 'home', 0
                self.menu.sync_focus()
                self.point_at('home:status')
                self.state.key(308, 1)
                context = self.menu.pointer.context
                self.menu.pointer.move_to(*context.center)
                self.assertFalse(self.state.key(button, 1))
                self.assertEqual(self.state.page, 'home')
                self.assertIsNotNone(self.menu.pointer.context)
                self.menu.pointer.move_to(context.center[0], context.center[1] - context.radius * .7)
                self.state.key(button, 1)
                self.assertEqual(self.state.page, 'status')
                self.assertIsNone(self.menu.pointer.context)

    def test_pointer_redraws_do_not_repeatedly_persist_unchanged_home_view(self):
        clock = [0.0]
        self.menu.pointer.clock = lambda: clock[0]
        positions = []
        inputs = Mock()
        inputs.devices = []
        inputs.close.return_value = []
        batches = 0
        latest = [sample()]

        def poll(_delay):
            nonlocal batches
            positions.append(self.menu.pointer.position)
            clock[0] = batches * .05
            latest[0] = sample() if batches == 0 else sample(left=(.9, 0))
            batches += 1
            if batches < 5:
                return []
            if batches > 5:
                self.fail('Shell did not finish the bounded pointer exercise')
            return [('H700 Gamepad', platform.EV_KEY, code, 1) for code in
                    (self.shell.DOWN, self.shell.DOWN, self.shell.DOWN, self.shell.A, self.shell.A)]

        inputs.poll.side_effect = poll
        inputs.stick_snapshot.side_effect = lambda: latest[0]
        framebuffer = Mock()
        framebuffer.close.return_value = []

        class CountedReport(self.shell.Report):
            def __init__(self, *args):
                super().__init__(*args)
                self.save_calls = []

            def save(self, state, phase, *args, **kwargs):
                self.save_calls.append((state.page, state.selection, phase))
                return super().save(state, phase, *args, **kwargs)

        report = CountedReport(Path(self.tmp.name) / 'data', Path(self.tmp.name) / 'boot')
        with patch.object(self.shell, 'ShellState', return_value=self.state), \
                patch.object(self.shell, 'Screen'):
            poweroff = Mock()
            self.shell.run(report, input_factory=lambda _log: inputs,
                           framebuffer_factory=lambda: framebuffer, poweroff=poweroff)
        self.assertGreater(len(set(positions)), 2)
        home_views = [row for row in report.events if row.get('event') == 'view' and row.get('page') == 'home']
        self.assertEqual(len(home_views), 1)
        running_home_saves = [row for row in report.save_calls if row == ('home', 0, 'running')]
        self.assertLessEqual(len(running_home_saves), 2)  # startup + first visible view only
        self.assertNotIn('position', json.dumps(report.events))
        self.assertNotIn('pointer', json.dumps(report.events))
        poweroff.assert_called_once()


class RenderingCostTests(unittest.TestCase):
    def test_cached_menu_matches_full_render_and_does_not_repaint_static_text(self):
        from PIL import ImageChops
        import guide_shell as shell
        sink = Mock()
        state = shell.ShellState()
        screen = shell.Screen(sink)
        screen.draw(state)
        self.assertEqual(screen._menu_base.size, (640, 480))
        state.menu_input.pointer.move_to(380, 160)
        with patch.object(screen, '_text', wraps=screen._text) as text:
            screen.draw(state, pointer_only=True)
        self.assertFalse(any('THE GUIDE' in str(call) for call in text.call_args_list))
        cached = sink.show.call_args.args[0].copy()
        screen.draw(state)
        self.assertIsNone(ImageChops.difference(cached, sink.show.call_args.args[0]).getbbox())
        state.menu_input.open_context()
        screen.draw(state, pointer_only=True)
        cached = sink.show.call_args.args[0].copy()
        screen.draw(state)
        self.assertIsNone(ImageChops.difference(cached, sink.show.call_args.args[0]).getbbox())


if __name__ == '__main__':
    unittest.main()
