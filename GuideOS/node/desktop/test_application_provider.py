from pathlib import Path
import tempfile
import unittest

from application_provider import ApplicationProvider


class ApplicationProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config = self.root / "node.json"
        self.executable = self.root / "example.exe"
        self.executable.write_bytes(b"MZ test fixture")
        self.provider = ApplicationProvider(self.config)

    def tearDown(self) -> None:
        self.provider.close()
        self.temporary.cleanup()

    def test_only_owner_registered_executables_can_be_requested(self) -> None:
        profile = self.provider.add(self.executable, "Example", "Example Window")
        self.assertEqual(profile["id"], "example")
        self.assertIsNone(self.provider.request("not-registered", "deck-a", "Deck"))
        session = self.provider.request("example", "deck-a", "Deck")
        self.assertIsNotNone(session)
        self.assertEqual(session["state"], "pending")

    def test_request_requires_local_owner_decision_and_isolated_identity(self) -> None:
        self.provider.add(self.executable, "Example", "Example Window")
        session = self.provider.request("example", "deck-a", "Alice's Deck")
        assert session is not None
        session_id = str(session["id"])
        self.assertIsNone(self.provider.session(session_id, "deck-b"))
        denied = self.provider.decide(session_id, False)
        self.assertEqual(denied["state"], "denied")
        self.assertIsNone(denied.get("stream_path"))

    def test_profile_persists_without_exposing_its_path(self) -> None:
        self.provider.add(self.executable, "Example", "Example Window")
        restored = ApplicationProvider(self.config)
        try:
            public = restored.profiles()[0]
            self.assertEqual(public["name"], "Example")
            self.assertNotIn("executable", public)
            self.assertNotIn(str(self.root), str(public))
        finally:
            restored.close()

    def test_rejects_non_executable_files(self) -> None:
        text = self.root / "notes.txt"
        text.write_text("hello", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.provider.add(text)


if __name__ == "__main__":
    unittest.main()
