import unittest

from windows_ui_performance import MovementGovernor


class MovementGovernorTests(unittest.TestCase):
    def test_commits_first_position_at_live_pointer(self):
        governor = MovementGovernor(60)
        governor.begin(1.0)
        decision = governor.decide(
            proposed_left=10, proposed_top=20,
            current_left=10, current_top=20,
            cursor_x=150, cursor_y=170, offset_x=30, offset_y=40,
            now=1.0,
        )
        self.assertTrue(decision.commit)
        self.assertEqual((decision.left, decision.top), (120, 130))
        self.assertGreater(decision.pointer_lag_px, 100)
        self.assertEqual(decision.governed_lag_px, 0.0)

    def test_suppresses_updates_inside_display_frame(self):
        governor = MovementGovernor(60)
        governor.begin(1.0)
        governor.decide(
            proposed_left=0, proposed_top=0, current_left=0, current_top=0,
            cursor_x=10, cursor_y=10, offset_x=0, offset_y=0, now=1.0)
        decision = governor.decide(
            proposed_left=1, proposed_top=1, current_left=10, current_top=10,
            cursor_x=20, cursor_y=20, offset_x=0, offset_y=0, now=1.001)
        self.assertFalse(decision.commit)
        self.assertEqual((decision.left, decision.top), (10, 10))
        self.assertGreater(decision.governed_lag_px, 10)
        self.assertEqual(governor.committed, 1)
        self.assertEqual(governor.suppressed, 1)

    def test_allows_next_display_frame(self):
        governor = MovementGovernor(100)
        governor.begin(1.0)
        governor.decide(
            proposed_left=0, proposed_top=0, current_left=0, current_top=0,
            cursor_x=10, cursor_y=10, offset_x=0, offset_y=0, now=1.0)
        decision = governor.decide(
            proposed_left=10, proposed_top=10, current_left=10, current_top=10,
            cursor_x=20, cursor_y=20, offset_x=0, offset_y=0, now=1.011)
        self.assertTrue(decision.commit)
        self.assertEqual((decision.left, decision.top), (20, 20))


if __name__ == "__main__":
    unittest.main()
