"""Behavioral tests for pointer timing and context-menu release confirmation."""

import math
import unittest

from guide_pointer_input import PointerController


OPTIONS = {
    'up': dict(id='open', label='Open'),
    'right': dict(id='back', label='Back'),
    'down': dict(id='home', label='Home'),
    'left': dict(id='close', label='Close'),
}


class PointerTests(unittest.TestCase):
    def setUp(self):
        self.pointer = PointerController()

    def update(self, left=(0, 0), right=(0, 0), now=0, **kwargs):
        return self.pointer.update(left, right, now=now, **kwargs)

    def test_initial_held_left_moves_without_neutral_reset(self):
        initial = self.pointer.position
        self.assertEqual(self.update(left=(1, 0)), (False, None))
        self.assertEqual(self.update(left=(1, 0), now=.05), (True, None))
        self.assertGreater(self.pointer.position[0] - initial[0], 0)
        self.assertLess(self.pointer.position[0] - initial[0], 35)

    def test_radial_deadzone_and_deflection_scale_speed(self):
        self.update()
        initial = self.pointer.position
        self.assertFalse(self.update(left=(.11, 0), now=.05)[0])
        self.assertFalse(self.update(left=(.08, .08), now=.10)[0])
        self.update(left=(.6, 0), now=.15)
        slow_distance = self.pointer.position[0] - initial[0]
        self.assertGreater(slow_distance, 0)
        self.assertLess(slow_distance, 22)
        self.update(left=(1, 0), now=.20)
        self.assertGreater(self.pointer.position[0] - initial[0] - slow_distance, slow_distance)
        self.assertLess(self.pointer.position[0] - initial[0], 60)

    def test_small_motion_starts_promptly_and_neutral_stops_without_drift(self):
        self.update()
        initial=self.pointer.position
        for frame in range(1,4):self.update(left=(.20,0),now=frame/60)
        self.assertGreaterEqual(self.pointer.position[0]-initial[0],.5)
        self.update(now=.06);stopped=self.pointer.position
        for frame in range(1,20):self.update(left=(.08,.04),now=.06+frame/60)
        self.assertEqual(self.pointer.position,stopped)

    def test_direction_reversal_is_responsive(self):
        self.update()
        for frame in range(1,7):self.update(left=(1,0),now=frame/60)
        self.update(left=(-1,0),now=7/60);turn=self.pointer.position[0]
        self.update(left=(-1,0),now=8/60)
        self.assertLess(self.pointer.position[0],turn)

    def test_full_deflection_reaches_practical_deck_speed(self):
        self.update()
        initial = self.pointer.position
        for frame in range(1, 11):
            self.update(left=(1, 0), now=frame / 60)
        distance = self.pointer.position[0] - initial[0]
        self.assertGreater(distance, 120)
        self.assertLess(distance, 130)

    def test_diagonal_speed_never_exceeds_cardinal_maximum(self):
        self.update()
        initial = self.pointer.position
        self.update(left=(1, 1), now=.05)
        delta = (self.pointer.position[0] - initial[0], self.pointer.position[1] - initial[1])
        self.assertGreater(math.hypot(*delta), 0)
        self.assertLessEqual(math.hypot(*delta), 35)
        self.assertAlmostEqual(delta[0], delta[1])

    def test_stalled_frame_catches_up_recent_motion_but_remains_bounded(self):
        self.update()
        initial = self.pointer.position
        self.update(left=(1, 0), now=20)
        self.assertGreater(self.pointer.position[0] - initial[0], 140)
        self.assertLessEqual(self.pointer.position[0] - initial[0], 160)
        stalled_position = self.pointer.position[0]
        self.assertFalse(self.update(left=(1, 0), now=20)[0])
        self.update(left=(1, 0), now=20.01)
        self.assertGreater(self.pointer.position[0], stalled_position)
        self.assertLessEqual(self.pointer.position[0] - stalled_position, 9)

    def test_pointer_clamps_at_all_viewport_edges(self):
        self.pointer.move_to(-10, 900)
        self.assertEqual(self.pointer.position, (0, 479))
        self.update()
        self.assertFalse(self.update(left=(-1, 1), now=.05)[0])
        self.pointer.move_to(900, -20)
        self.assertEqual(self.pointer.position, (639, 0))
        self.assertFalse(self.update(left=(1, -1), now=.10)[0])

    def test_reset_preserves_position_visibility_but_discards_held_input(self):
        self.pointer.move_to(30, 40)
        self.update()
        self.pointer.reset()
        self.assertEqual(self.pointer.position, (30, 40))
        self.assertTrue(self.pointer.visible)
        self.assertFalse(self.update(left=(1, 0), now=10)[0])

    def test_generation_and_missing_input_resume_without_fresh_neutral(self):
        self.update(generation=1)
        self.assertFalse(self.update(left=(1, 0), generation=2, now=.05)[0])
        self.assertTrue(self.update(left=(1, 0), generation=2, now=.1)[0])
        for missing in (None, (float('nan'), 0), (2, 0), (True, 0)):
            before=self.pointer.position
            self.assertFalse(self.update(left=missing, generation=2, now=.15)[0])
            self.assertTrue(self.update(left=(1, 0), generation=2, now=.20)[0])
            self.assertGreaterEqual(self.pointer.position[0],before[0])

    def test_backwards_clock_discards_old_hold(self):
        self.update(now=10)
        self.update(left=(1, 0), now=11)
        initial = self.pointer.position
        self.assertFalse(self.update(left=(1, 0), now=9)[0])
        self.assertEqual(self.pointer.position, initial)

    def test_clock_callable_is_used_unless_now_is_supplied(self):
        now = [5.0]
        pointer = PointerController(clock=lambda: now[0])
        pointer.update((0, 0), None)
        now[0] += .05
        self.assertTrue(pointer.update((1, 0), None)[0])
        self.assertGreater(pointer.position[0], 320)
        self.assertLess(pointer.position[0], 356)
        self.assertEqual(pointer.position[1], 240)


