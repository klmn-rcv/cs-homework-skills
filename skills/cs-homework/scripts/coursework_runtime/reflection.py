"""Persist model-authored recommendations and explicit attributed replies, without authorship inference."""
from copy import deepcopy
from pathlib import Path
import re
import uuid

from .context import STATE_DIR, fingerprint, resume, write_json
from .results import actual_path, captured_files, file_issue, immutable_issue, prepare_context, persist_context, reserve_directory


def reflection_checks(workspace, state, results, artifacts, analyses):
    registries = {"result_ids": results, "artifact_ids": artifacts, "analysis_ids": analyses}
    checks = []
    for reflection in state.get("reflections", []):
        # Receipt integrity is shared; source snapshot integrity belongs to its question.
        common = [issue] if (issue := immutable_issue(workspace, reflection)) else []
        questions = []
        for question in reflection["questions"]:
            issues = list(common)
            issues += [issue for item in question.get("source_snapshots", [])
                       if (issue := file_issue(workspace, {"path": item["snapshot_path"], "sha256": item["sha256"]}))]
            issues += [issue for item in question.get("dependencies", []) if (issue := file_issue(workspace, item))]
            for field, registry in registries.items():
                by_id = {item["id"]: item for item in registry}
                for source_id in question.get(field, []):
                    source = by_id.get(source_id)
                    if not source or not source["current"] or source["status"] != "valid":
                        issues.append({field: source_id, "reason": "Reflection basis is no longer current and valid"})
            questions.append({"id": question["id"], "status": question["status"], "content": question["content"],
                              "evidence_status": "needs_review" if issues else "valid", "issues": issues})
        checks.append({"id": reflection["id"], "key": reflection["key"],
                       "current": state.get("reflection_heads", {}).get(reflection["key"]) == reflection["id"],
                       "status": "needs_review" if any(q["issues"] for q in questions) else "valid",
                       "questions": questions, "record_path": reflection["receipt"]["path"]})
    return checks


def report_reflections(record, checks):
    selected = record.get("reflection_sources", [])
    if not isinstance(selected, list):
        raise ValueError("reflection_sources must be a list")
    statuses, sources = [], []
    for item in selected:
        if not isinstance(item, dict):
            raise ValueError("Each reflection source needs an exact reflection_id and question_ids")
        check = next((c for c in checks if c["id"] == item.get("reflection_id")), None)
        ids = item.get("question_ids")
        if not check or not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids) or len(ids) != len(set(ids)):
            raise ValueError("Report reflection sources need a known version and unique exact question_ids")
        questions = {q["id"]: q for q in check["questions"]}
        head = next((c for c in checks if c["key"] == check["key"] and c["current"]), None)
        current = {q["id"]: q for q in head["questions"]} if head else {}
        if any(i not in questions or i not in current or
               questions[i]["content"] != current[i]["content"] or
               current[i]["evidence_status"] != "valid" for i in ids):
            raise ValueError("Selected reflection questions require evidence review before report use")
        sources.append({"reflection_id": check["id"], "question_ids": ids})
        statuses += [current[i]["status"] for i in ids]
    status = "not_linked" if not statuses else "recommended_draft" if all(s == "recommended" for s in statuses) else "accepted_content" if all(s == "accepted" for s in statuses) else "mixed"
    return sources, status


