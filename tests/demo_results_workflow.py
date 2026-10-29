"""Retained two-group coursework demonstration through separate public CLI processes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix="coursework-results-demo-"))
    root.mkdir(parents=True, exist_ok=True)
    workspace = root / "integer-sums"
    workspace.mkdir()
    intake = root / "agent-inputs"
    intake.mkdir()
    receipts = root / "receipts"
    receipts.mkdir()
    cli = Path(__file__).resolve().parents[1] / "skills/cs-homework/scripts/coursework.py"
    (workspace / "solution.py").write_text(
        "from pathlib import Path\nimport sys\n"
        "numbers = list(map(int, Path(sys.argv[1]).read_text().split()))\n"
        "print(sum(numbers))\n"
        "with Path('executed-groups.log').open('a') as stream: stream.write(sys.argv[1] + '\\n')\n", encoding="utf-8")
    (workspace / "group-a.txt").write_text("2 3 5", encoding="utf-8")
    (workspace / "group-b.txt").write_text("7 11 13", encoding="utf-8")
    index = 0

    def call(label, command, record=None):
        nonlocal index
        index += 1
        argv = [sys.executable, "-B", str(cli), command, "--workspace", str(workspace)]
        if record is not None:
            path = intake / f"{index:02d}-{label}.json"
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            argv += ["--input", str(path)]
        actual = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8")
        (receipts / f"{index:02d}-{label}.json").write_text(json.dumps({
            "argv": argv, "exit_code": actual.returncode,
            "stdout": json.loads(actual.stdout) if actual.stdout else None, "stderr": actual.stderr},
            ensure_ascii=False, indent=2), encoding="utf-8")
        if actual.returncode:
            raise RuntimeError(actual.stderr)
        return json.loads(actual.stdout)

    def request(group, expected):
        return {"assignment": {"title": "分组整数求和"},
                "request": "运行已有程序的两组已知答案；有效结果复用，变化后只补跑受影响组，不修改实现。",
                "scope": {"goal": "分组结果及来源", "authorized_behaviors": ["run"]},
                "result_key": group,
                "execution": {"argv": [sys.executable, "solution.py", group + ".txt"],
                              "source_paths": ["solution.py"], "input_paths": [group + ".txt"],
                              "purposes": ["example", "correctness"], "basis": "明确的分组求和作业样例",
                              "dependency_coverage": {"status": "complete", "note": "读取源码；只有指定文本数据影响数值，执行日志仅记录次数。"},
                              "expected": {"stdout": str(expected) + os.linesep, "exit_code": 0,
                                           "basis": "独立手算：2+3+5=10，7+11+13=31，17+19=36"}}}

    a = call("initial-a", "run", request("group-a", 10))
    b = call("initial-b", "run", request("group-b", 31))
    reused_a = call("reuse-a", "run", request("group-a", 10))
    assert reused_a["reused"] and reused_a["result"]["id"] == a["result"]["id"]
    (workspace / "group-a.txt").write_text("17 19", encoding="utf-8")
    changed = call("fresh-context-after-input-change", "resume")
    by_key = {r["key"]: r for r in changed["results"] if r["current"]}
    assert by_key["group-a"]["status"] == "pending_update" and by_key["group-b"]["status"] == "valid"
    limited = call("analysis-only-decision", "results", {"scope": {"authorized_behaviors": ["analyze"]}})
    assert next(r for r in limited["results"] if r["key"] == "group-a")["update_action"] == "scope_decision_required"
    updated_a = call("update-only-a", "run", request("group-a", 36))
    reused_b = call("reuse-unchanged-b", "run", request("group-b", 31))
    assert reused_b["reused"] and reused_b["result"]["id"] == b["result"]["id"]
    final = call("fresh-context-final", "resume")
    executions = (workspace / "executed-groups.log").read_text().splitlines()
    assert executions == ["group-a.txt", "group-b.txt", "group-a.txt"]
    assert len(final["state"]["results"]) == 3
    old_stdout = workspace / a["run"]["execution"]["stdout"]["path"]
    assert old_stdout.read_text().strip() == "10"
    assert updated_a["run"]["execution"]["stdout"]["text"].strip() == "36"
    evidence = {"workspace": str(workspace), "receipts": str(receipts), "actual_executed_groups": executions,
                "original_a": a["result"]["id"], "updated_a": updated_a["result"]["id"],
                "unchanged_b": b["result"]["id"], "historical_a_output": str(old_stdout),
                "result_versions": len(final["state"]["results"]),
                "current_results": [r for r in final["results"] if r["current"]],
                "scope_decision": next(r for r in limited["results"] if r["key"] == "group-a")["update_action"]}
    (root / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
