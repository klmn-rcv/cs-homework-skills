"""Compile stable LaTeX projects; retain historical staged report interfaces."""
from pathlib import Path
import hashlib
import re
import uuid

from .context import STATE_DIR, fingerprint, resume, write_json
from .execution import execute
from .results import actual_path, captured_files, file_issue, prepare_context, persist_context, record_issues, reserve_directory


def review_prose(workspace, record):
    """Bind the agent's concrete advice to read source bytes; never persist it."""
    if not isinstance(record, dict) or "report" not in record.get("scope", {}).get("authorized_behaviors", []):
        raise ValueError("Current scope must authorize report prose review")
    sources = record.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Prose review needs exact source paths and SHA-256 hashes")
    texts, observed = {}, []
    for source in sources:
        name = source.get("path") if isinstance(source, dict) else None
        if not isinstance(name, str) or not name or name in texts:
            raise ValueError("Prose review source paths must be unique nonempty strings")
        path = actual_path(workspace, name)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != source.get("sha256"):
            raise ValueError(f"Prose review source changed; read and assess current bytes: {name}")
        texts[name] = data.decode("utf-8-sig")
        observed.append({"path": name, "sha256": digest})
    if not isinstance(record.get("reading_basis"), str) or not record["reading_basis"].strip():
        raise ValueError("Prose review needs the agent's actual reading basis")
    advice = record.get("advice")
    if not isinstance(advice, list):
        raise ValueError("Prose review advice must be a list; natural accurate prose may need no changes")
    for item in advice:
        if not isinstance(item, dict) or item.get("kind") not in {"style", "retain", "technical"}:
            raise ValueError("Each prose advice item needs kind=style, retain or technical")
        if any(not isinstance(item.get(k), str) or not item[k].strip() for k in ["path", "quote", "suggestion", "basis"]):
            raise ValueError("Prose advice needs source path, actual quote, concrete suggestion and basis")
        if item["path"] not in texts or item["quote"] not in texts[item["path"]]:
            raise ValueError("Prose advice must quote the actual declared source")
    return {"workspace": str(Path(workspace).resolve()), "mode": "review", "sources": observed,
            "reading_basis": record["reading_basis"], "advice": advice,
            "assessment_origin": "agent", "limitation": "Source identity and excerpts checked; semantic and style judgments are the agent's assessment"}


def report_checks(workspace, state, results, artifacts, analyses, *, reflections=None):
    from .reflection import reflection_checks, report_reflections
    if reflections is None:
        reflections = reflection_checks(workspace, state, results, artifacts, analyses)
    checks = []
    registries = {"result_ids": results, "artifact_ids": artifacts, "analysis_ids": analyses}
    for report in state.get("reports", []):
        issues = record_issues(workspace, report)
        for item in [*report["dependencies"], *report["files"]]:
            issue = file_issue(workspace, item)
            if issue:
                issues.append(issue)
        for field, registry in registries.items():
            by_id = {i["id"]: i for i in registry}
            for source_id in report.get(field, []):
                source = by_id.get(source_id)
                if not source or not source["current"] or source["status"] != "valid":
                    issues.append({field: source_id, "reason": "Report source no longer current and valid"})
        reviews = [r for r in state.get("report_reviews", []) if r["report_id"] == report["id"]]
        review = reviews[-1] if reviews else None
        if review:
            issues += record_issues(workspace, review)
        status = report["status"]
        try:
            _, reflection_status = report_reflections(report, reflections)
        except ValueError as exc:
            reflection_status = report.get("reflection_status", "not_linked")
            issues.append({"kind": "reflection", "reason": str(exc)})
        if status != "failed" and issues:
            status = "pending_update"
        elif status == "awaiting_review" and review:
            status = "valid" if review["passed"] else "review_failed"
        checks.append({"id": report["id"], "key": report["key"], "current": state.get("report_heads", {}).get(report["key"]) == report["id"],
                       "status": status, "reflection_status": reflection_status, "issues": issues, "project": report["project"], "record_path": report["receipt"]["path"]})
    return checks


