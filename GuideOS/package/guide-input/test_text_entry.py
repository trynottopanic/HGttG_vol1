"""Contract tests for editing and owner-bound text delivery."""

import unittest

from guide_text_entry import (
    TextEntryBusy, TextEntryManager, TextOwnershipError, TextRequest,
    TextSession, TextValidationError,
)


def request(**overrides):
    values = dict(owner_id="reader:instance-1", field_id="search", label="Search")
    values.update(overrides)
    return TextRequest(**values)


class EditingTests(unittest.TestCase):
    def test_submission_captures_caret_before_clearing_buffer(self):
        session=TextSession(request(initial='hello'))
        session.move(-3);session.submit()
        result=session.take_result(session.request.owner_id,session.token)
        self.assertEqual((result.text,result.cursor),('hello',2))
        self.assertEqual((session.text,session.cursor),('',0))

    def test_insert_at_cursor_backspace_and_delete_are_distinct(self):
        session = TextSession(request(initial="ac"))
        session.move(-1)
        self.assertTrue(session.insert("b"))
        self.assertEqual((session.text, session.cursor), ("abc", 2))
        session.backspace()
        self.assertEqual((session.text, session.cursor), ("ac", 1))
        session.delete()
        self.assertEqual((session.text, session.cursor), ("a", 1))

    def test_cursor_clamps_and_endpoints_do_not_destroy_text(self):
        session = TextSession(request(initial="test"))
        session.move(-100)
        self.assertEqual(session.cursor, 0)
        self.assertFalse(session.backspace())
        session.end()
        self.assertEqual(session.cursor, 4)
        self.assertFalse(session.delete())
        session.move(100)
        self.assertEqual(session.text, "test")
        session.home()
        self.assertEqual(session.cursor, 0)

    def test_rejected_paste_is_atomic_and_error_can_be_corrected(self):
        session = TextSession(request(initial="ab", max_length=3))
        session.home()
        self.assertFalse(session.insert("cd"))
        self.assertEqual((session.text, session.cursor), ("ab", 0))
        self.assertIsNotNone(session.error)
        self.assertTrue(session.insert("c"))
        self.assertEqual(session.text, "cab")
        self.assertIsNone(session.error)

    def test_utf8_limit_counts_bytes_separately_from_codepoints(self):
        session = TextSession(request(max_length=4, max_bytes=5))
        self.assertTrue(session.insert("é€"))
        self.assertEqual(session.cursor, 2)
        self.assertFalse(session.insert("a"))
        self.assertEqual(session.text, "é€")
        session.backspace()
        self.assertTrue(session.insert("a"))

    def test_exact_unicode_including_combining_characters_is_preserved(self):
        entered = "e\u0301 \u00e9 👩\u200d💻"
        session = TextSession(request(secret=True))
        session.insert(entered)
        session.submit()
        result = session.take_result(session.request.owner_id, session.token)
        self.assertEqual(result.text, entered)
        self.assertNotEqual(result.text[:2], "é")

    def test_single_line_rejects_controls_and_unicode_line_separators(self):
        for value in ("a\nb", "\t", "\r", "\x00", "\x1b", "\x7f", "\x85", "\u2028", "\u2029"):
            with self.subTest(value=repr(value)):
                session = TextSession(request(initial="safe"))
                self.assertFalse(session.insert(value))
                self.assertEqual(session.text, "safe")

    def test_multiline_accepts_newline_tab_but_not_other_controls(self):
        session = TextSession(request(multiline=True))
        self.assertTrue(session.insert("line\n\tsecond"))
        for value in ("\r", "\x00", "\x1b", "\ud800"):
            self.assertFalse(session.insert(value))
        self.assertEqual(session.text, "line\n\tsecond")

    def test_allowed_characters_apply_to_entire_paste(self):
        session = TextSession(request(allowed_characters="0123456789"))
        self.assertTrue(session.insert("12"))
        self.assertFalse(session.insert("3a"))
        self.assertEqual(session.text, "12")
        self.assertIsNotNone(session.error)

    def test_minimum_is_checked_on_submission_not_while_editing(self):
        session = TextSession(request(min_length=3))
        self.assertTrue(session.insert("ab"))
        self.assertFalse(session.submit())
        self.assertEqual(session.state, "editing")
        self.assertEqual(session.text, "ab")
        session.insert("c")
        self.assertTrue(session.submit())

    def test_empty_submission_is_distinct_from_cancel(self):
        submitted = TextSession(request())
        submitted.submit()
        accepted = submitted.take_result(submitted.request.owner_id, submitted.token)
        cancelled = TextSession(request(initial="draft"))
        cancelled.cancel()
        rejected = cancelled.take_result(cancelled.request.owner_id, cancelled.token)
        self.assertEqual((accepted.state, accepted.text), ("submitted", ""))
        self.assertEqual((rejected.state, rejected.text), ("cancelled", None))

    def test_invalid_request_does_not_silently_truncate_initial_text(self):
        invalid = (
            dict(initial="long", max_length=3), dict(initial="\x00"),
            dict(initial="é", max_bytes=1), dict(min_length=4, max_length=3),
            dict(max_length=True), dict(max_bytes=-1), dict(initial=12),
            dict(initial="a", allowed_characters="012"), dict(owner_id=""),
            dict(secret=1), dict(label="two\nlines"),
        )
        for overrides in invalid:
            with self.subTest(overrides=overrides):
                with self.assertRaises(TextValidationError):
                    request(**overrides)

    def test_zero_length_field_can_submit_but_cannot_insert(self):
        session = TextSession(request(max_length=0, max_bytes=0))
        self.assertFalse(session.insert("x"))
        self.assertTrue(session.submit())

    def test_invalid_insert_type_preserves_text(self):
        session = TextSession(request(initial="safe"))
        self.assertFalse(session.insert(None))
        self.assertEqual(session.text, "safe")


