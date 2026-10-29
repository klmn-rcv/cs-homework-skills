"""Result lifecycle at the public CLI: real execution, files, receipts and resume."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[1] / "skills/cs-homework/scripts/coursework.py"


class ResultsWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "assignment"
        self.workspace.mkdir()
        (self.workspace / "sum.py").write_text(
            "import sys\nfrom pathlib import Path\n"
            "data = Path(sys.argv[1]).read_text().split()\n"
            "print(sum(map(int, data)))\n"
            "with Path('executions.txt').open('a') as log: log.write(sys.argv[1] + '\\n')\n",
            encoding="utf-8")
        (self.workspace / "a.txt").write_text("1 2 3", encoding="utf-8")
        (self.workspace / "b.txt").write_text("10 20", encoding="utf-8")

    def cli(self, *args, ok=True, env=None):
        result = subprocess.run([sys.executable, "-B", str(CLI), *map(str, args)],
                                capture_output=True, text=True, encoding="utf-8", env=env)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        return result

    def input(self, record):
        path = self.root / "input.json"
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        return path

    def request(self, key="a", expected="6"):
        return {"assignment": {"title": "两组独立求和"},
                "request": "仅执行已有程序的要求样例，复用有效结果，不修改实现。",
                "scope": {"goal": "真实样例结果", "authorized_behaviors": ["run"]},
                "result_key": key,
                "execution": {"argv": [sys.executable, "sum.py", key + ".txt"],
                              "source_paths": ["sum.py"], "input_paths": [key + ".txt"],
                              "purposes": ["example", "correctness"], "basis": "给定整数求和样例",
                              "dependency_coverage": {"status": "complete", "note": "读过程序；只读取声明数据和源码，日志不影响计算。"},
                              "expected": {"stdout": expected + os.linesep, "exit_code": 0,
                                           "basis": "独立手算 1+2+3=6 或 10+20=30"}}}

    def run_result(self, record):
        return self.cli("run", "--workspace", self.workspace, "--input", self.input(record))

    def test_unchanged_result_reuses_actual_evidence_without_new_execution_or_history(self):
        first = self.run_result(self.request())
        result_id = first["result"]["id"]
        second = self.run_result(self.request())
        self.assertTrue(second["reused"])
        self.assertEqual(second["result"]["id"], result_id)
        self.assertEqual(second["state"]["revision"], first["state"]["revision"])
        self.assertEqual((self.workspace / "executions.txt").read_text(), "a.txt\n")
        resumed = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(resumed["results"][0]["status"], "valid")
        self.assertEqual(resumed["results"][0]["verification"]["status"], "passed")

    def test_changed_one_group_updates_only_that_group_and_keeps_historical_bytes_on_resume(self):
        first_a = self.run_result(self.request())
        first_b = self.run_result(self.request("b", "30"))
        a_id, b_id = first_a["result"]["id"], first_b["result"]["id"]
        old_stdout = self.workspace / first_a["run"]["execution"]["stdout"]["path"]
        (self.workspace / "a.txt").write_text("4 5", encoding="utf-8")
        resumed = self.cli("resume", "--workspace", self.workspace)
        by_id = {item["id"]: item for item in resumed["results"]}
        self.assertEqual(by_id[a_id]["status"], "pending_update")
        self.assertEqual(by_id[b_id]["status"], "valid")
        self.assertTrue(resumed["needs_review"])
        self.assertEqual(by_id[a_id]["issues"][0]["path"], "a.txt")
        new_a = self.run_result(self.request(expected="9"))
        self.assertNotEqual(new_a["result"]["id"], a_id)
        self.assertEqual(old_stdout.read_text(), "6\n")
        self.assertEqual(new_a["run"]["execution"]["stdout"]["text"], "9" + os.linesep)
        still_b = self.run_result(self.request("b", "30"))
        self.assertTrue(still_b["reused"])
        self.assertEqual(still_b["result"]["id"], b_id)
        self.assertEqual((self.workspace / "executions.txt").read_text(), "a.txt\nb.txt\na.txt\n")
        final = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(final["state"]["result_heads"], {"a": new_a["result"]["id"], "b": b_id})
        self.assertEqual(len(final["state"]["results"]), 3)
        self.assertTrue((self.workspace / ".coursework/history/0001.json").is_file())

    def test_parameter_change_can_be_inspected_without_permission_to_rerun(self):
        first = self.run_result(self.request())
        desired = self.request()["execution"]
        desired["argv"] = [sys.executable, "sum.py", "b.txt"]
        desired["input_paths"] = ["b.txt"]
        inspection = self.cli("results", "--workspace", self.workspace, "--input", self.input({
            "requested_results": [{"key": "a", "specification": desired}],
            "scope": {"authorized_behaviors": ["analyze"]}}))
        self.assertEqual(inspection["results"][0]["status"], "pending_update")
        self.assertEqual(inspection["results"][0]["issues"][0]["kind"], "parameters")
        self.assertEqual(inspection["results"][0]["update_action"], "scope_decision_required")
        self.assertEqual((self.workspace / "executions.txt").read_text(), "a.txt\n")
        self.assertEqual(inspection["state"]["revision"], first["state"]["revision"])

    def test_external_results_retain_attribution_and_captured_bytes_without_claiming_execution(self):
        external = self.root / "provided.csv"
        external.write_text("n,total\n3,6\n4,10\n", encoding="utf-8")
        record = {"assignment": {"title": "现有结果分析"}, "request": "只分析我提供的 CSV，不重新运行。",
                  "scope": {"goal": "已有数据来源", "authorized_behaviors": ["analyze"]},
                  "result_key": "provided-table", "data_paths": [str(external)],
                  "provenance": {"provided_by": "user", "location": "用户提供的 CSV 文件", "description": "用户称来自其先前运行，未提供命令和源码快照"}}
        imported = self.cli("import-result", "--workspace", self.workspace, "--input", self.input(record))
        result = imported["result"]
        self.assertEqual(result["origin"], "external")
        self.assertEqual(result["verification"]["status"], "unverified")
        self.assertEqual(result["provenance"], record["provenance"])
        self.assertEqual(imported["results"][0]["status"], "valid")
        self.assertEqual(imported["state"].get("runs", []), [])
        captured = self.workspace / result["data"][0]["snapshot_path"]
        self.assertEqual(captured.read_bytes(), external.read_bytes())
        external.write_text("n,total\n3,99\n", encoding="utf-8")
        resumed = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(resumed["results"][0]["status"], "pending_update")
        self.assertEqual(captured.read_text(), "n,total\n3,6\n4,10\n")
        self.assertFalse((self.workspace / "executions.txt").exists())

    def test_missing_or_tampered_evidence_and_source_mutation_are_not_current_valid_results(self):
        first = self.run_result(self.request())
        stdout = self.workspace / first["run"]["execution"]["stdout"]["path"]
        stdout.write_bytes(b"forged 999")
        view = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(view["results"][0]["status"], "pending_update")
        self.assertEqual(view["results"][0]["issues"][0]["kind"], "evidence")
        stdout.unlink()
        view = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(view["results"][0]["issues"][0]["reason"], "missing")
        (self.workspace / "mutator.py").write_text(
            "from pathlib import Path\nprint(Path('a.txt').read_text())\nPath('a.txt').write_text('changed while running')\n",
            encoding="utf-8")
        request = self.request()
        request["result_key"] = "mutating-input"
        request["execution"].update(argv=[sys.executable, "mutator.py"], source_paths=["mutator.py"],
                                       expected={"stdout": "1 2 3" + os.linesep, "basis": "Known original input text"})
        result = self.run_result(request)
        check = next(c for c in result["results"] if c["key"] == "mutating-input")
        self.assertEqual(result["run"]["status"], "completed")
        self.assertEqual(check["status"], "pending_update")
        self.assertIn("execution_consistency", [i["kind"] for i in check["issues"]])

    def test_derived_artifact_is_bound_to_exact_result_versions_and_affected_only_by_its_sources(self):
        a = self.run_result(self.request())
        b = self.run_result(self.request("b", "30"))
        table = self.workspace / "comparison.md"
        table.write_text("A: 6; B: 30\n", encoding="utf-8")
        request = {"assignment": {"title": "两组独立求和"}, "request": "用现有有效结果整理表格，不重新运行。",
                   "scope": {"goal": "可追溯表格", "authorized_behaviors": ["analyze"]},
                   "artifact": {"path": "comparison.md", "kind": "analysis",
                                "result_ids": [a["result"]["id"], b["result"]["id"]],
                                "basis": "表格数值分别读取两条运行记录的 stdout；没有独立测量。"}}
        linked = self.cli("link-results", "--workspace", self.workspace, "--input", self.input(request))
        self.assertEqual(linked["artifacts"][0]["status"], "valid")
        self.assertEqual(linked["artifact"]["result_ids"], request["artifact"]["result_ids"])
        snapshot = self.workspace / linked["artifact"]["snapshot_path"]
        self.assertEqual(snapshot.read_bytes(), table.read_bytes())
        (self.workspace / "a.txt").write_text("4 5", encoding="utf-8")
        resumed = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(resumed["artifacts"][0]["status"], "pending_update")
        self.assertEqual(resumed["artifacts"][0]["issues"][0]["result_id"], a["result"]["id"])
        new_a = self.run_result(self.request(expected="9"))
        request["artifact"]["result_ids"] = [a["result"]["id"], new_a["result"]["id"]]
        bad = self.cli("link-results", "--workspace", self.workspace, "--input", self.input(request), ok=False)
        self.assertEqual(bad.returncode, 2)
        self.assertIn("current", json.loads(bad.stderr)["error"])
        self.assertEqual(snapshot.read_text(), "A: 6; B: 30\n")

    def test_explicit_nonimpact_review_reuses_old_run_without_claiming_current_code_was_executed(self):
        first = self.run_result(self.request())
        code = self.workspace / "sum.py"
        code.write_text(code.read_text(encoding="utf-8") + "# Explanation only; executable statements unchanged.\n", encoding="utf-8")
        stale = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(stale["results"][0]["status"], "pending_update")
        record = {"assignment": {"title": "两组独立求和"}, "request": "只分析现有结果；源码仅补了注释，请判断影响。",
                  "scope": {"goal": "复核结果适用性", "authorized_behaviors": ["analyze"]},
                  "result_id": first["result"]["id"], "assessment": "unaffected",
                  "note": "对照原始运行源码快照和当前文件，唯一新增行是 Python 注释；输入、执行语句、参数及条件未改。",
                  "specification": self.request()["execution"]}
        reviewed = self.cli("review-result", "--workspace", self.workspace, "--input", self.input(record))
        self.assertEqual(reviewed["results"][0]["status"], "valid")
        self.assertTrue(reviewed["results"][0]["applicability_review"])
        self.assertEqual(len(reviewed["state"]["runs"]), 1)
        reused = self.run_result(self.request())
        self.assertTrue(reused["reused"])
        original = self.workspace / reused["run"]["execution"]["source_before"]["files"][0]["snapshot_path"]
        self.assertNotIn(b"Explanation only", original.read_bytes())
        self.assertEqual((self.workspace / "executions.txt").read_text(), "a.txt\n")
        code.write_text(code.read_text(encoding="utf-8").replace("sum(map(int, data))", "999"), encoding="utf-8")
        changed_again = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(changed_again["results"][0]["status"], "pending_update")

    def test_prior_saved_run_without_result_registry_is_adopted_after_review_without_execution(self):
        original = self.run_result(self.request())
        # A supported schema-1 context from the earlier run-only package: actual
        # run evidence exists, but no result registry or dependency assessment.
        state = original["state"]
        for key in ["results", "result_heads", "result_requests"]:
            state.pop(key)
        state_path = self.workspace / ".coursework/state.json"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        registry = self.workspace / ".coursework/results"
        registry.rename(self.root / "later-version-registry")
        subprocess.run(["git", "-C", str(self.workspace), "add", ".coursework"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.workspace), "-c", "user.name=Fixture", "-c", "user.email=fixture@local.invalid",
                        "commit", "-qm", "fixture: earlier schema-1 run-only context"], check=True, capture_output=True)
        review = {"assignment": state["assignment"], "request": "分析上次保存的真实结果，不重新运行。",
                  "scope": {"goal": "恢复旧运行", "authorized_behaviors": ["analyze"]},
                  "run_id": original["run"]["id"], "result_key": "a", "assessment": "unaffected",
                  "note": "读取旧命令、输出和源码快照，核对当前文件、输入及条件均一致；补充完整依赖声明。",
                  "specification": self.request()["execution"]}
        adopted = self.cli("review-result", "--workspace", self.workspace, "--input", self.input(review))
        self.assertEqual(adopted["results"][0]["status"], "valid")
        self.assertEqual(adopted["state"]["results"][0]["origin"], "workflow-run")
        self.assertEqual(adopted["state"]["results"][0]["run_id"], original["run"]["id"])
        self.assertEqual(len(adopted["state"]["runs"]), 1)
        self.assertEqual((self.workspace / "executions.txt").read_text(), "a.txt\n")

    def test_new_session_environment_does_not_invalidate_unrelated_conditions(self):
        (self.workspace / "sum.py").write_text(
            "import os,sys\nfrom pathlib import Path\n"
            "print(sum(map(int, Path(sys.argv[1]).read_text().split())) * int(os.environ['COURSEWORK_FACTOR']))\n"
            "with Path('executions.txt').open('a') as log: log.write('actual\\n')\n", encoding="utf-8")
        record = self.request()
        record["execution"]["capture_env"] = ["COURSEWORK_FACTOR"]
        path = self.input(record)
        original_env = {**os.environ, "COURSEWORK_FACTOR": "1", "UNRELATED_SESSION": "old-chat"}
        first = self.cli("run", "--workspace", self.workspace, "--input", path, env=original_env)
        next_env = {**original_env, "UNRELATED_SESSION": "new-chat"}
        second = self.cli("run", "--workspace", self.workspace, "--input", path, env=next_env)
        self.assertTrue(second["reused"])
        self.assertEqual(second["result"]["id"], first["result"]["id"])
        changed = self.cli("resume", "--workspace", self.workspace, env={**next_env, "COURSEWORK_FACTOR": "2"})
        self.assertEqual(changed["results"][0]["status"], "pending_update")
        self.assertEqual(changed["results"][0]["issues"][0]["kind"], "environment")
        self.assertEqual((self.workspace / "executions.txt").read_text(), "actual\n")

    def test_requirement_material_change_remains_unknown_until_actual_nonimpact_assessment(self):
        brief = self.workspace / "brief.md"
        brief.write_text("计算给定整数之和。\n", encoding="utf-8")
        plan = {"assignment": {"title": "两组独立求和"}, "request": "记录作业要求。",
                "scope": {"goal": "要求记录", "authorized_behaviors": ["plan"]},
                "sources": [{"id": "brief", "kind": "local", "path": "brief.md"}],
                "requirements": [{"id": "R1", "text": "计算整数和", "sources": [{"source_id": "brief", "locator": "第1行"}]}],
                "plan": {"implementation": [], "validation": []}, "next_steps": []}
        self.cli("plan", "--workspace", self.workspace, "--input", self.input(plan))
        request = self.request()
        request["execution"]["material_ids"] = ["brief"]
        original = self.run_result(request)
        self.assertEqual(original["results"][0]["status"], "valid")
        brief.write_text("# 作业\n计算给定整数之和。\n", encoding="utf-8")
        changed = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(changed["results"][0]["status"], "needs_review")
        self.cli("plan", "--workspace", self.workspace, "--input", self.input(plan))
        still_unknown = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(still_unknown["results"][0]["status"], "needs_review")
        review = {"assignment": request["assignment"], "request": "仅复核现有结果。",
                  "scope": {"goal": "要求变化影响", "authorized_behaviors": ["analyze"]},
                  "result_id": original["result"]["id"], "assessment": "unaffected",
                  "note": "重新阅读新旧材料，新增的只有标题；整数求和要求、输入、代码和参数均未改。",
                  "specification": request["execution"]}
        reviewed = self.cli("review-result", "--workspace", self.workspace, "--input", self.input(review))
        self.assertEqual(reviewed["results"][0]["status"], "valid")
        self.assertEqual((self.workspace / "executions.txt").read_text(), "a.txt\n")


if __name__ == "__main__":
    unittest.main()
