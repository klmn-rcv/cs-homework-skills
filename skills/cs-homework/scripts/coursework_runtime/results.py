"""Versioned result identity and actual-file checks; semantic applicability stays with the agent."""
import hashlib
import json
import os
from pathlib import Path
import uuid
from datetime import datetime, timezone

from .context import STATE_DIR, fingerprint, write_json


def reuse_identity(workspace, specification):
    from .execution import execution_identity
    identity = execution_identity(workspace, specification)
    identity.pop("environment_sha256")
    environment = {**os.environ, **specification.get("env", {})}
    keys = set(specification.get("capture_env", [])) | set(specification.get("env", {}))
    identity["relevant_environment"] = {k: environment.get(k) for k in sorted(keys)}
    return identity


def result_key(record):
    key = record.get("result_key")
    if key is None:
        encoded = json.dumps(record["execution"], sort_keys=True, ensure_ascii=False).encode("utf-8")
        return "execution-" + hashlib.sha256(encoded).hexdigest()[:24]
    if not isinstance(key, str) or not key.strip() or len(key) > 128:
        raise ValueError("result_key must be a nonempty string of at most 128 characters")
    return key


def actual_path(workspace, name):
    path = Path(name)
    return path if path.is_absolute() else Path(workspace) / path


def file_issue(workspace, item, field="path"):
    path = actual_path(workspace, item[field])
    if not path.is_file():
        return {"path": item[field], "reason": "missing"}
    if fingerprint(path) != item.get("sha256"):
        return {"path": item[field], "reason": "changed"}
    return None


def material_versions(state, specification):
    sources = {s["id"]: s for s in state.get("sources", [])}
    versions = []
    for source_id in specification.get("material_ids", []):
        if source_id not in sources:
            raise ValueError(f"Unknown result material: {source_id}")
        source = sources[source_id]
        digest = source.get("sha256")
        if source["kind"] == "chat":
            digest = hashlib.sha256(source["content"].encode("utf-8")).hexdigest()
        versions.append({"source_id": source_id, "sha256": digest})
    return versions


def applicability(state, result):
    return next((r for r in reversed(state.get("result_reviews", [])) if r["result_id"] == result["id"]), result)


def immutable_issue(workspace, item):
    receipt = item["receipt"]
    issue = file_issue(workspace, receipt)
    if issue:
        return {**issue, "kind": "evidence"}
    saved = json.loads(actual_path(workspace, receipt["path"]).read_text(encoding="utf-8"))
    if saved != {k: v for k, v in item.items() if k != "receipt"}:
        return {"kind": "evidence", "path": receipt["path"], "reason": "Saved state differs from immutable record"}
    return None


def record_issues(workspace, item):
    issues = []
    issue = immutable_issue(workspace, item)
    if issue:
        issues.append(issue)
    for evidence in item.get("evidence", []):
        issue = file_issue(workspace, evidence)
        if issue:
            issues.append({**issue, "kind": "evidence"})
    return issues