def save_reflection(workspace, record):
    from .context import require_writable_request
    require_writable_request(record)
    if not can_persist(record):
        raise ValueError("Current scope must authorize report for personal reflection")
    key = record.get("reflection_key")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", key):
        raise ValueError("reflection_key must be a safe stable label")
    need = record.get("need_basis")
    questions = record.get("questions")
    if not isinstance(need, str) or not need.strip() or not isinstance(questions, list) or len(questions) not in {2, 3}:
        raise ValueError("A needed reflection needs insufficiency basis and two or three concrete questions")
    workspace = Path(workspace).resolve()
    view = resume(workspace) if (workspace / STATE_DIR / "state.json").exists() else None
    if view and key in view["state"].get("reflection_heads", {}):
        raise ValueError("Preserve existing recommendations and decisions; reply to their current version")
    ids = []
    prepared = []
    for question in questions:
        if not isinstance(question, dict):
            raise ValueError("Reflection questions must be objects")
        for field in ["id", "question", "recommendation", "basis"]:
            if not isinstance(question.get(field), str) or not question[field].strip():
                raise ValueError(f"Each reflection question needs complete {field}")
        if question["id"] in ids:
            raise ValueError("Question IDs must be unique")
        ids.append(question["id"])
        if "background" in question and (not isinstance(question["background"], str) or not question["background"].strip()):
            raise ValueError("Omit unnecessary background; supplied background must be meaningful")
        paths = question.get("source_paths", [])
        if not isinstance(paths, list) or any(not isinstance(p, str) or not p or not actual_path(workspace, p).is_file() for p in paths):
            raise ValueError("Reflection source_paths must identify actual read evidence")
        linked = {}
        for field, registry in [("result_ids", "results"), ("artifact_ids", "artifacts"), ("analysis_ids", "analyses")]:
            values = question.get(field, [])
            checks = {c["id"]: c for c in view[registry]} if view else {}
            if not isinstance(values, list) or any(not isinstance(i, str) for i in values) or len(values) != len(set(values)) or any(i not in checks or not checks[i]["current"] or checks[i]["status"] != "valid" for i in values):
                raise ValueError("Reflection needs exact current valid evidence IDs")
            linked[field] = values
        if not paths and not any(linked.values()):
            raise ValueError("Reflection needs actual source files or current recorded evidence")
        prepared.append({**deepcopy(question), **linked, "status": "recommended", "content": question["recommendation"], "decisions": []})
    workspace, state, snapshot = prepare_context(workspace, record)
    reflection_id = uuid.uuid4().hex
    directory = workspace / STATE_DIR / "reflections" / reflection_id
    reserve_directory(workspace, directory, snapshot)
    directory.mkdir(parents=True)
    for index, question in enumerate(prepared):
        captured = captured_files(workspace, directory / f"sources-{index}", question.pop("source_paths", []))
        question["dependencies"] = [{"path": c["path"], "sha256": c["sha256"]} for c in captured]
        question["source_snapshots"] = captured
    reflection = {"id": reflection_id, "key": key, "created_at": state["updated_at"], "need_basis": need, "questions": prepared,
                  "evidence": [{"path": c["snapshot_path"], "sha256": c["sha256"]} for q in prepared for c in q["source_snapshots"]]}
    return persist_reflection(workspace, state, snapshot, directory, reflection)


def persist_reflection(workspace, state, snapshot, directory, reflection):
    write_json(directory / "record.json", reflection)
    reflection["receipt"] = {"path": (directory / "record.json").relative_to(workspace).as_posix(), "sha256": fingerprint(directory / "record.json")}
    state["reflections"] = [*state.get("reflections", []), reflection]
    state["reflection_heads"] = {**state.get("reflection_heads", {}), reflection["key"]: reflection["id"]}
    return {**persist_context(workspace, state, snapshot, directory, "coursework: preserve personal reflection and acceptance status"), "reflection": reflection}


def reply_reflection(workspace, record):
    from .context import require_writable_request
    require_writable_request(record)
    if not can_persist(record):
        raise ValueError("Current scope must authorize report for personal reflection")
    workspace = Path(workspace).resolve()
    view = resume(workspace)
    check = next((r for r in view["reflections"] if r["id"] == record.get("reflection_id")), None)
    if not check or not check["current"]:
        raise ValueError("Reply must target the current exact reflection version")
    reply = record.get("reply")
    if not isinstance(reply, dict) or not isinstance(reply.get("text"), str) or not reply["text"].strip():
        raise ValueError("Acceptance needs an actual explicit reply; silence is never acceptance")
    source = reply.get("source")
    if not isinstance(source, dict) or source.get("kind") not in {"user", "synthetic"} or not isinstance(source.get("locator"), str) or not source["locator"].strip():
        raise ValueError("Reply attribution needs user or synthetic kind and actual locator")
    answers = record.get("answers")
    if not isinstance(answers, list) or not answers:
        raise ValueError("Reply needs explicit accept/edit/replace decisions")
    old = next(r for r in view["state"]["reflections"] if r["id"] == check["id"])
    updated = deepcopy(old)
    updated.pop("receipt")
    questions = {q["id"]: q for q in updated["questions"]}
    current = {q["id"]: q for q in check["questions"]}
    changed = set()
    for answer in answers:
        if not isinstance(answer, dict):
            raise ValueError("Each answer must name explicit question_ids and action")
        ids, action = answer.get("question_ids"), answer.get("action")
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids) or len(ids) != len(set(ids)) or action not in {"accept", "edit", "replace"}:
            raise ValueError("Answer needs unique exact question_ids and accept/edit/replace action")
        if action != "accept" and (len(ids) != 1 or not isinstance(answer.get("answer"), str) or not answer["answer"].strip()):
            raise ValueError("An edit or replacement needs one question and a complete resulting answer")
        for question_id in ids:
            if question_id not in questions or question_id in changed or current[question_id]["evidence_status"] != "valid":
                raise ValueError("Reply needs distinct current questions with reviewed evidence")
            question = questions[question_id]
            if action == "accept" and question["status"] == "accepted":
                raise ValueError("This decision is already accepted; do not request or record repeated confirmation")
            question["content"] = question["recommendation"] if action == "accept" else answer["answer"]
            question["status"] = "accepted"
            question["decisions"].append({"action": action, "reply": reply["text"], "source": deepcopy(source), "answer": question["content"]})
            changed.add(question_id)
    workspace, state, snapshot = prepare_context(workspace, record)
    updated.update(id=uuid.uuid4().hex, previous_id=old["id"], created_at=state["updated_at"])
    directory = workspace / STATE_DIR / "reflections" / updated["id"]
    reserve_directory(workspace, directory, snapshot)
    directory.mkdir(parents=True)
    return persist_reflection(workspace, state, snapshot, directory, updated)


