# SPDX-License-Identifier: AGPL-3.0-or-later
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from deck_receiver import HandoffStore


class HandoffStoreTests(unittest.TestCase):
    def metadata(self, data: bytes) -> dict:
        return {
            "display_name": "My Movie.mp4",
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "position_ms": 372_450,
            "created_utc": "2026-09-04T07:00:00Z",
        }

    def test_verified_transfer_publishes_resume_manifest_last(self):
        data = b"video test bytes"
        with tempfile.TemporaryDirectory() as directory:
            store = HandoffStore(Path(directory))
            pending = store.begin(self.metadata(data))
            store.receive(pending.handoff_id, pending.token, io.BytesIO(data), len(data))
            manifest = store.commit(pending.handoff_id, pending.token)
            manifest_path = store.library / f"{pending.handoff_id}.guide-resume.json"
            self.assertTrue((store.library / manifest["media_file"]).is_file())
            self.assertEqual(json.loads(manifest_path.read_text())["position_ms"], 372_450)
            self.assertFalse(pending.part_path.exists())

    def test_bad_hash_is_discarded(self):
        promised = self.metadata(b"right")
        with tempfile.TemporaryDirectory() as directory:
            store = HandoffStore(Path(directory))
            pending = store.begin(promised)
            store.receive(pending.handoff_id, pending.token, io.BytesIO(b"wrong"), 5)
            with self.assertRaisesRegex(ValueError, "Verification failed"):
                store.commit(pending.handoff_id, pending.token)
            self.assertFalse(pending.part_path.exists())
            self.assertEqual(list(store.library.iterdir()), [])

    def test_directory_components_are_removed_from_name(self):
        data = b"123"
        metadata = self.metadata(data)
        metadata["display_name"] = "../../private/movie.mp4"
        with tempfile.TemporaryDirectory() as directory:
            pending = HandoffStore(Path(directory)).begin(metadata)
            self.assertEqual(pending.metadata["display_name"], "movie.mp4")

    def test_abandoned_parts_are_removed_on_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            incoming = Path(directory) / ".incoming"
            incoming.mkdir()
            abandoned_media = incoming / "old.part"
            abandoned_manifest = incoming / "old.json.part"
            abandoned_media.write_bytes(b"partial")
            abandoned_manifest.write_text("{", encoding="utf-8")
            HandoffStore(Path(directory))
            self.assertFalse(abandoned_media.exists())
            self.assertFalse(abandoned_manifest.exists())

    def test_ready_callback_runs_only_after_verified_publish(self):
        data = b"video test bytes"
        ready = []
        with tempfile.TemporaryDirectory() as directory:
            store = HandoffStore(Path(directory), on_commit=lambda manifest, path: ready.append((manifest, path)))
            pending = store.begin(self.metadata(data))
            self.assertEqual(ready, [])
            store.receive(pending.handoff_id, pending.token, io.BytesIO(data), len(data))
            self.assertEqual(ready, [])
            manifest = store.commit(pending.handoff_id, pending.token)
            self.assertEqual(len(ready), 1)
            self.assertEqual(ready[0][0]["handoff_id"], manifest["handoff_id"])
            self.assertTrue(ready[0][1].is_file())


if __name__ == "__main__":
    unittest.main()
