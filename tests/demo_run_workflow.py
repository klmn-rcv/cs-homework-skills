"""Retain real, inspectable execution/budget artifacts through the public CLI."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

from test_run_workflow import RunWorkflow


PROGRAM = """import sys, time
from pathlib import Path
if '--fail' in sys.argv:
    sys.stderr.write('specific failure')
    sys.exit(7)
if '--sleep' in sys.argv:
    time.sleep(float(sys.argv[sys.argv.index('--sleep') + 1]))
    Path(sys.argv[-1]).write_text('actually executed')
print(int(sys.stdin.readline()) * 2)
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New directory; defaults to a retained temporary directory")
    args = parser.parse_args()
    root = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix="coursework-run-demo-"))
    if args.output:
        root.mkdir(parents=True, exist_ok=False)
    scenario = RunWorkflow()
    scenario.root = root
    scenario.workspace = root / "existing-assignment"
    scenario.workspace.mkdir()
    scenario.code = scenario.workspace / "student.py"
    scenario.code.write_text(PROGRAM, encoding="utf-8")
    scenario.git("init", "-q")
    scenario.git("add", "student.py")
    scenario.git("-c", "user.name=Student", "-c", "user.email=student@example.invalid", "commit", "-qm", "student baseline")
    scenario.code.write_text(PROGRAM + "# staged student edit\n", encoding="utf-8")
    scenario.git("add", "student.py")
    scenario.code.write_text(PROGRAM + "# staged student edit\n# unstaged continuation\n", encoding="utf-8")
    code_before = scenario.code.read_bytes()
    staging_before = scenario.git("diff", "--cached", "--binary")
    success = scenario.run_request()
    failure_request = scenario.request()
    failure_request["execution"]["argv"].append("--fail")
    failure = scenario.run_request(failure_request)
    budget_request = scenario.request()
    budget_request["request"] = "按题目要求执行两单位固定实验，先试跑，超过本次短预算先询问；不要改实现。"
    budget_request["execution"].update(argv=[sys.executable, "student.py", "--sleep", "0.04", "full.txt"],
                                       purposes=["experiment"], workload_units=2, output_paths=["full.txt"],
                                       basis="用户明确要求的两单位固定实验；教师样例用于共同验证")
    budget_request["trial"] = {"argv": [sys.executable, "student.py", "--sleep", "0.02", "trial.txt"],
                               "workload_units": 1, "output_paths": ["trial.txt"]}
    budget_request["budget_seconds"] = 0.001
    pending = scenario.run_request(budget_request)
    scenario.assertEqual(pending["run"]["status"], "awaiting_confirmation")
    scenario.assertFalse((scenario.workspace / "full.txt").exists())
    confirmed = json.loads(scenario.cli("run", "--workspace", scenario.workspace, "--confirm", pending["run"]["id"],
                                        "--confirmation", "演示用户明确接受该试跑估时和预算计划，继续同一正式命令。").stdout)
    scenario.assertEqual(success["run"]["execution"]["check"]["status"], "passed")
    scenario.assertEqual(failure["run"]["execution"]["exit_code"], 7)
    scenario.assertEqual(confirmed["run"]["status"], "completed")
    scenario.assertEqual(scenario.code.read_bytes(), code_before)
    scenario.assertEqual(scenario.git("diff", "--cached", "--binary"), staging_before)
    evidence = {"success": success, "failure": failure, "pending": pending, "confirmed": confirmed,
                "source_and_staging_preserved": True,
                "fresh_process_resume": json.loads(scenario.cli("resume", "--workspace", scenario.workspace).stdout)}
    (root / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"demo_root": str(root), "evidence": str(root / "evidence.json"),
               "source_and_staging_preserved": True,
               "summaries": {name: str(scenario.workspace / result["run"]["summary_path"])
                             for name, result in [("success", success), ("failure", failure), ("pending", pending), ("confirmed", confirmed)]}}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