def save_report(workspace, record):
    from .context import require_writable_request
    require_writable_request(record)
    if not isinstance(record, dict) or "report" not in record.get("scope", {}).get("authorized_behaviors", []):
        raise ValueError("Current scope must authorize report")
    if record["scope"].get("report_mode") == "review":
        raise ValueError("Review-only scope permits advice through review-prose, not report writes")
    key = record.get("report_key")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", key):
        raise ValueError("report_key must be a safe stable label of 1-64 characters")
    content = record.get("content_review")
    if not isinstance(content, dict) or not isinstance(content.get("requirement_map"), list) or not content["requirement_map"]:
        raise ValueError("Report needs the agent's actual requirement-to-content map")
    for field in ["structure_basis", "format_basis", "technical_review", "voice_review", "thoughts_basis"]:
        if not isinstance(content.get(field), str) or not content[field].strip():
            raise ValueError(f"Report content_review needs {field}")
    names, staged = [], []
    for item in record.get("files", []):
        name = item.get("path") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name or Path(name).is_absolute() or any(p in {"..", ".git", STATE_DIR, "build", "pages"} for p in Path(name).parts):
            raise ValueError("Report files must be unique relative project paths outside build/pages/metadata")
        if name in names:
            raise ValueError("Report file paths must be unique")
        source = actual_path(workspace, item.get("source", "")).resolve()
        if not source.is_file():
            raise ValueError("Staged report file is missing")
        names.append(name)
        staged.append((name, source, source.read_bytes()))
    main = record.get("main_file")
    if main not in names or Path(main).suffix != ".tex":
        raise ValueError("main_file must name a supplied .tex source")
    if not isinstance(record.get("source_only", False), bool):
        raise ValueError("source_only must be boolean")
    if not record.get("source_only", False):
        compiler_options(record)
    dependencies = record.get("source_paths", [])
    if not isinstance(dependencies, list) or any(not isinstance(p, str) or not p or not actual_path(workspace, p).is_file() for p in dependencies):
        raise ValueError("source_paths must identify actual requirement/code/thought/format files")
    workspace = Path(workspace).resolve()
    previous = resume(workspace) if (workspace / STATE_DIR / "state.json").exists() else None
    from .reflection import report_reflections
    reflection_sources, reflection_status = report_reflections(record, previous["reflections"] if previous else [])
    selected = {}
    for field, registry in [("result_ids", "results"), ("artifact_ids", "artifacts"), ("analysis_ids", "analyses")]:
        ids = record.get(field, [])
        if not isinstance(ids, list) or any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
            raise ValueError(f"{field} must contain unique exact IDs")
        checks = {i["id"]: i for i in previous[registry]} if previous else {}
        if any(i not in checks or not checks[i]["current"] or checks[i]["status"] != "valid" for i in ids):
            raise ValueError("Report requires exact current valid results, artifacts and analyses")
        selected[field] = ids
    artifacts = {a["id"]: a for a in previous["state"].get("result_artifacts", [])} if previous else {}
    for item, (_, _, data) in zip(record["files"], staged):
        artifact_id = item.get("artifact_id")
        if artifact_id is not None and (artifact_id not in selected["artifact_ids"] or hashlib.sha256(data).hexdigest() != artifacts[artifact_id]["sha256"]):
            raise ValueError("A linked report asset must match the exact selected current artifact bytes")
    if previous:
        required = {i for a in previous["state"].get("result_artifacts", []) if a["id"] in selected["artifact_ids"] for i in a["result_ids"]}
        required |= {i["result_id"] for a in previous["state"].get("analyses", []) if a["id"] in selected["analysis_ids"] for i in a["inputs"]}
        if not required.issubset(selected["result_ids"]):
            raise ValueError("Include every exact result_id underlying selected analyses and artifacts")
    workspace, state, snapshot = prepare_context(workspace, record)
    report_id = uuid.uuid4().hex
    directory = workspace / STATE_DIR / "reports" / report_id
    project = workspace / "reports" / key / report_id
    reserve_directory(workspace, directory, snapshot)
    reserve_directory(workspace, project, snapshot)
    directory.mkdir(parents=True)
    project.mkdir(parents=True)
    files = []
    for name, source, data in staged:
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files.append({"path": target.relative_to(workspace).as_posix(), "sha256": fingerprint(target), "staged_from": str(source),
                      "artifact_id": next(i.get("artifact_id") for i in record["files"] if i["path"] == name)})
    captured = captured_files(workspace, directory / "sources", dependencies)
    report = {"id": report_id, "key": key, "created_at": state["updated_at"], "status": "source_only",
              "project": project.relative_to(workspace).as_posix(), "main_file": main, "files": files,
              "dependencies": [{"path": i["path"], "sha256": i["sha256"]} for i in captured],
              "source_snapshots": captured, "content_review": content, "reflection_sources": reflection_sources, "reflection_status": reflection_status, **selected}
    if previous:
        report["result_sources"] = [{"id": r["id"], "key": r["key"], "origin": r["origin"], "verification": r["verification"], "provenance": r.get("provenance")}
                                    for r in previous["state"].get("results", []) if r["id"] in selected["result_ids"]]
    if not record.get("source_only", False):
        compile_report(workspace, record, report, directory, project, snapshot)
    report["evidence"] = [{"path": p.relative_to(workspace).as_posix(), "sha256": fingerprint(p)}
                          for p in [*directory.rglob("*"), *project.rglob("*")] if p.is_file()]
    write_json(directory / "record.json", report)
    report["receipt"] = {"path": (directory / "record.json").relative_to(workspace).as_posix(), "sha256": fingerprint(directory / "record.json")}
    state["reports"] = [*state.get("reports", []), report]
    state["report_heads"] = {**state.get("report_heads", {}), key: report_id}
    return {**persist_context(workspace, state, snapshot, directory, f"coursework: record report {key} ({report['status']})",
                              extra_paths=[p.relative_to(workspace).as_posix() for p in project.rglob("*") if p.is_file()]), "report": report}


