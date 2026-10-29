"""Execute explicit argv and preserve facts; purpose and correctness reasoning stay with the agent."""
from datetime import datetime, timezone
import hashlib
import json
import os
import math
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import uuid

from .context import SCHEMA_VERSION, STATE_DIR, fingerprint, read_state, resume, write_json
from .git import begin_task, checkpoint, git


def now():
    return datetime.now(timezone.utc).isoformat()


def protected_path(workspace, name, snapshot):
    path = workspace / name
    if not path.is_relative_to(workspace) or path.resolve() != path:
        raise ValueError(f"Managed output must stay inside assignment without filesystem links: {name}")
    if path.relative_to(snapshot.root).as_posix() in snapshot.dirty_paths:
        raise ValueError(f"Preserved preexisting user change: {name}; reconcile before running")
    return path


def blob(workspace, directory, name, data):
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    preview = data.decode("utf-8", errors="replace")
    return {"path": path.relative_to(workspace).as_posix(), "sha256": fingerprint(path),
            "size_bytes": len(data), "text": preview,
            "text_decoding": {"encoding": "utf-8", "errors": "replace", "lossless": preview.encode("utf-8") == data}}


def source_state(workspace, spec, directory, snapshot):
    files = []
    relevant_git_paths = set()
    names = spec["source_paths"] + spec.get("input_paths", [])
    if "stdin_path" in spec:
        names += [spec["stdin_path"]]
    for index, name in enumerate(dict.fromkeys(names)):
        path = Path(name)
        path = (path if path.is_absolute() else workspace / path).resolve()
        if path.is_relative_to(snapshot.root) and path != snapshot.root and not path.is_dir():
            relevant_git_paths.add(path.relative_to(snapshot.root).as_posix())
        item = {"path": path.relative_to(workspace).as_posix() if path.is_relative_to(workspace) else str(path)}
        if path.is_file():
            item.update(blob(workspace, directory, f"files/{index:04d}.bin", path.read_bytes()))
            # `path` identifies the live source; snapshot_path identifies the captured bytes.
            item["snapshot_path"] = item.pop("path")
            item["path"] = path.relative_to(workspace).as_posix() if path.is_relative_to(workspace) else str(path)
            item.pop("text")
            item["status"] = "present"
        else:
            item["status"] = "missing"
        files.append(item)
    head = git(snapshot.root, "rev-parse", "HEAD", check=False)
    literal = [":(literal)" + name for name in sorted(relevant_git_paths)]
    # An empty pathspec means the entire repository to Git. External declared
    # dependencies get exact byte snapshots, but never widen this patch scope.
    staged = git(snapshot.root, "diff", "--cached", "--binary", "--no-ext-diff", "--no-renames", "--", *literal).stdout if literal else b""
    unstaged = git(snapshot.root, "diff", "--binary", "--no-ext-diff", "--no-renames", "--", *literal).stdout if literal else b""
    return {"git_root": str(snapshot.root),
            "head": head.stdout.decode("ascii").strip() if not head.returncode else None,
            "status": git(snapshot.root, "status", "--porcelain=v1", "-z").stdout.decode("utf-8", errors="replace"),
            "patch_scope": sorted(relevant_git_paths),
            "staged_diff": blob(workspace, directory, "staged.patch", staged),
            "unstaged_diff": blob(workspace, directory, "unstaged.patch", unstaged),
            "files": files}


def resolve_executable(workspace, spec, environment):
    name = spec["argv"][0]
    cwd = (workspace / spec.get("cwd", ".")).resolve()
    if Path(name).is_absolute() or any(separator in name for separator in ["/", "\\"]):
        return shutil.which(str((cwd / name).resolve()), path=environment.get("PATH"))
    search = os.pathsep.join(str((cwd / entry).resolve()) for entry in os.get_exec_path(environment))
    found = shutil.which(name, path=search)
    return str(Path(found).resolve()) if found else None


def execution_identity(workspace, spec):
    environment = {**os.environ, **spec.get("env", {})}
    executable = resolve_executable(workspace, spec, environment)
    return {"argv": spec["argv"], "cwd": str((workspace / spec.get("cwd", ".")).resolve()),
            "executable": executable,
            "executable_sha256": fingerprint(executable) if executable and Path(executable).is_file() else None,
            "environment_sha256": hashlib.sha256(json.dumps(sorted(environment.items()), ensure_ascii=False).encode("utf-8")).hexdigest()}


