"""Plain model-authored handoffs; prose is never parsed into authorization."""
import json
from pathlib import Path
import re

from .context import STATE_DIR, fingerprint
from .git import begin_task, checkpoint

NOTE_NAME = re.compile(r"handoff(?:-[0-9]+)?\.md\Z")


def handoff_files(workspace):
    directory = Path(workspace) / STATE_DIR
    return [{"path": path.relative_to(workspace).as_posix(), "sha256": fingerprint(path)}
            for path in sorted(directory.glob("handoff*.md"))
            if NOTE_NAME.fullmatch(path.name) and path.is_file() and path.resolve() == path]


def save_handoff(workspace, record):
    from .context import require_writable_request
    require_writable_request(record)
    workspace = Path(workspace).resolve()
    if not isinstance(record, dict) or not isinstance(record.get("scope"), dict):
        raise ValueError("Handoff needs the actual current human request and scope")
    scope = record.get("scope", {})
    authorized = scope.get("authorized_behaviors", [])
    if not isinstance(authorized, list) or any(not isinstance(item, str) for item in authorized):
        raise ValueError("Handoff needs explicit authorized behaviors")
    writing = set(authorized) & {"plan", "code", "run", "analyze", "report"}
    if scope.get("read_only", False) or not writing or writing == {"report"} and scope.get("report_mode") == "review":
        raise ValueError("A read-only request cannot save a handoff")
    if not isinstance(record.get("request"), str) or not record["request"].strip() or not scope.get("goal"):
        raise ValueError("Handoff needs the actual current human request and scope")
    if not isinstance(record.get("note_path"), str) or not record["note_path"]:
        raise ValueError("Handoff needs an agent-authored Markdown note_path")
    stage = Path(record["note_path"]).resolve()
    if stage.is_relative_to(workspace):
        raise ValueError("Prepare the handoff note outside the assignment")
    content = stage.read_text(encoding="utf-8-sig")
    if not content.strip():
        raise ValueError("Handoff note must contain the actual diagnosis and next action")
    directory = workspace / STATE_DIR
    if not workspace.is_dir() or directory.resolve() != directory:
        raise ValueError("Handoff needs an existing assignment and an unlinked .coursework directory")
    snapshot = begin_task(workspace)
    path = directory / "handoff.md"
    number = 1
    while path.exists() and path.relative_to(snapshot.root).as_posix() in snapshot.dirty_paths:
        path = directory / f"handoff-{number:04d}.md"
        number += 1
    if path.resolve() != path or path.exists() and not path.is_file():
        raise ValueError("Preserve linked or non-file handoff paths")
    directory.mkdir(exist_ok=True)
    text = ("# 当前任务交接\n\n## 人类请求与本次范围\n\n" + record["request"] + "\n\n```json\n" +
            json.dumps(scope, ensure_ascii=False, indent=2) + "\n```\n\n" + content)
    path.write_text(text, encoding="utf-8")
    name = path.relative_to(workspace).as_posix()
    saved = checkpoint(workspace, [name], snapshot, "coursework: save task handoff")
    return {"handoff": {"path": name, "sha256": fingerprint(path)},
            "handoffs": handoff_files(workspace), "git": saved}