def compiler_options(record):
    compiler = record.get("compiler", {})
    renderer = record.get("renderer", {})
    if not isinstance(compiler, dict) or not isinstance(renderer, dict):
        raise ValueError("Compiler and renderer options must be objects")
    engine = compiler.get("engine", "tectonic")
    executable = compiler.get("executable", engine)
    if engine not in {"tectonic", "xelatex", "pdflatex", "lualatex", "latexmk"} or not isinstance(executable, str) or not executable:
        raise ValueError("Compiler needs a supported LaTeX engine and literal executable")
    extra = compiler.get("args", [])
    environment = compiler.get("env", {})
    capture = compiler.get("capture_env", [])
    if not isinstance(extra, list) or any(not isinstance(a, str) or not a for a in extra) or not isinstance(environment, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in environment.items()) or not isinstance(capture, list) or any(not isinstance(k, str) for k in capture):
        raise ValueError("Compiler args/environment must be literal strings")
    dpi = renderer.get("dpi", 120)
    render_executable = renderer.get("executable", "pdftoppm")
    if isinstance(dpi, bool) or not isinstance(dpi, int) or not 72 <= dpi <= 300 or not isinstance(render_executable, str) or not render_executable:
        raise ValueError("Renderer needs a literal executable and integer dpi from 72 to 300")
    return engine, executable, extra, environment, capture, render_executable, dpi