def result_checks(workspace, state, *, materials=None, requested=None):
    desired = {**state.get("result_requests", {}), **(requested or {})}
    checks = []
    for result in state.get("results", []):
        current = applicability(state, result)
        issues = []
        evidence_items = [*result.get("evidence", [])]
        for saved in [result, *([current] if current is not result else [])]:
            issue = immutable_issue(workspace, saved)
            if issue:
                issues.append(issue)
        if current is not result:
            evidence_items += current.get("evidence", [])
        for evidence in evidence_items:
            if evidence:
                issue = file_issue(workspace, evidence)
                if issue:
                    issues.append({**issue, "kind": "evidence"})
        for dependency in current.get("dependencies", []):
            issue = file_issue(workspace, dependency)
            if issue:
                issues.append({**issue, "kind": "dependency"})
        if result["key"] in desired and current.get("specification") != desired[result["key"]]:
            issues.append({"kind": "parameters", "reason": "Current requested command/parameters differ from this result version"})
        if result.get("source_changed_during_execution"):
            issues.append({"kind": "execution_consistency", "reason": "Declared files changed during execution",
                           "paths": result["source_changed_during_execution"]})
        if result.get("missing_outputs"):
            issues.append({"kind": "output", "reason": "Declared output files were missing after execution",
                           "paths": result["missing_outputs"]})
        if current.get("execution_identity"):
            if reuse_identity(workspace, current["specification"]) != current["execution_identity"]:
                issues.append({"kind": "environment", "reason": "Executable or environment identity changed"})
        known_versions = {v["source_id"]: v["sha256"] for v in material_versions(state, current.get("specification", {}))}
        observed = {m["source_id"]: m for m in materials or []}
        for version in current.get("material_versions", []):
            source_id = version["source_id"]
            if known_versions.get(source_id) != version["sha256"] or observed.get(source_id, {}).get("status") not in {"unchanged", "recorded"}:
                issues.append({"kind": "material", "source_id": source_id,
                               "reason": "Material changed or its current applicability/freshness needs review"})
        status = "pending_update" if issues else "valid"
        if result.get("execution_status") != "completed":
            status = "failed"
        coverage = current.get("specification", {}).get("dependency_coverage", {})
        if not issues and status == "valid" and coverage.get("status") != "complete":
            status = "needs_review"
            issues.append({"kind": "coverage", "reason": "Declared dependencies are not confirmed complete"})
        if result.get("execution_status") == "completed" and issues and all(i["kind"] in {"material", "coverage"} for i in issues):
            status = "needs_review"
        checks.append({"id": result["id"], "key": result["key"], "origin": result["origin"],
                       "current": state.get("result_heads", {}).get(result["key"]) == result["id"],
                       "status": status, "issues": issues, "verification": result["verification"],
                       "applicability_review": current["receipt"] if current is not result else None,
                       "record_path": result["receipt"]["path"]})
    return checks


def artifact_checks(workspace, state, results):
    by_id = {r["id"]: r for r in results}
    analyses = {a["id"]: a for a in state.get("analyses", [])}
    computation_issues = {}
    checks = []
    for artifact in state.get("result_artifacts", []):
        issues = []
        analysis_id = artifact.get("analysis_id")
        if analysis_id:
            if analysis_id not in computation_issues:
                analysis = analyses.get(analysis_id)
                computation_issues[analysis_id] = (not analysis or analysis["status"] != "completed"
                                                   or bool(record_issues(workspace, analysis)))
            if computation_issues[analysis_id]:
                issues.append({"analysis_id": analysis_id, "reason": "Analysis computation evidence needs update"})
        for source_id in artifact["result_ids"]:
            source = by_id.get(source_id)
            if not source or not source["current"] or source["status"] != "valid":
                issues.append({"result_id": source_id, "reason": "Source result is no longer current and valid"})
        for item in [artifact, artifact["receipt"], {"path": artifact["snapshot_path"], "sha256": artifact["sha256"]}]:
            issue = file_issue(workspace, item)
            if issue:
                issues.append(issue)
        checks.append({"id": artifact["id"], "path": artifact["path"],
                       "current": state.get("artifact_heads", {}).get(artifact["path"]) == artifact["id"],
                       "status": "pending_update" if issues else "valid", "issues": issues,
                       "result_ids": artifact["result_ids"]})
    return checks


def reusable_result(workspace, state, record):
    key = result_key(record)
    head = state.get("result_heads", {}).get(key)
    candidate = next((r for r in state.get("results", []) if r["id"] == head), None)
    if not candidate:
        return None
    current = applicability(state, candidate)
    if current.get("specification") != record["execution"]:
        return None
    from .context import material_checks
    source_ids = {v["source_id"] for v in current.get("material_versions", [])}
    materials = material_checks(workspace, [s for s in state.get("sources", []) if s["id"] in source_ids])
    checks = result_checks(workspace, state, materials=materials, requested={key: record["execution"]})
    if next(c for c in checks if c["id"] == head)["status"] != "valid":
        return None
    if current.get("execution_identity") != reuse_identity(workspace, record["execution"]):
        return None
    return candidate


