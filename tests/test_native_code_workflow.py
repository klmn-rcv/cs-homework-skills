import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'skills/cs-homework/scripts/coursework.py'

class NativeTests(unittest.TestCase):
    def invoke(self, root, command, record):
        request = root.parent / (root.name + '-request.json')
        request.write_text(json.dumps(record), encoding='utf-8')
        result = subprocess.run([sys.executable, '-B', str(CLI), command, '--workspace', str(root), '--input', str(request)], capture_output=True, text=True)
        return result, json.loads(result.stdout or result.stderr)

    def test_native_edit_can_recover_original_and_capture_dirty_run_without_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'assignment'; root.mkdir()
            source = root / 'sum.py'; source.write_bytes(b'print(3)\n')
            record = {'request': 'Fix sum and verify', 'scope': {'goal': 'correct sum', 'authorized_behaviors': ['code']}, 'paths': ['sum.py', 'new.py']}
            result, saved = self.invoke(root, 'protect-edits', record)
            self.assertEqual(result.returncode, 0, saved)
            source.write_bytes(b'print(6)\n')
            self.assertEqual((root / saved['protection']['files'][0]['snapshot_path']).read_bytes(), b'print(3)\n')
            self.assertEqual(saved['protection']['files'][1]['status'], 'missing')
            record['execution'] = {'argv': [sys.executable, '-B', 'sum.py'], 'source_paths': ['sum.py'], 'expected': {'stdout': '6' + os.linesep, 'exit_code': 0, 'basis': '1+2+3'}, 'purposes': ['correctness'], 'basis': 'teacher sample'}
            result, run = self.invoke(root, 'capture-run', record)
            self.assertEqual(result.returncode, 0, run)
            self.assertEqual(run['execution']['check']['status'], 'passed')
            item = run['execution']['source_before']['files'][0]
            self.assertEqual((root / item['snapshot_path']).read_bytes(), b'print(6)\n')
            self.assertFalse((root / '.coursework/state.json').exists())

    def test_trial_waits_and_confirmation_requires_same_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'assignment'; root.mkdir()
            (root / 'work.py').write_bytes(b'import time; time.sleep(.01); print(6)')
            record = {'request':'Run with short budget', 'scope':{'goal':'measure', 'authorized_behaviors':['run']}, 'budget_seconds':.000001,
                'execution':{'argv':[sys.executable,'-B','work.py'], 'source_paths':['work.py'], 'purposes':['experiment'], 'basis':'requested experiment', 'requires_trial':True, 'workload_units':100},
                'trial':{'argv':[sys.executable,'-B','work.py'], 'workload_units':1}}
            result, waiting = self.invoke(root, 'capture-run', record)
            self.assertEqual(result.returncode, 0, waiting)
            self.assertEqual(waiting['status'], 'awaiting_confirmation')
            self.assertNotIn('execution', waiting)
            record.update(confirmation_of=waiting['receipt'], confirmation='Synthetic test confirmation, not human acceptance')
            (root / 'work.py').write_bytes(b'print(7)')
            result, failed = self.invoke(root, 'capture-run', record)
            self.assertEqual(result.returncode, 2, failed)
            self.assertIn('changed', failed['error'])

    def test_staged_and_untracked_originals_survive_native_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'assignment'; root.mkdir()
            def git(*args):
                return subprocess.run(['git','-C',str(root),*args], capture_output=True, check=True).stdout
            git('init','-q')
            source = root / 'a.py'; source.write_bytes(b'baseline')
            git('add','a.py'); git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','baseline')
            source.write_bytes(b'staged user bytes'); git('add','a.py')
            source.write_bytes(b'unstaged user bytes')
            (root / 'user.txt').write_bytes(b'untracked user bytes')
            before_index = git('show',':a.py')
            result, saved = self.invoke(root, 'protect-edits', {'request':'Fix existing code', 'scope':{'goal':'fix', 'authorized_behaviors':['code']}, 'paths':['a.py','user.txt','new.py']})
            self.assertEqual(result.returncode, 0, saved)
            source.write_bytes(b'native patch')
            self.assertEqual(git('show',':a.py'), before_index)
            originals = saved['protection']
            self.assertEqual((root / originals['files'][0]['snapshot_path']).read_bytes(), b'unstaged user bytes')
            self.assertEqual((root / originals['files'][1]['snapshot_path']).read_bytes(), b'untracked user bytes')
            self.assertIn(b'staged user bytes', (root / originals['staged_diff']['path']).read_bytes())
            self.assertIn(b'unstaged user bytes', (root / originals['unstaged_diff']['path']).read_bytes())

    def test_analysis_role_preserves_real_scope_without_code_permission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'assignment'; root.mkdir()
            (root / 'analysis.py').write_bytes(b'print(6)')
            record = {'request':'Calculate only', 'scope':{'goal':'metric', 'authorized_behaviors':['analyze']}, 'paths':['analysis.py']}
            result, refused = self.invoke(root, 'protect-edits', record)
            self.assertEqual(result.returncode, 2, refused)
            record['role'] = 'analyze'
            result, protected = self.invoke(root, 'protect-edits', record)
            self.assertEqual(result.returncode, 0, protected)
            record['execution'] = {'argv':[sys.executable,'-B','analysis.py'], 'source_paths':['analysis.py'], 'purposes':['experiment'], 'basis':'requested metric'}
            result, saved = self.invoke(root, 'capture-run', record)
            self.assertEqual(result.returncode, 0, saved)
            self.assertEqual(saved['scope']['authorized_behaviors'], ['analyze'])
            self.assertEqual(saved['execution']['stdout']['text'], '6' + os.linesep)

    def test_direct_csv_analysis_captures_real_files_without_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'assignment'; root.mkdir()
            (root / 'rows.csv').write_bytes(b'milliseconds\n100\n240\n560\n')
            (root / 'analysis.py').write_text("import csv\nfrom pathlib import Path\nvalues=[float(r['milliseconds'])/1000 for r in csv.DictReader(open('rows.csv'))]\nPath('table.txt').write_text(','.join(str(v) for v in values))\nprint(sum(values))\n", encoding='utf-8')
            record = {'request':'Analyze supplied rows only', 'scope':{'goal':'seconds table', 'authorized_behaviors':['analyze']}, 'role':'analyze',
                'execution':{'argv':[sys.executable,'-B','analysis.py'], 'source_paths':['analysis.py'], 'input_paths':['rows.csv'], 'output_paths':['table.txt'], 'purposes':['example'], 'basis':'user-supplied previous measurements; generation unverified'}}
            result, saved = self.invoke(root, 'capture-run', record)
            self.assertEqual(result.returncode, 0, saved)
            self.assertEqual(saved['execution']['exit_code'], 0)
            self.assertEqual((root / 'table.txt').read_text(), '0.1,0.24,0.56')
            self.assertEqual((root / 'rows.csv').read_bytes(), b'milliseconds\n100\n240\n560\n')
            self.assertFalse((root / '.coursework/state.json').exists())
            self.assertFalse((root / '.coursework/results').exists())
            self.assertEqual(saved['execution']['source_before']['files'][0]['path'], 'analysis.py')

    def test_readonly_guard_runs_before_git_or_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for command in ['protect-edits', 'capture-run']:
                result, saved = self.invoke(root, command, {'request':'Only inspect', 'scope':{'goal':'review', 'read_only':True, 'authorized_behaviors':['code']}, 'paths':['x']})
                self.assertEqual(result.returncode, 2, saved)
                self.assertEqual(list(root.iterdir()), [])

if __name__ == '__main__': unittest.main()