class SmoothPointerTests(unittest.TestCase):
    def test_resting_noise_and_immediate_stop_do_not_drift(self):
        pointer = PointerController()
        pointer.update((0, 0), now=0)
        for n in range(1, 101):
            self.assertFalse(pointer.update((.125 if n % 2 else .135, .01), now=n / 100)[0])
        self.assertEqual(pointer.position, (320, 240))
        pointer.update((1, 0), now=1.05)
        stopped = pointer.position
        for n in range(106, 200):
            self.assertFalse(pointer.update((.05, -.03), now=n / 100)[0])
        self.assertEqual(pointer.position, stopped)
        self.assertFalse(pointer.moving)

    def test_small_movements_accumulate_without_identical_frame_redraws(self):
        pointer = PointerController()
        pointer.move_to(100, 100)
        pointer.update((0, 0), now=0)
        redraws = sum(pointer.update((.161, 0), now=n / 100)[0] for n in range(1, 101))
        self.assertGreater(pointer.position[0], 104)
        self.assertGreater(redraws, 0)
        self.assertLess(redraws, 100)

    def test_motion_is_consistent_across_sample_rates(self):
        positions = []
        for rate in (30, 60, 120):
            pointer = PointerController()
            pointer.move_to(0, 100)
            pointer.update((0, 0), now=0)
            for n in range(1, rate + 1):
                pointer.update((.8, 0), now=n / rate)
            positions.append(pointer.position[0])
        self.assertLess(max(positions) - min(positions), .01)

    def test_alternating_angular_noise_is_filtered(self):
        pointer = PointerController(width=2000)
        pointer.update((0, 0), now=0)
        vertical_steps = []
        for n in range(1, 121):
            before = pointer.position[1]
            pointer.update((.8, .06 if n % 2 else -.06), now=n / 120)
            vertical_steps.append(abs(pointer.position[1] - before))
        self.assertLess(max(vertical_steps), .14)


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.pointer = PointerController()
        self.pointer.open_context(OPTIONS)

    def update(self, right=(0, 0), left=(0, 0), now=0, **kwargs):
        return self.pointer.update(left, right, now=now, **kwargs)

    def test_dpad_choice_is_immediate_and_closes_menu(self):
        self.assertEqual(self.pointer.choose('up'), 'open')
        self.assertIsNone(self.pointer.context)
        self.assertIsNone(self.pointer.choose('up'))

    def test_expanded_menus_match_rendered_angles_and_release_selection(self):
        for count in (5, 6, 7, 8):
            options = [dict(id=str(index), label='Action ' + str(index)) for index in range(count)]
            for index in range(count):
                self.pointer.open_context(options)
                self.update()
                key = list(self.pointer.context.options)[index]
                angle, _width = self.pointer.context.sectors()[key]
                x, y = self.pointer.context.center
                self.assertEqual(self.pointer.direction_at(x + 60 * math.cos(angle), y + 60 * math.sin(angle)), key)
                self.update(right=(math.cos(angle), math.sin(angle)))
                self.assertEqual(self.pointer.context.highlight, key)
                self.assertEqual(self.update(), (True, str(index)))

    def test_overflow_pages_keep_every_action_reachable_and_neutral_gate_new_page(self):
        options = [dict(id=str(index), label='Action ' + str(index)) for index in range(17)]
        self.pointer.open_context(options)
        seen = set()
        for _ in range(self.pointer.context.page_count):
            current = self.pointer.context
            self.assertLessEqual(len(current.options), 8)
            seen.update(row['id'] for row in current.options.values() if not row['id'].startswith('$page:'))
            next_key = next(key for key, row in current.options.items() if row['id'] == '$page:next')
            self.assertIsNone(self.pointer.choose(next_key))
            self.update(right=(0, -1))
            self.assertIsNone(self.pointer.context.highlight)
        self.assertEqual(seen, {str(index) for index in range(17)})

    def test_dpad_steps_do_not_trigger_on_neutral_stick_updates(self):
        self.pointer.open_context([dict(id=str(index), label=str(index)) for index in range(5)])
        self.update()
        self.pointer.step_choice(1)
        highlight = self.pointer.context.highlight
        self.assertEqual(self.update(), (False, None))
        self.assertEqual(self.pointer.context.highlight, highlight)
        self.assertEqual(self.pointer.choose(highlight), '0')

    def test_invalid_dpad_direction_does_not_close_context(self):
        self.assertIsNone(self.pointer.choose('diagonal'))
        self.assertIsNotNone(self.pointer.context)

    def test_held_stick_when_menu_opens_cannot_highlight_or_confirm(self):
        self.assertEqual(self.update(right=(1, 0)), (False, None))
        self.assertEqual(self.update(right=(1, 0), now=10), (False, None))
        self.assertEqual(self.update(now=11), (False, None))
        self.assertIsNone(self.pointer.context.highlight)
        self.assertIsNotNone(self.pointer.context)

    def test_right_stick_highlights_while_held_and_confirms_once_on_release(self):
        self.update()
        self.assertEqual(self.update(right=(1, 0), now=.1), (True, None))
        self.assertEqual(self.pointer.context.highlight, 'right')
        self.assertEqual(self.update(right=(1, 0), now=3000), (False, None))
        self.assertEqual(self.update(now=3001), (True, 'back'))
        self.assertIsNone(self.pointer.context)
        self.assertEqual(self.update(now=3002), (False, None))

    def test_direction_changes_before_release_choose_final_direction(self):
        self.update()
        self.update(right=(0, -1), now=.1)
        self.assertEqual(self.pointer.context.highlight, 'up')
        self.update(right=(0, 1), now=.2)
        self.assertEqual(self.pointer.context.highlight, 'down')
        self.assertEqual(self.update(now=.3), (True, 'home'))

    def test_hysteresis_keeps_highlight_until_neutral_release(self):
        self.update()
        self.assertEqual(self.update(right=(.54, 0)), (False, None))
        self.update(right=(.55, 0))
        self.assertEqual(self.update(right=(.31, 0)), (False, None))
        self.assertEqual(self.pointer.context.highlight, 'right')
        self.assertEqual(self.update(right=(.3, 0)), (True, 'back'))

    def test_missing_or_corrupt_right_sample_discards_pending_confirmation(self):
        for missing in (None, (float('nan'), 0), (0, 2), 'invalid'):
            with self.subTest(missing=missing):
                self.pointer.open_context(OPTIONS)
                self.update()
                self.update(right=(1, 0))
                self.assertEqual(self.update(right=missing), (True, None))
                self.assertEqual(self.update(), (False, None))
                self.assertIsNotNone(self.pointer.context)
                self.assertIsNone(self.pointer.context.highlight)

    def test_right_click_blocks_arming_until_released_and_neutral(self):
        self.update(right=(0, 0), right_click=True)
        self.assertEqual(self.update(right=(1, 0), right_click=False), (False, None))
        self.update(right=(0, 0), right_click=False)
        self.assertEqual(self.update(right=(1, 0)), (True, None))
        self.assertEqual(self.update(right=(1, 0), right_click=True), (True, None))
        self.assertEqual(self.update(), (False, None))
        self.assertIsNotNone(self.pointer.context)

    def test_generation_change_cannot_confirm_previously_highlighted_action(self):
        self.update(generation=1)
        self.update(right=(0, 1), generation=1)
        self.assertEqual(self.update(generation=2), (True, None))
        self.assertIsNotNone(self.pointer.context)
        self.assertIsNone(self.pointer.context.highlight)

    def test_invalid_clock_discards_highlight_instead_of_replaying_a_release(self):
        self.update()
        self.update(right=(1, 0), now=.1)
        self.assertEqual(self.update(now=float('nan')), (True, None))
        self.assertEqual(self.update(now=1), (False, None))
        self.assertIsNotNone(self.pointer.context)

    def test_reopened_context_does_not_inherit_held_selection(self):
        self.update()
        self.update(right=(1, 0))
        self.pointer.close_context()
        self.pointer.open_context(OPTIONS)
        self.assertEqual(self.update(right=(1, 0)), (False, None))
        self.assertEqual(self.update(), (False, None))
        self.assertIsNotNone(self.pointer.context)

    def test_reset_preserves_menu_but_discards_pending_selection(self):
        self.update()
        self.update(right=(-1, 0))
        self.pointer.reset()
        self.assertEqual(self.update(), (False, None))
        self.assertIsNotNone(self.pointer.context)
        self.assertIsNone(self.pointer.context.highlight)

    def test_empty_direction_does_not_repeat_or_select_another_option(self):
        self.pointer.open_context({'up': OPTIONS['up']})
        self.update()
        self.update(right=(0, -1))
        self.assertEqual(self.update(right=(1, 0)), (True, None))
        self.assertIsNone(self.pointer.context.highlight)
        self.assertEqual(self.update(), (False, None))
        self.assertIsNotNone(self.pointer.context)

    def test_left_pointer_moves_while_menu_center_stays_fixed_and_right_confirms(self):
        initial = self.pointer.position
        center = self.pointer.context.center
        self.update()
        self.update(left=(1, 0), right=(0, -1), now=.1)
        self.assertGreater(self.pointer.position[0], initial[0])
        self.assertLessEqual(self.pointer.position[0], initial[0] + 80)
        self.assertEqual(self.pointer.position[1], initial[1])
        self.assertEqual(self.pointer.context.center, center)
        self.assertEqual(self.update(left=(1, 0), now=.2), (True, 'open'))
        self.assertGreater(self.pointer.position[0], initial[0])
        self.assertLessEqual(self.pointer.position[0], initial[0] + 155)
        self.assertEqual(self.pointer.position[1], initial[1])
        self.assertTrue(self.update(left=(1, 0), now=.3)[0])
        self.assertGreater(self.pointer.position[0], initial[0])
        self.assertLessEqual(self.pointer.position[0], initial[0] + 240)
        self.assertEqual(self.pointer.position[1], initial[1])

    def test_opening_context_does_not_interrupt_an_already_armed_pointer(self):
        self.pointer.close_context()
        self.update()
        self.update(left=(1, 0), now=.05)
        initial = self.pointer.position
        self.pointer.open_context(OPTIONS)
        self.assertTrue(self.update(left=(1, 0), now=.10)[0])
        self.assertGreater(self.pointer.position[0], initial[0])
        self.assertLessEqual(self.pointer.position[0], initial[0] + 45)
        self.assertEqual(self.pointer.position[1], initial[1])

    def test_pointer_hit_testing_excludes_center_and_outside_and_maps_all_cardinals(self):
        x, y = self.pointer.context.center
        for dx, dy, direction in ((0, -70, 'up'), (70, 0, 'right'),
                                  (0, 70, 'down'), (-70, 0, 'left')):
            self.assertEqual(self.pointer.direction_at(x + dx, y + dy), direction)
        self.assertIsNone(self.pointer.direction_at(x, y))
        self.assertIsNone(self.pointer.direction_at(x + 25, y))
        self.assertEqual(self.pointer.direction_at(x + 84, y), 'right')
        self.assertIsNone(self.pointer.direction_at(x + 84.01, y))
        self.assertIsNone(self.pointer.direction_at(float('nan'), y))

    def test_pointer_hit_testing_never_selects_an_absent_option(self):
        self.pointer.open_context({'up': OPTIONS['up']})
        x, y = self.pointer.context.center
        self.assertIsNone(self.pointer.direction_at(x + 70, y))
        self.assertEqual(self.pointer.choose(self.pointer.direction_at(x, y - 70)), 'open')
        self.assertIsNone(self.pointer.direction_at(x, y - 70))

    def test_context_center_keeps_menu_and_outline_on_screen(self):
        self.pointer.open_context(OPTIONS, center=(0, 0))
        self.assertEqual(self.pointer.context.center, (86, 86))
        self.assertEqual(self.pointer.context.radius, 84)
        self.pointer.open_context(OPTIONS, center=(640, 480))
        self.assertEqual(self.pointer.context.center, (553, 393))
        self.assertEqual(self.pointer.position, (320, 240))

    def test_small_viewport_exposes_reduced_radius_without_imposing_hardware_minimum(self):
        pointer = PointerController(width=100, height=80)
        pointer.open_context(OPTIONS, center=(0, 0))
        self.assertEqual(pointer.context.center, (39.5, 39.5))
        self.assertEqual(pointer.context.radius, 37.5)

    def test_options_are_copied_so_caller_mutation_cannot_change_pending_action(self):
        options = {'up': dict(id='original', label='Original')}
        self.pointer.open_context(options)
        options['up']['id'] = 'changed'
        self.assertEqual(self.pointer.choose('up'), 'original')

    def test_invalid_options_do_not_replace_existing_context(self):
        original = self.pointer.context
        for options in ({'diagonal': OPTIONS['up']}, {'up': {}}, {'up': dict(id='', label='Bad')}, None):
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    self.pointer.open_context(options)
                self.assertIs(self.pointer.context, original)

    def test_angular_jitter_near_cardinal_boundary_keeps_highlight_stable(self):
        def position(degrees):
            angle = math.radians(degrees)
            return math.cos(angle), math.sin(angle)
        self.update()
        self.update(right=position(44))
        for degrees in (46, 44, 48, 43, 47):
            self.assertFalse(self.update(right=position(degrees))[0])
            self.assertEqual(self.pointer.context.highlight, 'right')
        self.assertTrue(self.update(right=position(54))[0])
        self.assertEqual(self.pointer.context.highlight, 'down')
        self.assertEqual(self.update(), (True, 'home'))


if __name__ == '__main__':
    unittest.main()
