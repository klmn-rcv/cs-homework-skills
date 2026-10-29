"""Persist model-led coding attempts and execute fixed, independently justified checks."""
from copy import deepcopy
from pathlib import Path
import uuid

from .context import STATE_DIR, SCHEMA_VERSION, fingerprint, previous_state, read_state, write_json, resume
from .execution import now, protected_path, save_run, validate_request
from .git import TaskSnapshot, begin_task, checkpoint


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} needs a substantive explanation")
    return value


def local_code_path(workspace, name):
    if not isinstance(name, str) or not name:
        raise ValueError("Code paths must name assignment files")
    path = workspace / name
    if path.is_absolute() and (not path.is_relative_to(workspace) or path.resolve() != path):
        raise ValueError("Code paths must remain inside assignment without filesystem links")
    if set(path.relative_to(workspace).parts) & {".git", STATE_DIR}:
        raise ValueError("Implementation paths must not overwrite Git or coursework evidence")
    if path.exists() and not path.is_file():
        raise ValueError("Code paths must name files")
    return path


def content_identity(path):
    return fingerprint(path) if path.is_file() else None


def save_session(workspace, session, snapshot, message, extra_paths=()):
    previous = read_state(workspace) if (workspace / STATE_DIR / "state.json").exists() else {}
    revision = previous.get("revision", 0) + 1
    receipt = f"{STATE_DIR}/code/{session['id']}/revisions/{revision:04d}.json"
    summary = f"{STATE_DIR}/code/{session['id']}/revisions/{revision:04d}.md"
    names = [f"{STATE_DIR}/state.json", f"{STATE_DIR}/history/{revision:04d}.json", receipt, summary]
    for name in names:
        path = protected_path(workspace, name, snapshot)
        if name != f"{STATE_DIR}/state.json" and path.exists():
            raise ValueError("Code history is immutable")
    session = {**session, "updated_at": now(), "receipt_path": receipt, "summary_path": summary}
    sessions = [s for s in previous.get("code_sessions", []) if s["id"] != session["id"]]
    state = {**previous, "kind": "coursework-context", "schema_version": SCHEMA_VERSION,
             "revision": revision, "updated_at": now(),
             "assignment": session["assignment"], "request": session["request"], "scope": session["scope"],
             "sources": previous.get("sources", []), "requirements": previous.get("requirements", []),
             "plan": previous.get("plan", {}), "questions": previous.get("questions", []),
             "code_sessions": [*sessions, session]}
    write_json(workspace / receipt, session)
    lines = ["# Coursework code checkpoint", "", session["request"], "",
             f"Status: {session['status']}", "", "## Validation"]
    for check in session.get("latest_checks", {}).values():
        lines.append(f"- {check['check_id']}: {check['status']}; run {check['run_id']}")
    for issue_id, issue in session.get("issues", {}).items():
        lines.append(f"- Issue {issue_id}: {issue['status']}; consecutive targeted no-progress repairs: {issue['no_progress']}")
    lines += ["", "## Continue", *[f"- {item}" for item in session.get("next_steps", [])]]
    (workspace / summary).write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(workspace / STATE_DIR / "state.json", state)
    write_json(workspace / STATE_DIR / "history" / f"{revision:04d}.json", state)
    paths = [*names, *extra_paths]
    return {"session": session, "git": checkpoint(workspace, paths, snapshot, message), "deliverables": paths}


def start_code(workspace, record):
    from .context import require_writable_request
    require_writable_request(record)
    workspace = Path(workspace).resolve()
    if not workspace.is_dir():
        raise ValueError("Code work needs an existing assignment directory")
    if not isinstance(record, dict):
        raise ValueError("Code input must be a JSON object")
    if "code" not in record.get("scope", {}).get("authorized_behaviors", []):
        raise ValueError("Current scope must authorize implementation/repair; ask before changing code")
    text(record.get("request"), "Current request")
    text(record.get("scope", {}).get("goal"), "Current goal")
    code_paths = record.get("code_paths")
    checks = record.get("checks")
    if not isinstance(code_paths, list) or not code_paths or len(code_paths) != len(set(code_paths)):
        raise ValueError("Declare the explicit implementation files before editing")
    for name in code_paths:
        local_code_path(workspace, name)
    if not isinstance(checks, list) or not checks:
        raise ValueError("Code work needs independently justified correctness checks")
    ids, dependencies = set(), {}
    for check in checks:
        check_id = text(check.get("id"), "Check ID")
        if check_id in ids:
            raise ValueError("Check IDs must be unique")
        ids.add(check_id)
        text(check.get("issue_id"), "Check issue ID")
        if check.get("kind") not in {"teacher", "boundary", "oracle", "regression"}:
            raise ValueError("Check kind must describe its independent validation role")
        spec = check.get("execution", {})
        validate_request({**record, "execution": spec})
        if spec.get("purposes") != ["correctness"] or not spec.get("expected"):
            raise ValueError("Code checks need correctness purpose and an independent expectation")
        for name in [*spec.get("source_paths", []), *spec.get("input_paths", []), *([spec["stdin_path"]] if "stdin_path" in spec else [])]:
            path = Path(name)
            path = path if path.is_absolute() else workspace / path
            if path.resolve() not in [local_code_path(workspace, p) for p in code_paths]:
                if not path.is_file():
                    raise ValueError("Fixed test/input dependencies must exist before the coding session")
                dependencies[str(path.resolve())] = fingerprint(path)
    previous_state(workspace)
    snapshot = begin_task(workspace)
    session = {"id": uuid.uuid4().hex, "assignment": deepcopy(record["assignment"]),
               "request": record["request"], "scope": deepcopy(record["scope"]),
               "code_paths": code_paths, "checks": deepcopy(checks), "fixed_dependencies": dependencies,
               "created_at": now(), "status": "ready", "steps": [], "latest_checks": {},
               "issues": {}, "next_steps": record.get("next_steps", ["Implement within the recorded constraints, then run the fixed checks."]),
               "task_snapshot": {"root": str(snapshot.root), "dirty_paths": sorted(snapshot.dirty_paths)},
               "code_identity": {p: content_identity(local_code_path(workspace, p)) for p in code_paths}}
    return save_session(workspace, session, snapshot, "coursework: begin code implementation and validation")


