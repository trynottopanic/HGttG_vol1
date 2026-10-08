import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import guide_browser_metrics as metrics


class MetricsTests(unittest.TestCase):
    def test_rollup_units_and_field_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'rollup'
            path.write_text('Rss: 12 kB\nPss: 8 kB\nPss_Anon: 3 kB\nSwap: 2 kB\nOwnerText: 1 kB\n')
            self.assertEqual(metrics.memory_fields(path),
                             {'Rss': 12288, 'Pss': 8192, 'Pss_Anon': 3072, 'Swap': 2048})

    def test_disappearing_process_is_unavailable(self):
        self.assertEqual(metrics.memory_fields(Path('/no-such-guide-rollup')), {})

    def test_unknown_phase_cannot_log_owner_text(self):
        with self.assertRaises(ValueError): metrics.emit('https://owner.example/private')

    def test_sample_records_fixed_phase_without_command_lines(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output): metrics.emit('periodic')
        row = json.loads(output.getvalue().split(' ', 1)[1])
        self.assertEqual(row['phase'], 'periodic')
        self.assertNotIn('argv', output.getvalue())
        self.assertLessEqual(len(row['processes']), 24)


if __name__ == '__main__': unittest.main()
