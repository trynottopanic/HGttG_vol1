import json
from pathlib import Path
import tempfile
import unittest

from notepad_store import (CardBinding, DestinationState, MAX_UTF8_BYTES,
                           NotepadStore, StoreError, normalize_basename, normalize_text)


class NotepadStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'GUIDE' / 'DOCUMENTS' / 'NOTEPAD'
        self.root.mkdir(parents=True)
        self.binding = CardBinding(('cid', 'diskseq-1'), 1)
        self.live = self.binding
        self.store = NotepadStore(self.root, Path(self.temp.name) / 'recovery', lambda: self.live)

    def test_create_normalizes_name_and_line_endings(self):
        receipt = self.store.save(name='café notes', text='one\r\ntwo\rthree',
                                  expected=DestinationState(False), binding=self.binding, replace=False)
        self.assertEqual(receipt.filename, 'café notes.txt')
        self.assertEqual((self.root / receipt.filename).read_bytes(), b'one\ntwo\nthree')

    def test_existing_file_needs_explicit_replace(self):
        (self.root / 'note.txt').write_text('old', encoding='utf-8')
        with self.assertRaisesRegex(StoreError, 'explicit replacement'):
            self.store.save(name='note', text='new', expected=DestinationState(True, self.store._digest(b'old')),
                            binding=self.binding, replace=False)
        self.assertEqual((self.root / 'note.txt').read_text(encoding='utf-8'), 'old')

    def test_changed_card_does_not_write(self):
        self.live = CardBinding(('cid', 'diskseq-2'), 2)
        with self.assertRaisesRegex(StoreError, 'removed or reinserted'):
            self.store.save(name='note', text='new', expected=DestinationState(False), binding=self.binding, replace=False)
        self.assertFalse((self.root / 'note.txt').exists())

    def test_changed_destination_refuses_overwrite(self):
        path = self.root / 'note.txt'
        path.write_text('old', encoding='utf-8')
        with self.assertRaisesRegex(StoreError, 'changed since'):
            self.store.save(name='note', text='new', expected=DestinationState(True, self.store._digest(b'other')),
                            binding=self.binding, replace=True)
        self.assertEqual(path.read_text(encoding='utf-8'), 'old')

    def test_failure_keeps_recovery_record_and_never_exposes_destination(self):
        original = self.store._require_binding
        calls = [0]
        def remove_after_setup(binding):
            calls[0] += 1
            if calls[0] == 2:
                self.live = CardBinding(('cid', 'diskseq-2'), 2)
            return original(binding)
        self.store._require_binding = remove_after_setup
        with self.assertRaises(StoreError):
            self.store.save(name='note', text='new', expected=DestinationState(False), binding=self.binding, replace=False)
        self.assertFalse((self.root / 'note.txt').exists())
        records = list((Path(self.temp.name) / 'recovery').glob('*.json'))
        self.assertEqual(len(records), 1)
        self.assertEqual(json.loads(records[0].read_text())['state'], 'prepared')
        self.assertEqual(self.store.recoveries(self.live)[0].state, 'different-card')

    def test_recovery_reports_committed_cleanup_without_modifying_files(self):
        record = self.store._record('fixture', dict(
            collection='documents.notepad', filename='note.txt',
            binding=dict(identity=list(self.binding.identity), generation=self.binding.insertion_generation),
            temporary='.guideos-notepad-fixture.tmp', digest=self.store._digest(b'new'), state='prepared'))
        (self.root / 'note.txt').write_text('new', encoding='utf-8')
        before = (self.root / 'note.txt').read_bytes()
        self.assertEqual(self.store.recoveries(self.binding)[0].state, 'committed-cleanup')
        self.assertEqual((self.root / 'note.txt').read_bytes(), before)
        self.assertTrue(record.exists())

    def test_bounds_and_portable_names(self):
        with self.assertRaises(StoreError):
            normalize_text('x' * 5121)
        with self.assertRaises(StoreError):
            normalize_text('é' * (MAX_UTF8_BYTES // 2 + 1))
        for name in ('', '.', 'NUL', 'COM1', 'bad/name', 'trailing '):
            with self.assertRaises(StoreError):
                normalize_basename(name)


if __name__ == '__main__':
    unittest.main()
