"""Read-only factual support for the agent's scoped semantic acceptance."""
from pathlib import Path

from .context import STATE_DIR, fingerprint
from .results import actual_path, inspect_results


def inspect_acceptance(workspace, record):
    if not isinstance(record, dict) or not isinstance(record.get("request"), str) or not record["request"].strip():
        raise ValueError("Acceptance needs the current human request")
    scope = record.get("scope")
    if not isinstance(scope, dict) or not isinstance(scope.get("authorized_behaviors"), list):
        raise ValueError("Acceptance needs the current scope, not saved authorization")
    workspace = Path(workspace).resolve()
    if not workspace.is_dir():
        raise ValueError("Acceptance workspace must already exist; inspection never creates it")
    view = inspect_results(workspace, record, refresh_online=False) if (workspace / STATE_DIR / "state.json").exists() else None
    items = record.get("items", [])
    if not isinstance(items, list):
        raise ValueError("Acceptance items must be an agent-authored list")
    assessed, ids = [], set()
    for item in items:
        if not isinstance(item, dict) or item.get("status") not in {"passed", "failed", "pending_update", "unverified"}:
            raise ValueError("Each acceptance item needs passed, failed, pending_update or unverified status")
        for field in ["id", "requirement", "basis"]:
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"Each acceptance item needs {field}")
        if item["id"] in ids:
            raise ValueError("Acceptance item IDs must be unique")
        ids.add(item["id"])
        for field in ["evidence", "missing", "affected_scope"]:
            if not isinstance(item.get(field), list):
                raise ValueError(f"Acceptance item {field} must be a list")
        facts = [inspect_evidence(workspace, evidence, view) for evidence in item["evidence"]]
        status = item["status"]
        missing = list(item["missing"])
        if status == "passed":
            if not facts or missing:
                status = "unverified"
                if not facts:
                    missing.append("No concrete evidence was supplied for the passed assessment")
            for fact in facts:
                if fact["status"] != "passed":
                    priority = {"passed": 0, "unverified": 1, "pending_update": 2, "failed": 3}
                    if priority[fact["status"]] > priority[status]:
                        status = fact["status"]
                    missing.extend(fact.get("issues", []))
        elif status == "failed" and not any(fact["status"] == "failed" for fact in facts):
            # A semantic failure from an old reading is not a verdict on new bytes.
            stale = [fact for fact in facts if fact["status"] != "passed"]
            if stale or not facts:
                status = "pending_update" if any(fact["status"] == "pending_update" for fact in stale) else "unverified"
                missing.extend(issue for fact in stale for issue in fact.get("issues", []))
                if not facts:
                    missing.append("No current concrete evidence supports the failed assessment")
        route = item.get("route")
        if route is not None and route not in {"code", "report", "analyze"}:
            raise ValueError("Acceptance repair route must be code, report or analyze")
        allowed = route in scope["authorized_behaviors"] and not scope.get("read_only", False)
        if scope.get("report_mode") == "review":
            allowed = False
        follow_up = {"route": route, "action": "none" if status == "passed" or route is None else
                     "diagnose_then_route_within_current_scope" if allowed else "scope_decision_required"}
        assessed.append({**item, "agent_status": item["status"], "status": status,
                         "missing": missing, "evidence_checks": facts, "follow_up": follow_up})
    statuses = {i["status"] for i in assessed}
    status = "passed" if statuses == {"passed"} else "partial" if "passed" in statuses else "failed" if "failed" in statuses else "pending_update" if "pending_update" in statuses else "unverified"
    return {"workspace": str(workspace), "request": record["request"], "scope": scope,
            "mode": "read_only", "assessment_origin": "agent", "status": status,
            "items": assessed, "context": view,
            "limitation": "Facts check declared bytes and saved records; scope relevance, algorithms, content and semantic judgments require the agent's actual reading. No program or repair was run."}


def inspect_evidence(workspace, evidence, view):
    if not isinstance(evidence, dict) or not isinstance(evidence.get("note"), str) or not evidence["note"].strip():
        raise ValueError("Evidence needs a concrete actual-reading note")
    kind = evidence.get("kind")
    if kind == "file":
        name = evidence.get("path")
        if not isinstance(name, str) or not name or not isinstance(evidence.get("sha256"), str):
            raise ValueError("File evidence needs its exact path and actually read SHA-256")
        path = actual_path(workspace, name)
        if not path.is_file():
            return {**evidence, "status": "unverified", "issues": [f"Missing evidence: {name}"]}
        digest = fingerprint(path)
        same = digest == evidence["sha256"]
        return {**evidence, "current_sha256": digest, "status": "passed" if same else "pending_update",
                "issues": [] if same else [f"Evidence bytes changed; read current file: {name}"]}
    registry = {"result": "results", "artifact": "artifacts", "analysis": "analyses", "report": "reports", "reflection": "reflections"}.get(kind)
    if registry is None or not isinstance(evidence.get("id"), str):
        raise ValueError("Recorded evidence needs kind=result/artifact/analysis/report/reflection and exact id")
    fact = next((i for i in view[registry] if i["id"] == evidence["id"]), None) if view else None
    if fact is None:
        return {**evidence, "status": "unverified", "issues": [f"No saved {kind} evidence with this ID"]}
    status, issues = "passed", []
    if not fact["current"] or fact["status"] == "pending_update" or fact.get("issues"):
        status, issues = "pending_update", ["Evidence is historical or requires a current update"]
    elif fact["status"] in {"failed", "review_failed"}:
        status, issues = "failed", ["Recorded execution or report review failed"]
    elif fact["status"] not in {"valid", "source_only"}:
        status, issues = "unverified", ["Saved evidence still needs review"]
    if evidence.get("require_verified") and status == "passed":
        verification = fact.get("verification", {}).get("status")
        if verification == "failed":
            status, issues = "failed", ["Independent correctness check failed despite process completion"]
        elif verification not in {"passed", "independently_checked"}:
            status, issues = "unverified", ["No passed independent correctness check is recorded"]
    if kind == "report" and status == "passed":
        if evidence.get("require_pdf_review") and fact["status"] != "valid":
            status, issues = "unverified", ["Current PDF compilation and complete content/page review are not recorded"]
        # Legacy require_accepted remains provenance in the returned evidence.
        # Readiness depends on current content/evidence, not an attributed reply.
    return {**evidence, "status": status, "fact": fact, "issues": issues}
