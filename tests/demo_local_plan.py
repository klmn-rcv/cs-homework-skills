"""Retain an inspectable local-materials demo, using only the public companion CLI."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from test_local_plan import LocalPlanWorkflow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New directory; defaults to a temporary directory")
    args = parser.parse_args()
    root = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix="coursework-plan-demo-"))
    if args.output:
        root.mkdir(parents=True, exist_ok=False)
    scenario = LocalPlanWorkflow()
    scenario.root = root
    scenario.materials = root / "materials"
    shutil.copytree(Path(__file__).parent / "fixtures/local-plan", scenario.materials)
    workspace = root / "existing-assignment"
    workspace.mkdir()
    scenario.git(workspace, "init", "-q")
    student = workspace / "student.py"
    student.write_text("# original student code\n", encoding="utf-8")
    scenario.git(workspace, "add", "student.py")
    scenario.git(workspace, "-c", "user.name=Student", "-c", "user.email=student@example.invalid",
                 "commit", "-qm", "student baseline")
    student.write_text("# staged student work\n", encoding="utf-8")
    scenario.git(workspace, "add", "student.py")
    student.write_text("# staged student work\n# unstaged continuation\n", encoding="utf-8")
    index_before = scenario.git(workspace, "diff", "--cached", "--binary")
    first = json.loads(scenario.plan(workspace).stdout)
    # A later conversation only needs the assignment path and current request.
    restored = json.loads(scenario.cli("resume", "--workspace", workspace).stdout)
    continued = scenario.record()
    continued["request"] = "沿用已确认范围，继续原计划；不重复询问已有决定。"
    continued["decisions"] = []
    second = json.loads(scenario.plan(workspace, continued).stdout)
    scenario.assertEqual(scenario.git(workspace, "diff", "--cached", "--binary"), index_before)
    scenario.assertEqual(student.read_text(encoding="utf-8"), "# staged student work\n# unstaged continuation\n")
    scenario.assertEqual(second["state"]["decisions"], first["state"]["decisions"])
    plan_text = (workspace / ".coursework/plan.md").read_text(encoding="utf-8")
    with (scenario.materials / "brief.md").open("a", encoding="utf-8") as stream:
        stream.write("课程后续补充：检查多条等长路径的行为。\n")
    changed = json.loads(scenario.cli("resume", "--workspace", workspace).stdout)
    scenario.assertTrue(changed["needs_review"])
    evidence = {"first": first, "fresh_process_resume": restored, "continued": second,
                "after_material_change": changed,
                "git_status": scenario.git(workspace, "status", "--short"),
                "preexisting_index_preserved": True, "preexisting_working_copy_preserved": True}
    (root / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(plan_text)
    print(json.dumps({"demo_root": str(root), "evidence": str(root / "evidence.json"),
                      "git_status": evidence["git_status"], "needs_review_after_change": True},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