def register_run_result(workspace, state, record, run, *, persist=True):
    execution = run.get("execution")
    if not execution:
        return None, []
    before, after = execution["source_before"]["files"], execution["source_after"]["files"]
    evidence = [{"path": run["evidence_path"], "sha256": fingerprint(workspace / run["evidence_path"])}]
    for phase in [execution["source_before"], execution["source_after"]]:
        evidence += [phase["staged_diff"], phase["unstaged_diff"]]
        evidence += [{"path": f["snapshot_path"], "sha256": f["sha256"]} for f in phase["files"] if "snapshot_path" in f]
    evidence += [execution[k] for k in ["stdin", "stdout", "stderr"] if k in execution]
    evidence += [{"path": f["snapshot_path"], "sha256": f["sha256"]} for f in execution["outputs"] if "snapshot_path" in f]
    environment = execution["environment"]
    spec = run["specification"]
    relevant_keys = set(spec.get("capture_env", [])) | set(spec.get("env", {}))
    identity = {"argv": execution["requested_argv"], "cwd": execution["cwd"],
                "executable": environment["executable"], "executable_sha256": environment["executable_sha256"],
                "relevant_environment": {k: spec.get("env", {}).get(k, environment["selected"].get(k)) for k in sorted(relevant_keys)}}
    result = {"id": run["id"], "key": result_key(record), "origin": "workflow-run",
              "run_id": run["id"], "created_at": run["created_at"],
              "specification": run["specification"], "execution_identity": identity,
              "execution_status": execution["status"], "verification": execution["check"],
              "dependencies": before, "evidence": evidence,
              "material_versions": material_versions(state, run["specification"]),
              "source_changed_during_execution": [(a["path"]) for a, b in zip(before, after)
                                                   if a.get("sha256") != b.get("sha256")],
              "missing_outputs": [f["path"] for f in execution["outputs"] if f["status"] == "missing"]}
    if not persist:
        return result, []
    path = workspace / STATE_DIR / "results" / result["id"] / "record.json"
    if path.exists():
        raise ValueError("Result records are immutable")
    write_json(path, result)
    result["receipt"] = {"path": path.relative_to(workspace).as_posix(), "sha256": fingerprint(path)}
    state["results"] = [*state.get("results", []), result]
    state["result_heads"] = {**state.get("result_heads", {}), result["key"]: result["id"]}
    return result, [result["receipt"]["path"]]


def inspect_results(workspace, record=None, *, refresh_online=False):
    from .context import resume
    from .execution import scope_allows_run
    record = record or {}
    if not isinstance(record, dict):
        raise ValueError("Result inspection must be a JSON object")
    requested = {}
    items = record.get("requested_results", [])
    if not isinstance(items, list):
        raise ValueError("requested_results must be a list")
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str) or not item["key"] or not isinstance(item.get("specification"), dict):
            raise ValueError("Each requested result needs key and specification")
        if item["key"] in requested:
            raise ValueError("Each result key may have only one current specification")
        requested[item["key"]] = item["specification"]
    view = resume(workspace, refresh_online=refresh_online, requested_results=requested)
    for item in view["results"]:
        specification = requested.get(item["key"], view["state"].get("result_requests", {}).get(item["key"], {}))
        if not item["current"]:
            item["update_action"] = "historical_only"
        elif item["status"] == "valid":
            item["update_action"] = "reuse"
        elif item["status"] == "needs_review":
            item["update_action"] = "semantic_review_required"
        elif not scope_allows_run(record.get("scope", {}), specification):
            item["update_action"] = "scope_decision_required"
        else:
            item["update_action"] = "prepare_targeted_run_and_check_budget"
    return view


def prepare_context(workspace, record):
    from .context import read_state, SCHEMA_VERSION
    from .git import begin_task
    from .execution import protected_path
    workspace = Path(workspace).resolve()
    if not workspace.is_dir():
        raise ValueError("Existing-result work needs an existing assignment directory")
    for key in ["assignment", "scope"]:
        if not isinstance(record.get(key), dict):
            raise ValueError(f"Result work needs {key}")
    if not isinstance(record["assignment"].get("title"), str) or not record["assignment"]["title"].strip() or not isinstance(record.get("request"), str) or not record["request"].strip():
        raise ValueError("Result work needs assignment title and current request")
    scope = record["scope"]
    authorized = scope.get("authorized_behaviors")
    if not isinstance(scope.get("goal"), str) or not scope["goal"].strip() or not isinstance(authorized, list) or any(not isinstance(a, str) or a not in {"plan", "run", "analyze", "report", "check", "code"} for a in authorized) or not set(authorized) & {"run", "analyze", "report", "check", "code"}:
        raise ValueError("Result work needs an explicit authorized current scope")
    directory = workspace / STATE_DIR
    from .context import previous_state
    previous = previous_state(workspace)
    snapshot = begin_task(workspace)
    state = {**previous, "kind": "coursework-context", "schema_version": SCHEMA_VERSION,
             "assignment": record["assignment"], "request": record["request"], "scope": record["scope"],
             "sources": previous.get("sources", []), "questions": previous.get("questions", []),
             "revision": previous.get("revision", 0) + 1, "updated_at": datetime.now(timezone.utc).isoformat()}
    for name in [f"{STATE_DIR}/state.json", f"{STATE_DIR}/history/{state['revision']:04d}.json"]:
        path = protected_path(workspace, name, snapshot)
        if name.endswith(f"/{state['revision']:04d}.json") and path.exists():
            raise ValueError("Result history is immutable")
    return workspace, state, snapshot