def compile_report(workspace, record, report, directory, project, snapshot, output_directory=None):
    engine, executable, extra, environment, capture, render_executable, dpi = compiler_options(record)
    build = (output_directory or project) / "build"
    build.mkdir()
    pdf = build / (Path(report["main_file"]).stem + ".pdf")
    if engine == "tectonic":
        argv = [executable, "-X", "compile", "--untrusted", "--keep-logs", "--keep-intermediates", *extra, "--outdir", str(build), report["main_file"]]
    elif engine == "latexmk":
        argv = [executable, "-pdf", "-interaction=nonstopmode", "-halt-on-error", *extra, "-outdir=" + str(build), report["main_file"]]
    else:
        argv = [executable, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", *extra, "-output-directory=" + str(build), report["main_file"]]
    spec = {"argv": argv, "cwd": str(project), "source_paths": [f["path"] for f in report["files"]],
            "input_paths": [d["path"] for d in report["dependencies"]], "output_paths": [str(pdf)], "env": environment, "capture_env": capture}
    report["compilation"] = []
    for index in range(2 if engine in {"xelatex", "pdflatex", "lualatex"} else 1):
        execution = execute(workspace, spec, directory / f"compile-{index + 1}", snapshot)
        report["compilation"].append(execution)
        if execution["status"] != "completed":
            break
    final = report["compilation"][-1]
    log = "\n".join(final.get(k, {}).get("text", "") for k in ["stdout", "stderr"])
    log += "\n" + "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in build.rglob("*.log"))
    patterns = {"undefined_reference": r"(?i)(undefined references|undefined citations|(?:reference|citation)\s+[^\n]*undefined|unresolved references|rerun to get cross-references right)",
                "missing_glyph": r"(?i)missing character:", "layout_warning": r"(?i)(overfull|underfull)\s+\\[hv]box"}
    report["diagnostics"] = {k: list(dict.fromkeys(m.group(0) for m in re.finditer(pattern, log))) for k, pattern in patterns.items()}
    unchanged = all(a.get("sha256") == b.get("sha256") for e in report["compilation"]
                    for a, b in zip(e["source_before"]["files"], e["source_after"]["files"]))
    if final["status"] != "completed" or not pdf.is_file() or not pdf.read_bytes().startswith(b"%PDF-") or not unchanged or report["diagnostics"]["undefined_reference"] or report["diagnostics"]["missing_glyph"]:
        report.update(status="failed", diagnostic="Compilation, PDF output, source stability or reference/glyph checks failed; inspect preserved logs and source")
        return
    report.update(status="awaiting_review", pdf={"path": pdf.relative_to(workspace).as_posix(), "sha256": fingerprint(pdf)})
    pages = (output_directory or project) / "pages"
    pages.mkdir()
    render_spec = {"argv": [render_executable, "-png", "-r", str(dpi), str(pdf), str(pages / "page")],
                   "source_paths": [str(pdf)], "output_paths": []}
    report["rendering"] = execute(workspace, render_spec, directory / "render", snapshot)
    report["pages"] = [{"path": p.relative_to(workspace).as_posix(), "sha256": fingerprint(p)} for p in sorted(pages.glob("page-*.png")) if p.is_file()]
    if report['rendering']['status'] != 'completed' or not report['pages']:
        report.update(status='failed', diagnostic='Current PDF rendering failed; inspect the preserved renderer output')


def compile_project(workspace, record):
    """Optionally compile an existing stable project, without a stage registry."""
    from .native import current_request, directory_for
    from .git import begin_task
    scope = current_request(record)
    if 'report' not in scope.get('authorized_behaviors', []):
        raise ValueError('Current scope must authorize report compilation')
    if record.get('source_only'):
        raise ValueError('Source-only requests need no compile-project call')
    compiler_options(record)
    workspace = Path(workspace).resolve()
    project = (workspace / record.get('project', '.')).resolve()
    main = record.get('main_file', 'main.tex')
    source = (project / main).resolve()
    if not project.is_relative_to(workspace) or not source.is_relative_to(project) or source.suffix != '.tex' or not source.is_file():
        raise ValueError('Supply an existing LaTeX main file inside the assignment project')
    # Capture every project input, including included sources/assets not known to
    # the caller. Generated build/page and metadata trees are not source inputs.
    excluded = {'.git', '.coursework', 'build', 'pages'}
    files = [p for p in project.rglob('*') if p.is_file() and not excluded.intersection(p.relative_to(project).parts) and p.suffix.lower() not in {'.log', '.aux', '.synctex', '.toc', '.out'}]
    if any(p.resolve() != p for p in files):
        raise ValueError('Project inputs must not traverse filesystem links')
    dependencies = record.get('source_paths', [])
    if not isinstance(dependencies, list) or any(not isinstance(p, str) or not actual_path(workspace, p).is_file() for p in dependencies):
        raise ValueError('source_paths must name actual supporting materials')
    directory = directory_for(workspace, 'builds')
    snapshot = begin_task(workspace)
    directory.mkdir(parents=True)
    report = {'request': record['request'], 'scope': scope, 'project': project.relative_to(workspace).as_posix(), 'main_file': source.relative_to(project).as_posix(),
              'files': [{'path': p.relative_to(workspace).as_posix(), 'sha256': fingerprint(p)} for p in files],
              'dependencies': [{'path': p, 'sha256': fingerprint(actual_path(workspace, p))} for p in dependencies]}
    compile_report(workspace, record, report, directory, project, snapshot, output_directory=directory)
    report['receipt'] = (directory / 'receipt.json').relative_to(workspace).as_posix()
    write_json(directory / 'receipt.json', report)
    return report


def review_report(workspace, record):
    from .context import require_writable_request
    require_writable_request(record)
    if not isinstance(record, dict) or "report" not in record.get("scope", {}).get("authorized_behaviors", []):
        raise ValueError("Current scope must authorize report review")
    if record["scope"].get("report_mode") == "review":
        raise ValueError("Review-only advice uses review-prose; review-report persists acceptance evidence")
    workspace = Path(workspace).resolve()
    view = resume(workspace)
    report_id = record.get("report_id")
    report = next((r for r in view["state"].get("reports", []) if r["id"] == report_id), None)
    check = next((r for r in view["reports"] if r["id"] == report_id), None)
    if not report or not check["current"] or check["issues"] or report["status"] != "awaiting_review":
        raise ValueError("Review requires an intact current compiled report and valid upstream sources")
    assessments = record.get("checks")
    if not isinstance(assessments, dict):
        raise ValueError("Review needs actual content and visual checks")
    for field in ["technical", "numerical", "structure", "voice", "visual"]:
        item = assessments.get(field)
        if not isinstance(item, dict) or item.get("status") not in {"passed", "failed", "unverified"} or not isinstance(item.get("basis"), str) or not item["basis"].strip():
            raise ValueError(f"Review needs actual {field} status and basis")
    pages = report.get("pages", [])
    if assessments["visual"]["status"] == "passed" and (not pages or report["rendering"]["status"] != "completed" or assessments["visual"].get("pages") != [p["path"] for p in pages]):
        raise ValueError("A passing visual check must inspect every actual rendered page of this report")
    workspace, state, snapshot = prepare_context(workspace, record)
    directory = workspace / STATE_DIR / "report-reviews" / uuid.uuid4().hex
    reserve_directory(workspace, directory, snapshot)
    review = {"report_id": report_id, "created_at": state["updated_at"], "checks": assessments,
              "passed": all(assessments[f]["status"] == "passed" for f in ["technical", "numerical", "structure", "voice", "visual"]),
              "evidence": [report["receipt"], report["pdf"], *pages]}
    write_json(directory / "record.json", review)
    review["receipt"] = {"path": (directory / "record.json").relative_to(workspace).as_posix(), "sha256": fingerprint(directory / "record.json")}
    state["report_reviews"] = [*state.get("report_reviews", []), review]
    return {**persist_context(workspace, state, snapshot, directory, "coursework: record report content and page review"), "report_review": review}
