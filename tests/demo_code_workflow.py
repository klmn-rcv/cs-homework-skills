"""Retain real CLI code/repair/pause artifacts for human inspection."""
import argparse
import json
from pathlib import Path
import tempfile

from test_code_workflow import CodeWorkflow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix="coursework-code-demo-"))
    root.mkdir(parents=True, exist_ok=True)
    cases = [("delivery", "test_code_only_new_implementation_has_actual_teacher_boundary_oracle_evidence_and_commit"),
             ("repair", "test_known_bug_is_diagnosed_repaired_and_original_cases_rerun_without_rewriting_oracle"),
             ("pause", "test_three_actual_targeted_no_progress_repairs_pause_only_that_issue")]
    evidence = []
    for label, method in cases:
        case = CodeWorkflow(method)
        case.demo_root = root / label
        case.setUp()
        try:
            getattr(case, method)()
            state = json.loads((root / label / "assignment/.coursework/state.json").read_text(encoding="utf-8"))
            session = state["code_sessions"][-1]
            evidence.append({"case": label, "workspace": str(root / label / "assignment"),
                             "status": session["status"], "run_count": len(state["runs"]),
                             "session": session["id"], "issues": session["issues"]})
        finally:
            case.doCleanups()
    (root / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(root)


if __name__ == "__main__":
    main()
