"""Temporal, focus, and directional acceptance tests for analog text entry."""

from types import SimpleNamespace
import math
import unittest

from guide_keyboard import Keyboard
from guide_stick_input import StickController, DIRECTIONS
from guide_text_entry import TextEntryManager, TextOwnershipError, TextRequest


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


class KeyboardFixture:
    def __init__(self):
        self.session = SimpleNamespace(state='editing', token='focus-1',
                                       request=SimpleNamespace(owner_id='notes:1'))
        self.manager = SimpleNamespace(active=self.session)
        self.focus = (3, 3)
        self.movements = []
        self.activations = []

    def move_selection(self, dx, dy):
        self.movements.append((dx, dy))
        self.focus = self.focus[0] + dx, self.focus[1] + dy
        return True

    def activate_neighbor(self, dx, dy):
        self.activations.append((self.focus[0] + dx, self.focus[1] + dy))
        return True

    @property
    def neighbors(self):
        return {direction: (self.focus[0] + direction[0], self.focus[1] + direction[1])
                for direction in DIRECTIONS}


class StickTests(unittest.TestCase):
    def setUp(self):
        self.keyboard = KeyboardFixture()
        self.clock = Clock()
        self.controller = StickController(self.keyboard, self.clock)

    def update(self, left=(0, 0), right=(0, 0), now=None, generation=0):
        if now is not None:
            self.clock.now = now
        return self.controller.update(left, right, generation)

    def test_held_sticks_on_open_do_nothing_until_independently_neutral(self):
        self.assertFalse(self.update(left=(1, 0), right=(1, 0)))
        self.assertFalse(self.update(left=(1, 0), right=(1, 0), now=3))
        self.assertFalse(self.update(left=(0, 0), right=(1, 0)))
        self.assertTrue(self.update(left=(1, 0), right=(1, 0)))
        self.assertEqual(self.keyboard.movements, [(1, 0)])
        self.assertEqual(self.keyboard.activations, [])
        self.update(left=(1, 0), right=(0, 0))
        self.assertTrue(self.update(left=(1, 0), right=(1, 0)))
        self.assertEqual(self.keyboard.activations, [])
        self.update()
        self.assertEqual(len(self.keyboard.activations), 1)

    def test_left_flick_then_fixed_repeat_delay_and_rate(self):
        self.update()
        self.assertTrue(self.update(left=(1, 0), now=.1))
        for now in (.2, .449):
            self.assertFalse(self.update(left=(1, 0), now=now))
        self.assertTrue(self.update(left=(1, 0), now=.45))
        self.assertFalse(self.update(left=(1, 0), now=.574))
        self.assertTrue(self.update(left=(1, 0), now=.575))
        self.assertFalse(self.update(left=(1, 0), now=.699))
        self.assertTrue(self.update(left=(1, 0), now=.700))
        self.assertEqual(self.keyboard.movements, [(1, 0)] * 4)

    def test_delayed_update_never_replays_a_repeat_burst(self):
        self.update()
        self.update(left=(1, 0), now=.1)
        self.update(left=(1, 0), now=10)
        self.assertEqual(len(self.keyboard.movements), 2)
        self.assertFalse(self.update(left=(1, 0), now=10))
        self.assertFalse(self.update(left=(1, 0), now=10.124))
        self.assertTrue(self.update(left=(1, 0), now=10.125))
        self.assertEqual(len(self.keyboard.movements), 3)

    def test_direction_change_moves_immediately_and_restarts_hold_delay(self):
        self.update()
        self.update(left=(1, 0), now=.1)
        self.assertTrue(self.update(left=(0, -1), now=.2))
        self.assertFalse(self.update(left=(0, -1), now=.549))
        self.assertTrue(self.update(left=(0, -1), now=.55))
        self.assertEqual(self.keyboard.movements, [(1, 0), (0, -1), (0, -1)])

    def test_angular_noise_near_sector_boundary_does_not_generate_extra_moves(self):
        def position(degrees):
            angle = math.radians(degrees)
            return math.cos(angle), math.sin(angle)
        self.update()
        self.update(left=position(21), now=.1)
        for index, degrees in enumerate((22, 23, 22, 24, 21, 23)):
            self.assertFalse(self.update(left=position(degrees), now=.11 + index * .01))
        self.assertEqual(self.keyboard.movements, [(1, 0)])
        self.assertTrue(self.update(left=position(31), now=.2))
        self.assertFalse(self.update(left=position(23), now=.21))
        self.assertTrue(self.update(left=position(14), now=.22))
        self.assertEqual(self.keyboard.movements, [(1, 0), (1, 1), (1, 0)])

    def test_returning_neutral_cancels_repeat_and_next_flick_is_immediate(self):
        self.update()
        self.update(left=(-1, 0), now=.1)
        self.update(now=.2)
        self.assertFalse(self.update(now=5))
        self.assertTrue(self.update(left=(-1, 0), now=5.01))
        self.assertEqual(self.keyboard.movements, [(-1, 0)] * 2)

    def test_drift_does_not_engage_and_hysteresis_does_not_chatter(self):
        self.update()
        for magnitude in (.1, .3, .4, .549):
            self.assertFalse(self.update(left=(magnitude, 0), right=(magnitude, 0)))
        self.assertTrue(self.update(left=(.55, 0), right=(.55, 0), now=.1))
        self.assertFalse(self.update(left=(.4, 0), right=(.4, 0), now=.2))
        self.assertTrue(self.update(left=(.4, 0), right=(.4, 0), now=.45))
        self.assertEqual(len(self.keyboard.activations), 0)
        self.update(left=(.3, 0), right=(.3, 0), now=.5)
        self.assertTrue(self.update(left=(.55, 0), right=(.55, 0), now=.51))
        self.assertEqual(len(self.keyboard.activations), 0)  # moving the anchor cancelled the first preview
        self.update(now=.52)
        self.assertEqual(len(self.keyboard.activations), 1)

    def test_all_eight_sectors_have_expected_direction(self):
        for dx, dy in DIRECTIONS:
            with self.subTest(direction=(dx, dy)):
                self.update()
                self.update(left=(dx, dy), right=(dx, dy))
                self.assertEqual(self.keyboard.movements[-1], (dx, dy))
                self.update()
                self.assertEqual(self.keyboard.activations[-1],
                                 (self.keyboard.focus[0] + dx, self.keyboard.focus[1] + dy))

    def test_diagonal_engagement_uses_radial_distance(self):
        self.update()
        self.assertTrue(self.update(left=(.4, -.4)))
        self.assertEqual(self.keyboard.movements, [(1, -1)])

    def test_right_hold_sweeps_preview_and_release_selects_once(self):
        self.update()
        self.assertTrue(self.update(right=(1, 0), now=.1))
        for now, position in ((.5, (1, 0)), (5, (0, 1)), (10, (-1, -1))):
            self.update(right=position, now=now)
        self.assertEqual(self.keyboard.activations, [])
        self.assertEqual(self.keyboard.stick_highlight, (2, 2))
        self.assertEqual(self.keyboard.focus, (3, 3))
        self.update(now=11)
        self.assertEqual(self.keyboard.activations, [(2, 2)])
        self.assertTrue(self.update(right=(-1, -1), now=11.1))
        self.update(now=11.2)
        self.assertEqual(len(self.keyboard.activations), 2)
        self.assertEqual(self.keyboard.activations[-1], (2, 2))

    def test_unavailable_neighbor_does_not_commit_on_release(self):
        keyboard = Keyboard(TextEntryManager(), TextRequest('notes', 'body', 'Note'))
        controller = StickController(keyboard)
        controller.update((0, 0), (0, 0), now=0)
        controller.update((0, 0), (0, -1), now=.1)
        self.assertIsNone(keyboard.stick_highlight)
        controller.update((0, 0), (0, 0), now=.2)
        self.assertEqual(keyboard.session.text, '')

    def test_simultaneous_left_movement_precedes_right_neighbor_activation(self):
        self.update()
        self.update(left=(1, 0), right=(1, 1), now=.1)
        self.assertEqual(self.keyboard.focus, (4, 3))
        self.assertEqual(self.keyboard.activations, [])
        self.update(now=.2)
        self.assertEqual(self.keyboard.activations, [(5, 4)])

    def test_missing_stick_requires_neutral_after_reappearance(self):
        self.update()
        self.update(left=(1, 0), now=.1)
        self.assertFalse(self.update(left=None, now=.2))
        self.assertFalse(self.update(left=(1, 0), now=3))
        self.update(left=(0, 0), now=3.1)
        self.assertTrue(self.update(left=(1, 0), now=3.2))
        self.assertEqual(len(self.keyboard.movements), 2)

    def test_missing_left_does_not_disarm_present_right(self):
        self.update(left=None)
        self.assertTrue(self.update(left=None, right=(0, 1)))
        self.update(left=None)
        self.assertEqual(self.keyboard.activations, [(3, 4)])

    def test_invalid_samples_disarm_instead_of_producing_movement(self):
        invalid = ((float('nan'), 0), (float('inf'), 0), (1.01, 0),
                   (True, 0), ('1', 0), (0,), 'invalid')
        for value in invalid:
            with self.subTest(value=value):
                self.controller.reset()
                self.update()
                count = len(self.keyboard.movements)
                self.assertFalse(self.update(left=value))
                self.assertFalse(self.update(left=(1, 0)))
                self.assertEqual(len(self.keyboard.movements), count)

    def test_reset_suppresses_held_sticks_until_new_neutral(self):
        self.update()
        self.update(left=(1, 0), right=(0, 1))
        self.controller.reset()
        self.assertFalse(self.update(left=(1, 0), right=(0, 1), now=5))
        self.update(now=5.1)
        self.assertTrue(self.update(left=(1, 0), right=(0, 1), now=5.2))
        self.assertEqual(len(self.keyboard.movements), 2)
        self.assertEqual(len(self.keyboard.activations), 0)
        self.update(now=5.3)
        self.assertEqual(len(self.keyboard.activations), 1)

    def test_right_click_reset_preserves_left_repeat_and_requires_right_neutral(self):
        self.update()
        self.update(left=(1, 0), right=(1, 0), now=.1)
        self.controller.reset_right()
        self.assertTrue(self.update(left=(1, 0), right=(1, 0), now=.45))
        self.assertEqual(len(self.keyboard.movements), 2)
        self.assertEqual(len(self.keyboard.activations), 0)
        self.update(left=(1, 0), right=(0, 0), now=.46)
        self.assertTrue(self.update(left=(1, 0), right=(1, 0), now=.47))
        self.assertEqual(len(self.keyboard.movements), 2)
        self.assertEqual(len(self.keyboard.activations), 0)
        self.update(now=.48)
        self.assertEqual(len(self.keyboard.activations), 1)

    def test_generation_change_suppresses_old_hold_and_requires_neutral(self):
        self.update(generation=4)
        self.update(left=(1, 0), generation=4)
        self.assertFalse(self.update(left=(1, 0), now=2, generation=5))
        self.update(generation=5)
        self.assertTrue(self.update(left=(1, 0), generation=5))
        self.assertEqual(len(self.keyboard.movements), 2)

    def test_stale_owner_and_reopen_cannot_receive_old_hold(self):
        self.update()
        self.keyboard.manager.active = None
        self.assertFalse(self.update(left=(1, 0), right=(1, 0)))
        replacement = SimpleNamespace(state='editing', token='focus-2',
                                      request=SimpleNamespace(owner_id='notes:1'))
        self.keyboard.session = replacement
        self.keyboard.manager.active = replacement
        self.assertFalse(self.update(left=(1, 0), right=(1, 0)))
        self.update()
        self.assertTrue(self.update(left=(1, 0), right=(1, 0)))
        self.assertEqual(len(self.keyboard.movements), 1)

    def test_terminal_session_never_receives_stick_actions(self):
        self.update()
        self.keyboard.session.state = 'submitted'
        self.assertFalse(self.update(left=(1, 0), right=(1, 0)))
        self.assertEqual(self.keyboard.movements, [])
        self.assertEqual(self.keyboard.activations, [])

    def test_mid_update_focus_loss_prevents_right_action(self):
        self.update()
        def move(dx, dy):
            self.keyboard.manager.active = None
            return True
        self.keyboard.move_selection = move
        self.update(left=(1, 0), right=(1, 0))
        self.assertEqual(self.keyboard.activations, [])

    def test_ownership_race_from_keyboard_is_safely_disarmed(self):
        self.update()
        def expired(dx, dy):
            raise TextOwnershipError('Expired fixture')
        self.keyboard.activate_neighbor = expired
        self.assertTrue(self.update(right=(1, 0)))
        self.assertTrue(self.update())  # stale preview must be erased from the display
        self.keyboard.activate_neighbor = lambda dx, dy: True
        self.assertFalse(self.update(right=(1, 0)))

    def test_backward_or_invalid_clock_disarms_held_sticks(self):
        self.update(now=10)
        self.update(left=(1, 0), now=11)
        self.assertFalse(self.update(left=(1, 0), now=9))
        self.update(now=9.1)
        self.assertTrue(self.update(left=(1, 0), now=9.2))
        self.assertFalse(self.update(left=(1, 0), now=float('nan')))
        self.assertFalse(self.update(left=(1, 0), now=10))
        self.assertEqual(len(self.keyboard.movements), 2)

    def test_explicit_now_overrides_clock(self):
        self.controller.update((0, 0), (0, 0), now=5)
        self.controller.update((1, 0), (0, 0), now=5.1)
        self.assertTrue(self.controller.update((1, 0), (0, 0), now=5.45))
        self.assertEqual(len(self.keyboard.movements), 2)


