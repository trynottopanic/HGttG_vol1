import json
from pathlib import Path
import tempfile
import unittest
from audio_core import catalog, outputs_from_dump, selected_path


class CatalogTests(unittest.TestCase):
    def test_reject_links_unknown_formats_and_stale_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'song.wav').write_bytes(b'RIFF')
            (root/'other.txt').write_text('no')
            (root/'outside.wav').symlink_to('/etc/passwd')
            rows = catalog(root)
            self.assertEqual([r['title'] for r in rows], ['song'])
            self.assertEqual(selected_path(rows, rows[0]['id'], root), root/'song.wav')
            (root/'song.wav').unlink()
            (root/'song.wav').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):
                selected_path(rows, rows[0]['id'], root)
            with self.assertRaises(ValueError):
                selected_path(rows, 'not-cataloged', root)

    def test_endpoint_discovery_never_uses_default_or_microphones(self):
        def item(kind, name):
            return dict(type='PipeWire:Interface:Node', info=dict(props={'media.class':kind,'node.name':name}))
        rows = outputs_from_dump([item('Audio/Source','microphone'), item('Audio/Sink','bluez_output.test'),item('Audio/Sink','alsa_output.test')])
        self.assertEqual([r['id'] for r in rows], ['bluez_output.test','alsa_output.test'])
        self.assertTrue(rows[0]['bluetooth'])


if __name__ == '__main__':
    unittest.main()