def captured_files(workspace, directory, names):
    files = []
    for index, name in enumerate(names):
        source = actual_path(workspace, name)
        target = directory / f"{index:04d}.bin"
        target.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        target.write_bytes(data)
        files.append({"path": str(source.resolve()), "snapshot_path": target.relative_to(workspace).as_posix(),
                      "sha256": fingerprint(target), "size_bytes": len(data)})
    return files


def reserve_directory(workspace, directory, snapshot):
    from .execution import protected_path
    protected_path(workspace, directory.relative_to(workspace).as_posix(), snapshot)
    if directory.exists():
        raise ValueError("Evidence directories are immutable")


def persist_context(workspace, state, snapshot, directory, message, *, extra_paths=()):
    from .context import resume
    from .git import checkpoint
    write_json(workspace / STATE_DIR / "state.json", state)
    write_json(workspace / STATE_DIR / "history" / f"{state['revision']:04d}.json", state)
    paths = [p.relative_to(workspace).as_posix() for p in directory.rglob("*") if p.is_file()]
    paths += [f"{STATE_DIR}/state.json", f"{STATE_DIR}/history/{state['revision']:04d}.json", *extra_paths]
    commit = checkpoint(workspace, paths, snapshot, message)
    return {**resume(workspace), "git": commit, "deliverables": paths}


def import_result(workspace, record):
    from .context import require_writable_request
    require_writable_request(record)
    if not isinstance(record, dict):
        raise ValueError("External result input must be a JSON object")
    key = record.get("result_key")
    if not isinstance(key, str) or not key.strip() or len(key) > 128:
        raise ValueError("External results need a stable result_key")
    names = record.get("data_paths")
    if not isinstance(names, list) or not names or any(not isinstance(n, str) or not n for n in names):
        raise ValueError("External results need actual data_paths")
    provenance = record.get("provenance")
    if not isinstance(provenance, dict) or any(not isinstance(provenance.get(k), str) or not provenance[k].strip() for k in ["provided_by", "location", "description"]):
        raise ValueError("External results need provider, location and source description")
    verification = record.get("verification", {"status": "unverified", "note": "Only source bytes are archived; no independent correctness check was supplied"})
    if not isinstance(verification, dict) or verification.get("status") not in {"unverified", "independently_checked"} or not isinstance(verification.get("note"), str) or not verification["note"].strip():
        raise ValueError("External verification needs explicit status and note")
    verification_paths = verification.get("evidence_paths", [])
    if not isinstance(verification_paths, list) or any(not isinstance(n, str) or not n for n in verification_paths) or verification["status"] == "independently_checked" and not verification_paths:
        raise ValueError("An independent external check needs actual evidence_paths")
    for name in [*names, *verification_paths]:
        if not actual_path(workspace, name).is_file():
            raise ValueError(f"External result/evidence file is missing: {name}")
    workspace, state, snapshot = prepare_context(workspace, record)
    result_id = uuid.uuid4().hex
    directory = workspace / STATE_DIR / "results" / result_id
    reserve_directory(workspace, directory, snapshot)
    data = captured_files(workspace, directory / "data", names)
    verification_files = captured_files(workspace, directory / "verification", verification_paths)
    evidence = [{"path": f["snapshot_path"], "sha256": f["sha256"]} for f in [*data, *verification_files]]
    specification = {"data_paths": names, "parameters": record.get("parameters", {}),
                     "dependency_coverage": {"status": "complete", "note": "Only identity of supplied external data; no claim of correspondence to current implementation"}}
    result = {"id": result_id, "key": key, "origin": "external", "created_at": state["updated_at"],
              "provenance": provenance, "verification": {**verification, "evidence": verification_files},
              "specification": specification, "data": data, "dependencies": data,
              "evidence": evidence, "execution_status": "completed"}
    write_json(directory / "record.json", result)
    result["receipt"] = {"path": (directory / "record.json").relative_to(workspace).as_posix(),
                         "sha256": fingerprint(directory / "record.json")}
    state["results"] = [*state.get("results", []), result]
    state["result_heads"] = {**state.get("result_heads", {}), key: result_id}
    state["result_requests"] = {**state.get("result_requests", {}), key: specification}
    return {**persist_context(workspace, state, snapshot, directory, f"coursework: attribute external result {key}"), "result": result}


