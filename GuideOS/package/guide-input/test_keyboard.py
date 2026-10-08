"""Controller acceptance against the real reusable editor, without Wi-Fi."""
import string
import unittest

from guide_keyboard import Keyboard
from guide_text_entry import TextEntryBusy, TextEntryManager, TextOwnershipError, TextRequest


class KeyboardTests(unittest.TestCase):
    def make_keyboard(self, **changes):
        values = dict(owner_id='ordinary.example', field_id='title', label='Title')
        values.update(changes)
        return Keyboard(TextEntryManager(), TextRequest(**values))

    def activate(self, keyboard, action, value=None):
        for row, keys in enumerate(keyboard.rows):
            for column, key in enumerate(keys):
                if key.action == action and (value is None or key.value == value) and key.enabled:
                    keyboard.focus = (row, column)
                    return keyboard.handle('activate')
        self.fail('No enabled key for ' + action)

    def reachable(self, keyboard):
        keyboard._repair_focus()
        reached, pending = {keyboard.focus}, [keyboard.focus]
        while pending:
            current = pending.pop()
            for action in ('up', 'down', 'left', 'right'):
                keyboard.focus = current
                keyboard.handle(action)
                row, column = keyboard.focus
                self.assertTrue(keyboard.rows[row][column].enabled)
                if keyboard.focus not in reached:
                    reached.add(keyboard.focus)
                    pending.append(keyboard.focus)
        return reached

    def test_shoulder_layers_preserve_draft_caret_and_letter_case(self):
        keyboard = self.make_keyboard(initial='draft')
        keyboard.handle('case')
        keyboard.handle('home')
        for action in ('next-layer', 'previous-layer'):
            keyboard.handle(action)
            self.assertEqual(keyboard.page, 2)
            self.assertEqual(''.join(key.value for key in keyboard.rows[0]), '1234567890')
            self.assertEqual((keyboard.session.text, keyboard.session.cursor), ('draft', 0))
            keyboard.handle(action)
            self.assertEqual(keyboard.page, 1)
        for value in (0, 2):
            self.assertFalse(keyboard.handle('next-layer', value=value))
        self.assertEqual(keyboard.page, 1)

    def test_numeric_layer_keeps_confirm_cancel_and_editing_controls(self):
        keyboard = self.make_keyboard()
        keyboard.handle('next-layer')
        actions = {key.action for row in keyboard.rows for key in row if key.enabled}
        self.assertTrue({'submit', 'cancel', 'backspace', 'delete', 'home', 'end'} <= actions)
        values = {key.value for row in keyboard.rows for key in row if key.enabled and key.action == 'insert'}
        self.assertTrue(set(string.digits + string.punctuation) <= values)

    def test_all_supported_controller_characters_are_available(self):
        keyboard = self.make_keyboard()
        characters = set()
        for page in range(3):
            keyboard.page = page
            for row in keyboard.rows:
                characters.update(key.value for key in row if key.enabled and key.action == 'insert')
        self.assertEqual(characters, set(string.printable[:95]))

    def test_navigation_reaches_every_enabled_key_on_each_page(self):
        keyboard = self.make_keyboard(multiline=True)
        for page in range(3):
            keyboard.page = page
            expected = {(r, c) for r, keys in enumerate(keyboard.rows)
                        for c, key in enumerate(keys) if key.enabled}
            self.assertEqual(self.reachable(keyboard), expected)

    def test_numeric_field_skips_disabled_characters_and_starts_on_digits(self):
        keyboard = self.make_keyboard(purpose='number', allowed_characters=string.digits,
                                      max_length=4)
        self.assertEqual(keyboard.focus, (3, 0))
        for page in range(3):
            keyboard.page = page
            expected = {(r, c) for r, keys in enumerate(keyboard.rows)
                        for c, key in enumerate(keys) if key.enabled}
            self.assertEqual(self.reachable(keyboard), expected)
        keyboard.handle('insert', text='A')
        self.assertEqual(keyboard.session.text, '')
        self.assertIsNotNone(keyboard.session.error)

    def test_ordinary_title_mid_string_edit_and_explicit_commit(self):
        keyboard = self.make_keyboard(initial='cat', submit_label='SAVE TITLE')
        self.activate(keyboard, 'home')
        self.activate(keyboard, 'right')
        self.activate(keyboard, 'insert', 'o')
        self.activate(keyboard, 'delete')
        self.assertEqual(keyboard.session.text, 'cot')
        self.activate(keyboard, 'end')
        self.activate(keyboard, 'backspace')
        keyboard.handle('insert', text='de')
        self.assertEqual(keyboard.session.text, 'code')
        self.assertEqual(keyboard.session.state, 'editing')
        self.activate(keyboard, 'submit')
        result = keyboard.take_result()
        self.assertEqual((result.owner_id, result.field_id, result.state, result.text),
                         ('ordinary.example', 'title', 'submitted', 'code'))
        self.assertIsNone(keyboard.manager.active)
        self.assertFalse(keyboard.handle('activate'))

    def test_multiline_field_uses_same_controller_and_core(self):
        keyboard = self.make_keyboard(initial='first', multiline=True, submit_label='KEEP')
        self.activate(keyboard, 'insert', '\n')
        keyboard.handle('insert', text='second')
        self.activate(keyboard, 'home')
        keyboard.handle('insert', text='A ')
        self.activate(keyboard, 'end')
        self.activate(keyboard, 'submit')
        self.assertEqual(keyboard.take_result().text, 'A first\nsecond')

    def test_single_line_field_rejects_newline_from_another_input_adapter(self):
        keyboard = self.make_keyboard(initial='one line')
        self.assertFalse(any(key.enabled and key.value == '\n'
                             for row in keyboard.rows for key in row))
        keyboard.handle('insert', text='\nsecond')
        self.assertEqual(keyboard.session.text, 'one line')
        self.assertIsNotNone(keyboard.session.error)

    def test_release_and_repeat_do_not_type_or_submit(self):
        keyboard = self.make_keyboard()
        for value in (0, 2):
            self.assertFalse(keyboard.handle('activate', value=value))
        self.assertEqual(keyboard.session.text, '')
        keyboard.handle('activate')
        keyboard.handle('activate', value=2)
        self.assertEqual(keyboard.session.text, 'q')
        keyboard.focus = (4, 4)
        keyboard.handle('activate', value=2)
        self.assertEqual(keyboard.session.state, 'editing')
        keyboard.handle('activate')
        keyboard.handle('activate', value=2)
        self.assertEqual(keyboard.take_result().text, 'q')

    def test_page_changes_and_character_limit_never_submit(self):
        keyboard = self.make_keyboard(max_length=2)
        keyboard.handle('insert', text='aA')
        for action in ('case', 'more', 'case'):
            self.activate(keyboard, action)
            self.assertEqual(keyboard.session.text, 'aA')
        keyboard.handle('insert', text='z')
        self.assertEqual(keyboard.session.text, 'aA')
        self.assertEqual(keyboard.session.state, 'editing')
        self.assertIsNotNone(keyboard.session.error)

    def test_failed_validation_allows_correction_before_commit(self):
        keyboard = self.make_keyboard(min_length=3)
        keyboard.handle('insert', text='ab')
        self.activate(keyboard, 'submit')
        self.assertEqual(keyboard.session.state, 'editing')
        self.assertIsNotNone(keyboard.session.error)
        self.assertIsNone(keyboard.take_result())
        keyboard.handle('insert', text='c')
        self.activate(keyboard, 'submit')
        self.assertEqual(keyboard.take_result().text, 'abc')

    def test_cancel_does_not_replace_the_callers_committed_value(self):
        current_title = 'Original title'
        keyboard = self.make_keyboard(initial=current_title)
        keyboard.handle('insert', text=' edited')
        self.activate(keyboard, 'cancel')
        result = keyboard.take_result()
        if result.state == 'submitted':
            current_title = result.text
        self.assertEqual(current_title, 'Original title')
        self.assertIsNone(result.text)
        self.assertEqual(keyboard.session.text, '')

    def test_old_keyboard_close_cannot_cancel_owners_new_session(self):
        manager = TextEntryManager()
        request = TextRequest('same.owner', 'field', 'Title')
        old = Keyboard(manager, request)
        old.handle('cancel')
        old.take_result()
        new = Keyboard(manager, request)
        new.handle('insert', text='new draft')
        old.close()
        self.assertIs(manager.active, new.session)
        self.assertEqual(new.session.text, 'new draft')

    def test_another_keyboard_cannot_take_existing_focus(self):
        keyboard = self.make_keyboard(initial='kept draft')
        with self.assertRaises(TextEntryBusy):
            Keyboard(keyboard.manager, TextRequest('other.owner', 'field', 'Other'))
        self.assertIs(keyboard.manager.active, keyboard.session)
        self.assertEqual(keyboard.session.text, 'kept draft')

    def test_closing_a_submitted_but_unconsumed_secret_revokes_result(self):
        keyboard = self.make_keyboard(secret=True, initial='private-secret')
        keyboard.handle('submit')
        keyboard.close('owner-exit')
        self.assertIsNone(keyboard.manager.active)
        self.assertEqual(keyboard.session.text, '')
        self.assertIsNone(keyboard.session.take_result(
            keyboard.session.request.owner_id, keyboard.session.token))

    def test_unicode_text_is_preserved_by_the_generic_adapter(self):
        keyboard = self.make_keyboard(max_length=40)
        text = 'Caf\u00e9 e\u0301 \u03b1\u03b2'
        keyboard.handle('insert', text=text)
        self.activate(keyboard, 'submit')
        self.assertEqual(keyboard.take_result().text, text)

    def test_neighbor_geometry_uses_grid_columns_and_wider_action_centers(self):
        keyboard = self.make_keyboard()
        keyboard.focus = (1, 4)  # G, directly below T and above B.
        self.assertEqual(keyboard.neighbors, {
            (-1, -1): (0, 3), (0, -1): (0, 4), (1, -1): (0, 5),
            (-1, 0): (1, 3), (1, 0): (1, 5),
            (-1, 1): (2, 3), (0, 1): (2, 4), (1, 1): (2, 5)})
        keyboard.focus = (3, 5)  # 6, above the wider DEL action.
        self.assertEqual(keyboard.neighbors[0, 1], (4, 3))
        self.assertEqual(keyboard.neighbors[-1, 1], (4, 2))
        self.assertEqual(keyboard.neighbors[1, 1], (4, 4))
        keyboard.focus = (4, 3)
        self.assertEqual(keyboard.neighbors[0, -1], (3, 5))
        keyboard.focus = (0, 9)  # P, with an empty grid cell below it.
        self.assertNotIn((0, 1), keyboard.neighbors)
        self.assertEqual(keyboard.neighbors[-1, 1], (1, 8))

    def test_neighbors_never_wrap_or_skip_disabled_immediate_keys(self):
        keyboard = self.make_keyboard()
        self.assertEqual(keyboard.neighbors, {(1, 0): (0, 1), (0, 1): (1, 0), (1, 1): (1, 1)})
        keyboard.focus = (5, 4)
        self.assertNotIn((1, 0), keyboard.neighbors)  # Disabled single-line NEWLINE.
        self.assertFalse(any(dy == 1 for dx, dy in keyboard.neighbors))
        constrained = self.make_keyboard(allowed_characters='qs')
        self.assertEqual(constrained.neighbors, {(1, 1): (1, 1)})
        self.assertFalse(constrained.activate_neighbor(1, 0))
        self.assertFalse(constrained.activate_neighbor(0, 1))
        self.assertEqual(constrained.session.text, '')

    def test_neighbor_targets_are_unique_enabled_and_local_for_every_key(self):
        keyboard = self.make_keyboard(multiline=True)
        for page in range(3):
            keyboard.page = page
            for row, keys in enumerate(keyboard.rows):
                for column, key in enumerate(keys):
                    keyboard.focus = (row, column)
                    targets = list(keyboard.neighbors.values())
                    self.assertEqual(len(targets), len(set(targets)))
                    self.assertNotIn(keyboard.focus, targets)
                    self.assertLessEqual(len(targets), 8)
                    for target_row, target_column in targets:
                        self.assertTrue(keyboard.rows[target_row][target_column].enabled)
                        self.assertLessEqual(abs(target_row - row), 1)
                        if target_row == row:
                            self.assertEqual(abs(target_column - column), 1)

    def test_neighbor_character_activation_keeps_primary_selection(self):
        keyboard = self.make_keyboard()
        keyboard.focus = (1, 4)
        expected = ''.join(keyboard.rows[row][column].value
                           for row, column in keyboard.neighbors.values())
        for direction in tuple(keyboard.neighbors):
            self.assertTrue(keyboard.activate_neighbor(*direction))
            self.assertEqual(keyboard.focus, (1, 4))
        self.assertEqual(keyboard.session.text, expected)

    def test_neighbor_actions_share_case_symbol_edit_and_submit_semantics(self):
        keyboard = self.make_keyboard(initial='abc')
        keyboard.focus = (4, 1)  # MORE, adjacent to CASE and SPACE.
        keyboard.activate_neighbor(-1, 0)
        self.assertEqual((keyboard.page, keyboard.focus, keyboard.session.text), (1, (4, 1), 'abc'))
        keyboard.activate_neighbor(1, 0)
        self.assertEqual(keyboard.session.text, 'abc ')
        keyboard.focus = (4, 0)
        keyboard.activate_neighbor(1, 0)
        self.assertEqual((keyboard.page, keyboard.focus), (2, (4, 0)))
        keyboard.focus = (4, 2)  # SPACE, adjacent to backward DEL.
        keyboard.activate_neighbor(1, 0)
        self.assertEqual((keyboard.session.text, keyboard.focus), ('abc', (4, 2)))
        keyboard.focus = (4, 3)  # DEL, adjacent to submit.
        keyboard.activate_neighbor(1, 0)
        self.assertEqual(keyboard.session.state, 'submitted')
        self.assertEqual(keyboard.focus, (4, 3))
        self.assertFalse(keyboard.activate_neighbor(1, 0))
        self.assertEqual(keyboard.take_result().text, 'abc')

    def test_neighbor_cancel_and_failed_submission_do_not_change_primary_focus(self):
        keyboard = self.make_keyboard(min_length=3, initial='a')
        keyboard.focus = (4, 3)
        keyboard.activate_neighbor(1, 0)
        self.assertEqual((keyboard.session.state, keyboard.focus), ('editing', (4, 3)))
        self.assertIsNotNone(keyboard.session.error)
        keyboard.focus = (4, 4)
        keyboard.activate_neighbor(1, 0)
        self.assertEqual((keyboard.session.state, keyboard.focus), ('cancelled', (4, 4)))
        self.assertIsNone(keyboard.take_result().text)

    def test_stick_cardinals_keep_dpad_traversal_and_diagonal_changes_focus_once(self):
        class ObservedKeyboard(Keyboard):
            def __setattr__(self, name, value):
                if name == 'focus' and hasattr(self, 'focus_changes'):
                    self.focus_changes.append(value)
                super().__setattr__(name, value)
        keyboard = ObservedKeyboard(TextEntryManager(), TextRequest('example', 'field', 'Text'))
        for direction, action in (((-1, 0), 'left'), ((1, 0), 'right'), ((0, -1), 'up'), ((0, 1), 'down')):
            keyboard.focus = (0, 0)
            keyboard.handle(action)
            expected = keyboard.focus
            keyboard.focus = (0, 0)
            keyboard.move_selection(*direction)
            self.assertEqual(keyboard.focus, expected)
        keyboard.focus = (0, 0)
        keyboard.focus_changes = []
        keyboard.move_selection(1, 1)
        self.assertEqual(keyboard.focus_changes, [(1, 1)])

    def test_stick_entry_points_obey_session_ownership_and_terminal_state(self):
        keyboard = self.make_keyboard()
        for method in (keyboard.move_selection, keyboard.activate_neighbor):
            self.assertFalse(method(0, 0))
            with self.assertRaises(ValueError):
                method(2, 1)
        keyboard.manager._active = None  # Simulate a stale route after focus replacement.
        for method in (keyboard.move_selection, keyboard.activate_neighbor):
            with self.assertRaises(TextOwnershipError):
                method(1, 0)
        keyboard.session.teardown()
        self.assertEqual(keyboard.neighbors, {})
        self.assertFalse(keyboard.move_selection(1, 0))
        self.assertFalse(keyboard.activate_neighbor(1, 0))


if __name__ == '__main__':
    unittest.main()
