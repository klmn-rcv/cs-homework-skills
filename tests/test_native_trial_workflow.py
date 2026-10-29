"""Trial regressions through public CLIs and small real subprocesses."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid


CLI = Path(__file__).resolve().parents[1] / 'skills/cs-homework/scripts/coursework.py'


class NativeTrialWorkflow(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        evidence = os.environ.get('COURSEWORK_REVIEW_EVIDENCE')
        if evidence:
            destination = Path(evidence) / (self._testMethodName + '-' + uuid.uuid4().hex)
            self.addCleanup(lambda: shutil.copytree(self.root, destination))
        self.sequence = 0

    def case(self, name):
        workspace = self.root / name
        workspace.mkdir()
        (workspace / 'echo.py').write_text(
            'import sys\nsys.stdout.buffer.write(sys.stdin.buffer.read())\n', encoding='utf-8')
        return workspace, {
            'assignment': {'title': 'Small literal trial fixture'},
            'request': 'Run this fixed experiment with a small trial first',
            'scope': {'goal': 'fixed experiment', 'authorized_behaviors': ['run']},
            'execution': {'argv': [sys.executable, '-B', 'echo.py'],
                          'source_paths': ['echo.py'], 'purposes': ['experiment'],
                          'basis': 'Supplied echo fixture', 'requires_trial': True,
                          'workload_units': 2},
            'trial': {'argv': [sys.executable, '-B', 'echo.py'], 'workload_units': 1},
        }

    def invoke(self, workspace, record, command='capture-run', *, env=None, ok=True):
        self.sequence += 1
        prefix = self.root / f'cli-{self.sequence:02d}'
        request = prefix.with_suffix('.input.json')
        request.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        argv = [sys.executable, '-B', '-X', 'utf8', str(CLI), command,
                '--workspace', str(workspace), '--input', str(request)]
        process = subprocess.run(argv, capture_output=True, env=env)
        command_record = {'argv': argv, 'cwd': os.getcwd(), 'exit_code': process.returncode,
                          'environment_changes': {key: value for key, value in (env or os.environ).items()
                                                  if os.environ.get(key) != value}}
        prefix.with_suffix('.command.json').write_text(json.dumps(command_record), encoding='utf-8')
        prefix.with_suffix('.stdout').write_bytes(process.stdout)
        prefix.with_suffix('.stderr').write_bytes(process.stderr)
        if ok:
            self.assertEqual(process.returncode, 0, process.stderr.decode('utf-8'))
        saved = json.loads(process.stdout or process.stderr)
        return process, saved.get('run', saved)

    def test_explicit_trial_stdin_replaces_other_mode_and_full_input_is_preserved(self):
        # Literal echo outputs are the oracle, independent of trial merging.
        modes = [({'stdin_path': 'full.txt'}, {'stdin_text': 'TRIAL'}),
                 ({'stdin_text': 'FULL'}, {'stdin_path': 'trial.txt'}),
                 ({'stdin_text': 'FULL'}, {'stdin_text': 'TRIAL'}),
                 ({'stdin_path': 'full.txt'}, {'stdin_path': 'trial.txt'})]
        cases = [(command, full, trial) for command in ('capture-run', 'run') for full, trial in modes]
        for index, (command, full_input, trial_input) in enumerate(cases):
            with self.subTest(command=command, mode=index):
                workspace, record = self.case(str(index))
                (workspace / 'full.txt').write_bytes(b'FULL')
                (workspace / 'trial.txt').write_bytes(b'TRIAL')
                record['execution'].update(full_input)
                record['trial'].update(trial_input)
                _, saved = self.invoke(workspace, record, command)
                self.assertEqual(saved['trial']['stdin']['text'], 'TRIAL')
                self.assertEqual(saved['trial']['stdout']['text'], 'TRIAL')
                self.assertEqual(saved['execution']['stdin']['text'], 'FULL')
                self.assertEqual(saved['execution']['stdout']['text'], 'FULL')
                self.assertEqual(saved['status'], 'completed')
                if command == 'capture-run':
                    self.assertFalse((workspace / '.coursework/state.json').exists())

    def test_scaled_trial_without_oracle_does_not_inherit_full_answer(self):
        workspace, record = self.case('scaled')
        (workspace / 'echo.py').write_text(
            'import sys\nprint(int(sys.stdin.read()) * 2)\n', encoding='utf-8')
        record['execution'].update(stdin_text='21', expected={
            'stdout': '42' + os.linesep, 'exit_code': 0, 'basis': 'Supplied 21 -> 42 fixture'})
        record['trial']['stdin_text'] = '2'
        _, saved = self.invoke(workspace, record)
        self.assertEqual(saved['trial']['stdout']['text'], '4' + os.linesep)
        self.assertEqual(saved['trial']['check']['status'], 'unverified')
        self.assertEqual(saved['status'], 'completed')
        self.assertEqual(saved['execution']['stdout']['text'], '42' + os.linesep)
        self.assertEqual(saved['execution']['check']['status'], 'passed')

    def test_confirmation_cannot_cover_changed_request_scope_or_budget_conditions(self):
        changes = [ {'request': 'A different experiment'},
                    {'scope': {'goal': 'different goal', 'authorized_behaviors': ['run', 'analyze']}},
                    {'scope': {'goal': 'fixed experiment', 'authorized_behaviors': ['run']}},
                    {'budget_seconds': .002},
                    {'trial': {'argv': [sys.executable, '-B', 'echo.py'],
                               'workload_units': 2, 'stdin_text': 'different sample'}},
                    {'execution': {'argv': [sys.executable, '-B', 'echo.py'],
                                   'source_paths': ['echo.py'], 'purposes': ['experiment'],
                                   'basis': 'Supplied echo fixture', 'stdin_text': 'OTHER'}},
                    {'estimate_basis': 'A different estimate'},
                    {'role': 'analyze'} ]
        workspace, record = self.case('confirmation')
        (workspace / 'echo.py').write_text(
            "import sys\nfrom pathlib import Path\n"
            "if sys.stdin.read() == 'FULL': Path('full-started.txt').write_text('ran')\n",
            encoding='utf-8')
        record['scope']['authorized_behaviors'].append('analyze')
        record['execution']['stdin_text'] = 'FULL'
        record['trial']['stdin_text'] = 'TRIAL'
        record['budget_seconds'] = .000001
        _, waiting = self.invoke(workspace, record)
        self.assertEqual(waiting['status'], 'awaiting_confirmation')
        pending_bytes = (workspace / waiting['receipt']).read_bytes()
        reply = '  Synthetic fixture reply: accept this saved plan only.\n'
        original = copy.deepcopy(record)
        record.update(confirmation_of=waiting['receipt'], confirmation=reply)
        for change in changes:
            with self.subTest(change=change):
                changed = {**copy.deepcopy(record), **change}
                process, refused = self.invoke(workspace, changed, ok=False)
                self.assertEqual(process.returncode, 2, refused)
                self.assertFalse((workspace / 'full-started.txt').exists())
                self.assertEqual((workspace / waiting['receipt']).read_bytes(), pending_bytes)
        # A changed task can obtain a fresh estimate instead of reusing approval.
        fresh = {**original, 'request': 'A different experiment'}
        _, rechecked = self.invoke(workspace, fresh)
        self.assertEqual(rechecked['status'], 'awaiting_confirmation')
        self.assertNotEqual(rechecked['receipt'], waiting['receipt'])
        self.assertFalse((workspace / 'full-started.txt').exists())
        # The unchanged plan preserves the raw supplied reply, with its provenance.
        _, confirmed = self.invoke(workspace, record)
        self.assertEqual(confirmed['status'], 'completed')
        self.assertEqual(confirmed['confirmation'], reply)
        self.assertEqual((workspace / 'full-started.txt').read_text(), 'ran')
        self.assertEqual((workspace / waiting['receipt']).read_bytes(), pending_bytes)

    def test_executable_replaced_during_trial_cannot_become_accepted_baseline(self):
        cases = [(command, budget) for command in ('capture-run', 'run') for budget in (1800, .000001)]
        for command, budget in cases:
            with self.subTest(command=command, budget=budget):
                workspace, record = self.case('drift-' + command + str(budget))
                wrapper = workspace / ('full.cmd' if os.name == 'nt' else 'full.sh')
                original = (b'@echo off\r\necho ORIGINAL\r\necho ran>full-started.txt\r\n'
                            if os.name == 'nt' else
                            b'#!/bin/sh\necho ORIGINAL\necho ran > full-started.txt\n')
                replacement = original.replace(b'ORIGINAL', b'REPLACED')
                wrapper.write_bytes(original)
                wrapper.chmod(0o755)
                # Only our disposable wrapper changes; no installed executable is touched.
                (workspace / 'mutate.py').write_text(
                    'from pathlib import Path\n'
                    f'Path({str(wrapper)!r}).write_bytes({replacement!r})\n', encoding='utf-8')
                record['execution']['argv'] = [str(wrapper)]
                record['trial'].update(argv=[sys.executable, '-B', 'mutate.py'],
                                       source_paths=['mutate.py'])
                record['budget_seconds'] = budget
                _, saved = self.invoke(workspace, record, command)
                self.assertEqual(wrapper.read_bytes(), replacement)
                self.assertEqual(saved['status'], 'trial_failed')
                self.assertNotIn('execution', saved)
                self.assertFalse((workspace / 'full-started.txt').exists())
                identity = saved['execution_identity' if command == 'capture-run' else 'plan_identity']
                self.assertEqual(identity['executable_sha256'],
                                 hashlib.sha256(original).hexdigest())

    def test_explicit_trial_oracle_is_honored_and_failure_blocks_full_run(self):
        for command in ('capture-run', 'run'):
            for trial_answer in ('TRIAL', 'WRONG'):
                with self.subTest(command=command, answer=trial_answer):
                    workspace, record = self.case(command + trial_answer)
                    (workspace / 'echo.py').write_text(
                        'import sys\nfrom pathlib import Path\ndata = sys.stdin.buffer.read()\n'
                        "if data == b'FULL': Path('full-started.txt').write_bytes(b'ran')\n"
                        'sys.stdout.buffer.write(data)\n', encoding='utf-8')
                    record['execution'].update(stdin_text='FULL', expected={
                        'stdout': 'FULL', 'basis': 'Literal echo fixture'})
                    record['trial'].update(stdin_text='TRIAL', expected={
                        'stdout': trial_answer, 'basis': 'Independent supplied trial answer'})
                    _, saved = self.invoke(workspace, record, command)
                    self.assertEqual(saved['trial']['stdout']['text'], 'TRIAL')
                    if trial_answer == 'TRIAL':
                        self.assertEqual(saved['trial']['check']['status'], 'passed')
                        self.assertEqual(saved['execution']['stdout']['text'], 'FULL')
                        self.assertEqual(saved['execution']['check']['status'], 'passed')
                        self.assertEqual(saved['status'], 'completed')
                        self.assertTrue((workspace / 'full-started.txt').exists())
                    else:
                        self.assertEqual(saved['trial']['check']['status'], 'failed')
                        self.assertEqual(saved['status'], 'trial_failed')
                        self.assertNotIn('execution', saved)
                        self.assertFalse((workspace / 'full-started.txt').exists())

    def test_trial_without_input_override_keeps_full_input_but_not_full_oracle(self):
        for command in ('capture-run', 'run'):
            for mode in ('stdin_text', 'stdin_path'):
                with self.subTest(command=command, mode=mode):
                    workspace, record = self.case(command + mode)
                    (workspace / 'full.txt').write_bytes(b'FULL')
                    record['execution'][mode] = 'FULL' if mode == 'stdin_text' else 'full.txt'
                    record['execution']['expected'] = {'stdout': 'FULL', 'basis': 'Literal echo fixture'}
                    _, saved = self.invoke(workspace, record, command)
                    self.assertEqual(saved['trial']['stdout']['text'], 'FULL')
                    self.assertEqual(saved['trial']['check']['status'], 'unverified')
                    self.assertEqual(saved['execution']['stdout']['text'], 'FULL')
                    self.assertEqual(saved['execution']['check']['status'], 'passed')

    def test_pending_confirmation_rechecks_source_inputs_executable_and_environment(self):
        for change in ('wrapper', 'environment', 'source', 'full-input', 'trial-input'):
            with self.subTest(change=change):
                workspace, record = self.case(change)
                wrapper = workspace / ('full.cmd' if os.name == 'nt' else 'full.sh')
                wrapper.write_bytes(b'@echo off\r\necho ran>full-started.txt\r\n' if os.name == 'nt'
                                    else b'#!/bin/sh\necho ran > full-started.txt\n')
                wrapper.chmod(0o755)
                record['execution']['argv'] = [str(wrapper)]
                (workspace / 'full.txt').write_bytes(b'FULL')
                (workspace / 'trial.txt').write_bytes(b'TRIAL')
                record['execution']['stdin_path'] = 'full.txt'
                record['trial']['stdin_path'] = 'trial.txt'
                record['budget_seconds'] = .000001
                _, waiting = self.invoke(workspace, record)
                self.assertEqual(waiting['status'], 'awaiting_confirmation')
                record.update(confirmation_of=waiting['receipt'], confirmation='Synthetic fixture reply')
                environment = os.environ.copy()
                if change == 'wrapper':
                    wrapper.write_bytes(wrapper.read_bytes() + b'\necho REPLACED\n')
                elif change == 'environment':
                    environment['COURSEWORK_TRIAL_FIXTURE'] = 'changed for this child only'
                elif change == 'source':
                    (workspace / 'echo.py').write_bytes(b'print("changed")\n')
                else:
                    (workspace / ('full.txt' if change == 'full-input' else 'trial.txt')).write_bytes(b'changed')
                process, refused = self.invoke(workspace, record, env=environment, ok=False)
                self.assertEqual(process.returncode, 2, refused)
                self.assertFalse((workspace / 'full-started.txt').exists())


if __name__ == '__main__':
    unittest.main()
