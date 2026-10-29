#!/usr/bin/env python3
"""Deterministic companion to the model-led coursework Skills."""
import argparse
import json
from pathlib import Path
import sys

from coursework_runtime.native import protect_edits, capture_run
from coursework_runtime.context import resume
from coursework_runtime.planning import save_plan
from coursework_runtime.execution import save_run, confirm_run
from coursework_runtime.results import inspect_results, import_result, link_results, review_result
from coursework_runtime.coding import start_code, step_code
from coursework_runtime.analysis import save_analysis
from coursework_runtime.report import save_report, review_report, review_prose, compile_project
from coursework_runtime.reflection import save_reflection, reply_reflection, review_reflection
from coursework_runtime.acceptance import inspect_acceptance
from coursework_runtime.handoff import save_handoff


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["protect-edits", "capture-run", "compile-project"]:
        native = commands.add_parser(name, help="Optional stable-project compilation and page capture" if name == "compile-project" else "Optional native-edit protection or exact standalone run receipt")
        native.add_argument("--workspace", type=Path, required=True)
        native.add_argument("--input", type=Path, required=True)
    plan = commands.add_parser("plan", help="Save an agent-prepared local-materials plan")
    plan.add_argument("--workspace", type=Path, required=True)
    plan.add_argument("--input", type=Path, required=True)
    plan.add_argument("--new", action="store_true", help="Require a new, independent assignment directory")
    restore = commands.add_parser("resume", help="Read saved context and check current material bytes")
    restore.add_argument("--workspace", type=Path, required=True)
    handoff = commands.add_parser("handoff", help="Save a model-authored note for an authorized writing task")
    handoff.add_argument("--workspace", type=Path, required=True)
    handoff.add_argument("--input", type=Path, required=True)
    execute = commands.add_parser("run", help="Execute existing assignment code and save actual evidence")
    execute.add_argument("--workspace", type=Path, required=True)
    run_mode = execute.add_mutually_exclusive_group(required=True)
    run_mode.add_argument("--input", type=Path)
    run_mode.add_argument("--confirm", help="Continue this saved over-budget run after explicit user confirmation")
    execute.add_argument("--confirmation", help="User's actual confirmation reply")
    results = commands.add_parser("results", help="Inspect current result versions without executing or changing files")
    results.add_argument("--workspace", type=Path, required=True)
    results.add_argument("--input", type=Path, help="Agent-prepared current specifications and current task scope")
    results.add_argument("--offline", action="store_true")
    acceptance = commands.add_parser("check", help="Inspect agent-authored scoped acceptance without writes or execution")
    acceptance.add_argument("--workspace", type=Path, required=True)
    acceptance.add_argument("--input", type=Path, required=True)
    external = commands.add_parser("import-result", help="Attribute and archive actual user-provided result files")
    external.add_argument("--workspace", type=Path, required=True)
    external.add_argument("--input", type=Path, required=True)
    link = commands.add_parser("link-results", help="Bind a derived assignment artifact to exact current result versions")
    link.add_argument("--workspace", type=Path, required=True)
    link.add_argument("--input", type=Path, required=True)
    review = commands.add_parser("review-result", help="Record an actual semantic comparison finding no effect on a result")
    review.add_argument("--workspace", type=Path, required=True)
    review.add_argument("--input", type=Path, required=True)
    for name in ["code-start", "code-step"]:
        code = commands.add_parser(name, help="Preserve model-led coding work and verify fixed independent checks")
        code.add_argument("--workspace", type=Path, required=True)
        code.add_argument("--input", type=Path, required=True)
    analyze = commands.add_parser("analyze", help="Compute and save analysis from exact current result bytes")
    analyze.add_argument("--workspace", type=Path, required=True)
    analyze.add_argument("--input", type=Path, required=True)
    report = commands.add_parser("report", help="Historical staged report version interface; stable projects can use compile-project")
    report.add_argument("--workspace", type=Path, required=True)
    report.add_argument("--input", type=Path, required=True)
    report_review = commands.add_parser("review-report", help="Record actual content and rendered-page review")
    report_review.add_argument("--workspace", type=Path, required=True)
    report_review.add_argument("--input", type=Path, required=True)
    prose = commands.add_parser("review-prose", help="Return agent-authored prose advice against exact source bytes without writes")
    prose.add_argument("--workspace", type=Path, required=True)
    prose.add_argument("--input", type=Path, required=True)
    reflection = commands.add_parser("reflection", help="Preserve grounded model-authored reflection recommendations")
    reflection.add_argument("--workspace", type=Path, required=True)
    reflection.add_argument("--input", type=Path, required=True)
    reflection_reply = commands.add_parser("reflection-reply", help="Preserve explicit attributed accept/edit/replace decisions")
    reflection_reply.add_argument("--workspace", type=Path, required=True)
    reflection_reply.add_argument("--input", type=Path, required=True)
    reflection_review = commands.add_parser("reflection-review", help="Attribute actual evidence comparison without creating human acceptance")
    reflection_review.add_argument("--workspace", type=Path, required=True)
    reflection_review.add_argument("--input", type=Path, required=True)
    restore.add_argument("--offline", action="store_true", help="Compatibility flag; inspections always verify local history only")
    args = parser.parse_args()
    try:
        if args.command in {"protect-edits", "capture-run", "compile-project"}:
            record = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = {"protect-edits": protect_edits, "capture-run": capture_run, "compile-project": compile_project}[args.command](args.workspace, record)
        elif args.command == "plan":
            record = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = save_plan(args.workspace, record, new=args.new)
        elif args.command == "run":
            if args.confirm:
                result = confirm_run(args.workspace, args.confirm, args.confirmation)
            else:
                record = json.loads(args.input.read_text(encoding="utf-8-sig"))
                result = save_run(args.workspace, record)
        elif args.command == "resume":
            result = resume(args.workspace, refresh_online=False)
        elif args.command == "handoff":
            record = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = save_handoff(args.workspace, record)
        elif args.command == "results":
            record = json.loads(args.input.read_text(encoding="utf-8-sig")) if args.input else None
            result = inspect_results(args.workspace, record, refresh_online=False)
        elif args.command == "check":
            record = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = inspect_acceptance(args.workspace, record)
        elif args.command == "import-result":
            record = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = import_result(args.workspace, record)
        elif args.command == "link-results":
            record = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = link_results(args.workspace, record)
        elif args.command == "review-result":
            record = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = review_result(args.workspace, record)
        elif args.command in {"code-start", "code-step"}:
            record = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = start_code(args.workspace, record) if args.command == "code-start" else step_code(args.workspace, record)
        elif args.command == "analyze":
            record = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = save_analysis(args.workspace, record)
        elif args.command == "report":
            record = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = save_report(args.workspace, record)
        elif args.command == "review-report":
            record = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = review_report(args.workspace, record)
        elif args.command == "review-prose":
            record = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = review_prose(args.workspace, record)
        elif args.command == "reflection":
            record = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = save_reflection(args.workspace, record)
        elif args.command == "reflection-reply":
            record = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = reply_reflection(args.workspace, record)
        elif args.command == "reflection-review":
            record = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = review_reflection(args.workspace, record)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
