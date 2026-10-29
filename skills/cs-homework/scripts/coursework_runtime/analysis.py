"""Execute explicit, agent-authored analysis against exact current result bytes."""
from pathlib import Path
import re
import uuid

from .context import STATE_DIR, fingerprint, resume, write_json
from .execution import execute, protected_path
from .results import actual_path, prepare_context, reserve_directory, persist_context, record_issues


def analysis_checks(workspace, state, results, artifacts):
    result_map = {r["id"]: r for r in results}
    artifact_map = {a["id"]: a for a in artifacts}
    checks = []
    for analysis in state.get("analyses", []):
        issues = record_issues(workspace, analysis)
        for source_id in {i["result_id"] for i in analysis["inputs"]}:
            source = result_map.get(source_id)
            if not source or not source["current"] or source["status"] != "valid":
                issues.append({"result_id": source_id, "reason": "Source is no longer current and valid"})
        for product in analysis["products"]:
            artifact = artifact_map.get(product["artifact_id"])
            if not artifact or artifact["status"] != "valid":
                issues.append({"path": product["path"], "reason": "Analysis product needs update"})
        checks.append({"id": analysis["id"], "key": analysis["key"],
                       "current": state.get("analysis_heads", {}).get(analysis["key"]) == analysis["id"],
                       "status": "failed" if analysis["status"] == "failed" else "pending_update" if issues else "valid",
                       "issues": issues, "record_path": analysis["receipt"]["path"]})
    return checks


