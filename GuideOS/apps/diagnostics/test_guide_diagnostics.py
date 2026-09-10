from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import guide_diagnostics as diagnostics


class DiagnosticTests(unittest.TestCase):
    def test_redaction_removes_secrets_addresses_and_media_paths(self) -> None:
        value = ("password=hunter2 token:abc MAC AA:BB:CC:DD:EE:FF "
                 "/media/guide-card/Movies/private.mkv")
        safe = diagnostics.redact(value)
        self.assertNotIn("hunter2", safe)
        self.assertNotIn("abc", safe)
        self.assertNotIn("AA:BB", safe)
        self.assertNotIn("private.mkv", safe)

    def test_text_report_has_stable_protocol_and_sections(self) -> None:
        rendered = diagnostics.text_report({"checks": {"overall": "ready"}})
        self.assertIn("PROTOCOL=guide-diagnostics/1", rendered)
        self.assertIn("=== CHECKS ===", rendered)

    def test_saved_reports_are_private_and_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            text = root / "latest.txt"
            machine = root / "latest.json"
            report = {"checks": {"overall": "ready"}}
            with patch.object(diagnostics, "TEXT_REPORT", text), \
                 patch.object(diagnostics, "JSON_REPORT", machine), \
                 patch.object(diagnostics, "collect_report", return_value=report):
                self.assertEqual(diagnostics.main(["--save", "--json"]), 0)
            self.assertEqual(json.loads(machine.read_text(encoding="utf-8")), report)
            self.assertIn("GUIDEOS DIAGNOSTIC REPORT", text.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