def review_reflection(workspace, record):
    from .context import require_writable_request
    require_writable_request(record)
    """Attribute an actual evidence comparison, preserving or reopening only its question."""
    if not can_persist(record):
        raise ValueError("Current scope must authorize report for reflection evidence review")
    workspace = Path(workspace).resolve()
    view = resume(workspace)
    check = next((r for r in view["reflections"] if r["id"] == record.get("reflection_id")), None)
    if not check or not check["current"]:
        raise ValueError("Review requires a current exact reflection version")
    old = next(r for r in view["state"]["reflections"] if r["id"] == check["id"])
    if immutable_issue(workspace, old):
        raise ValueError("Preserve and repair damaged immutable reflection evidence before reviewing applicability")
    reviews = record.get("reviews")
    if not isinstance(reviews, list) or not reviews:
        raise ValueError("Review needs actual per-question evidence comparisons")
    questions = {q["id"]: q for q in old["questions"]}
    seen = set()
    for review in reviews:
        if not isinstance(review, dict) or review.get("question_id") not in questions or review["question_id"] in seen or review.get("disposition") not in {"still_supported", "revise"} or not isinstance(review.get("basis"), str) or not review["basis"].strip():
            raise ValueError("Review needs each exact question once, still_supported/revise and actual comparison basis")
        if review["disposition"] == "revise" and (not isinstance(review.get("recommendation"), str) or not review["recommendation"].strip()):
            raise ValueError("A revised reflection needs a complete new recommendation; earlier acceptance cannot be reused")
        seen.add(review["question_id"])
        if any(file_issue(workspace, item, "snapshot_path") for item in questions[review["question_id"]].get("source_snapshots", [])):
            raise ValueError("Preserve and repair damaged immutable selected-question evidence before reviewing applicability")
        paths = review.get("source_paths", [])
        if not isinstance(paths, list) or any(not isinstance(p, str) or not p or not actual_path(workspace, p).is_file() for p in paths):
            raise ValueError("Review source_paths must identify newly read actual evidence")
        for field, registry in [("result_ids", "results"), ("artifact_ids", "artifacts"), ("analysis_ids", "analyses")]:
            ids = review.get(field, questions[review["question_id"]].get(field, []))
            by_id = {c["id"]: c for c in view[registry]}
            if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids) or len(ids) != len(set(ids)) or any(i not in by_id or not by_id[i]["current"] or by_id[i]["status"] != "valid" for i in ids):
                raise ValueError("Reviewed reflection needs current valid evidence IDs")
        if not paths and not any(review.get(f, questions[review["question_id"]].get(f, [])) for f in ["result_ids", "artifact_ids", "analysis_ids"]):
            raise ValueError("A review needs actual current evidence")
    workspace, state, snapshot = prepare_context(workspace, record)
    updated = deepcopy(old)
    updated.pop("receipt")
    updated.update(id=uuid.uuid4().hex, previous_id=old["id"], created_at=state["updated_at"])
    directory = workspace / STATE_DIR / "reflections" / updated["id"]
    reserve_directory(workspace, directory, snapshot)
    directory.mkdir(parents=True)
    for index, review in enumerate(reviews):
        question = next(q for q in updated["questions"] if q["id"] == review["question_id"])
        captured = captured_files(workspace, directory / f"sources-{index}", review.get("source_paths", []))
        question["source_snapshots"] = captured
        question["dependencies"] = [{"path": c["path"], "sha256": c["sha256"]} for c in captured]
        for field in ["result_ids", "artifact_ids", "analysis_ids"]:
            question[field] = review.get(field, question.get(field, []))
        comparison = {"disposition": review["disposition"], "basis": review["basis"], "prior_reflection_id": old["id"]}
        if review["disposition"] == "revise":
            comparison.update(prior_content=question["content"], prior_status=question["status"])
            question.update(recommendation=review["recommendation"], content=review["recommendation"], status="recommended", basis=review["basis"])
        question["reviews"] = [*question.get("reviews", []), comparison]
        updated["evidence"] += [{"path": c["snapshot_path"], "sha256": c["sha256"]} for c in captured]
    return persist_reflection(workspace, state, snapshot, directory, updated)


def can_persist(record):
    scope = record.get("scope", {}) if isinstance(record, dict) else {}
    return isinstance(scope, dict) and "report" in scope.get("authorized_behaviors", []) and scope.get("report_mode") != "review" and not scope.get("read_only", False)