class CompletionAndSecretTests(unittest.TestCase):
    def test_secret_display_and_representations_never_contain_value(self):
        secret = "Unusual-s3cret-phrase"
        original = request(secret=True, initial=secret)
        session = TextSession(original)
        self.assertEqual(session.display_text(), "•" * len(secret))
        self.assertNotIn(secret, repr(original))
        self.assertNotIn(secret, repr(session))
        self.assertEqual(session.request.initial, "")
        session.submit()
        self.assertEqual(session.text, "")
        self.assertEqual(session.cursor, 0)
        result = session.take_result(original.owner_id, session.token)
        self.assertNotIn(secret, repr(result))
        self.assertEqual(result.text, secret)

    def test_cancel_clears_draft_and_never_returns_it(self):
        session = TextSession(request(secret=True, initial="cancelled-secret"))
        session.cancel()
        result = session.take_result(session.request.owner_id, session.token)
        self.assertIsNone(result.text)
        self.assertEqual(session.text, "")
        self.assertEqual(session.display_text(), "")

    def test_results_are_delivered_once_only_to_original_owner_and_token(self):
        session = TextSession(request(initial="result"))
        session.submit()
        for owner, token in (("other-owner", session.token), (session.request.owner_id, "old-token")):
            with self.assertRaises(TextOwnershipError):
                session.take_result(owner, token)
        result = session.take_result(session.request.owner_id, session.token)
        self.assertEqual(result.text, "result")
        self.assertIsNone(session.take_result(session.request.owner_id, session.token))

    def test_terminal_session_cannot_edit_or_replace_result(self):
        session = TextSession(request(initial="accepted"))
        session.submit()
        for action in (lambda: session.insert("oops"), session.backspace,
                       session.delete, session.home, session.end,
                       session.submit, session.cancel):
            self.assertFalse(action())
        self.assertEqual(session.take_result(session.request.owner_id, session.token).text,
                         "accepted")

    def test_teardown_discards_submitted_but_unconsumed_secret(self):
        session = TextSession(request(secret=True, initial="pending-secret"))
        session.submit()
        session.teardown()
        self.assertEqual((session.text, session.cursor, session.state), ("", 0, "cancelled"))
        self.assertIsNone(session.take_result(session.request.owner_id, session.token))


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.manager = TextEntryManager()
        self.session = self.manager.open(request())
        self.owner = self.session.request.owner_id
        self.token = self.session.token

    def test_unconsumed_entry_cannot_be_replaced(self):
        with self.assertRaises(TextEntryBusy):
            self.manager.open(request(field_id="different"))
        self.manager.dispatch(self.owner, self.token, "submit")
        with self.assertRaises(TextEntryBusy):
            self.manager.open(request(field_id="different"))
        self.manager.take_result(self.owner, self.token)
        self.assertIsNotNone(self.manager.open(request(field_id="different")))

    def test_different_owner_or_generation_cannot_inject_or_take_text(self):
        for owner, token in (("other", self.token), (self.owner, "old")):
            with self.assertRaises(TextOwnershipError):
                self.manager.dispatch(owner, token, "insert", "injected")
            with self.assertRaises(TextOwnershipError):
                self.manager.take_result(owner, token)
        self.assertEqual(self.session.text, "")

    def test_stale_input_cannot_replay_into_reopened_same_field(self):
        self.manager.dispatch(self.owner, self.token, "cancel")
        self.manager.take_result(self.owner, self.token)
        replacement = self.manager.open(request())
        self.assertNotEqual(replacement.token, self.token)
        with self.assertRaises(TextOwnershipError):
            self.manager.dispatch(self.owner, self.token, "insert", "stale")
        self.assertEqual(replacement.text, "")

    def test_editing_result_is_not_ready_and_does_not_release_focus(self):
        self.assertIsNone(self.manager.take_result(self.owner, self.token))
        self.assertIs(self.manager.active, self.session)

    def test_owner_exit_releases_focus_and_returns_no_draft(self):
        self.session.insert("unfinished")
        result = self.manager.cancel_owner(self.owner)
        self.assertEqual((result.state, result.reason, result.text),
                         ("cancelled", "owner-exit", None))
        self.assertIsNone(self.manager.active)
        self.assertEqual(self.session.text, "")
        with self.assertRaises(TextOwnershipError):
            self.manager.dispatch(self.owner, self.token, "insert", "late")

    def test_focus_loss_revokes_even_submitted_pending_result(self):
        self.session.insert("pending")
        self.session.submit()
        result = self.manager.focus_lost(self.owner)
        self.assertEqual((result.state, result.reason, result.text),
                         ("cancelled", "focus-lost", None))
        self.assertIsNone(self.session.take_result(self.owner, self.token))
        self.assertIsNone(self.manager.active)

    def test_other_owner_exit_does_not_cancel_current_input(self):
        self.assertIsNone(self.manager.cancel_owner("some-other-app"))
        self.assertIs(self.manager.active, self.session)

    def test_teardown_discards_all_state_and_old_routes(self):
        self.session.insert("draft")
        self.manager.teardown()
        self.assertIsNone(self.manager.active)
        self.assertEqual(self.session.text, "")
        with self.assertRaises(TextOwnershipError):
            self.manager.take_result(self.owner, self.token)

    def test_semantic_dispatch_edits_and_completes(self):
        for action, value in (("insert", "abcd"), ("left", None),
                              ("backspace", None), ("delete", None),
                              ("home", None), ("right", None),
                              ("insert", "Z"), ("end", None), ("submit", None)):
            self.manager.dispatch(self.owner, self.token, action, value)
        self.assertEqual(self.manager.take_result(self.owner, self.token).text, "aZb")
        self.assertIsNone(self.manager.active)


if __name__ == "__main__":
    unittest.main()