def step_code(workspace, record):
    from .context import require_writable_request
    require_writable_request(record)
    workspace = Path(workspace).resolve()
    previous = read_state(workspace)
    session = next((deepcopy(s) for s in previous.get("code_sessions", []) if s["id"] == record.get("session_id")), None)
    if not session:
        raise ValueError("Unknown coding session")
    if previous["scope"] != session["scope"] or previous["request"] != session["request"]:
        raise ValueError("Task request/scope changed; establish a fresh authorized code session")
    text(record.get("note"), "Implementation/verification note")
    changes = record.get("changes", [])
    if not isinstance(changes, list):
        raise ValueError("changes must list explicit staged replacements")
    issue_id = record.get("issue_id")
    diagnosis = record.get("diagnosis")
    prior_failures = {c["check_id"] for c in session["latest_checks"].values() if c["status"] != "passed" and c["issue_id"] == issue_id}
    review = record.get("requirements_review", [])
    if not isinstance(review, list) or any(not isinstance(r, dict) or r.get("status") not in {"passed", "failed", "unverified"}
                                         or not r.get("requirement") or not r.get("basis") for r in review):
        raise ValueError("requirements_review needs attributed requirement/status/basis entries")
    if "next_steps" in record and (not isinstance(record["next_steps"], list) or any(not isinstance(n, str) or not n.strip() for n in record["next_steps"])):
        raise ValueError("next_steps must list concrete continuation notes")
    if changes and session["steps"]:
        text(issue_id, "Target issue ID")
        if session["issues"].get(issue_id, {}).get("status") == "paused":
            raise ValueError("This issue paused after three targeted repairs without progress; ask the user before resuming it")
        if not isinstance(diagnosis, dict) or diagnosis.get("category") != "implementation":
            raise ValueError("Before editing a failed implementation, diagnose environment/input/oracle/implementation causes")
        for key in ["finding", "prediction"]:
            text(diagnosis.get(key), "Diagnosis " + key)
        failing = {c["run_id"] for c in session["latest_checks"].values() if c["status"] != "passed" and c["issue_id"] == issue_id}
        if not failing or not set(diagnosis.get("basis_run_ids", [])) <= failing or not diagnosis.get("basis_run_ids"):
            raise ValueError("Diagnosis must cite the actual failing checks for this issue")
        progress = record.get("progress", {})
        if progress.get("status") not in {"made", "none"}:
            raise ValueError("Record the agent's progress prediction as made/none with a substantive note")
        text(progress.get("note"), "Progress prediction")
    for name, digest in session["fixed_dependencies"].items():
        if content_identity(Path(name)) != digest:
            raise ValueError("Fixed test/input changed; preserve correct expectations and review the source before starting a new session")
    for name, digest in session["code_identity"].items():
        if content_identity(local_code_path(workspace, name)) != digest:
            raise ValueError("Implementation changed outside the saved session; review and start a fresh snapshot before applying replacements")
    replacements = []
    seen = set()
    for change in changes:
        name = change.get("path")
        if name not in session["code_paths"] or name in seen:
            raise ValueError("Changes must name distinct declared implementation paths")
        seen.add(name)
        path = local_code_path(workspace, name)
        if change.get("expected_sha256") != content_identity(path):
            raise ValueError("Implementation bytes differ from expected_sha256; preserve concurrent/user edits")
        staged = Path(change.get("staged_path", ""))
        if not staged.is_file() or staged.resolve().is_relative_to(workspace):
            raise ValueError("Stage replacement bytes outside the assignment before applying")
        data = staged.read_bytes()
        if path.is_file() and data == path.read_bytes():
            raise ValueError("A repair attempt must contain an actual targeted code change")
        replacements.append((name, path, data))
    snapshot = begin_task(workspace)
    protected_path(workspace, f"{STATE_DIR}/state.json", snapshot)
    step_id = uuid.uuid4().hex
    relative = f"{STATE_DIR}/code/{session['id']}/steps/{step_id}"
    directory = protected_path(workspace, relative, snapshot)
    if directory.exists():
        raise ValueError("Code attempt evidence is immutable")
    files = []
    for index, (name, path, data) in enumerate(replacements):
        directory.mkdir(parents=True, exist_ok=True)
        before = directory / f"{index:04d}-before.bin"
        if path.is_file():
            before.write_bytes(path.read_bytes())
            files.append(before.relative_to(workspace).as_posix())
        after = directory / f"{index:04d}-after.bin"
        after.write_bytes(data)
        files.append(after.relative_to(workspace).as_posix())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    session["code_identity"] = {p: content_identity(local_code_path(workspace, p)) for p in session["code_paths"]}
    attempt = {"id": step_id, "note": record["note"], "issue_id": issue_id, "diagnosis": diagnosis,
               "progress": record.get("progress"), "changes": [{"path": p, "sha256": fingerprint(target)} for p, target, _ in replacements],
               "started_at": now(), "status": "in_progress", "evidence_directory": relative,
               "code_identity": session["code_identity"], "checks": []}
    attempt_path = f"{relative}/attempt.json"
    write_json(workspace / attempt_path, attempt)
    session["steps"].append(attempt)
    session["status"] = "in_progress"
    session["next_steps"] = ["Inspect this saved attempt and actual run records if verification was interrupted; do not infer success."]
    save_session(workspace, session, snapshot, "coursework: preserve implementation attempt before validation", [*files, attempt_path])
    outcomes = []
    for check in session["checks"]:
        if session["issues"].get(check["issue_id"], {}).get("status") == "paused":
            continue
        run_record = {"assignment": session["assignment"], "request": session["request"], "scope": session["scope"],
                      "result_key": f"code-{session['id']}-{check['id']}", "execution": check["execution"]}
        result = save_run(workspace, run_record)
        execution = result["run"].get("execution", {})
        valid = next((r["status"] == "valid" for r in result["results"] if r["id"] == result["run"]["id"]), False)
        outcome = {"check_id": check["id"], "issue_id": check["issue_id"], "run_id": result["run"]["id"],
                   "status": "passed" if valid and result["run"]["status"] == "completed" and execution.get("check", {}).get("status") == "passed" else "failed",
                   "evidence_path": result["run"]["evidence_path"], "reused": result["reused"]}
        outcomes.append(outcome)
        session["latest_checks"][check["id"]] = outcome
    for group in {c["issue_id"] for c in session["checks"]}:
        group_checks = [c for c in session["latest_checks"].values() if c["issue_id"] == group]
        passed = group_checks and all(c["status"] == "passed" for c in group_checks)
        prior = session["issues"].get(group, {"no_progress": 0, "status": "unverified"})
        streak = prior["no_progress"]
        if changes and group == issue_id:
            current_failures = {c["check_id"] for c in group_checks if c["status"] != "passed"}
            improved = passed or current_failures < prior_failures
            attempt["progress_signal"] = {"basis": "Actual fixed-case failure set; success or a strict reduction counts as progress for this bounded suite.",
                                          "before_failed_checks": sorted(prior_failures), "after_failed_checks": sorted(current_failures),
                                          "status": "made" if improved else "none"}
        if passed:
            streak = 0
        elif changes and group == issue_id:
            streak = 0 if improved else streak + 1
        session["issues"][group] = {"status": "passed" if passed else "paused" if streak >= 3 else "needs_diagnosis",
                                    "no_progress": streak}
    session["requirements_review"] = review
    all_pass = len(session["latest_checks"]) == len(session["checks"]) and all(c["status"] == "passed" for c in session["latest_checks"].values())
    paused = any(v["status"] == "paused" for v in session["issues"].values())
    session["status"] = "verified" if all_pass and review and all(r["status"] == "passed" for r in review) else "partial_paused" if paused else "needs_review" if all_pass else "needs_repair"
    session["next_steps"] = record.get("next_steps", ["Continue independent authorized work; ask about the paused issue." if paused else "Diagnose actual failures or finish the requirements review."])
    completed = {**attempt, "status": session["status"], "finished_at": now(), "checks": outcomes,
                 "requirements_review": review, "next_steps": session["next_steps"]}
    session["steps"][-1] = completed
    step_path = f"{relative}/result.json"
    finish_snapshot = begin_task(workspace)
    write_json(workspace / step_path, completed)
    result = save_session(workspace, session, finish_snapshot,
                          f"coursework: code validation {session['status']}", [step_path])
    original = TaskSnapshot(Path(session["task_snapshot"]["root"]), frozenset(session["task_snapshot"]["dirty_paths"]))
    code_commit = checkpoint(workspace, [p for p, _, _ in replacements], original,
                             f"coursework: implementation {session['status']}") if replacements else {"commit": None, "skipped_preexisting": []}
    return {**result, "step": completed, "implementation_git": code_commit, **resume(workspace)}
