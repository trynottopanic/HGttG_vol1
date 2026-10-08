from __future__ import annotations

import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

NODE_LINK = Path(__file__).resolve().parents[1] / "node_link"
sys.path.insert(0, str(NODE_LINK))

import guide_se_deck


class FakeClient:
    def __init__(self) -> None:
        self.cancelled = ""

    def capabilities(self) -> dict:
        return {"capabilities": [{"id": "semiotic.text", "available": True,
                                  "state": "ready", "reason": ""}]}

    def semiotic_submit(self, text: str) -> dict:
        if not text:
            raise AssertionError("text must be supplied")
        return {"job_id": "ab" * 16, "state": "queued"}

    def semiotic_job(self, job_id: str) -> dict:
        if job_id != "ab" * 16:
            raise AssertionError("wrong job")
        return {"state": "complete", "result": {"text": "A bounded summary."},
                "uncertainty": "Verify important claims.", "proposed_actions": []}

    def semiotic_cancel(self, job_id: str) -> dict:
        self.cancelled = job_id
        return {"state": "cancelled"}


class DeckAdapterTests(unittest.TestCase):
    def test_status_is_bounded_line_protocol(self) -> None:
        output = io.StringIO()
        with mock.patch.object(guide_se_deck, "session_client", return_value=FakeClient()), \
                contextlib.redirect_stdout(output):
            self.assertEqual(guide_se_deck.status(), 0)
        self.assertEqual(output.getvalue().splitlines()[:2],
                         ["GUIDE-SE-STATUS-1", "READY=YES"])

    def test_summary_uses_only_fixed_volatile_files(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            input_path = root / "input.txt"
            summary_path = root / "summary.txt"
            uncertainty_path = root / "uncertainty.txt"
            input_path.write_text("Selected context.", encoding="utf-8")
            output = io.StringIO()
            with mock.patch.object(guide_se_deck, "INPUT_FILE", input_path), \
                    mock.patch.object(guide_se_deck, "SUMMARY_FILE", summary_path), \
                    mock.patch.object(guide_se_deck, "UNCERTAINTY_FILE", uncertainty_path), \
                    mock.patch.object(guide_se_deck, "session_client", return_value=FakeClient()), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(guide_se_deck.summarize(str(input_path)), 0)
            self.assertEqual(summary_path.read_text(encoding="utf-8"), "A bounded summary.")
            self.assertEqual(uncertainty_path.read_text(encoding="utf-8"),
                             "Verify important claims.")
            self.assertIn("GUIDE-SE-SUMMARY-1", output.getvalue())

    def test_unapproved_input_path_is_rejected(self) -> None:
        with self.assertRaises(guide_se_deck.NodeLinkError):
            guide_se_deck.read_input("/tmp/some-other-file")


if __name__ == "__main__":
    unittest.main()
