"""Persist the agent's sourced plan without generating assignment code or reports."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .context import SCHEMA_VERSION, STATE_DIR, fingerprint, read_state, resume, write_json
from .git import begin_task, checkpoint
from .online import prepare_online_source, archive_online_sources


BEHAVIORS = {"plan", "code", "run", "analyze", "report", "check"}


def text(value):
    return isinstance(value, str) and bool(value.strip())


def records(value, name):
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{name} must be a list of records")
    return value


def prepare_record(workspace, record):
    if not isinstance(record, dict):
        raise ValueError("Planning input must be a JSON object")
    for key in ["assignment", "request", "scope", "sources", "requirements", "plan", "next_steps"]:
        if key not in record:
            raise ValueError(f"Missing plan field: {key}")
    for key in ["assignment", "scope", "plan"]:
        if not isinstance(record[key], dict):
            raise ValueError(f"{key} must be an object")
    for key in ["sources", "requirements", "decisions", "questions", "next_steps", "source_reviews"]:
        records(record.get(key, []), key)
    if not text(record["assignment"].get("title")) or not text(record["request"]):
        raise ValueError("An assignment title and current request are required")
    scope = record["scope"]
    if not text(scope.get("goal")) or not isinstance(scope.get("authorized_behaviors"), list) or not scope["authorized_behaviors"]:
        raise ValueError("Scope needs a goal and authorized_behaviors")
    for key in ["authorized_behaviors", "deliverables", "checkpoints"]:
        if not isinstance(scope.get(key, []), list) or any(not text(item) for item in scope.get(key, [])):
            raise ValueError(f"scope.{key} must be a list of nonempty strings")
    if set(scope["authorized_behaviors"]) - BEHAVIORS or "plan" not in scope["authorized_behaviors"]:
        raise ValueError("A plan record must include authorized behavior plan")
    source_ids = set()
    for source in record["sources"]:
        if not text(source.get("id")) or source["id"] in source_ids:
            raise ValueError("Source IDs must be present and unique")
        source_ids.add(source["id"])
        if source.get("kind") == "local":
            if not text(source.get("path")):
                raise ValueError("Local sources need a file path")
            path = Path(source.get("path", ""))
            path = (path if path.is_absolute() else workspace / path).resolve()
            if not path.is_file():
                raise ValueError(f"Unreadable local material: {path}")
            source["path"] = path.relative_to(workspace).as_posix() if path.is_relative_to(workspace) else str(path)
            source["sha256"] = fingerprint(path)
            source["size_bytes"] = path.stat().st_size
        elif source.get("kind") == "chat" and text(source.get("content")):
            pass
        elif source.get("kind") == "online":
            prepare_online_source(workspace, source)
        else:
            raise ValueError("Plans accept local files, nonempty chat sources and captured online materials")
    requirement_ids = set()
    for requirement in record["requirements"]:
        if not text(requirement.get("id")) or requirement["id"] in requirement_ids or not text(requirement.get("text")):
            raise ValueError("Requirements need unique IDs and text")
        requirement_ids.add(requirement["id"])
    for item in record["requirements"] + record.get("decisions", []) + record.get("questions", []):
        citations = records(item.get("sources", []), "citations")
        if not citations or any(not text(c.get("source_id")) or c["source_id"] not in source_ids or not text(c.get("locator")) for c in citations):
            raise ValueError("Every requirement, decision and question needs valid source IDs and locators")
    unread = {s["id"] for s in record["sources"] if s["kind"] == "online" and s["reading"]["status"] == "unread"}
    for requirement in record["requirements"]:
        if any(c["source_id"] in unread for c in requirement["sources"]):
            raise ValueError("Unread online content cannot support assignment requirements; record the access gap as a question")
    for review in record.get("source_reviews", []):
        if review.get("source_id") not in source_ids or not text(review.get("note")) or not isinstance(review.get("affected_artifacts"), list) or any(not text(p) for p in review["affected_artifacts"]):
            raise ValueError("Source reviews need a known source ID, impact note and affected_artifacts list")
    for kind in ["decisions", "questions"]:
        ids = set()
        for item in record.get(kind, []):
            if not text(item.get("id")) or item["id"] in ids or not text(item.get("text")):
                raise ValueError(f"{kind} need unique IDs and text")
            ids.add(item["id"])
            if kind == "decisions":
                if not text(item.get("status")) or item["status"] not in {"confirmed", "proposed", "superseded"}:
                    raise ValueError("Decisions need a recognized status")
                if "supersedes" in item and not text(item["supersedes"]):
                    raise ValueError("supersedes must name an earlier decision ID")
            if kind == "questions" and not isinstance(item.get("blocking", True), bool):
                raise ValueError("Question blocking must be a boolean")
    for mode in ["implementation", "validation"]:
        if mode not in record["plan"]:
            raise ValueError(f"Plan needs {mode} steps (an empty list is allowed when explained)")
        for step in records(record["plan"][mode], f"plan.{mode}"):
            references = step.get("requirements", [])
            if not text(step.get("description")) or not isinstance(references, list) or any(not text(item) or item not in requirement_ids for item in references):
                raise ValueError("Plan steps need descriptions and valid requirement references")
    for step in record["next_steps"]:
        if not text(step.get("behavior")) or step["behavior"] not in BEHAVIORS or not text(step.get("description")):
            raise ValueError("Next steps need a recognized behavior and description")
    # Optional structured planning binds native notes to the requirements actually
    # extracted, not timestamps or a mandatory copy of the whole remote document.
    for source in record["sources"]:
        if source["kind"] == "online" and not source.get("receipt"):
            claims = [r for r in record["requirements"] if any(c["source_id"] == source["id"] for c in r["sources"])]
            source["sha256"] = hashlib.sha256(json.dumps(claims, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return record


def render_plan(state):
    def citations(item):
        return "; ".join(f"{s['source_id']} · {s['locator']}" for s in item.get("sources", []))

    lines = [f"# {state['assignment']['title']}", "", f"计划版本：{state['revision']}", "",
             "## 本次任务范围", "", state["request"], "", state["scope"]["goal"], "",
             "授权行为：" + ", ".join(state["scope"]["authorized_behaviors"])]
    for checkpoint_text in state["scope"].get("checkpoints", []):
        lines.append("- 检查点：" + checkpoint_text)
    for deliverable in state["scope"].get("deliverables", []):
        lines.append("- 交付物：" + deliverable)
    lines.extend(["", "## 已有材料", ""])
    for source in state["sources"]:
        if source["kind"] == "online":
            description = (f"{source['url']} · {source['purpose']} · access={source['access_status']} · "
                           f"reading={source['reading']['status']} · {source['reading']['note']} · read_at={source['retrieved_at']}")
        else:
            description = source["path"] if source["kind"] == "local" else source["content"]
        lines.append(f"- {source['id']} ({source['kind']}): {description}")
    lines.extend(["", "## 带来源的要求", ""])
    for item in state["requirements"]:
        lines.append(f"- {item['id']} [{item.get('category', 'other')}]: {item['text']}（{citations(item)}）")
    lines.extend(["", "## 已确认决定与待解决问题", ""])
    for item in state.get("decisions", []):
        lines.append(f"- {item['id']} [{item['status']}]: {item['text']}（{citations(item)}）")
    for item in state.get("questions", []):
        lines.append(f"- 问题 {item['id']} [blocking={item.get('blocking', True)}]: {item['text']}（{citations(item)}）")
    for mode, title in [("implementation", "实施计划"), ("validation", "验证计划")]:
        lines.extend(["", "## " + title, ""])
        for item in state["plan"][mode]:
            lines.append(f"- {item['description']}（要求：{', '.join(item.get('requirements', []))}）")
    lines.extend(["", "## 下一步", ""])
    for item in state["next_steps"]:
        lines.append(f"- [{item['behavior']}] {item['description']}")
    if state.get("source_changes"):
        lines.extend(["", "## 在线材料变化及影响", ""])
        for change in state["source_changes"]:
            lines.append(f"- {change['source_id']} · revision {change['revision']} · {change['old_sha256']} -> {change['new_sha256']} · "
                         f"{change['review']['status']}: {change['review']['note']} · artifacts={change['review'].get('affected_artifacts', [])}")
    return "\n".join(lines) + "\n"


def save_plan(workspace, record, *, new=False):
    from .context import require_writable_request
    require_writable_request(record)
    workspace = Path(workspace).resolve()
    if new and workspace.exists():
        raise ValueError("New assignment directory already exists; choose an independent unused directory")
    record = prepare_record(workspace, record)
    workspace.mkdir(parents=True, exist_ok=True)
    state_dir = workspace / STATE_DIR
    if state_dir.resolve() != state_dir:
        raise ValueError("The coursework state directory must not be a filesystem link")
    from .context import previous_state
    previous = previous_state(workspace)
    snapshot = begin_task(workspace, independent=new)
    decisions = {item["id"]: item for item in previous.get("decisions", [])}
    for item in record.get("decisions", []):
        old = decisions.get(item["id"])
        if old and old.get("status") == "confirmed" and old != item:
            raise ValueError("Keep confirmed decisions; a changed decision needs a new ID and supersedes")
        if item.get("supersedes"):
            prior_id = item["supersedes"]
            if prior_id not in decisions:
                raise ValueError("Superseded decision does not exist")
            decisions[prior_id] = {**decisions[prior_id], "status": "superseded"}
        decisions[item["id"]] = item
    sources = {item["id"]: item for item in previous.get("sources", [])}
    changes = list(previous.get("source_changes", []))
    reviews = {r["source_id"]: r for r in record.get("source_reviews", [])}
    for item in record["sources"]:
        old = sources.get(item["id"])
        if old and (old["kind"] != item["kind"] or
                    (item["kind"] == "chat" and old["content"] != item["content"]) or
                    (item["kind"] == "online" and old["url"] != item["url"]) or
                    (item["kind"] == "local" and old["path"] != item["path"])):
            raise ValueError("A different material or chat supplement needs a new source ID")
        if old and item["kind"] == "online" and old["sha256"] != item["sha256"]:
            review = reviews.get(item["id"])
            changes.append({"source_id": item["id"], "revision": previous.get("revision", 0) + 1,
                            "old_sha256": old["sha256"], "new_sha256": item["sha256"],
                            "previous_receipt": old.get("receipt"),
                            "review": {**review, "status": "reviewed"} if review else
                            {"status": "pending", "note": "Re-read changed requirements and review affected plan and downstream artifacts."}})
        sources[item["id"]] = item
    for change in changes:
        review = reviews.get(change["source_id"])
        if review and change["review"]["status"] == "pending" and sources[change["source_id"]]["sha256"] == change["new_sha256"]:
            change["review"] = {**review, "status": "reviewed"}
    state = {**previous, **record, "schema_version": SCHEMA_VERSION, "kind": "coursework-context",
             "decisions": list(decisions.values()), "sources": list(sources.values()),
             "revision": previous.get("revision", 0) + 1,
             "updated_at": datetime.now(timezone.utc).isoformat()}
    if changes:
        state["source_changes"] = changes
    captures = archive_online_sources(workspace, state["sources"])
    paths = [f"{STATE_DIR}/state.json", f"{STATE_DIR}/plan.md",
             f"{STATE_DIR}/history/{state['revision']:04d}.json"]
    paths.extend(captures)
    for name in paths:
        path = workspace / name
        if path.resolve() != path:
            raise ValueError(f"Managed outputs must not be filesystem links: {name}")
        if path.relative_to(snapshot.root).as_posix() in snapshot.dirty_paths:
            raise ValueError(f"Preserved preexisting user change: {name}; reconcile it before saving a new plan")
    if (workspace / paths[2]).exists():
        raise ValueError("Plan history is immutable; refusing to replace an existing revision")
    for name, data in captures.items():
        (workspace / name).parent.mkdir(parents=True, exist_ok=True)
        (workspace / name).write_bytes(data)
    write_json(workspace / paths[0], state)
    (workspace / paths[1]).write_text(render_plan(state), encoding="utf-8")
    write_json(workspace / paths[2], state)
    result = checkpoint(workspace, paths, snapshot, f"coursework: save plan revision {state['revision']}")
    return {**resume(workspace), "git": result, "deliverables": paths[:2]}
