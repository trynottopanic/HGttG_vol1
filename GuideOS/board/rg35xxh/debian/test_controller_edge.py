"""Regression cases from the pre-flash diagnostic edge review.

Run on Linux alongside test_controller.py. These assert intended behavior;
the first three reproduced defects in the original reviewed implementation.
"""
import unittest
from unittest.mock import patch

import test_controller as base

m = base.m


class EdgeCaseTests(unittest.TestCase):
    def session(self, schedule):
        return base.GuidedWorkflowTests().setup_session(schedule)

    def test_combination_preserves_tap_inside_one_poll_batch(self):
        test, clock = self.session([
            (0.8, 1, 310, 1),
            (0.901, 1, 305, 1), (0.909, 1, 305, 0),
            (1.3, 1, 310, 0),
        ])
        test.mapping = {'L1': [0, 310], 'A': [0, 305]}
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]):
            test.combination('L1', 'A', 'L1 + A')
        self.assertEqual(test.results[-1]['outcome'], 'complete')

    def test_axis_rejects_second_axis_after_first_is_selected(self):
        test, clock = self.session([
            (0.8, 3, 0, 1800), (1.0, 3, 1, 1800), (1.5, 3, 0, 0),
        ])
        test.inputs.devices[0].axes[1] = dict(
            value=0, minimum=-1800, maximum=1800, center=0, flat=32)
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]):
            result = test.discover_axis('LEFT STICK', 'right')
        self.assertIsNone(result)
        self.assertEqual(test.results[-1]['outcome'], 'ambiguous')

    def test_choice_does_not_confirm_batch_with_event_loss(self):
        test, clock = self.session([(0.8, 1, 304, 1)])
        test.mapping = {'A': [0, 304], 'B': [0, 305]}
        original_poll = test.inputs.poll

        def lossy_poll():
            events = original_poll()
            if events:
                test.inputs.generation += 1
            return events

        test.inputs.poll = lossy_poll
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]):
            result = test.choice('RUMBLE', 'Run a brief pulse?')
        self.assertIsNot(result, True)

    def timed_session(self, batches):
        test, clock = self.session([])
        test.neutral = lambda *args, **kwargs: True
        test.mapping = {'A': [0, 304]}

        def poll():
            clock[0] += .05
            if not batches:
                return []
            delivered, values = batches.pop(0)
            clock[0] = max(clock[0], delivered)
            return [m.TimedEvent((0, m.EV_KEY, 304, value), stamp)
                    for stamp, value in values]

        test.inputs.poll = poll
        return test, clock

    def test_hold_uses_kernel_duration_when_all_events_arrive_together(self):
        test, clock = self.timed_session([
            (3.0, [(0.8, 1), (2.0, 0), (2.2, 1), (2.3, 0)])])
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]):
            self.assertTrue(test.button('A', True))
        self.assertEqual(test.results[-1]['transitions'],
                         [[0.8, 1], [2.0, 0], [2.2, 1], [2.3, 0]])

    def test_processing_delay_does_not_turn_short_tap_into_hold(self):
        test, clock = self.timed_session([
            (1.0, [(0.8, 1)]), (2.5, [(0.9, 0)]),
            (3.0, [(1.2, 1), (1.3, 0)])])
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]):
            self.assertFalse(test.button('A', True))
        self.assertEqual(test.results[-1]['outcome'], 'not observed')

    def test_one_tap_with_duplicate_edges_is_not_two_confirmations(self):
        trial = m.ButtonTrial(required_taps=2)
        for stamp, value in [(1, 1), (1.1, 1), (1.2, 2), (1.3, 0), (1.4, 0)]:
            trial.event((0, 304), value, stamp)
        self.assertFalse(trial.complete)
        self.assertEqual(trial.taps, 1)
        trial.event((0, 304), 1, 2)
        trial.event((0, 304), 0, 2.1)
        self.assertTrue(trial.complete)

    def test_discovery_accepts_two_valid_taps_in_single_poll(self):
        test, clock = self.timed_session([
            (3.0, [(0.8, 1), (1.0, 0), (1.2, 1), (1.4, 0)])])
        test.mapping = {}
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]):
            self.assertTrue(test.button('A'))
        self.assertEqual(test.mapping['A'], [0, 304])

    def test_other_control_cannot_supply_second_confirmation(self):
        trial = m.ButtonTrial(required_taps=2)
        trial.event((0, 304), 1, 1)
        trial.event((0, 304), 0, 1.1)
        trial.event((0, 305), 1, 1.2)
        trial.event((0, 305), 0, 1.3)
        self.assertFalse(trial.complete)
        self.assertTrue(trial.ambiguous)


if __name__ == '__main__':
    unittest.main()