def link_results(workspace, record):
    from .context import require_writable_request
    require_writable_request(record)
    from .context import resume
    if not isinstance(record, dict) or not isinstance(record.get("artifact"), dict):
        raise ValueError("Link input needs artifact")
    item = record["artifact"]
    for key in ["path", "kind", "basis"]:
        if not isinstance(item.get(key), str) or not item[key].strip():
            raise ValueError(f"Artifact needs {key}")
    ids = item.get("result_ids")
    if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("Artifact needs unique exact result_ids")
    workspace = Path(workspace).resolve()
    source = actual_path(workspace, item["path"]).resolve()
    if not source.is_file() or not source.is_relative_to(workspace) or STATE_DIR in source.relative_to(workspace).parts or ".git" in source.relative_to(workspace).parts:
        raise ValueError("Artifact must be an actual assignment file outside managed metadata")
    view = resume(workspace)
    checks = {r["id"]: r for r in view["results"]}
    if any(i not in checks or not checks[i]["current"] or checks[i]["status"] != "valid" for i in ids):
        raise ValueError("Use only current valid result versions; review stale, unknown or mixed versions first")
    keys = [checks[i]["key"] for i in ids]
    if len(set(keys)) != len(keys):
        raise ValueError("An artifact must not mix versions of the same result key")
    workspace, state, snapshot = prepare_context(workspace, record)
    artifact_id = uuid.uuid4().hex
    directory = workspace / STATE_DIR / "artifacts" / artifact_id
    reserve_directory(workspace, directory, snapshot)
    captured = captured_files(workspace, directory / "content", [str(source)])[0]
    artifact = {**item, "id": artifact_id, "path": source.relative_to(workspace).as_posix(),
                "snapshot_path": captured["snapshot_path"], "sha256": captured["sha256"],
                "created_at": state["updated_at"], "result_sources": [
                    {"id": i, "key": checks[i]["key"], "origin": checks[i]["origin"],
                     "record_path": checks[i]["record_path"]} for i in ids]}
    write_json(directory / "record.json", artifact)
    artifact["receipt"] = {"path": (directory / "record.json").relative_to(workspace).as_posix(),
                           "sha256": fingerprint(directory / "record.json")}
    state["result_artifacts"] = [*state.get("result_artifacts", []), artifact]
    state["artifact_heads"] = {**state.get("artifact_heads", {}), artifact["path"]: artifact_id}
    return {**persist_context(workspace, state, snapshot, directory, f"coursework: link result sources for {artifact['path']}"), "artifact": artifact}