def save_analysis(workspace, record):
    from .context import require_writable_request
    require_writable_request(record)
    if not isinstance(record, dict):
        raise ValueError("Analysis input must be a JSON object")
    if not set(record.get("scope", {}).get("authorized_behaviors", [])) & {"analyze", "report"}:
        raise ValueError("Current scope must authorize analysis or necessary report figures")
    key = record.get("analysis_key")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", key):
        raise ValueError("analysis_key must be a safe stable label of 1-64 characters")
    assessment = record.get("assessment")
    if not isinstance(assessment, dict) or any(not isinstance(assessment.get(k), str) or not assessment[k].strip()
            for k in ["goal", "completeness", "units", "anomalies", "limitations"]):
        raise ValueError("Analysis needs actual goal, completeness, units, anomalies and limitations assessments")
    computation = record.get("computation")
    if not isinstance(computation, dict) or any(not isinstance(computation.get(k), str) or not computation[k].strip()
            for k in ["python", "script", "basis"]):
        raise ValueError("Analysis needs a Python executable, an actual script and calculation basis")
    script = actual_path(workspace, computation["script"]).resolve()
    if not script.is_file():
        raise ValueError("Analysis script is missing")
    products = computation.get("products")
    if not isinstance(products, list) or not products:
        raise ValueError("Analysis must declare its actual products")
    names = []
    for item in products:
        if not isinstance(item, dict) or item.get("kind") not in {"metrics", "table", "figure", "analysis"}:
            raise ValueError("Each product needs metrics, table, figure or analysis kind")
        name = item.get("path")
        if not isinstance(name, str) or not name or Path(name).is_absolute() or any(p in {"..", ".git", STATE_DIR} for p in Path(name).parts):
            raise ValueError("Product paths must remain in the new analysis output directory")
        if name in names:
            raise ValueError("Analysis product paths must be unique")
        names.append(name)
    if not isinstance(computation.get("parameters", {}), dict):
        raise ValueError("Analysis parameters must be an object")
    environment = computation.get("env", {})
    captured_env = computation.get("capture_env", [])
    if not isinstance(environment, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in environment.items()) or not isinstance(captured_env, list) or any(not isinstance(k, str) for k in captured_env):
        raise ValueError("Analysis environment must contain string overrides and capture names")
    inputs = record.get("inputs")
    if not isinstance(inputs, list) or not inputs or any(not isinstance(i, dict) or not isinstance(i.get("result_id"), str) or not isinstance(i.get("path"), str) for i in inputs):
        raise ValueError("Analysis needs exact result_id and captured path for each input")
    workspace = Path(workspace).resolve()
    view = resume(workspace)
    checks = {r["id"]: r for r in view["results"]}
    results = {r["id"]: r for r in view["state"].get("results", [])}
    source_inputs = []
    ids = list(dict.fromkeys(i["result_id"] for i in inputs))
    for item in inputs:
        result_id = item["result_id"]
        check = checks.get(result_id)
        if not check or not check["current"] or check["status"] != "valid":
            raise ValueError("Use only exact current valid result versions; resolve stale or unknown sources first")
        result = results[result_id]
        path = actual_path(workspace, item["path"]).resolve()
        evidence = next((e for e in result["evidence"] if actual_path(workspace, e["path"]).resolve() == path), None)
        if not evidence or not path.is_file() or fingerprint(path) != evidence["sha256"]:
            raise ValueError("Analysis input must name intact captured evidence from its result version")
        source_inputs.append({"result_id": result_id, "key": result["key"], "origin": result["origin"],
                              "path": str(path), "sha256": evidence["sha256"],
                              "verification": result["verification"], "provenance": result.get("provenance")})
    if len({checks[i]["key"] for i in ids}) != len(ids):
        raise ValueError("Analysis must not mix versions of the same result key")
    workspace, state, snapshot = prepare_context(workspace, record)
    analysis_id = uuid.uuid4().hex
    directory = workspace / STATE_DIR / "analyses" / analysis_id
    output = workspace / "analysis" / key / analysis_id
    reserve_directory(workspace, directory, snapshot)
    reserve_directory(workspace, output, snapshot)
    for name in names:
        protected_path(workspace, (output / name).relative_to(workspace).as_posix(), snapshot)
    directory.mkdir(parents=True)
    output.mkdir(parents=True)
    captured_script = directory / "compute.py"
    captured_script.write_bytes(script.read_bytes())
    manifest = {"inputs": source_inputs, "parameters": computation.get("parameters", {}),
                "assessment": assessment}
    write_json(directory / "input.json", manifest)
    specification = {"argv": [computation["python"], str(captured_script), str(directory / "input.json"), str(output)],
                     "source_paths": [str(captured_script), str(directory / "input.json")],
                     "input_paths": [i["path"] for i in source_inputs],
                     "output_paths": [str(output / n) for n in names],
                     "env": environment, "capture_env": captured_env}
    execution = execute(workspace, specification, directory / "execution", snapshot)
    success = execution["status"] == "completed" and all(f["status"] != "missing" for f in execution["outputs"])
    if any(a.get("sha256") != b.get("sha256") for a, b in zip(execution["source_before"]["files"], execution["source_after"]["files"])):
        success = False
    after = resume(workspace)
    if any(not c["current"] or c["status"] != "valid" for c in after["results"] if c["id"] in ids):
        success = False
    analysis = {"id": analysis_id, "key": key, "created_at": state["updated_at"],
                "status": "completed" if success else "failed", "inputs": source_inputs,
                "assessment": assessment, "basis": computation["basis"], "parameters": computation.get("parameters", {}),
                "script": {"original_path": str(script), "path": captured_script.relative_to(workspace).as_posix(),
                           "sha256": fingerprint(captured_script)}, "execution": execution, "products": []}
    extra_paths = []
    if success:
        retired_paths = {p["path"] for a in state.get("analyses", []) if a["key"] == key for p in a["products"]}
        state["artifact_heads"] = {p: i for p, i in state.get("artifact_heads", {}).items() if p not in retired_paths}
        for item, saved in zip(products, execution["outputs"]):
            source = output / item["path"]
            if source.resolve() != source or not source.is_file():
                raise ValueError("Analysis products must be actual files without filesystem links")
            path = source.relative_to(workspace).as_posix()
            artifact_id = uuid.uuid4().hex
            artifact = {"id": artifact_id, "path": path, "kind": item["kind"],
                        "result_ids": ids, "basis": computation["basis"], "analysis_id": analysis_id,
                        "snapshot_path": saved["snapshot_path"], "sha256": saved["sha256"],
                        "created_at": state["updated_at"], "result_sources": [
                            {"id": i, "key": checks[i]["key"], "origin": checks[i]["origin"],
                             "record_path": checks[i]["record_path"]} for i in ids]}
            receipt = directory / "artifacts" / f"{artifact_id}.json"
            write_json(receipt, artifact)
            artifact["receipt"] = {"path": receipt.relative_to(workspace).as_posix(), "sha256": fingerprint(receipt)}
            state["result_artifacts"] = [*state.get("result_artifacts", []), artifact]
            state["artifact_heads"] = {**state.get("artifact_heads", {}), path: artifact_id}
            analysis["products"].append({"path": path, "kind": item["kind"], "artifact_id": artifact_id,
                                         "sha256": saved["sha256"]})
            extra_paths.append(path)
    else:
        analysis["diagnostic"] = "Inspect actual exit, missing outputs, source changes and data checks; no products were accepted as current analysis"
        extra_paths = [p.relative_to(workspace).as_posix() for p in output.rglob("*") if p.is_file() and p.resolve() == p]
    analysis["evidence"] = [{"path": p.relative_to(workspace).as_posix(), "sha256": fingerprint(p)}
                            for p in directory.rglob("*") if p.is_file()]
    write_json(directory / "record.json", analysis)
    analysis["receipt"] = {"path": (directory / "record.json").relative_to(workspace).as_posix(),
                           "sha256": fingerprint(directory / "record.json")}
    state["analyses"] = [*state.get("analyses", []), analysis]
    state["analysis_heads"] = {**state.get("analysis_heads", {}), key: analysis_id}
    return {**persist_context(workspace, state, snapshot, directory, f"coursework: record analysis {key} ({analysis['status']})", extra_paths=extra_paths),
            "analysis": analysis}
