"""Optional byte preservation and execution receipts for native assignment work."""
from pathlib import Path
import uuid

from .context import require_writable_request, write_json
from .execution import execute, source_state, validate_request, files_unchanged, prepare_trial, execution_unchanged
from .git import begin_task


def current_request(record):
    require_writable_request(record)
    if not isinstance(record, dict):
        raise ValueError('Current request must be an object')
    scope = record.get('scope', {})
    if not isinstance(record.get('request'), str) or not record['request'].strip() or not scope.get('goal'):
        raise ValueError('Supply the current human request and scope')
    return scope


def directory_for(workspace, kind):
    directory = workspace / '.coursework' / 'native' / kind / uuid.uuid4().hex
    # Resolve before any writes: retain existing linked metadata boundaries.
    if directory.resolve() != directory:
        raise ValueError('Evidence directory must not traverse filesystem links')
    return directory


def protect_edits(workspace, record):
    scope = current_request(record)
    role = record.get('role', 'code')
    if role not in {'code', 'analyze', 'report'} or role not in scope.get('authorized_behaviors', []):
        raise ValueError('Current scope must authorize this edit role (code/analyze/report)')
    workspace = Path(workspace).resolve()
    paths = record.get('paths')
    if not isinstance(paths, list) or not paths or any(not isinstance(p, str) or not p for p in paths):
        raise ValueError('Supply exact paths before editing')
    for name in paths:
        path = workspace / name
        if not path.is_relative_to(workspace) or path.resolve() != path or '.git' in path.relative_to(workspace).parts or path.is_dir():
            raise ValueError('Edit paths must be exact assignment files without links')
    directory = directory_for(workspace, 'originals')
    snapshot = begin_task(workspace)
    protection = source_state(workspace, {'source_paths': paths}, directory, snapshot)
    result = {'request': record['request'], 'scope': scope, 'protection': protection,
              'dirty_paths': sorted(snapshot.dirty_paths), 'receipt': (directory / 'receipt.json').relative_to(workspace).as_posix()}
    write_json(directory / 'receipt.json', result)
    return result


def capture_run(workspace, record):
    scope = current_request(record)
    role = record.get('role', 'run')
    if role in {'analyze', 'report'} and role not in scope.get('authorized_behaviors', []):
        raise ValueError('Current scope must authorize the execution role')
    # Reuse command validation, without context, registration or a code session.
    checked = {**record, 'assignment': record.get('assignment', {'title': 'Native assignment execution'})}
    validate_request(checked, role=role)
    workspace = Path(workspace).resolve()
    directory = directory_for(workspace, 'runs')
    spec = record['execution']
    conditions = {'trial': record.get('trial'), 'budget_seconds': record.get('budget_seconds', 1800),
                  'estimate_basis': record.get('estimate_basis')}
    confirmation = record.get('confirmation_of')
    if confirmation:
        import json
        receipt = (workspace / confirmation).resolve()
        if not receipt.is_relative_to(workspace):
            raise ValueError('Confirmation receipt must stay within assignment')
        previous = json.loads(receipt.read_text(encoding='utf-8'))
        if (previous.get('status') != 'awaiting_confirmation' or previous['specification'] != spec
                or previous.get('role', 'run') != role or previous.get('request') != record['request']
                or previous.get('scope') != scope or previous.get('conditions') != conditions
                or not isinstance(record.get('confirmation'), str) or not record['confirmation'].strip()):
            raise ValueError('Request/scope/plan changed or confirmation missing; check and estimate a fresh run')
        if not execution_unchanged(workspace, spec, previous['planned_source'], previous['execution_identity']):
            raise ValueError('Source/input/environment changed; repeat the trial')
    snapshot = begin_task(workspace)
    result = {'request': record['request'], 'scope': record['scope'], 'specification': spec,
              'role': role, 'conditions': conditions}
    if confirmation:
        result['confirmation_of'] = confirmation
        result['confirmation'] = record['confirmation']
        result['execution'] = execute(workspace, spec, directory / 'execution', snapshot)
    elif 'trial' in record:
        trial_spec, result['planned_source'], result['execution_identity'] = prepare_trial(
            workspace, spec, record['trial'], directory / 'planned', snapshot)
        trial = execute(workspace, trial_spec, directory / 'trial', snapshot)
        result['trial'] = trial
        estimate = trial['elapsed_seconds'] * (1 + spec.get('workload_units', 1) / record['trial']['workload_units'])
        result['estimated_seconds'] = estimate
        if (trial['status'] != 'completed' or not files_unchanged(workspace, trial['source_before'])
                or not execution_unchanged(workspace, spec, result['planned_source'], result['execution_identity'])):
            result['status'] = 'trial_failed'
            result['diagnostic'] = 'Trial failed or source/input/executable/environment changed; check and estimate a fresh run'
        elif estimate > record.get('budget_seconds', 1800):
            result['status'] = 'awaiting_confirmation'
        else:
            result['execution'] = execute(workspace, spec, directory / 'execution', snapshot)
    else:
        result['execution'] = execute(workspace, spec, directory / 'execution', snapshot)
    if 'execution' in result:
        result['status'] = result['execution']['status']
    result['receipt'] = (directory / 'receipt.json').relative_to(workspace).as_posix()
    write_json(directory / 'receipt.json', result)
    return result