def review_result(workspace, record):
    from .context import require_writable_request
    require_writable_request(record)
    from .context import resume
    from .execution import validate_request
    if not isinstance(record, dict) or record.get("assessment") != "unaffected" or not isinstance(record.get("note"), str) or not record["note"].strip():
        raise ValueError("A non-impact review needs assessment=unaffected and the actual comparison rationale")
    view = resume(workspace)
    result = next((r for r in view["state"].get("results", []) if r["id"] == record.get("result_id")), None)
    legacy_run = None
    if not result and record.get("run_id") and not record.get("result_id"):
        legacy_run = next((r for r in view["state"].get("runs", []) if r["id"] == record["run_id"]), None)
        if not legacy_run or any(r.get("run_id") == legacy_run["id"] for r in view["state"].get("results", [])):
            raise ValueError("Adoption needs an existing saved run not already in the result registry")
        saved = actual_path(workspace, legacy_run["evidence_path"])
        if not saved.is_file() or json.loads(saved.read_text(encoding="utf-8")) != legacy_run:
            raise ValueError("Saved legacy run record is missing or differs from handoff state")
        result, _ = register_run_result(Path(workspace).resolve(), view["state"],
                                        {**record, "execution": legacy_run["specification"]}, legacy_run, persist=False)
        if result is None or view["state"].get("result_heads", {}).get(result["key"]):
            raise ValueError("Adoption needs a completed run and unused result key")
        original_issues = [{"kind": "evidence"} for f in result["evidence"] if file_issue(workspace, f)]
        if result["source_changed_during_execution"]:
            original_issues.append({"kind": "execution_consistency"})
        if result["missing_outputs"]:
            original_issues.append({"kind": "output"})
        check = {"issues": original_issues}
    else:
        if not result or view["state"].get("result_heads", {}).get(result["key"]) != result["id"]:
            raise ValueError("Review needs an exact current result version")
        check = next(c for c in view["results"] if c["id"] == result["id"])
    if result["origin"] != "workflow-run" or result["execution_status"] != "completed" or any(i["kind"] in {"evidence", "execution_consistency", "output"} for i in check["issues"]):
        raise ValueError("A review cannot repair failed execution, corrupt evidence or inconsistent original inputs")
    specification = record.get("specification")
    # Validate the command schema only. A semantic review never executes it;
    # actual current authorization is checked separately by prepare_context.
    validate_request({**record, "execution": specification,
                      "scope": {"goal": "Validate saved execution specification", "authorized_behaviors": ["run"]}})
    if specification.get("dependency_coverage", {}).get("status") != "complete":
        raise ValueError("Review must confirm complete relevant dependency and condition coverage")
    versions = material_versions(view["state"], specification)
    materials = {m["source_id"]: m for m in view["materials"]}
    if any(materials[v["source_id"]]["status"] not in {"unchanged", "recorded"} for v in versions):
        raise ValueError("Re-read and update changed/unavailable materials before recording non-impact")
    names = list(dict.fromkeys([*specification["source_paths"], *specification.get("input_paths", []),
                                *([specification["stdin_path"]] if "stdin_path" in specification else [])]))
    if any(not actual_path(workspace, name).is_file() for name in names):
        raise ValueError("Missing dependencies cannot be declared unaffected")
    original_run = legacy_run or next(r for r in view["state"].get("runs", []) if r["id"] == result["run_id"])
    expected = specification.get("expected", {})
    actual = original_run["execution"]
    for stream in ["stdout", "stderr"]:
        if stream in expected and (stream not in actual or actual_path(workspace, actual[stream]["path"]).read_bytes() != expected[stream].encode("utf-8")):
            raise ValueError("Current independent expected output does not match the original result")
    if "exit_code" in expected and actual["exit_code"] != expected["exit_code"]:
        raise ValueError("Current expected exit code does not match the original result")
    workspace, state, snapshot = prepare_context(workspace, record)
    added_paths = []
    if legacy_run:
        reserve_directory(workspace, workspace / STATE_DIR / "results" / result["id"], snapshot)
        result, added_paths = register_run_result(workspace, state, {**record, "execution": legacy_run["specification"]}, legacy_run)
    review_id = uuid.uuid4().hex
    directory = workspace / STATE_DIR / "result-reviews" / review_id
    reserve_directory(workspace, directory, snapshot)
    dependencies = captured_files(workspace, directory / "dependencies", names)
    review = {"id": review_id, "result_id": result["id"], "assessment": "unaffected", "note": record["note"],
              "recorded_at": state["updated_at"], "specification": specification, "dependencies": dependencies,
              "material_versions": versions, "execution_identity": reuse_identity(workspace, specification),
              "evidence": [{"path": f["snapshot_path"], "sha256": f["sha256"]} for f in dependencies]}
    write_json(directory / "record.json", review)
    review["receipt"] = {"path": (directory / "record.json").relative_to(workspace).as_posix(),
                         "sha256": fingerprint(directory / "record.json")}
    state["result_reviews"] = [*state.get("result_reviews", []), review]
    state["result_requests"] = {**state.get("result_requests", {}), result["key"]: specification}
    return {**persist_context(workspace, state, snapshot, directory, f"coursework: review result applicability {result['key']}", extra_paths=added_paths), "review": review}
