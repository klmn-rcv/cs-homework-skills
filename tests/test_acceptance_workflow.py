"""Acceptance at the public CLI; semantic assessments are explicitly agent-authored."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / "skills/cs-homework/scripts/coursework.py"


class AcceptanceWorkflow(unittest.TestCase):
    def setUp(self):
        if hasattr(self, "demo_root"):
            self.root = Path(self.demo_root)
            self.root.mkdir(parents=True, exist_ok=False)
        else:
            self.temp = tempfile.TemporaryDirectory()
            self.addCleanup(self.temp.cleanup)
            self.root = Path(self.temp.name)
        self.workspace = self.root / "assignment"
        self.workspace.mkdir()
        self.number = 0

    def call(self, command, record, ok=True):
        self.number += 1
        path = self.root / f"input-{self.number}.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        actual = subprocess.run([sys.executable, "-B", str(CLI), command,
                                 "--workspace", str(self.workspace), "--input", str(path)],
                                capture_output=True, text=True, encoding="utf-8")
        if hasattr(self, "demo_root"):
            (self.root / f"receipt-{self.number}.json").write_text(json.dumps({"command": command,
                "exit_code": actual.returncode, "output": json.loads(actual.stdout) if actual.stdout else None,
                "stderr": actual.stderr}, ensure_ascii=False, indent=2), encoding="utf-8")
        if not ok:
            return actual
        self.assertEqual(actual.returncode, 0, actual.stderr)
        return json.loads(actual.stdout)

    def snapshot(self):
        return {p.relative_to(self.workspace).as_posix(): p.read_bytes()
                for p in self.workspace.rglob("*") if p.is_file()}

    def context(self):
        return {"request": "Check my existing sum code only. Do not run or change it.",
                "scope": {"goal": "Code-only acceptance", "authorized_behaviors": ["check"]}}

    def evidence(self, name):
        return {"kind": "file", "path": name,
                "sha256": hashlib.sha256((self.workspace / name).read_bytes()).hexdigest(),
                "note": "Actually read these exact bytes for the stated assessment"}

    def item(self, key, status, evidence=None, **extra):
        return {"id": key, "requirement": key, "status": status,
                "basis": "Agent assessment of the actual task and files, not an automatic semantic oracle",
                "evidence": evidence or [], "missing": [], "affected_scope": ["solution.py"], **extra}

    def git(self, *args):
        actual = subprocess.run(["git", "-C", str(self.workspace), *args], capture_output=True)
        self.assertEqual(actual.returncode, 0, actual.stderr)
        return actual.stdout

    def run_record(self, answer="6", key="teacher"):
        return {"assignment": {"title": "Integer sum"}, "request": "Run the required teacher case.",
                "scope": {"goal": "Teacher evidence", "authorized_behaviors": ["run"]}, "result_key": key,
                "execution": {"argv": [sys.executable, "-B", "solution.py"], "source_paths": ["solution.py"],
                              "stdin_text": "1 2 3", "purposes": ["correctness"], "basis": "Teacher case 1+2+3=6",
                              "dependency_coverage": {"status": "complete", "note": "Read this one-file stdin program"},
                              "expected": {"stdout": answer + os.linesep, "exit_code": 0, "basis": "Independent teacher answer"}}}

    def report_record(self, links=None):
        stage = self.root / "main.tex"
        stage.write_text("\\documentclass{article}\\begin{document}The method adds integer values. "
                         "Examples do not establish every input.\\end{document}\n", encoding="utf-8")
        return {"assignment": {"title": "Sum report"}, "request": "Write report source with existing thoughts.",
                "scope": {"goal": "Report source", "authorized_behaviors": ["report"]},
                "report_key": "sum", "source_only": True, "main_file": "main.tex",
                "files": [{"source": str(stage), "path": "main.tex"}], "source_paths": ["thoughts.md"],
                "reflection_sources": links or [],
                "content_review": {"requirement_map": [{"requirement": "Explain sum and limitations", "source": "thoughts.md", "location": "main.tex"}],
                                   "structure_basis": "Current brief requires method and limits, no template structure",
                                   "format_basis": "Ordinary article; no sample content reused",
                                   "technical_review": "Method description inspected against the specific task",
                                   "voice_review": "Objective description, no invented experience",
                                   "thoughts_basis": "Actual supplied thoughts.md, or exact linked recommendation as declared"}}

    def test_check_without_state_or_git_never_runs_or_initializes_and_reports_missing_evidence(self):
        (self.workspace / "solution.py").write_text("from pathlib import Path\nPath('ran.txt').write_text('side effect')\nprint(0)\n", encoding="utf-8")
        before = self.snapshot()
        actual = self.call("check", {**self.context(), "items": [
            self.item("required-language", "passed", [self.evidence("solution.py")]),
            self.item("actual-behavior", "unverified", missing=["No independent execution record; running was not authorized"], route="code")]})
        self.assertEqual([i["status"] for i in actual["items"]], ["passed", "unverified"])
        self.assertEqual(actual["status"], "partial")
        self.assertEqual(actual["items"][1]["follow_up"]["action"], "scope_decision_required")
        self.assertEqual(actual["assessment_origin"], "agent")
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.workspace / ".git").exists())
        self.assertFalse((self.workspace / ".coursework").exists())
        self.assertFalse((self.workspace / "ran.txt").exists())

    def test_default_acceptance_resolves_missing_proof_with_only_necessary_run_and_preserves_originals(self):
        (self.workspace / "brief.md").write_text("Python stdin整数求和；教师输入1 2 3，输出6。\n", encoding="utf-8")
        (self.workspace / "solution.py").write_text(
            "import sys\nprint(sum(map(int,sys.stdin.read().split())))\n", encoding="utf-8")
        (self.workspace / "original-report.tex").write_text("学生已有报告原稿\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("add", "brief.md", "solution.py", "original-report.tex")
        self.git("-c", "user.name=Student", "-c", "user.email=student@local.invalid", "commit", "-qm", "student original")
        (self.workspace / "student.txt").write_text("已暂存个人笔记\n", encoding="utf-8")
        self.git("add", "student.txt")
        index = self.git("diff", "--cached", "--binary")
        originals = {p: p.read_bytes() for p in self.workspace.iterdir() if p.is_file()}
        current = {"request": "按题目验收现有程序，不修实现。",
                   "scope": {"goal": "整数求和程序验收", "authorized_behaviors": ["check", "run"]}}
        method = self.item("brief.md:1-Python-stdin-sum", "passed", [self.evidence("brief.md"), self.evidence("solution.py")],
                           basis="读取当前Python程序：stdin分割后逐项转整数并求和，输出到stdout。")
        before = self.snapshot()
        pending = self.call("check", {**current, "items": [method,
            self.item("brief.md:1-teacher", "unverified", missing=["缺少当前程序教师输入的实际执行记录；需要定向检查1 2 3。"])]})
        self.assertEqual([i["status"] for i in pending["items"]], ["passed", "unverified"])
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.workspace / ".coursework").exists())
        record = {**self.run_record(), **current}
        record["execution"]["basis"] = "验收brief.md:1缺少教师样例实际证据；只补检1 2 3，独立已知答案6。"
        actual = self.call("run", record)
        self.assertEqual(actual["run"]["request"], current["request"])
        self.assertEqual(actual["run"]["scope"], current["scope"])
        self.assertEqual(actual["run"]["execution"]["stdout"]["text"], "6" + os.linesep)
        self.assertEqual(actual["run"]["execution"]["check"]["status"], "passed")
        self.assertEqual(actual["run"]["budget"]["limit_seconds"], 1800)
        before = self.snapshot()
        passed = self.call("check", {**current, "items": [method,
            self.item("brief.md:1-teacher", "passed", [{"kind": "result", "id": actual["result"]["id"],
                "require_verified": True, "note": "已读实际输入1 2 3和stdout6，与教师答案及独立算术1+2+3=6一致。"}])]})
        self.assertEqual(passed["status"], "passed")
        self.assertEqual(passed["mode"], "read_only")
        self.assertEqual(self.snapshot(), before)
        reused = self.call("run", record)
        self.assertTrue(reused["reused"])
        self.assertEqual(len(reused["state"]["runs"]), 1)
        self.assertEqual(reused["state"]["revision"], actual["state"]["revision"])
        self.assertEqual(originals, {p: p.read_bytes() for p in originals})
        self.assertEqual(self.git("diff", "--cached", "--binary"), index)
        self.assertEqual({p.name for p in self.workspace.iterdir() if p.is_file()}, {p.name for p in originals})

    def test_grounded_recommendations_need_no_acceptance_and_source_only_needs_no_pdf(self):
        (self.workspace / "thoughts.md").write_text("User-supplied thought: examples do not establish every input.\n", encoding="utf-8")
        context = self.report_record()
        reflection = self.call("reflection", {**context, "reflection_key": "limits",
            "need_basis": "A later possible extension lacks a user decision",
            "questions": [{"id": "Q1", "question": "What does an example establish?",
                           "recommendation": "Examples do not establish every input.", "basis": "Supplied thought distinguishes examples from proof",
                           "source_paths": ["thoughts.md"]},
                          {"id": "Q2", "question": "What future validation would help?",
                           "recommendation": "I would separately check large integer inputs.", "basis": "An optional future proposal, no execution claimed",
                           "source_paths": ["thoughts.md"]}]})["reflection"]
        report = self.call("report", context)["report"]
        check_context = {"request": "Check the current report source and supplied personal thoughts only; do not run or change anything.",
                         "scope": {"goal": "Report-source acceptance", "authorized_behaviors": ["check"]}}
        check = {**check_context, "items": [
            self.item("source-delivery", "passed", [{"kind": "report", "id": report["id"], "note": "Read actual complete source project"}]),
            self.item("provided-personal-thought", "passed", [self.evidence("thoughts.md")])]}
        before = self.snapshot()
        actual = self.call("check", check)
        self.assertEqual(actual["status"], "passed")
        self.assertEqual(actual["context"]["reports"][-1]["reflection_status"], "not_linked")
        self.assertFalse(actual["context"]["needs_review"])  # Unused proposals do not require review.
        self.assertEqual(self.snapshot(), before)
        linked = self.call("report", self.report_record([{"reflection_id": reflection["id"], "question_ids": ["Q1"]}]))["report"]
        evidence = {"kind": "report", "id": linked["id"], "require_accepted": True,
                    "note": "Q1 is used in this report but has no attributed acceptance"}
        pending = self.call("check", {**check_context, "items": [self.item("personal-acceptance", "passed", [evidence])]})
        self.assertEqual(pending["items"][0]["status"], "passed")
        self.assertEqual(pending["context"]["reports"][-1]["status"], "source_only")
        self.assertEqual(pending["context"]["reports"][-1]["reflection_status"], "recommended_draft")
        self.assertEqual(pending["context"]["state"]["reflections"][-1], reflection)
        accepted = self.call("reflection-reply", {**context, "reflection_id": reflection["id"],
            "reply": {"text": "Synthetic fixture: accept Q1 only.", "source": {"kind": "synthetic", "locator": "AcceptanceWorkflow fixture; not a real user's reply"}},
            "answers": [{"question_ids": ["Q1"], "action": "accept"}]})["reflection"]
        final = self.call("report", self.report_record([{"reflection_id": accepted["id"], "question_ids": ["Q1"]}]))["report"]
        evidence["id"] = final["id"]
        actual = self.call("check", {**check_context, "items": [self.item("personal-acceptance", "passed", [evidence])]})
        self.assertEqual(actual["status"], "passed")
        self.assertEqual(actual["context"]["reflections"][-1]["questions"][1]["status"], "recommended")
        evidence.pop("require_accepted")
        evidence["require_pdf_review"] = True
        pdf = self.call("check", {"request": "Check whether a current reviewed PDF can also be delivered without running anything.",
            "scope": {"goal": "PDF evidence inspection", "authorized_behaviors": ["check"]},
            "items": [self.item("pdf-delivery", "passed", [evidence])]})
        self.assertEqual(pdf["items"][0]["status"], "unverified")

    def test_successful_process_is_failed_correctness_and_check_preserves_source_state_and_exact_index(self):
        (self.workspace / "solution.py").write_text("import sys\nprint(len(sys.stdin.read().split()))\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("add", "solution.py")
        (self.workspace / "notes.txt").write_text("Student's untracked notes")
        execution = self.call("run", self.run_record())
        self.assertEqual(execution["run"]["execution"]["exit_code"], 0)
        self.assertEqual(execution["run"]["execution"]["check"]["status"], "failed")
        before = self.snapshot()
        result = {"kind": "result", "id": execution["result"]["id"], "require_verified": True,
                  "note": "Read actual stdout 3 against independent expected 6"}
        actual = self.call("check", {**self.context(), "items": [self.item("teacher-answer", "passed", [result], route="code")]})
        self.assertEqual(actual["items"][0]["status"], "failed")
        self.assertEqual(actual["items"][0]["agent_status"], "passed")
        self.assertEqual(actual["items"][0]["follow_up"]["action"], "scope_decision_required")
        self.assertEqual(self.snapshot(), before)
        combined = {**self.context(), "scope": {"goal": "Repair and accept", "authorized_behaviors": ["check", "code"]}}
        authorized = self.call("check", {**combined, "items": [self.item("teacher-answer", "failed", [result], route="code")]})
        self.assertEqual(authorized["items"][0]["follow_up"]["action"], "diagnose_then_route_within_current_scope")
        self.assertEqual(self.snapshot(), before)

    def test_stale_files_and_changed_requested_parameters_are_pending_without_a_new_run(self):
        (self.workspace / "solution.py").write_text("print(6)\n", encoding="utf-8")
        run = self.call("run", self.run_record())
        original_source = self.evidence("solution.py")
        record = {**self.context(), "requested_results": [{"key": "teacher", "specification": {
            **self.run_record()["execution"], "stdin_text": "4 5"}}], "items": [
                self.item("teacher-current-parameters", "passed", [{"kind": "result", "id": run["result"]["id"],
                    "require_verified": True, "note": "Original teacher record does not match the new requested input"}]) ]}
        before = self.snapshot()
        changed = self.call("check", record)
        self.assertEqual(changed["items"][0]["status"], "pending_update")
        self.assertEqual(changed["context"]["results"][0]["update_action"], "scope_decision_required")
        self.assertEqual(self.snapshot(), before)
        (self.workspace / "solution.py").write_text("print(9)\n", encoding="utf-8")
        before = self.snapshot()
        stale = self.call("check", {**self.context(), "items": [self.item("source-inspection", "passed", [original_source])]})
        self.assertEqual(stale["items"][0]["status"], "pending_update")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(stale["context"]["state"]["runs"]), 1)

    def test_changed_only_evidence_cannot_retain_a_cached_negative_assessment(self):
        program = self.workspace / "solution.py"
        program.write_text("value = 2\n", encoding="utf-8")
        old_reading = self.evidence("solution.py")
        failed = self.item("required-value-one", "failed", [old_reading], route="code",
                           basis="Actual read found value=2, whereas the requirement asks for 1")
        program.write_text("value = 1\n", encoding="utf-8")
        before = self.snapshot()
        actual = self.call("check", {**self.context(), "items": [failed]})
        item = actual["items"][0]
        self.assertEqual(item["agent_status"], "failed")
        self.assertEqual(item["status"], "pending_update")
        self.assertEqual(item["evidence_checks"][0]["sha256"], old_reading["sha256"])
        self.assertIn("read current file", " ".join(item["missing"]))
        self.assertEqual(self.snapshot(), before)

    def test_failed_run_on_changed_source_is_pending_for_current_acceptance_with_original_failure_preserved(self):
        program = self.workspace / "solution.py"
        program.write_text("print(3)\n", encoding="utf-8")
        old_run = self.call("run", self.run_record())
        self.assertEqual(old_run["run"]["execution"]["check"]["status"], "failed")
        program.write_text("print(6)\n", encoding="utf-8")
        before = self.snapshot()
        old_result = {"kind": "result", "id": old_run["result"]["id"], "require_verified": True,
                      "note": "Read the prior stdout3 against the unchanged teacher answer6"}
        checked = self.call("check", {**self.context(), "items": [
            self.item("teacher-current-source", "failed", [old_result], route="code")]})
        item = checked["items"][0]
        self.assertEqual(item["status"], "pending_update")
        self.assertEqual(item["agent_status"], "failed")
        fact = item["evidence_checks"][0]["fact"]
        self.assertEqual(fact["status"], "failed")
        self.assertTrue(any(issue["kind"] == "dependency" for issue in fact["issues"]))
        self.assertEqual(self.snapshot(), before)

    def test_report_advice_authorization_does_not_authorize_persisting_repairs(self):
        (self.workspace / "main.tex").write_text("Unsupported performance conclusion.\n", encoding="utf-8")
        before = self.snapshot()
        actual = self.call("check", {"request": "Review my report and give advice only.",
            "scope": {"goal": "Report advice", "authorized_behaviors": ["report", "check"], "report_mode": "review"},
            "items": [self.item("claim-support", "failed", [self.evidence("main.tex")], route="report")]})
        self.assertEqual(actual["items"][0]["follow_up"]["action"], "scope_decision_required")
        self.assertEqual(self.snapshot(), before)

    def test_report_advice_with_mixed_permissions_requires_scope_decision_for_analysis(self):
        (self.workspace / "main.tex").write_text("Unsupported conclusion.\n", encoding="utf-8")
        before = self.snapshot()
        actual = self.call("check", {"request": "Give report advice only; execute and change nothing.",
            "scope": {"goal": "Advice", "authorized_behaviors": ["report", "check", "analyze", "code"],
                      "report_mode": "review"},
            "items": [self.item("derived-claim", "failed", [self.evidence("main.tex")], route="analyze")]})
        self.assertEqual(actual["items"][0]["follow_up"]["action"], "scope_decision_required")
        self.assertEqual(self.snapshot(), before)
    def test_mixed_assignment_readonly_then_authorized_code_repair_partial_block_and_report_reacceptance(self):
        program = self.workspace / "solution.py"
        original = "import sys\nprint(len(sys.stdin.read().split()))\n"
        program.write_text(original, encoding="utf-8")
        (self.workspace / "brief.md").write_text("Python stdin/stdout, manual integer accumulation, standard library only. Teacher 1 2 3 => 6; empty => 0. Report source only: Method, Results, Limits.\n", encoding="utf-8")
        (self.workspace / "format.tex").write_text("\\documentclass[11pt]{article}\\section{Galaxy history}Template example only.\n", encoding="utf-8")
        old = self.workspace / "old-report.tex"
        old.write_text("\\section{Galaxy history}The answer is 3. Every input is correct.\n", encoding="utf-8")
        (self.workspace / "thoughts.md").write_text("Supplied fixture thought: passing selected examples does not prove every input.\n", encoding="utf-8")
        (self.workspace / "student-note.txt").write_text("Staged student version\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("add", "student-note.txt")
        (self.workspace / "student-note.txt").write_text("Student's additional unstaged text\n", encoding="utf-8")
        staged_student = self.git("diff", "--cached", "--binary", "--", "student-note.txt")
        original_run = self.call("run", self.run_record())
        index = (self.workspace / ".git/index").read_bytes()
        observed = {"kind": "result", "id": original_run["result"]["id"], "require_verified": True,
                    "note": "Actual zero-exit stdout 3 conflicts with independent teacher answer 6"}
        language = self.item("language-and-io", "passed", [self.evidence("solution.py")])
        behavior = self.item("teacher-and-required-method", "failed", [observed, self.evidence("solution.py")],
                             route="code", basis="Actual source counts tokens with len; brief requires manual integer addition; input 1 2 3 produces 3, teacher requires 6")
        report_gap = self.item("report-structure-and-claims", "failed", [self.evidence("old-report.tex"), self.evidence("brief.md"), self.evidence("format.tex")],
                               route="report", affected_scope=["report"],
                               basis="Old report copies format example Galaxy history instead of required Method/Results/Limits, gives wrong teacher answer and claims every input without proof")
        check_context = {"request": "Check existing code and report source only; do not modify or run.",
                         "scope": {"goal": "Code and report-source acceptance", "authorized_behaviors": ["check"]}}
        before = self.snapshot()
        readonly = self.call("check", {**check_context, "items": [language, behavior, report_gap]})
        self.assertEqual([i["status"] for i in readonly["items"]], ["passed", "failed", "failed"])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(program.read_text(), original)
        self.assertEqual((self.workspace / ".git/index").read_bytes(), index)
        repair_context = {"assignment": {"title": "Integer sum"},
                          "request": "Repair the sum code and check the report; leave report edits for a later decision.",
                          "scope": {"goal": "Working code; report acceptance advice", "authorized_behaviors": ["code", "check"]}}
        routed = self.call("check", {**repair_context, "items": [behavior, report_gap]})
        self.assertEqual([i["follow_up"]["action"] for i in routed["items"]],
                         ["diagnose_then_route_within_current_scope", "scope_decision_required"])
        teacher = self.run_record()["execution"]
        empty = {**teacher, "stdin_text": "", "expected": {"stdout": "0" + os.linesep, "exit_code": 0, "basis": "Independent empty sum is zero"}}
        session = self.call("code-start", {**repair_context, "code_paths": ["solution.py"],
            "checks": [{"id": "teacher", "issue_id": "sum", "kind": "teacher", "execution": teacher},
                       {"id": "empty", "issue_id": "sum", "kind": "boundary", "execution": empty}]})["session"]
        baseline = self.call("code-step", {"session_id": session["id"], "note": "Capture actual original teacher failure before repair"})
        failed_ids = [c["run_id"] for c in baseline["step"]["checks"] if c["status"] == "failed"]
        stage = self.root / "fixed.py"
        stage.write_text("import sys\ntotal = 0\nfor token in sys.stdin.read().split():\n    total += int(token)\nprint(total)\n", encoding="utf-8")
        repaired = self.call("code-step", {"session_id": session["id"], "issue_id": "sum", "note": "Manual accumulation replaces token counting",
            "diagnosis": {"category": "implementation", "finding": "len counts three tokens; teacher arithmetic 1+2+3=6 and empty sum0 were checked; input/environment/oracle are sound",
                          "prediction": "Adding parsed integers should return6 while retaining0 for empty input", "basis_run_ids": failed_ids},
            "changes": [{"path": "solution.py", "staged_path": str(stage), "expected_sha256": baseline["session"]["code_identity"]["solution.py"]}],
            "progress": {"status": "made", "note": "Specific count-versus-value correction; actual original cases determine progress"},
            "requirements_review": [{"requirement": "Python stdin/stdout, manual addition, standard library only", "status": "passed",
                                      "basis": "Read import sys, explicit total loop and int parsing; no sum/library algorithm substitution"}],
            "next_steps": ["Report remains unchanged; its structure and unsupported all-input claim need a scope decision"]})
        self.assertEqual(repaired["session"]["status"], "verified")
        self.assertEqual(repaired["session"]["checks"], session["checks"])
        current_results = [r for r in repaired["results"] if r["current"] and r["status"] == "valid"]
        passed_behavior = self.item("teacher-and-required-method", "passed", [self.evidence("solution.py"), *[
            {"kind": "result", "id": r["id"], "require_verified": True, "note": "Original teacher6 and empty0 rechecked after the exact manual-accumulation repair"} for r in current_results]])
        self.assertEqual(self.git("diff", "--cached", "--binary", "--", "student-note.txt"), staged_student)
        index = (self.workspace / ".git/index").read_bytes()
        before = self.snapshot()
        partial = self.call("check", {**repair_context, "items": [passed_behavior, report_gap]})
        self.assertEqual(partial["status"], "partial")
        self.assertEqual(partial["items"][1]["follow_up"]["action"], "scope_decision_required")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((self.workspace / ".git/index").read_bytes(), index)
        old_bytes = old.read_bytes()
        run_count = len(repaired["state"]["runs"])
        report_context = self.report_record()
        report_context.update(request="Fix only the report source from current valid code/results; do not rerun code.",
                              scope={"goal": "Correct editable report source", "authorized_behaviors": ["report", "check"]})
        stage_tex = self.root / "fixed-report.tex"
        stage_tex.write_text("\\documentclass[11pt]{article}\n\\begin{document}\n\\section{Method}An explicit loop parses each integer and adds it to total.\n"
                            "\\section{Results}Teacher input 1 2 3 produced 6; empty input produced 0.\n"
                            "\\section{Limits}These cases match independent answers; they do not establish all inputs.\n\\end{document}\n", encoding="utf-8")
        report_context.update(files=[{"source": str(stage_tex), "path": "main.tex"}],
                              source_paths=["brief.md", "solution.py", "old-report.tex", "format.tex", "thoughts.md"],
                              result_ids=[r["id"] for r in current_results])
        report_context["content_review"].update(structure_basis="brief.md explicitly requires Method/Results/Limits; Galaxy history is format-example content only",
            format_basis="Only 11pt article style is reused from format.tex",
            technical_review="Manual total loop matches current solution.py; actual teacher6 and empty0 checks are exact selected results; no universal-correctness claim",
            thoughts_basis="Supplied fixture thoughts.md limits the inference to tested cases; no AI recommendation acceptance is claimed")
        final_report = self.call("report", report_context)["report"]
        self.assertEqual(old.read_bytes(), old_bytes)
        self.assertEqual(self.git("diff", "--cached", "--binary", "--", "student-note.txt"), staged_student)
        index = (self.workspace / ".git/index").read_bytes()
        before = self.snapshot()
        final = self.call("check", {**report_context, "items": [passed_behavior,
            self.item("report-structure-and-claims", "passed", [self.evidence(final_report["project"] + "/main.tex"),
                {"kind": "report", "id": final_report["id"], "note": "Read exact project: required three sections, method loop, actual6/0 and bounded conclusion"}], affected_scope=["report source"])]})
        self.assertEqual(final["status"], "passed")
        self.assertEqual(len(final["context"]["state"]["runs"]), run_count)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((self.workspace / ".git/index").read_bytes(), index)


if __name__ == "__main__":
    unittest.main()
