import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('report',Path(__file__).with_name('diagnostic-report.py'))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class ReportTests(unittest.TestCase):
    def test_empty_evidence_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as p:
            report=m.build(Path(p))
        statuses={r['feature']:r['state'] for r in report['features']}
        self.assertEqual(statuses['Graphics rendering'],'not demonstrated')
        self.assertEqual(statuses['Bluetooth controller'],'not observed')
        self.assertEqual(statuses['Start / Power / Reset'],'excluded')

    def test_fps_is_measured_and_observation_is_distinct(self):
        with tempfile.TemporaryDirectory() as p:
            p=Path(p)
            (p/'cube.txt').write_text('Rendered 1799 frames in 29.98 sec (60.00 fps)\n')
            (p/'controller-summary.json').write_text(json.dumps({'results':[{'phase':'experience','label':'readability','outcome':'unanswered','answer':None}]}))
            report=m.build(p)
        self.assertEqual(next(r for r in report['features'] if r['feature']=='Graphics rendering')['state'],'measured')
        self.assertIsNone(report['observations'][0]['answer'])

    def test_html_escapes_recorded_strings(self):
        with tempfile.TemporaryDirectory() as p:
            p=Path(p); (p/'kernel.txt').write_text('<script>bad()</script>')
            html=m.render(m.build(p))
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)

if __name__=='__main__': unittest.main()
