"""Run public CLI requests against real, small assignment programs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[1] / "skills/cs-homework/scripts/coursework.py"


class RunWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "已有作业"
        self.workspace.mkdir()
        self.code = self.workspace / "student.py"
        self.code.write_text("import sys\nprint(int(sys.stdin.readline()) * 2)\n", encoding="utf-8")

    def request(self):
        return {
            "assignment": {"title": "已有程序的真实运行"},
            "request": "只运行已有代码，用题目已知答案检查；不要修改实现。",
            "scope": {"goal": "运行证据", "authorized_behaviors": ["run"], "deliverables": ["运行证据"]},
            "execution": {"argv": [sys.executable, "student.py"], "stdin_text": "21\n",
                          "source_paths": ["student.py"], "input_paths": [],
                          "purposes": ["correctness", "example"],
                          "basis": "用户请求及教师样例 21 -> 42",
                          "expected": {"stdout": "42" + os.linesep, "exit_code": 0,
                                       "basis": "教师给定的样例答案"}},
        }

    def cli(self, *args, ok=True):
        result = subprocess.run([sys.executable, "-B", str(CLI), *map(str, args)],
                                capture_output=True, text=True, encoding="utf-8")
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def run_request(self, record=None):
        path = self.root / "request.json"
        path.write_text(json.dumps(record or self.request(), ensure_ascii=False), encoding="utf-8")
        return json.loads(self.cli("run", "--workspace", self.workspace, "--input", path).stdout)

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.workspace), *args], capture_output=True,
                                text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_direct_run_initializes_context_and_records_actual_known_answer(self):
        result = self.run_request()
        run = result["run"]
        self.assertEqual(run["status"], "completed")
        actual = run["execution"]
        self.assertEqual(actual["argv"], [sys.executable, "student.py"])
        self.assertEqual(actual["stdin"]["text"], "21\n")
        self.assertEqual(actual["stdout"]["text"], "42" + os.linesep)
        self.assertEqual(actual["stderr"]["text"], "")
        self.assertEqual(actual["exit_code"], 0)
        self.assertGreater(actual["elapsed_seconds"], 0)
        self.assertEqual(actual["check"]["status"], "passed")
        self.assertTrue(actual["environment"]["platform"])
        self.assertTrue(actual["environment"]["executable_sha256"])
        resumed = json.loads(self.cli("resume", "--workspace", self.workspace).stdout)
        self.assertEqual(resumed["state"]["scope"]["authorized_behaviors"], ["run"])
        self.assertEqual(resumed["state"]["runs"][-1]["id"], run["id"])
        self.assertFalse((self.workspace / ".coursework/plan.md").exists())
        self.assertTrue((self.workspace / actual["stdout"]["path"]).is_file())
        self.assertEqual(self.code.read_text(encoding="utf-8"), "import sys\nprint(int(sys.stdin.readline()) * 2)\n")

    def test_expected_nonzero_exit_is_successful_reusable_evidence_but_unexpected_exit_or_output_fails(self):
        self.code.write_text("import sys\nsys.stderr.write('invalid integer\\n')\nsys.exit(2)\n", encoding="utf-8")
        record = self.request()
        record["result_key"] = "malformed-input"
        record["execution"].update(stdin_text="bad\n", purposes=["correctness"],
            dependency_coverage={"status": "complete", "note": "只读取声明源码与标准输入。"},
            expected={"stdout": "", "stderr": "invalid integer" + os.linesep, "exit_code": 2,
                      "basis": "接口要求非法整数在stderr输出invalid integer并退出2。"})
        first = self.run_request(record)
        self.assertEqual(first["run"]["status"], "completed")
        actual = first["run"]["execution"]
        self.assertEqual(actual["exit_code"], 2)
        self.assertEqual(actual["stderr"]["text"], "invalid integer" + os.linesep)
        self.assertEqual(actual["check"]["comparisons"], {"stdout": True, "stderr": True, "exit_code": True})
        self.assertEqual(first["results"][0]["status"], "valid")
        reused = self.run_request(record)
        self.assertTrue(reused["reused"])
        self.assertEqual(reused["result"]["id"], first["result"]["id"])
        for key, expected in [("positive-exit", {"exit_code": 0}),
                              ("unspecified-exit", {"stderr": "invalid integer" + os.linesep}),
                              ("wrong-diagnostic", {"exit_code": 2, "stderr": "different" + os.linesep})]:
            record["result_key"] = key
            record["execution"]["expected"] = {**expected, "basis": "独立接口预期；原样保留此用例。"}
            failed = self.run_request(record)["run"]
            self.assertEqual(failed["status"], "failed", key)
            self.assertEqual(failed["execution"]["exit_code"], 2)

    def test_explicit_readonly_scope_refuses_execution_even_if_run_is_listed(self):
        record = self.request()
        record["scope"].update(read_only=True, authorized_behaviors=["check", "run"])
        path = self.root / "readonly.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        refused = self.cli("run", "--workspace", self.workspace, "--input", path, ok=False)
        self.assertEqual(refused.returncode, 2)
        self.assertIn("authorize", refused.stderr)
        self.assertFalse((self.workspace / ".coursework").exists())
        self.assertFalse((self.workspace / ".git").exists())

    def test_real_trial_over_budget_waits_then_confirmation_runs_saved_plan_without_hard_timeout(self):
        self.code.write_text("import sys,time\nfrom pathlib import Path\ntime.sleep(float(sys.argv[1]))\n"
                             "Path(sys.argv[2]).write_text('actual')\nprint('done')\n", encoding="utf-8")
        record = self.request()
        record["request"] = "按要求执行两单位固定实验，先试跑；超过本次短预算先问我，不改实现。"
        record["execution"].update(argv=[sys.executable, "student.py", "0.04", "full.txt"],
                                   purposes=["experiment"], workload_units=2,
                                   basis="用户明确要求的两单位固定实验",
                                   expected={"stdout": "done" + os.linesep, "exit_code": 0, "basis": "specified completion marker"})
        record["trial"] = {"argv": [sys.executable, "student.py", "0.02", "trial.txt"], "workload_units": 1}
        record["budget_seconds"] = 0.001
        waiting = self.run_request(record)["run"]
        self.assertEqual(waiting["status"], "awaiting_confirmation")
        self.assertTrue((self.workspace / "trial.txt").exists())
        self.assertFalse((self.workspace / "full.txt").exists())
        self.assertGreater(waiting["budget"]["estimated_seconds"], 0.001)
        self.assertEqual(waiting["trial"]["exit_code"], 0)
        confirmed = json.loads(self.cli("run", "--workspace", self.workspace, "--confirm", waiting["id"],
                                        "--confirmation", "用户接受该试跑估时与超预算计划，继续运行。").stdout)["run"]
        self.assertEqual(confirmed["status"], "completed")
        self.assertEqual(confirmed["id"], waiting["id"])
        self.assertGreater(confirmed["execution"]["elapsed_seconds"], 0.001)
        self.assertTrue((self.workspace / "full.txt").exists())
        self.assertEqual(confirmed["execution"]["check"]["status"], "passed")
        self.assertEqual(confirmed["confirmation"]["text"], "用户接受该试跑估时与超预算计划，继续运行。")

    def test_failure_keeps_stderr_exit_dirty_source_and_student_staging_without_authorizing_repairs(self):
        self.git("init", "-q")
        self.git("add", "student.py")
        self.git("-c", "user.name=Student", "-c", "user.email=student@example.invalid", "commit", "-qm", "student baseline")
        head = self.git("rev-parse", "HEAD")
        self.code.write_text("import sys\n# staged student edit\nprint('wrong')\n", encoding="utf-8")
        self.git("add", "student.py")
        self.code.write_text("import sys\n# staged student edit\nprint('wrong')\n"
                             "# unstaged student edit\nsys.stderr.write('specific failure')\nsys.exit(7)\n", encoding="utf-8")
        code_before = self.code.read_bytes()
        staged_before = self.git("diff", "--cached", "--binary")
        result = self.run_request()
        run, execution = result["run"], result["run"]["execution"]
        self.assertEqual(run["status"], "failed")
        self.assertEqual(execution["exit_code"], 7)
        self.assertEqual(execution["stdout"]["text"], "wrong" + os.linesep)
        self.assertEqual(execution["stderr"]["text"], "specific failure")
        self.assertEqual(execution["check"]["status"], "failed")
        self.assertEqual(execution["source_before"]["head"], head)
        source = execution["source_before"]["files"][0]
        self.assertEqual((self.workspace / source["snapshot_path"]).read_bytes(), code_before)
        self.assertIn("staged student edit", execution["source_before"]["staged_diff"]["text"])
        self.assertIn("unstaged student edit", execution["source_before"]["unstaged_diff"]["text"])
        self.assertEqual(self.code.read_bytes(), code_before)
        self.assertEqual(self.git("diff", "--cached", "--binary"), staged_before)
        self.assertFalse(run["follow_up"]["implementation_edits_authorized"])
        self.assertEqual(run["follow_up"]["status"], "needs_diagnosis")
        self.assertIn("code", run["follow_up"]["scope_decision_if_implementation_change_needed"])

    def test_confirmation_refuses_changed_production_stdin_even_when_trial_uses_other_input(self):
        data = self.workspace / "input.txt"
        data.write_text("21\n", encoding="utf-8")
        trial_data = self.workspace / "trial-input.txt"
        trial_data.write_text("1\n", encoding="utf-8")
        record = self.request()
        record["execution"].pop("stdin_text")
        record["execution"]["stdin_path"] = "input.txt"
        record["trial"] = {"argv": [sys.executable, "student.py"], "stdin_path": "trial-input.txt", "workload_units": 1}
        record["budget_seconds"] = 0.0001
        waiting = self.run_request(record)["run"]
        self.assertEqual(waiting["status"], "awaiting_confirmation")
        data.write_text("99\n", encoding="utf-8")
        result = self.cli("run", "--workspace", self.workspace, "--confirm", waiting["id"],
                          "--confirmation", "同意继续", ok=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("changed", json.loads(result.stderr)["error"])
        resumed = json.loads(self.cli("resume", "--workspace", self.workspace).stdout)
        self.assertNotIn("execution", resumed["state"]["runs"][-1])

    def test_declared_output_file_is_linked_to_the_actual_run_and_preserved_as_evidence(self):
        self.code.write_text("from pathlib import Path\nPath('answer.txt').write_text('42')\n", encoding="utf-8")
        record = self.request()
        record["execution"].update(output_paths=["answer.txt"], expected={"exit_code": 0, "basis": "Successful output-file example"})
        run = self.run_request(record)["run"]
        artifact = run["execution"]["outputs"][0]
        self.assertEqual(artifact["path"], "answer.txt")
        self.assertEqual(artifact["status"], "present")
        self.assertEqual((self.workspace / artifact["snapshot_path"]).read_bytes(), b"42")
        self.assertEqual((self.workspace / "answer.txt").read_bytes(), b"42")

    def test_non_utf8_chinese_output_preserves_exact_bytes_and_labels_the_text_preview(self):
        self.code.write_text("import sys\nsys.stdout.buffer.write(bytes.fromhex('d6d0cec4'))\n", encoding="utf-8")
        record = self.request()
        record["execution"].pop("expected")
        run = self.run_request(record)["run"]
        stdout = run["execution"]["stdout"]
        self.assertEqual((self.workspace / stdout["path"]).read_bytes(), b"\xd6\xd0\xce\xc4")
        self.assertEqual(run["execution"]["check"]["status"], "unverified")
        self.assertEqual(stdout["text_decoding"]["encoding"], "utf-8")
        self.assertFalse(stdout["text_decoding"]["lossless"])

    def test_default_thirty_minute_threshold_can_wait_on_a_short_real_trial(self):
        self.code.write_text("import sys,time\nfrom pathlib import Path\n"
                             "for _ in range(int(sys.argv[1])): time.sleep(0.01)\n"
                             "Path(sys.argv[2]).write_text('actual')\nprint('done')\n", encoding="utf-8")
        record = self.request()
        record["request"] = "执行明确要求的固定规模长实验，先试跑估时，使用默认询问阈值。"
        record["execution"].update(argv=[sys.executable, "student.py", "10000000", "must-not-run.txt"],
                                   purposes=["experiment"], basis="用户给定的正式工作量与试跑规模",
                                   expected={"stdout": "done" + os.linesep, "exit_code": 0, "basis": "固定工作完成标记"})
        record["execution"]["workload_units"] = 10000000
        record["trial"] = {"argv": [sys.executable, "student.py", "1", "trial.txt"], "workload_units": 1}
        run = self.run_request(record)["run"]
        self.assertEqual(run["status"], "awaiting_confirmation")
        self.assertEqual(run["budget"]["limit_seconds"], 1800)
        self.assertTrue(run["budget"]["is_default"])
        self.assertFalse(run["budget"]["hard_timeout"])
        self.assertNotIn("execution", run)
        self.assertFalse((self.workspace / "must-not-run.txt").exists())
        self.assertLess(run["trial"]["elapsed_seconds"], 30)

    def test_code_only_scope_allows_necessary_correctness_but_rejects_experiment(self):
        record = self.request()
        record["request"] = "只编程并作必要正确性验证；不要扩展实验或报告。"
        record["scope"]["authorized_behaviors"] = ["code"]
        record["execution"]["purposes"] = ["correctness"]
        self.assertEqual(self.run_request(record)["run"]["execution"]["check"]["status"], "passed")
        record["execution"]["purposes"] = ["experiment"]
        path = self.root / "outside-scope.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        result = self.cli("run", "--workspace", self.workspace, "--input", path, ok=False)
        self.assertEqual(result.returncode, 2)
        resumed = json.loads(self.cli("resume", "--workspace", self.workspace).stdout)
        self.assertEqual(len(resumed["state"]["runs"]), 1)
        self.assertEqual(resumed["state"]["scope"]["authorized_behaviors"], ["code"])

    def test_missing_executable_and_input_have_saved_diagnostics_and_no_invented_exit(self):
        record = self.request()
        record["execution"]["argv"][0] = "coursework-missing-executable-835726"
        run = self.run_request(record)["run"]
        self.assertEqual(run["status"], "not_started")
        self.assertIsNone(run["execution"]["exit_code"])
        self.assertIn("Executable unavailable", run["execution"]["diagnostic"])
        self.assertEqual(run["execution"]["check"]["status"], "unverified")
        record = self.request()
        record["execution"].pop("stdin_text")
        record["execution"]["stdin_path"] = "missing-input.txt"
        run = self.run_request(record)["run"]
        self.assertEqual(run["status"], "not_started")
        self.assertIn("missing-input.txt", run["execution"]["diagnostic"])
        resumed = json.loads(self.cli("resume", "--workspace", self.workspace).stdout)
        self.assertEqual(len(resumed["state"]["runs"]), 2)

    def test_zero_exit_with_wrong_known_answer_fails_check(self):
        self.code.write_text("print(41)\n", encoding="utf-8")
        run = self.run_request()["run"]
        self.assertEqual(run["execution"]["exit_code"], 0)
        self.assertEqual(run["execution"]["stdout"]["text"], "41" + os.linesep)
        self.assertEqual(run["status"], "failed")
        self.assertFalse(run["execution"]["check"]["comparisons"]["stdout"])

    def test_saved_state_user_edit_is_preserved_before_any_later_execution(self):
        self.run_request()
        state = self.workspace / ".coursework/state.json"
        value = json.loads(state.read_text(encoding="utf-8"))
        value["student_note"] = "保留学生手动补充"
        state.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        self.git("add", ".coursework/state.json")
        before = state.read_bytes()
        before_index = self.git("diff", "--cached", "--binary")
        self.code.write_text("from pathlib import Path\nPath('must-not-run.txt').write_text('bad')\n", encoding="utf-8")
        path = self.root / "request.json"
        result = self.cli("run", "--workspace", self.workspace, "--input", path, ok=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Preserved preexisting user change", result.stderr)
        self.assertEqual(state.read_bytes(), before)
        self.assertEqual(self.git("diff", "--cached", "--binary"), before_index)
        self.assertFalse((self.workspace / "must-not-run.txt").exists())

    def test_explicit_relative_executable_is_resolved_from_actual_child_working_directory(self):
        child_cwd = self.workspace / "work"
        child_cwd.mkdir()
        record = self.request()
        record["execution"].update(argv=[os.path.relpath(sys.executable, child_cwd), "../student.py"], cwd="work")
        run = self.run_request(record)["run"]
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["execution"]["argv"][0], str(Path(sys.executable).resolve()))
        self.assertEqual(run["execution"]["cwd"], str(child_cwd))
        self.assertEqual(run["execution"]["check"]["status"], "passed")

    def test_run_preserves_sourced_planning_context_and_later_plan_preserves_execution_evidence(self):
        plan = {"assignment": {"title": "已有程序"}, "request": "只规划",
                "scope": {"goal": "运行前梳理", "authorized_behaviors": ["plan"]},
                "sources": [{"id": "chat", "kind": "chat", "content": "保留当前实现，样例21得到42"}],
                "requirements": [{"id": "R1", "text": "样例21得到42", "sources": [{"source_id": "chat", "locator": "当前请求"}]}],
                "decisions": [{"id": "D1", "text": "保留已有实现", "status": "confirmed",
                               "sources": [{"source_id": "chat", "locator": "当前请求"}]}],
                "questions": [], "plan": {"implementation": [], "validation": [{"description": "检查教师样例", "requirements": ["R1"]}]},
                "next_steps": []}
        path = self.root / "plan.json"
        path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        first = json.loads(self.cli("plan", "--workspace", self.workspace, "--input", path).stdout)
        result = self.run_request()
        self.assertEqual(result["state"]["requirements"], first["state"]["requirements"])
        self.assertEqual(result["state"]["decisions"], first["state"]["decisions"])
        self.assertEqual(result["state"]["plan"], first["state"]["plan"])
        later = json.loads(self.cli("plan", "--workspace", self.workspace, "--input", path).stdout)
        self.assertEqual(later["state"]["runs"], result["state"]["runs"])
        self.assertEqual(later["state"]["revision"], 3)
        self.assertTrue((self.workspace / result["run"]["evidence_path"]).is_file())

    def test_unrelated_student_changes_are_not_copied_into_evidence_and_staging_is_preserved(self):
        private = self.workspace / "unrelated.txt"
        private.write_text("unrelated baseline\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("add", "student.py", "unrelated.txt")
        self.git("-c", "user.name=Student", "-c", "user.email=student@example.invalid", "commit", "-qm", "student baseline")
        self.code.write_text(self.code.read_text(encoding="utf-8") + "# relevant staged code\n", encoding="utf-8")
        private.write_text("UNRELATED-STAGED-CONTENT-731\n", encoding="utf-8")
        self.git("add", "student.py", "unrelated.txt")
        self.code.write_text(self.code.read_text(encoding="utf-8") + "# relevant unstaged code\n", encoding="utf-8")
        private.write_text("UNRELATED-STAGED-CONTENT-731\nUNRELATED-UNSTAGED-CONTENT-842\n", encoding="utf-8")
        staged_before = self.git("diff", "--cached", "--binary")
        private_before = private.read_bytes()
        result = self.run_request()
        self.assertEqual(result["run"]["status"], "completed")
        for name in result["deliverables"]:
            content = (self.workspace / name).read_bytes()
            self.assertFalse(b"UNRELATED-STAGED-CONTENT-731" in content, "Unrelated staged content in " + name)
            self.assertFalse(b"UNRELATED-UNSTAGED-CONTENT-842" in content, "Unrelated unstaged content in " + name)
        source = result["run"]["execution"]["source_before"]
        self.assertIn("relevant staged code", source["staged_diff"]["text"])
        self.assertIn("relevant unstaged code", source["unstaged_diff"]["text"])
        self.assertIn("unrelated.txt", source["status"])
        self.assertEqual(self.git("diff", "--cached", "--binary"), staged_before)
        self.assertEqual(private.read_bytes(), private_before)
        invalid = self.request()
        invalid["execution"]["source_paths"] = ["."]
        refused = self.run_request(invalid)["run"]
        self.assertEqual(refused["status"], "not_started")
        self.assertEqual(refused["plan_state"]["patch_scope"], [])
        self.assertEqual(refused["plan_state"]["staged_diff"]["size_bytes"], 0)
        self.assertEqual(refused["plan_state"]["unstaged_diff"]["size_bytes"], 0)
        self.assertEqual(self.git("diff", "--cached", "--binary"), staged_before)

    def test_external_declared_source_is_snapshotted_without_widening_git_patch_scope(self):
        external = self.root / "external-student.py"
        external.write_bytes(self.code.read_bytes())
        self.code.unlink()
        private = self.workspace / "unrelated.txt"
        private.write_text("baseline\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("add", "unrelated.txt")
        self.git("-c", "user.name=Student", "-c", "user.email=student@example.invalid", "commit", "-qm", "student baseline")
        private.write_text("unrelated staged value\n", encoding="utf-8")
        self.git("add", "unrelated.txt")
        private.write_text("unrelated staged value\nunrelated working value\n", encoding="utf-8")
        staged_before = self.git("diff", "--cached", "--binary")
        record = self.request()
        record["execution"].update(argv=[sys.executable, str(external)], source_paths=[str(external)])
        run = self.run_request(record)["run"]
        self.assertEqual(run["execution"]["check"]["status"], "passed")
        for source in [run["plan_state"], run["execution"]["source_before"], run["execution"]["source_after"]]:
            self.assertEqual(source["patch_scope"], [])
            self.assertEqual(source["staged_diff"]["size_bytes"], 0)
            self.assertEqual(source["unstaged_diff"]["size_bytes"], 0)
            self.assertEqual((self.workspace / source["files"][0]["snapshot_path"]).read_bytes(), external.read_bytes())
        self.assertEqual(self.git("diff", "--cached", "--binary"), staged_before)


if __name__ == "__main__":
    unittest.main()