def files_unchanged(workspace, source):
    for item in source["files"]:
        path = Path(item["path"])
        path = path if path.is_absolute() else workspace / path
        if not path.is_file() or fingerprint(path) != item.get("sha256"):
            return False
    return True


def execution_unchanged(workspace, spec, source, identity):
    """Compare declared bytes and the executable/environment to their saved plan."""
    return files_unchanged(workspace, source) and execution_identity(workspace, spec) == identity


def prepare_trial(workspace, spec, trial, directory, snapshot):
    """Normalize trial overrides and capture the full plan before any trial runs.

    Receipts and persistence belong to the caller; this needs no registered state.
    """
    trial_spec = {**spec, **trial}
    if 'stdin_path' in trial:
        trial_spec.pop('stdin_text', None)
    elif 'stdin_text' in trial:
        trial_spec.pop('stdin_path', None)
    trial_spec.pop('expected', None)
    if 'expected' in trial:
        trial_spec['expected'] = trial['expected']
    plan_spec = {**spec, 'source_paths': [*spec['source_paths'], *trial.get('source_paths', []),
                                        *trial.get('input_paths', [])]}
    if 'stdin_path' in trial:
        plan_spec['source_paths'].append(trial['stdin_path'])
    source = source_state(workspace, plan_spec, directory, snapshot)
    return trial_spec, source, execution_identity(workspace, spec)


