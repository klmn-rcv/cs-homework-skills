"""Code-only delivery through the companion CLI, real code and independent answers."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / "skills/cs-homework/scripts/coursework.py"


class CodeWorkflow(unittest.TestCase):
    def setUp(self):
        if hasattr(self, "demo_root"):
            self.root = Path(self.demo_root)
            self.root.mkdir(parents=True)
        else:
            self.tmp = tempfile.TemporaryDirectory()
            self.addCleanup(self.tmp.cleanup)
            self.root = Path(self.tmp.name)
        self.workspace = self.root / "assignment"
        self.workspace.mkdir()
        self.number = 0

    def cli(self, command, record, ok=True):
        self.number += 1
        path = self.root / f"input-{self.number}.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        argv = [sys.executable, "-B", str(CLI), command,
                "--workspace", str(self.workspace), "--input", str(path)]
        result = subprocess.run(argv,
                                capture_output=True, text=True, encoding="utf-8")
        if hasattr(self, "demo_root"):
            (self.root / f"receipt-{self.number}.json").write_text(json.dumps({
                "argv": argv, "exit_code": result.returncode,
                "stdout": json.loads(result.stdout) if result.stdout else None, "stderr": result.stderr},
                ensure_ascii=False, indent=2), encoding="utf-8")
        if not ok:
            self.assertEqual(result.returncode, 2, result.stdout)
            return result
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def request(self):
        cases = [("teacher", "1 2 3", "6"), ("boundary", "", "0"),
                 ("oracle", "-2 0 9", "7")]
        return {"assignment": {"title": "整数求和"}, "request": "实现求和，只交代码及必要测试。",
                "scope": {"goal": "符合样例和边界的程序", "authorized_behaviors": ["code"]},
                "code_paths": ["solution.py"],
                "checks": [{"id": name, "issue_id": "sum", "kind": name,
                            "execution": {"argv": [sys.executable, "-B", "solution.py"],
                                          "source_paths": ["solution.py"], "stdin_text": data,
                                          "purposes": ["correctness"], "basis": "任务要求求和",
                                          "dependency_coverage": {"status": "complete", "note": "只读取标准输入和当前源码"},
                                          "expected": {"stdout": answer + os.linesep, "exit_code": 0,
                                                       "basis": "教师给定6；空和0；独立手算-2+0+9=7"}}}
                           for name, data, answer in cases]}

    def change(self, source, digest=None, name="solution.py"):
        path = self.root / f"replacement-{self.number}-{name}"
        path.write_text(source, encoding="utf-8")
        return {"path": name, "staged_path": str(path), "expected_sha256": digest}

    def test_authorized_code_continues_handoff_only_context_preserving_student_files_and_index(self):
        solution = self.workspace / "solution.py"
        solution.write_text("import sys\nprint(sum(map(int, sys.stdin.read().split())))\n", encoding="utf-8")
        note = self.root / "handoff.md"
        note.write_text("等待用户决定是否允许代码修复；已有接口说明可复用。\n", encoding="utf-8")
        self.cli("handoff", {"request": "只写报告，保存待决定问题。",
                            "scope": {"goal": "报告", "authorized_behaviors": ["report"]},
                            "note_path": str(note)})
        handoff = self.workspace / ".coursework/handoff.md"
        handoff.write_text(handoff.read_text(encoding="utf-8") + "学生补充，原样保留。\n", encoding="utf-8")
        (self.workspace / "student.txt").write_text("学生已暂存的笔记\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.workspace), "add", "student.txt"], check=True, capture_output=True)
        index_before = subprocess.run(["git", "-C", str(self.workspace), "diff", "--cached", "--binary"],
                                      check=True, capture_output=True).stdout
        original = {p: p.read_bytes() for p in [solution, handoff, self.workspace / "student.txt"]}
        self.assertFalse((self.workspace / ".coursework/state.json").exists())
        started = self.cli("code-start", self.request())
        verified = self.cli("code-step", {"session_id": started["session"]["id"],
            "note": "用户现在授权代码工作；先用原教师、空输入和独立负数答案复验已有实现。",
            "requirements_review": [{"requirement": "整数求和", "status": "passed",
                                     "basis": "实际读取当前程序，并比较三类独立预期。"}]})
        self.assertEqual(verified["session"]["status"], "verified")
        self.assertTrue(all(c["status"] == "passed" for c in verified["step"]["checks"]))
        self.assertEqual(original, {p: p.read_bytes() for p in original})
        self.assertEqual(index_before, subprocess.run(
            ["git", "-C", str(self.workspace), "diff", "--cached", "--binary"],
            check=True, capture_output=True).stdout)

    def test_code_start_preserves_foreign_context_without_initializing_git(self):
        directory = self.workspace / ".coursework"
        directory.mkdir()
        foreign = directory / "unknown.txt"
        foreign.write_text("用户文件", encoding="utf-8")
        before = foreign.read_bytes()
        refused = self.cli("code-start", self.request(), ok=False)
        self.assertIn("recognized", refused.stderr)
        self.assertEqual(foreign.read_bytes(), before)
        self.assertFalse((directory / "state.json").exists())
        self.assertFalse((self.workspace / ".git").exists())

    def test_code_validation_accepts_required_error_exit_without_repairing_correct_program(self):
        (self.workspace / "solution.py").write_text(
            "import sys\ntry:\n    values=list(map(int,sys.stdin.read().split()))\n"
            "except ValueError:\n    sys.stderr.write('invalid integer\\n')\n    sys.exit(2)\n"
            "print(sum(values))\n", encoding="utf-8")
        request = self.request()
        boundary = request["checks"][1]["execution"]
        boundary["stdin_text"] = "bad"
        boundary["expected"] = {"stdout": "", "stderr": "invalid integer" + os.linesep,
                                "exit_code": 2, "basis": "非法整数接口约定：stderr诊断并退出2。"}
        original = (self.workspace / "solution.py").read_bytes()
        started = self.cli("code-start", request)
        checked = self.cli("code-step", {"session_id": started["session"]["id"],
            "note": "核对现有程序的教师样例、非法输入和负数独立答案。",
            "requirements_review": [{"requirement": "整数求和及非法输入退出2", "status": "passed",
                                     "basis": "阅读异常处理与求和语句，并保留独立接口预期。"}]})
        self.assertEqual(checked["session"]["status"], "verified")
        self.assertTrue(all(c["status"] == "passed" for c in checked["step"]["checks"]))
        run = next(r for r in checked["state"]["runs"] if r["specification"]["stdin_text"] == "bad")
        self.assertEqual(run["execution"]["exit_code"], 2)
        self.assertEqual(run["execution"]["stderr"]["text"], "invalid integer" + os.linesep)
        self.assertTrue(all(r["status"] == "valid" for r in checked["results"]))
        self.assertEqual((self.workspace / "solution.py").read_bytes(), original)

    def test_code_only_new_implementation_has_actual_teacher_boundary_oracle_evidence_and_commit(self):
        started = self.cli("code-start", self.request())
        step = self.cli("code-step", {"session_id": started["session"]["id"],
            "note": "使用内置逐项求和；题目允许标准库和sum。",
            "changes": [self.change("import sys\nprint(sum(map(int, sys.stdin.read().split())))\n")],
            "requirements_review": [{"requirement": "Python、标准输入输出、整数求和", "status": "passed",
                                      "basis": "阅读实际代码；教师样例、空输入和负数独立预期均核对。"}],
            "next_steps": []})
        self.assertEqual(step["session"]["status"], "verified")
        self.assertEqual(len(step["step"]["checks"]), 3)
        self.assertTrue(all(c["status"] == "passed" for c in step["step"]["checks"]))
        state = json.loads((self.workspace / ".coursework/state.json").read_text(encoding="utf-8"))
        self.assertEqual(len(state["runs"]), 3)
        self.assertFalse((self.workspace / "report").exists())
        shown = subprocess.run(["git", "-C", str(self.workspace), "show", "--format=", "--name-only", "HEAD"], capture_output=True, text=True).stdout
        self.assertIn("solution.py", shown)
        self.assertEqual(subprocess.run(["git", "-C", str(self.workspace), "status", "--porcelain"], capture_output=True, text=True).stdout, "")

    def test_known_bug_is_diagnosed_repaired_and_original_cases_rerun_without_rewriting_oracle(self):
        (self.workspace / "solution.py").write_text("import sys\nprint(len(sys.stdin.read().split()))\n", encoding="utf-8")
        start = self.cli("code-start", self.request())["session"]
        failed = self.cli("code-step", {"session_id": start["id"], "note": "先复现原始教师样例及边界。"})
        self.assertEqual(failed["session"]["status"], "needs_repair")
        failures = [c["run_id"] for c in failed["step"]["checks"] if c["status"] == "failed"]
        old_stdout = self.workspace / next(r for r in failed["state"]["runs"] if r["id"] == failures[0])["execution"]["stdout"]["path"]
        repaired = self.cli("code-step", {"session_id": start["id"], "issue_id": "sum",
            "note": "原实现数了元素个数，修复为值的总和，保留教师预期。",
            "diagnosis": {"category": "implementation", "finding": "len 返回3而非输入整数之和6；空输入恰好0并不能证明实现正确。",
                          "prediction": "改为整数累加后教师与负数用例应同时通过，空输入仍是0。", "basis_run_ids": failures},
            "changes": [self.change("import sys\nprint(sum(map(int, sys.stdin.read().split())))\n", failed["session"]["code_identity"]["solution.py"])],
            "progress": {"status": "made", "note": "针对len导致的具体错误改为求和；由原样例复跑判断。"},
            "requirements_review": [{"requirement": "整数求和与空输入", "status": "passed", "basis": "实际源码和三类独立预期核对"}], "next_steps": []})
        self.assertEqual(repaired["session"]["status"], "verified")
        self.assertEqual(repaired["step"]["progress_signal"]["status"], "made")
        self.assertEqual(repaired["step"]["progress_signal"]["before_failed_checks"], ["oracle", "teacher"])
        self.assertEqual(repaired["step"]["progress_signal"]["after_failed_checks"], [])
        self.assertEqual(old_stdout.read_text().strip(), "3")
        self.assertEqual(repaired["session"]["checks"], start["checks"])
        self.assertTrue(all(c["status"] == "passed" for c in repaired["step"]["checks"]))
        old = [r for r in repaired["results"] if r["id"] in failures]
        self.assertTrue(all(not r["current"] and r["status"] != "valid" for r in old))
        self.assertTrue(all(any(i["kind"] == "dependency" for i in r["issues"]) for r in old))
        self.assertIn("solution.py", repaired["implementation_git"]["skipped_preexisting"])

    def test_three_actual_targeted_no_progress_repairs_pause_only_that_issue(self):
        request = self.request()
        request["code_paths"].append("empty_case.py")
        request["checks"] = [request["checks"][0], request["checks"][1]]
        request["checks"][1]["issue_id"] = "independent-empty"
        request["checks"][1]["execution"]["argv"][-1] = "empty_case.py"
        request["checks"][1]["execution"]["source_paths"] = ["empty_case.py"]
        start = self.cli("code-start", request)["session"]
        first = self.cli("code-step", {"session_id": start["id"], "note": "建立教师失败与另一文件中独立空输入失败的基线。",
            "changes": [self.change("import sys\nv=list(map(int,sys.stdin.read().split()))\nprint(0)\n"),
                        self.change("print(-1)\n", name="empty_case.py")]})
        latest = first
        for replacement, note in [("print(sum(v[:0]))", "怀疑切片边界，检查空切片路径"),
                                  ("print(sum(v)-sum(v))", "怀疑累加初值，检查重复相减路径"),
                                  ("print(sum(v)*0)", "怀疑标量处理，检查乘法路径")]:
            failures = [c["run_id"] for c in latest["step"]["checks"] if c["status"] == "failed" and c["issue_id"] == "sum"]
            latest = self.cli("code-step", {"session_id": start["id"], "issue_id": "sum", "note": note,
                "diagnosis": {"category": "implementation", "finding": "教师输出仍为0而正确预期6；检查目标累加路径。",
                              "prediction": "这次目标路径调整可能恢复6，原教师样例可直接否证。", "basis_run_ids": failures},
                "changes": [self.change("import sys\nv=list(map(int,sys.stdin.read().split()))\n"+replacement+"\n", latest["session"]["code_identity"]["solution.py"])],
                "progress": {"status": "made" if replacement == "print(sum(v)*0)" else "none", "note": "这是假定的进展看法；实际同一教师失败仍输出0，必须以复验信号为准。"},
                "next_steps": ["暂停求和修复并保留三轮源代码和实际日志；继续整理独立空输入验证及运行说明。"]})
        self.assertEqual(latest["session"]["status"], "partial_paused")
        self.assertEqual(latest["session"]["issues"]["sum"]["no_progress"], 3)
        self.assertEqual(latest["session"]["issues"]["independent-empty"]["status"], "needs_diagnosis")
        self.assertEqual(len(latest["session"]["steps"]), 4)
        self.assertEqual(len({s["code_identity"]["solution.py"] for s in latest["session"]["steps"]}), 4)
        refused = self.cli("code-step", {"session_id": start["id"], "issue_id": "sum", "note": "第四轮应停止",
             "changes": [self.change("print(6)\n", latest["session"]["code_identity"]["solution.py"])]}, ok=False)
        self.assertIn("paused", refused.stderr)
        continued = self.cli("code-step", {"session_id": start["id"], "issue_id": "independent-empty",
             "note": "保留求和暂停项，修复另一文件中独立的空输入约定。",
             "diagnosis": {"category": "implementation", "finding": "独立空输入程序输出-1，空和应为0；该文件不参与暂停的求和程序。",
                           "prediction": "改为0会通过原空输入用例，暂停的求和证据保持失败。",
                           "basis_run_ids": [latest["session"]["latest_checks"]["boundary"]["run_id"]]},
             "changes": [self.change("print(0)\n", latest["session"]["code_identity"]["empty_case.py"], "empty_case.py")],
             "progress": {"status": "made", "note": "由原独立空输入用例核对-1到0的修正。"},
             "next_steps": ["独立空输入程序已完成；求和程序保留三次无进展的现场，等待用户决定继续投入。"]})
        self.assertEqual([c["check_id"] for c in continued["step"]["checks"]], ["boundary"])
        self.assertEqual(continued["session"]["issues"]["independent-empty"]["status"], "passed")
        self.assertEqual(continued["session"]["issues"]["sum"]["no_progress"], 3)
        self.assertEqual((self.workspace / "empty_case.py").read_text(), "print(0)\n")
        self.assertEqual(continued["session"]["status"], "partial_paused")

    def test_scope_test_input_and_concurrent_student_edits_are_protected_before_applying_code(self):
        request = self.request()
        request["scope"]["authorized_behaviors"] = ["run"]
        refused = self.cli("code-start", request, ok=False)
        self.assertIn("authorize", refused.stderr)
        self.assertFalse((self.workspace / ".git").exists())
        (self.workspace / "solution.py").write_text("print(0)\n", encoding="utf-8")
        request = self.request()
        (self.root / "teacher.txt").write_text("1 2 3", encoding="utf-8")
        request["checks"][0]["execution"].pop("stdin_text")
        request["checks"][0]["execution"]["stdin_path"] = str(self.root / "teacher.txt")
        start = self.cli("code-start", request)["session"]
        (self.root / "teacher.txt").write_text("", encoding="utf-8")
        refused = self.cli("code-step", {"session_id": start["id"], "note": "不允许弱化教师输入"}, ok=False)
        self.assertIn("Fixed test/input changed", refused.stderr)
        (self.root / "teacher.txt").write_text("1 2 3", encoding="utf-8")
        (self.workspace / "solution.py").write_text("# student's concurrent work\nprint(0)\n", encoding="utf-8")
        refused = self.cli("code-step", {"session_id": start["id"], "note": "不能覆盖并发修改"}, ok=False)
        self.assertIn("outside the saved session", refused.stderr)


if __name__ == "__main__":
    unittest.main()
