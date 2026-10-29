"""Report prose advice is read-only; authorized edits reuse report staging."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / "skills/cs-homework/scripts/coursework.py"


class ReportProseWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "assignment"
        self.workspace.mkdir()
        self.source = self.workspace / "main.tex"
        self.source.write_text("本次实验具有重要意义。仅在给定的 3 组输入上核对了结果。\n", encoding="utf-8")

    def call(self, command, record=None, ok=True):
        args = [sys.executable, "-B", str(CLI), command, "--workspace", str(self.workspace)]
        if record is not None:
            path = self.root / "request.json"
            path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            args += ["--input", str(path)]
        actual = subprocess.run(args,
                                capture_output=True, text=True, encoding="utf-8")
        if not ok:
            return actual
        self.assertEqual(actual.returncode, 0, actual.stderr)
        return json.loads(actual.stdout)

    def review(self):
        return {"request": "只审校已有报告，给建议，不改文件。",
                "scope": {"goal": "具体语言建议", "authorized_behaviors": ["report"], "report_mode": "review"},
                "sources": [{"path": "main.tex", "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest()}],
                "reading_basis": "已通读main.tex；保留3组范围限定；首句没有独立技术信息。",
                "advice": [{"kind": "style", "path": "main.tex", "quote": "本次实验具有重要意义。",
                            "suggestion": "删除这句空泛评价，直接进入样例范围。", "basis": "未说明具体意义，后句已给出实际观察范围。"}]}

    def report(self):
        stage = self.root / "polished.tex"
        stage.write_text("仅在给定的 3 组输入上核对了结果。\n", encoding="utf-8")
        return {"assignment": {"title": "已有报告语言润色"}, "request": "润色已有报告，只要源码。",
                "scope": {"goal": "润色后的可编辑源码", "authorized_behaviors": ["report"], "report_mode": "polish"},
                "report_key": "polished", "source_only": True, "main_file": "main.tex",
                "files": [{"source": str(stage), "path": "main.tex"}], "source_paths": ["main.tex"],
                "content_review": {"requirement_map": [{"requirement": "保留原有样例范围", "source": "main.tex:1", "location": "main.tex"}],
                    "structure_basis": "原有单段与顺序保留", "format_basis": "无额外格式参考，仅编辑正文",
                    "technical_review": "3组和仅限给定输入的范围不变；没有引入性能或普遍正确性结论",
                    "voice_review": "删除无信息的评价；后句自然准确，保留原文", "thoughts_basis": "没有新增或改变个人思考接受状态",
                    "prose_review": {"comparison_basis": "逐句对照原文与成稿；只删除没有独立信息的评价，其余原样保留。"}}}

    def tree_bytes(self):
        return {str(p.relative_to(self.workspace)): p.read_bytes() for p in self.workspace.rglob("*") if p.is_file()}

    def test_review_only_returns_concrete_advice_without_creating_git_or_context(self):
        before = self.tree_bytes()
        actual = self.call("review-prose", self.review())
        self.assertEqual(actual["advice"][0]["suggestion"], "删除这句空泛评价，直接进入样例范围。")
        self.assertEqual(actual["sources"][0]["sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(actual["mode"], "review")
        self.assertEqual(self.tree_bytes(), before)
        self.assertFalse((self.workspace / ".git").exists())
        self.assertFalse((self.workspace / ".coursework").exists())

    def test_review_scope_cannot_apply_a_staged_report(self):
        record = self.report()
        record["request"] = self.review()["request"]
        record["scope"] = self.review()["scope"]
        before = self.tree_bytes()
        for command in ["report", "review-report"]:
            actual = self.call(command, record, ok=False)
            self.assertEqual(actual.returncode, 2)
            self.assertIn("review-prose", actual.stderr)
        self.assertEqual(self.tree_bytes(), before)
        self.assertFalse((self.workspace / ".git").exists())

    def test_explicit_readonly_overrides_report_writing_and_compiler_permission(self):
        record = self.report()
        record["scope"].update(read_only=True, authorized_behaviors=["report", "run", "analyze"])
        record["source_only"] = False
        # An executable with an observable effect must never be launched for this request.
        compiler = self.root / "compiler.py"
        marker = self.root / "compiler-ran"
        compiler.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('ran')\n", encoding="utf-8")
        record["compiler"] = {"engine": "pdflatex", "executable": sys.executable,
                              "args": [str(compiler)]}
        before = self.tree_bytes()
        actual = self.call("report", record, ok=False)
        self.assertEqual(actual.returncode, 2)
        self.assertEqual(self.tree_bytes(), before)
        self.assertFalse(marker.exists())
        self.assertFalse((self.workspace / ".git").exists())

    def git(self, *args):
        actual = subprocess.run(["git", "-C", str(self.workspace), *args], capture_output=True)
        self.assertEqual(actual.returncode, 0, actual.stderr)
        return actual.stdout

    def test_review_preserves_dirty_index_context_and_pending_reflections_byte_for_byte(self):
        self.call("report", self.report())
        state_path = self.workspace / ".coursework/state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["reflection_fixture"] = {"accepted": ["保留已有判断"], "pending": ["未接受的推荐"]}
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        self.git("add", ".coursework/state.json", "main.tex")
        self.source.write_text(self.source.read_text(encoding="utf-8") + "尚未验证其他输入。\n", encoding="utf-8")
        before = self.tree_bytes()
        self.call("review-prose", self.review())
        self.assertEqual(self.tree_bytes(), before)

    def test_stale_source_or_unread_quote_cannot_be_presented_as_current_advice(self):
        record = self.review()
        self.source.write_text("新的正文已经替换旧主张。", encoding="utf-8")
        before = self.tree_bytes()
        stale = self.call("review-prose", record, ok=False)
        self.assertEqual(stale.returncode, 2)
        self.assertIn("read and assess current bytes", stale.stderr)
        record = self.review()
        unmatched = self.call("review-prose", record, ok=False)
        self.assertEqual(unmatched.returncode, 2)
        self.assertIn("quote the actual declared source", unmatched.stderr)
        self.assertEqual(self.tree_bytes(), before)

    def test_natural_prose_can_remain_and_suspect_claim_is_separate_advice(self):
        self.source.write_text("首先计算前缀和，再处理查询。3个样例通过，因此所有输入均正确。", encoding="utf-8")
        record = self.review()
        record["advice"] = [{"kind": "retain", "path": "main.tex", "quote": "首先计算前缀和，再处理查询。",
                             "suggestion": "保留此句。", "basis": "首先和再表达真实计算顺序，不是冗余套接。"},
                            {"kind": "technical", "path": "main.tex", "quote": "3个样例通过，因此所有输入均正确。",
                             "suggestion": "另行核对证明或更多判定依据；不在纯语言审校中替换为猜测的结论。",
                             "basis": "样例通过不能支持所有输入的全称主张。"}]
        before = self.tree_bytes()
        actual = self.call("review-prose", record)
        self.assertEqual([i["kind"] for i in actual["advice"]], ["retain", "technical"])
        self.assertEqual(self.tree_bytes(), before)
        record["advice"] = []
        self.assertEqual(self.call("review-prose", record)["advice"], [])

    def test_authorized_polish_uses_new_report_version_and_captures_original(self):
        before = self.source.read_bytes()
        self.call("report", self.report())
        state_path = self.workspace / ".coursework/state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        reflections = {"accepted": ["已有明确接受的判断"], "pending": ["尚未接受的完整推荐"], "other_metadata": {"keep": True}}
        state["reflection_fixture"] = reflections
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        self.git("add", ".coursework/state.json")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture: existing reflection metadata")
        actual = self.call("report", self.report())
        report = actual["report"]
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual((self.workspace / report["project"] / "main.tex").read_text(encoding="utf-8"), "仅在给定的 3 组输入上核对了结果。\n")
        captured = self.workspace / report["source_snapshots"][0]["snapshot_path"]
        self.assertEqual(captured.read_bytes(), before)
        self.assertIn("逐句对照", report["content_review"]["prose_review"]["comparison_basis"])
        self.assertEqual(actual["state"]["scope"]["report_mode"], "polish")
        self.assertEqual(actual["state"].get("runs", []), [])
        self.assertEqual(actual["state"]["reflection_fixture"], reflections)

    def test_review_only_does_not_gain_run_permission_from_report_support(self):
        (self.workspace / "known.py").write_text("from pathlib import Path\nPath('ran.txt').write_text('ran')\nprint(6)\n", encoding="utf-8")
        record = {**self.report(), "scope": self.review()["scope"], "request": self.review()["request"],
                  "execution": {"argv": [sys.executable, "known.py"], "source_paths": ["known.py"],
                    "purposes": ["correctness"], "basis": "已知样例", "report_support": {"basis": "声称是报告支持的调用"},
                    "dependency_coverage": {"status": "complete", "note": "单个已有脚本"},
                    "expected": {"stdout": "6" + os.linesep, "basis": "独立字面量"}}}
        before = self.tree_bytes()
        actual = self.call("run", record, ok=False)
        self.assertEqual(actual.returncode, 2)
        self.assertEqual(self.tree_bytes(), before)
        self.assertFalse((self.workspace / "ran.txt").exists())

    def test_review_limits_override_mixed_permissions_until_current_scope_changes(self):
        (self.workspace / "known.py").write_text("print(6)\n", encoding="utf-8")
        record = {**self.report(), "result_key": "known", "scope": {"goal": "执行样例", "authorized_behaviors": ["run", "report"]},
                  "execution": {"argv": [sys.executable, "known.py"], "source_paths": ["known.py"],
                    "purposes": ["correctness"], "basis": "已知样例", "report_support": {"basis": "已记录报告所需样例"},
                    "dependency_coverage": {"status": "complete", "note": "单个已有脚本"},
                    "expected": {"stdout": "6" + os.linesep, "basis": "独立字面量"}}}
        self.call("run", record)
        (self.workspace / "known.py").write_text("print(7)\n", encoding="utf-8")
        inspect = {"scope": self.review()["scope"], "requested_results": [{"key": "known", "specification": record["execution"]}]}
        before = self.tree_bytes()
        actual = self.call("results", inspect)
        self.assertEqual(actual["results"][0]["update_action"], "scope_decision_required")
        self.assertEqual(self.tree_bytes(), before)
        for authorization in ["run", "code"]:
            inspect["scope"] = {**self.review()["scope"], "authorized_behaviors": ["report", authorization]}
            self.assertEqual(self.call("results", inspect)["results"][0]["update_action"], "scope_decision_required")
            # A new human request can authorize actual execution; the old advice limit is removed.
            inspect["scope"] = {"goal": "Run the changed case", "authorized_behaviors": [authorization]}
            self.assertEqual(self.call("results", inspect)["results"][0]["update_action"], "prepare_targeted_run_and_check_budget")
        record["scope"] = inspect["scope"]
        record["execution"]["expected"]["stdout"] = "7" + os.linesep
        self.assertEqual(self.call("run", record)["run"]["execution"]["check"]["status"], "passed")

    def test_polishing_linked_report_preserves_actual_accepted_and_pending_reflections(self):
        (self.workspace / "method.py").write_text("def total(n):\n    return n * (n + 1) // 2\n", encoding="utf-8")
        setup = {"assignment": {"title": "已有报告与个人思考"}, "request": "根据已有方法准备个人思考和完整源码草稿。",
                 "scope": {"goal": "含完整推荐的报告草稿", "authorized_behaviors": ["report"]}}
        proposed = self.call("reflection", {**setup, "reflection_key": "limitations",
            "need_basis": "这份报告需要个人判断，已有材料只有实现和样例范围说明。",
            "questions": [
                {"id": "Q1", "question": "现有材料能否说明已完成全部测试？",
                 "recommendation": "代码给出非负整数求和公式，但没有提供执行记录，因此不能写成已完成全部测试。",
                 "basis": "method.py:1-2是公式实现，不包含实际运行证据。", "source_paths": ["method.py"]},
                {"id": "Q2", "question": "若要支持非整数输入，应先明确什么？",
                 "recommendation": "若需要支持非整数输入，我会先明确类型约束；本次尚未实现额外校验。",
                 "basis": "method.py没有类型检查，非整数支持也没有作业要求。", "source_paths": ["method.py"]}]})["reflection"]
        replied = self.call("reflection-reply", {**setup, "reflection_id": proposed["id"],
            "reply": {"text": "Synthetic fixture: accept Q1 only; Q2 remains unanswered.",
                      "source": {"kind": "synthetic", "locator": "test_report_prose_workflow partial-reply fixture"}},
            "answers": [{"question_ids": ["Q1"], "action": "accept"}]})["reflection"]
        paragraphs = "\n\n".join(q["content"] for q in replied["questions"])
        links = [{"reflection_id": replied["id"], "question_ids": ["Q1", "Q2"]}]
        draft = self.root / "linked-draft.tex"
        draft.write_text("\\documentclass{article}\\begin{document}\n本次实验具有重要意义。\n" + paragraphs + "\n\\end{document}\n", encoding="utf-8")
        record = {**self.report(), **setup, "files": [{"source": str(draft), "path": "main.tex"}],
                  "source_paths": ["main.tex", "method.py"], "reflection_sources": links}
        record["content_review"].update({
            "requirement_map": [{"requirement": "完整个人思考草稿并保留接受状态", "source": "当前请求及reflection记录", "location": "main.tex两段思考"}],
            "structure_basis": "保持两段思考的顺序与内容，不新增结构。", "format_basis": "仅要源码，保留已有article外壳。",
            "technical_review": "读method.py，公式实现没有运行或额外类型检查；两段明确没有执行记录、未实现校验和未来的输入约束判断。",
            "voice_review": "正文是具体方法限制与计划，没有新增亲历；仅删除没有独立信息的实验意义评价。",
            "thoughts_basis": "真实reflection API记录：Q1仅由明确标识的synthetic回复接受，Q2完整推荐仍待确认；两段如实链接。",
            "prose_review": {"comparison_basis": "逐句对照，两个完整思考段落不改；新版本仅删开头无独立信息的评价，保留实际接受和待确认来源。"}})
        original = self.call("report", record)
        self.assertEqual(original["report"]["reflection_status"], "mixed")
        old_source = original["report"]["files"][0]["path"]
        advice = {**self.review(), "sources": [{"path": old_source, "sha256": hashlib.sha256((self.workspace / old_source).read_bytes()).hexdigest()}]}
        advice["advice"][0]["path"] = old_source
        advice["reading_basis"] = "已读完整源码草稿与method.py；Q1已接受、Q2尚未接受，语言建议不修改任何思考或状态。"
        advice["advice"][0]["basis"] = "首句没有独立判断信息；后文已有两段具体的方法限制和未来计划。"
        before_advice = self.tree_bytes()
        self.call("review-prose", advice)
        self.assertEqual(self.tree_bytes(), before_advice)
        polished = self.root / "linked-polished.tex"
        polished.write_text("\\documentclass{article}\\begin{document}\n" + paragraphs + "\n\\end{document}\n", encoding="utf-8")
        polish_scope = {"goal": "润色已有报告源码，保留已有思考状态", "authorized_behaviors": ["report"], "report_mode": "polish"}
        final = self.call("report", {**record, "request": "仅润色已有报告，只要源码；保留既有个人思考内容和接受状态。",
            "scope": polish_scope, "files": [{"source": str(polished), "path": "main.tex"}], "source_paths": [old_source, "method.py"]})
        self.assertNotEqual(final["report"]["id"], original["report"]["id"])
        self.assertEqual(final["state"]["reflections"], original["state"]["reflections"])
        self.assertEqual(final["state"]["reflection_heads"], original["state"]["reflection_heads"])
        self.assertEqual(final["report"]["reflection_sources"], links)
        self.assertEqual(final["report"]["reflection_status"], "mixed")
        self.assertIn(paragraphs, (self.workspace / final["report"]["project"] / "main.tex").read_text(encoding="utf-8"))
        resumed = self.call("resume")
        current = next(r for r in resumed["reflections"] if r["current"])
        self.assertEqual([q["status"] for q in current["questions"]], ["accepted", "recommended"])
        self.assertEqual([q["evidence_status"] for q in current["questions"]], ["valid", "valid"])
        self.assertEqual(resumed["state"]["reflections"][-1]["questions"][0]["decisions"][-1]["source"]["kind"], "synthetic")
        self.assertEqual(next(r for r in resumed["reports"] if r["current"])["reflection_status"], "mixed")
        self.assertEqual(resumed["state"]["scope"], polish_scope)


if __name__ == "__main__":
    unittest.main()
