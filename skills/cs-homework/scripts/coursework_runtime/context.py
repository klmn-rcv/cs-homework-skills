"""Portable assignment state and material verification; no semantic inference."""
import hashlib
import json
from pathlib import Path
import tempfile


STATE_DIR = ".coursework"
SCHEMA_VERSION = 1


def require_writable_request(record):
    """Current explicit limits override historical or mixed behavior permissions."""
    scope = record.get("scope", {}) if isinstance(record, dict) else {}
    if not isinstance(scope, dict):
        raise ValueError("Current scope must be an object")
    behaviors = scope.get("authorized_behaviors", [])
    if (scope.get("read_only") or scope.get("report_mode") == "review"
            or behaviors and not set(behaviors) & {"plan", "code", "run", "analyze", "report"}):
        raise ValueError("Current scope must authorize writes and execution; read-only/report advice permits inspection only (review-prose)")


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_state(workspace):
    path = Path(workspace) / STATE_DIR / "state.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or state.get("schema_version") != SCHEMA_VERSION or state.get("kind") != "coursework-context":
        raise ValueError("Unsupported coursework state schema; preserve it for migration")
    return state


def previous_state(workspace):
    """A plain handoff can precede the first structured workflow record."""
    directory = Path(workspace) / STATE_DIR
    if directory.resolve() != directory:
        raise ValueError("The coursework state directory must not be a filesystem link")
    if (directory / "state.json").exists():
        return read_state(workspace)
    if directory.exists():
        from .handoff import NOTE_NAME
        children = list(directory.iterdir()) if directory.is_dir() else []
        if not children or any(not path.is_file() or path.resolve() != path or
                               not NOTE_NAME.fullmatch(path.name) for path in children):
            raise ValueError("Existing .coursework has no recognized context; preserve it")
    return {}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def local_path(workspace, source):
    path = Path(source["path"])
    return path if path.is_absolute() else Path(workspace) / path


def material_checks(workspace, sources, *, refresh_online=False):
    checks = []
    for source in sources:
        item = {"source_id": source["id"]}
        if source["kind"] == "chat":
            item["status"] = "recorded"
        elif source["kind"] == "online":
            from .online import online_check
            item = online_check(workspace, source, refresh=refresh_online)
        else:
            path = local_path(workspace, source)
            if not path.is_file():
                item["status"] = "missing"
            else:
                item["current_sha256"] = fingerprint(path)
                item["status"] = "unchanged" if item["current_sha256"] == source["sha256"] else "changed"
        checks.append(item)
    return checks


def assignment_files(workspace):
    """Optional byte inventory, not evidence validation or a required notes format."""
    return [{"path": path.relative_to(workspace).as_posix(), "sha256": fingerprint(path)}
            for path in sorted(workspace.rglob("*"))
            if ".git" not in path.relative_to(workspace).parts
            and path.is_file() and path.resolve() == path]


def resume(workspace, *, refresh_online=False, requested_results=None):
    workspace = Path(workspace).resolve()
    if not workspace.is_dir():
        raise ValueError("Resume needs an existing assignment directory")
    path = workspace / STATE_DIR / "state.json"
    from .handoff import handoff_files
    fallback = {"workspace": str(workspace), "state": None, "results": [], "artifacts": [],
                "analyses": [], "reports": [], "reflections": [], "materials": [],
                "blocking_questions": [], "handoffs": handoff_files(workspace),
                "needs_review": True}
    if not path.exists():
        return {**fallback, "files": assignment_files(workspace), "context_status": "absent"}
    try:
        state = read_state(workspace)
    except (ValueError, UnicodeError) as error:
        return {**fallback, "files": assignment_files(workspace), "context_status": "unrecognized", "context_issue": str(error)}
    # Preserve partial legacy records for reading; never manufacture stage completion.
    if not (isinstance(state.get("sources"), list)
            and isinstance(state.get("requirements", []), list)
            and isinstance(state.get("plan", {}), dict)):
        return {**fallback, "files": assignment_files(workspace), "state": state, "context_status": "incomplete"}
    checks = material_checks(workspace, state["sources"], refresh_online=refresh_online)
    for item in checks:
        if item["status"] in {"changed", "missing", "unavailable", "incomplete", "not_checked", "cache_invalid", "unread"}:
            affected = [r["id"] for r in state.get("requirements", [])
                        if any(c["source_id"] == item["source_id"] for c in r["sources"])]
            item["affected_requirements"] = affected
            item["affected_plan_steps"] = [step["description"] for steps in state.get("plan", {}).values()
                                          if isinstance(steps, list) for step in steps
                                          if isinstance(step, dict) and set(step.get("requirements", [])) & set(affected)]
            item["artifact_impact"] = "needs_semantic_review"
    from .results import result_checks, artifact_checks
    results = result_checks(workspace, state, materials=checks, requested=requested_results)
    artifacts = artifact_checks(workspace, state, results)
    from .analysis import analysis_checks
    analyses = analysis_checks(workspace, state, results, artifacts)
    from .reflection import reflection_checks
    reflections = reflection_checks(workspace, state, results, artifacts, analyses)
    from .report import report_checks
    reports = report_checks(workspace, state, results, artifacts, analyses, reflections=reflections)
    from .handoff import handoff_files
    return {"workspace": str(workspace), "state": state, "results": results, "artifacts": artifacts, "analyses": analyses, "reports": reports, "reflections": reflections,
            "handoffs": handoff_files(workspace),
            "materials": checks,
            "blocking_questions": [item for item in state.get("questions", []) if item.get("blocking", True)],
            "needs_review": any(item["status"] in {"changed", "missing", "unread", "cache_invalid", "unavailable", "incomplete", "not_checked"} for item in checks)
            or any(change["review"]["status"] == "pending" for change in state.get("source_changes", []))
            or any(item["current"] and item["status"] != "valid" for item in [*results, *artifacts, *analyses])
            or any(item["current"] and item["status"] not in {"valid", "source_only"} for item in reports)
            or any(item["current"] and item["status"] != "valid" for item in reflections)}