class KeyboardIntegrationTests(unittest.TestCase):
    def test_real_keyboard_moves_primary_then_types_neighbor_without_moving_it(self):
        keyboard = Keyboard(TextEntryManager(), TextRequest('notes:1', 'body', 'Note'))
        keyboard.focus = (1, 4)  # g
        controller = StickController(keyboard)
        controller.update((0, 0), (0, 0), now=0)
        self.assertTrue(controller.update((1, 0), (1, 0), now=.1))
        self.assertEqual(keyboard.focus, (1, 5))  # h selected by the left stick
        self.assertEqual(keyboard.session.text, '')
        controller.update((0, 0), (0, 0), now=.2)
        self.assertEqual(keyboard.session.text, 'j')  # its immediate right neighbor
        controller.update((0, 0), (1, 0), now=5)
        self.assertEqual(keyboard.session.text, 'j')
        self.assertEqual(keyboard.focus, (1, 5))

    def test_neighbor_submit_ends_session_and_suppresses_later_held_input(self):
        manager = TextEntryManager()
        keyboard = Keyboard(manager, TextRequest('notes:1', 'body', 'Note', initial='saved text'))
        keyboard.focus = (4, 3)  # DEL; the adjacent right key is Done
        controller = StickController(keyboard)
        controller.update((0, 0), (0, 0), now=0)
        self.assertTrue(controller.update((0, 0), (1, 0), now=.1))
        self.assertEqual(keyboard.session.state, 'editing')
        controller.update((0, 0), (0, 0), now=.2)
        self.assertEqual(keyboard.session.state, 'submitted')
        self.assertFalse(controller.update((1, 0), (1, 0), now=3))
        self.assertEqual(keyboard.take_result().text, 'saved text')


if __name__ == '__main__':
    unittest.main()