def execute(workspace, spec, directory, snapshot):
    directory.mkdir(parents=True)
    record = {"requested_argv": spec["argv"], "argv": list(spec["argv"]),
              "cwd": str((workspace / spec.get("cwd", ".")).resolve()), "started_at": now(),
              "source_before": source_state(workspace, spec, directory / "before", snapshot)}
    environment = os.environ.copy()
    environment.update(spec.get("env", {}))
    executable = resolve_executable(workspace, spec, environment)
    record["environment"] = {
        "platform": platform.platform(), "machine": platform.machine(),
        "runtime_python": sys.version, "runtime_executable": sys.executable,
        "executable": executable,
        "executable_sha256": fingerprint(executable) if executable and Path(executable).is_file() else None,
        "inherited_environment_sha256": hashlib.sha256(json.dumps(sorted(environment.items()), ensure_ascii=False).encode("utf-8")).hexdigest(),
        "overrides": spec.get("env", {}),
        "selected": {key: environment.get(key) for key in ["PATH", "LANG", "LC_ALL", "PYTHONPATH", *spec.get("capture_env", [])]},
    }
    started = time.monotonic()
    try:
        missing = [f["path"] for f in record["source_before"]["files"] if f["status"] == "missing"]
        if missing:
            raise FileNotFoundError("Missing declared source/input: " + ", ".join(missing))
        if "stdin_path" in spec:
            input_path = Path(spec["stdin_path"])
            data = (input_path if input_path.is_absolute() else workspace / input_path).read_bytes()
        else:
            data = spec.get("stdin_text", "").encode("utf-8")
        record["stdin"] = blob(workspace, directory, "stdin.bin", data)
        if not executable:
            raise FileNotFoundError(f"Executable unavailable: {spec['argv'][0]}")
        record["argv"][0] = executable
        result = subprocess.run(record["argv"], cwd=record["cwd"], input=data,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
        record["exit_code"] = result.returncode
        record["stdout"] = blob(workspace, directory, "stdout.bin", result.stdout)
        record["stderr"] = blob(workspace, directory, "stderr.bin", result.stderr)
        expected = spec.get("expected")
        if expected:
            comparisons = {}
            for key in ["stdout", "stderr"]:
                if key in expected:
                    comparisons[key] = result.__getattribute__(key) == expected[key].encode("utf-8")
            if "exit_code" in expected:
                comparisons["exit_code"] = result.returncode == expected["exit_code"]
            record["check"] = {"status": "passed" if all(comparisons.values()) else "failed",
                               "comparisons": comparisons, "expected": expected}
        else:
            record["check"] = {"status": "unverified", "reason": "No independent expected output was supplied"}
        expected_exit = expected.get("exit_code", 0) if expected else 0
        record["status"] = "completed" if result.returncode == expected_exit else "failed"
        if record["check"]["status"] == "failed":
            record["status"] = "failed"
    except OSError as exc:
        record.update(status="not_started", exit_code=None, diagnostic=str(exc),
                      check={"status": "unverified", "reason": "Execution could not start"})
    record["elapsed_seconds"] = time.monotonic() - started
    record["finished_at"] = now()
    record["source_after"] = source_state(workspace, spec, directory / "after", snapshot)
    record["outputs"] = []
    for index, name in enumerate(spec.get("output_paths", [])):
        path = Path(name)
        path = path if path.is_absolute() else workspace / path
        item = {"path": name, "status": "missing"}
        if path.is_file():
            item = blob(workspace, directory, f"outputs/{index:04d}.bin", path.read_bytes())
            item["snapshot_path"] = item.pop("path")
            item.update(path=name, status="present")
            item.pop("text")
        record["outputs"].append(item)
    return record


def scope_allows_run(scope, specification, *, role="run"):
    if scope.get("read_only") or scope.get("report_mode") == "review":
        return False
    authorized = scope.get("authorized_behaviors", [])
    if role in {"analyze", "report"}:
        return role in authorized
    if role != "run":
        return False
    support = specification.get("report_support", {})
    return "run" in authorized or ("code" in authorized and set(specification.get("purposes", [])) == {"correctness"}) or (
        "report" in authorized and scope.get("report_mode") != "review" and isinstance(support, dict)
        and isinstance(support.get("basis"), str) and bool(support["basis"].strip()))


def validate_request(record, *, role="run"):
    if not isinstance(record, dict):
        raise ValueError("Run input must be a JSON object")
    for key in ["assignment", "scope", "execution"]:
        if not isinstance(record.get(key), dict):
            raise ValueError(f"Run input needs {key}")
    if not isinstance(record["assignment"].get("title"), str) or not record["assignment"]["title"].strip() or not isinstance(record.get("request"), str) or not record["request"].strip():
        raise ValueError("Run input needs assignment title and current request")
    scope, spec = record["scope"], record["execution"]
    if not isinstance(scope.get("goal"), str) or not scope["goal"].strip() or not isinstance(scope.get("authorized_behaviors"), list):
        raise ValueError("Run input needs an explicit current scope")
    if not scope["authorized_behaviors"] or any(not isinstance(item, str) or item not in {"plan", "code", "run", "analyze", "report", "check"} for item in scope["authorized_behaviors"]):
        raise ValueError("Current scope needs recognized authorized behaviors")
    purposes = spec.get("purposes")
    if not isinstance(purposes, list) or not purposes or any(not isinstance(p, str) for p in purposes) or set(purposes) - {"correctness", "example", "experiment"}:
        raise ValueError("Execution needs recognized purposes")
    report_support = spec.get("report_support")
    if report_support is not None and (not isinstance(report_support, dict) or not isinstance(report_support.get("basis"), str) or not report_support["basis"].strip()):
        raise ValueError("report_support needs the actual basis for a necessary existing-code report run")
    if not scope_allows_run(scope, spec, role=role):
        raise ValueError("Current scope must authorize run, necessary code validation, or an explicit existing-code report supplement")
    if not isinstance(spec.get("basis"), str) or not spec["basis"].strip():
        raise ValueError("Record the assignment/user basis for this execution")
    coverage = spec.get("dependency_coverage")
    if coverage is not None and (not isinstance(coverage, dict) or coverage.get("status") not in {"complete", "partial", "unknown"}
                                 or not isinstance(coverage.get("note"), str) or not coverage["note"].strip()):
        raise ValueError("dependency_coverage needs complete/partial/unknown status and actual inspection note")
    if "material_ids" in spec and (not isinstance(spec["material_ids"], list) or any(not isinstance(i, str) or not i for i in spec["material_ids"])):
        raise ValueError("material_ids must list known source IDs")
    if "force_rerun" in record and not isinstance(record["force_rerun"], bool):
        raise ValueError("force_rerun must be a boolean recording the explicit decision to rerun")
    for key in ["argv", "source_paths"]:
        if not isinstance(spec.get(key), list) or not spec[key] or any(not isinstance(v, str) or not v for v in spec[key]):
            raise ValueError(f"execution.{key} must be nonempty literal strings")
    if "stdin_text" in spec and "stdin_path" in spec:
        raise ValueError("Choose stdin_text or stdin_path")
    expected = spec.get("expected")
    if expected is not None and (not isinstance(expected, dict) or not expected.get("basis") or
                                 not any(k in expected for k in ["stdout", "stderr", "exit_code"])):
        raise ValueError("Expected results need independent basis and a comparison")
    for value in [record.get("budget_seconds", 1800), spec.get("workload_units", 1)]:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError("Budget and workload units must be positive finite numbers")
    if "trial" in record:
        trial = record["trial"]
        if not isinstance(trial, dict) or not isinstance(trial.get("argv"), list) or not trial["argv"] or any(not isinstance(a, str) or not a for a in trial["argv"]):
            raise ValueError("Trial needs literal argv")
        units = trial.get("workload_units")
        if isinstance(units, bool) or not isinstance(units, (int, float)) or not math.isfinite(units) or units <= 0:
            raise ValueError("Trial needs positive finite workload_units")
        if set(trial) - {"argv", "stdin_text", "stdin_path", "input_paths", "source_paths", "output_paths", "expected", "workload_units"}:
            raise ValueError("Trial may vary only argv, inputs, declared sources, independent expected output and workload units")
    elif spec.get("requires_trial"):
        raise ValueError("This long execution needs a trial before estimation")
    for execution in [spec, *([record["trial"]] if "trial" in record else [])]:
        if "stdin_text" in execution and "stdin_path" in execution:
            raise ValueError("Choose stdin_text or stdin_path")
        for key in ["source_paths", "input_paths", "output_paths", "capture_env"]:
            if key in execution and (not isinstance(execution[key], list) or any(not isinstance(v, str) or not v for v in execution[key])):
                raise ValueError(f"{key} must be a list of nonempty strings")
        for key in ["stdin_path", "cwd"]:
            if key in execution and (not isinstance(execution[key], str) or not execution[key]):
                raise ValueError(f"{key} must be a nonempty path")
        if "stdin_text" in execution and not isinstance(execution["stdin_text"], str):
            raise ValueError("stdin_text must be a string")
        if "env" in execution and (not isinstance(execution["env"], dict) or any(not isinstance(k, str) or not k or not isinstance(v, str) for k, v in execution["env"].items())):
            raise ValueError("env must map nonempty environment names to string values")
        if any("\0" in item for item in execution.get("argv", [])) or any("=" in k or "\0" in k or "\0" in v for k, v in execution.get("env", {}).items()):
            raise ValueError("Arguments and environment must be valid literal process values")
        expected = execution.get("expected")
        if expected is not None:
            if not isinstance(expected, dict) or not isinstance(expected.get("basis"), str) or not expected["basis"].strip() or not any(k in expected for k in ["stdout", "stderr", "exit_code"]):
                raise ValueError("Expected results need independent basis and a comparison")
            if any(k in expected and not isinstance(expected[k], str) for k in ["stdout", "stderr"]) or ("exit_code" in expected and (isinstance(expected["exit_code"], bool) or not isinstance(expected["exit_code"], int))):
                raise ValueError("Expected output must be text and expected exit_code must be an integer")
    return record


def save_run(workspace, record):
    from .context import require_writable_request
    require_writable_request(record)
    workspace = Path(workspace).resolve()
    record = validate_request(record)
    if not workspace.is_dir():
        raise ValueError("Direct execution needs an existing assignment directory")
    state_dir = workspace / STATE_DIR
    if state_dir.resolve() != state_dir:
        raise ValueError("The coursework state directory must not be a filesystem link")
    from .context import previous_state
    previous = previous_state(workspace)
    from .results import reusable_result, result_key, material_versions
    result_key(record)
    material_versions(previous, record["execution"])
    reusable = reusable_result(workspace, previous, record)
    if reusable and not record.get("force_rerun", False):
        return {**resume(workspace), "result": reusable, "reused": True,
                "run": next(r for r in previous["runs"] if r["id"] == reusable["run_id"]),
                "git": {"commit": None, "skipped_preexisting": []}, "deliverables": []}
    snapshot = begin_task(workspace)
    revision = previous.get("revision", 0) + 1
    run_id = uuid.uuid4().hex
    relative = f"{STATE_DIR}/runs/{run_id}"
    for name in [f"{STATE_DIR}/state.json", f"{STATE_DIR}/history/{revision:04d}.json", relative,
                 f"{STATE_DIR}/results/{run_id}"]:
        path = protected_path(workspace, name, snapshot)
        if name != f"{STATE_DIR}/state.json" and path.exists():
            raise ValueError("Run evidence and history are immutable")
    run = {"id": run_id, "request": record["request"], "scope": record["scope"],
           "result_key": result_key(record),
           "specification": record["execution"], "created_at": now(),
           "budget": {"limit_seconds": record.get("budget_seconds", 1800),
                      "is_default": "budget_seconds" not in record, "hard_timeout": False,
                      "estimate_basis": record.get("estimate_basis", "Observed trial elapsed multiplied by production/trial workload units; includes trial cost")}}
    if "trial" in record:
        trial_spec, run["plan_state"], run["plan_identity"] = prepare_trial(
            workspace, record["execution"], record["trial"], workspace / relative / "plan", snapshot)
        run["trial"] = execute(workspace, trial_spec, workspace / relative / "trial", snapshot)
        estimated = run["trial"]["elapsed_seconds"] * record["execution"].get("workload_units", 1) / record["trial"]["workload_units"]
        run["budget"].update(estimated_seconds=estimated,
                             trial_seconds=run["trial"]["elapsed_seconds"],
                             estimated_total_seconds=estimated + run["trial"]["elapsed_seconds"])
        if run["trial"]["status"] != "completed":
            run["status"] = "trial_failed"
        elif not execution_unchanged(workspace, record["execution"], run["plan_state"], run["plan_identity"]):
            run["status"] = "trial_failed"
            run["diagnostic"] = "Source/input/execution environment changed during trial; prepare a fresh plan"
        elif run["budget"]["estimated_total_seconds"] > run["budget"]["limit_seconds"]:
            run["status"] = "awaiting_confirmation"
        else:
            run["execution"] = execute(workspace, record["execution"], workspace / relative / "execution", snapshot)
            run["status"] = run["execution"]["status"]
    else:
        run["plan_state"] = source_state(workspace, record["execution"], workspace / relative / "plan", snapshot)
        run["plan_identity"] = execution_identity(workspace, record["execution"])
        run["execution"] = execute(workspace, record["execution"], workspace / relative / "execution", snapshot)
        run["status"] = run["execution"]["status"]
    return persist_run(workspace, previous, record, run, relative, snapshot, revision)


def persist_run(workspace, previous, record, run, relative, snapshot, revision):
    if run["status"] in {"failed", "trial_failed", "not_started"}:
        run["follow_up"] = {"status": "needs_diagnosis",
                            "implementation_edits_authorized": "code" in record["scope"]["authorized_behaviors"],
                            "instruction": "Inspect actual command, inputs, environment, independent expectations and code before classifying the cause",
                            "scope_decision_if_implementation_change_needed": "Ask the user to authorize code changes when code is outside current scope"}
    run["evidence_path"] = relative + "/record.json"
    run["summary_path"] = relative + "/run.md"
    runs = [item for item in previous.get("runs", []) if item["id"] != run["id"]]
    state = {**previous, "kind": "coursework-context", "schema_version": SCHEMA_VERSION,
             "assignment": record["assignment"], "request": record["request"], "scope": record["scope"],
             "sources": previous.get("sources", []), "questions": previous.get("questions", []),
             "revision": revision, "updated_at": now(), "runs": [*runs, run]}
    state["result_requests"] = {**previous.get("result_requests", {}), run["result_key"]: run["specification"]}
    write_json(workspace / relative / "record.json", run)
    (workspace / relative / "run.md").write_text(render_run(run), encoding="utf-8")
    from .results import register_run_result
    result, result_paths = register_run_result(workspace, state, {**record, "result_key": run["result_key"], "execution": run["specification"]}, run)
    write_json(workspace / STATE_DIR / "state.json", state)
    write_json(workspace / STATE_DIR / "history" / f"{revision:04d}.json", state)
    paths = [p.relative_to(workspace).as_posix() for p in (workspace / relative).rglob("*") if p.is_file()]
    paths += [f"{STATE_DIR}/state.json", f"{STATE_DIR}/history/{revision:04d}.json"]
    paths += result_paths
    commit = checkpoint(workspace, paths, snapshot, f"coursework: record run {run['id']}")
    return {**resume(workspace), "run": run, "result": result, "reused": False,
            "git": commit, "deliverables": paths}


def render_run(run):
    lines = ["# Actual coursework run", "", f"- Run: {run['id']}", f"- Status: {run['status']}",
             "", run["request"], "", "- Authorized behaviors: " + ", ".join(run["scope"]["authorized_behaviors"]),
             "- Purposes: " + ", ".join(run["specification"]["purposes"]),
             "- Basis: " + run["specification"]["basis"], "", "## Budget", "", "```json",
             json.dumps(run["budget"], ensure_ascii=False, indent=2), "```"]
    if run.get("diagnostic"):
        lines += ["", "Diagnostic: " + run["diagnostic"]]
    for label in ["trial", "execution"]:
        actual = run.get(label)
        if not actual:
            continue
        lines += ["", "## " + label, "", "- Actual argv: " + json.dumps(actual["argv"], ensure_ascii=False),
                  "- Working directory: " + actual["cwd"], f"- Exit code: {actual['exit_code']}",
                  f"- Elapsed seconds: {actual['elapsed_seconds']:.6f}", "- Check: " + actual["check"]["status"]]
        if actual.get("diagnostic"):
            lines.append("Diagnostic: " + actual["diagnostic"])
        for stream in ["stdin", "stdout", "stderr"]:
            if stream in actual:
                lines.append(f"- {stream}: {actual[stream]['path']} (sha256 {actual[stream]['sha256']})")
        lines += ["", "Source state: " + str(actual["source_before"]["head"])]
        for source in actual["source_before"]["files"]:
            lines.append(f"- {source['path']}: {source.get('sha256', 'missing')}")
    lines += ["", "Full execution facts and captured bytes are in record.json and the sibling evidence directories."]
    return "\n".join(lines) + "\n"


def confirm_run(workspace, run_id, confirmation):
    """Confirmation is agent-supplied evidence of a real user reply, never inferred by this helper."""
    if not isinstance(confirmation, str) or not confirmation.strip():
        raise ValueError("Supply the user's explicit confirmation text")
    workspace = Path(workspace).resolve()
    previous = read_state(workspace)
    candidates = [run for run in previous.get("runs", []) if run["id"] == run_id]
    if not candidates or candidates[0]["status"] != "awaiting_confirmation":
        raise ValueError("Confirmation must identify a saved run awaiting confirmation")
    run = candidates[0]
    from .context import require_writable_request
    require_writable_request(previous)
    spec = run["specification"]
    if previous["scope"] != run["scope"] or previous["request"] != run["request"]:
        raise ValueError("Current task scope/request changed; prepare a fresh run plan")
    if not execution_unchanged(workspace, spec, run["plan_state"], run["plan_identity"]):
        raise ValueError("Source/input/executable/environment changed since trial; prepare a fresh run plan")
    snapshot = begin_task(workspace)
    revision = previous["revision"] + 1
    relative = f"{STATE_DIR}/runs/{run_id}/confirmations/{uuid.uuid4().hex}"
    for name in [f"{STATE_DIR}/state.json", f"{STATE_DIR}/history/{revision:04d}.json", relative,
                 f"{STATE_DIR}/results/{run_id}"]:
        path = protected_path(workspace, name, snapshot)
        if name != f"{STATE_DIR}/state.json" and path.exists():
            raise ValueError("Run evidence and history are immutable")
    run["confirmation"] = {"text": confirmation, "recorded_at": now()}
    run["execution"] = execute(workspace, spec, workspace / relative / "execution", snapshot)
    run["status"] = run["execution"]["status"]
    record = {"assignment": previous["assignment"], "request": run["request"], "scope": run["scope"],
              "result_key": run["result_key"]}
    return persist_run(workspace, previous, record, run, relative, snapshot, revision)
