"""Public optional compilation: real stable project, no state or result registry."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'skills/cs-homework/scripts/coursework.py'
TECTONIC = Path(os.environ.get('COURSEWORK_TEST_TECTONIC', 'missing-tectonic'))
POPPLER = Path(os.environ.get('COURSEWORK_TEST_PDFTOPPM', 'missing-pdftoppm'))


class NativeReportTests(unittest.TestCase):
    def invoke(self, root, record):
        with tempfile.TemporaryDirectory() as outside:
            request = Path(outside) / 'request.json'
            request.write_text(json.dumps(record), encoding='utf-8')
            run = subprocess.run([sys.executable, '-B', str(CLI), 'compile-project', '--workspace', str(root), '--input', str(request)], capture_output=True, text=True)
            return run.returncode, json.loads(run.stdout or run.stderr)

    @unittest.skipUnless(TECTONIC.is_file() and POPPLER.is_file(), 'Real LaTeX and Poppler required')
    def test_stable_project_compiles_twice_and_failed_attempt_never_accepts_old_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / 'report'; project.mkdir()
            main = project / 'main.tex'
            main.write_text(r'\documentclass{article}\begin{document}\input{body}\end{document}', encoding='utf-8')
            body = project / 'body.tex'; body.write_text('Measured sum: 6.', encoding='utf-8')
            record = {'request':'Continue this report and build PDF', 'scope':{'goal':'report PDF', 'authorized_behaviors':['report']},
                      'project':'report', 'main_file':'main.tex', 'source_paths':[],
                      'compiler':{'engine':'tectonic','executable':str(TECTONIC)},
                      'renderer':{'executable':str(POPPLER)}}
            code, first = self.invoke(root, record)
            self.assertEqual(code, 0, first)
            self.assertEqual(first['status'], 'awaiting_review', first)
            self.assertTrue(first['pages'])
            original_main = main.read_bytes()
            body.write_text('Measured sum: 7.', encoding='utf-8')
            code, second = self.invoke(root, record)
            self.assertEqual(second['status'], 'awaiting_review', second)
            self.assertNotEqual(first['pdf']['path'], second['pdf']['path'])
            captured = second['compilation'][0]['source_before']['files']
            self.assertIn('report/body.tex', [f['path'] for f in captured])
            body.write_text(r'\undefinedCommand', encoding='utf-8')
            code, failed = self.invoke(root, record)
            self.assertEqual(failed['status'], 'failed', failed)
            self.assertNotIn('pdf', failed)
            self.assertEqual(main.read_bytes(), original_main)
            self.assertTrue((root / second['pdf']['path']).is_file())
            self.assertFalse((root / '.coursework/state.json').exists())
            self.assertFalse((root / 'reports').exists())

    def test_advice_readonly_and_source_only_refuse_before_side_effects(self):
        for scope_extra, extra in [({'report_mode':'review'}, {}), ({'read_only':True}, {}), ({}, {'source_only':True})]:
            with self.subTest(scope=scope_extra, extra=extra), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                record = {'request':'Review or source only', 'scope':{'goal':'report', 'authorized_behaviors':['report'], **scope_extra}, **extra}
                code, refused = self.invoke(root, record)
                self.assertEqual(code, 2, refused)
                self.assertEqual(list(root.iterdir()), [])


if __name__ == '__main__': unittest.main()
