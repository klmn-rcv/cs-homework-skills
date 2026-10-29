"""Model-led personal thoughts through the shared public CLI (synthetic replies)."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / "skills/cs-homework/scripts/coursework.py"


class ReflectionWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "assignment"
        self.workspace.mkdir()
        (self.workspace / "solution.py").write_text("def sum_to(n):\n    return n * (n + 1) // 2\n", encoding="utf-8")
        (self.workspace / "brief.md").write_text("Explain the method and personal limitations. Source only.\n", encoding="utf-8")

    def call(self, command, record=None, ok=True):
        args = [sys.executable, "-B", str(CLI), command, "--workspace", str(self.workspace)]
        if record is not None:
            path = self.root / "input.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            args += ["--input", str(path)]
        actual = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
        if not ok:
            return actual
        self.assertEqual(actual.returncode, 0, actual.stderr)
        return json.loads(actual.stdout)

    def context(self):
        return {"assignment": {"title": "Integer sum"}, "request": "Write report source and help me express thoughts.",
                "scope": {"goal": "Report source with grounded thoughts", "authorized_behaviors": ["report"]}}

    def prepare(self):
        return {**self.context(), "reflection_key": "limitations", "need_basis": "brief.md:1 requires personal limitations; no supplied thoughts",
                "questions": [
                    {"id": "Q1", "question": "What can this example establish?",
                     "recommendation": "The formula explains sums of nonnegative integers. Without actual execution evidence I would not claim that every input has been tested.",
                     "basis": "solution.py:1-2 is a closed formula; no execution evidence supplied", "source_paths": ["solution.py"]},
                    {"id": "Q2", "question": "How should noninteger inputs be handled?",
                     "background": "The current function has no type check and uses integer floor division.",
                     "recommendation": "I would make the nonnegative integer input contract explicit and add validation if other inputs must be supported.",
                     "basis": "solution.py:2 floor division; brief.md does not specify other input types", "source_paths": ["solution.py", "brief.md"]}]}

    def report(self, reflection, question_ids=None):
        question_ids = question_ids or [q["id"] for q in reflection["questions"]]
        stage = self.root / "main.tex"
        stage.write_text("\\documentclass{article}\\begin{document}\n" + "\n\n".join(q["content"] for q in reflection["questions"] if q["id"] in question_ids) + "\n\\end{document}\n", encoding="utf-8")
        return self.call("report", {**self.context(), "report_key": "integer-sum", "source_only": True,
                    "files": [{"source": str(stage), "path": "main.tex"}], "main_file": "main.tex", "source_paths": ["brief.md", "solution.py"],
                    "reflection_sources": [{"reflection_id": reflection["id"], "question_ids": question_ids}],
                    "content_review": {"requirement_map": [{"requirement": "limitations", "source": "brief.md:1", "location": "main.tex"}],
                                       "structure_basis": "brief requires method and limitations", "format_basis": "No supplied template",
                                       "technical_review": "Read exact formula and limited claims", "voice_review": "No invented testing experience",
                                       "thoughts_basis": "Complete proposed paragraphs, pending unless explicit fixture reply is recorded"}})

    def test_unanswered_recommendations_are_complete_pending_and_linked_to_report_across_resume(self):
        actual = self.call("reflection", self.prepare())
        reflection = actual["reflection"]
        self.assertEqual([q["status"] for q in reflection["questions"]], ["recommended", "recommended"])
        self.assertEqual(reflection["questions"][0]["content"], self.prepare()["questions"][0]["recommendation"])
        self.assertNotIn("background", reflection["questions"][0])
        report = self.report(reflection)
        self.assertEqual(report["report"]["reflection_status"], "recommended_draft")
        restored = self.call("resume")
        self.assertEqual(restored["reflections"][0]["questions"][0]["status"], "recommended")
        self.assertEqual(restored["reports"][0]["reflection_status"], "recommended_draft")
        self.assertEqual(len(restored["state"]["reports"]), 1)
        self.assertEqual(restored["state"]["request"], self.context()["request"])

    def test_mixed_legacy_history_continues_and_checks_without_new_reply(self):
        original = self.call("reflection", self.prepare())["reflection"]
        legacy = self.call("reflection-reply", self.reply(original,
            [{"question_ids": ["Q1"], "action": "accept"}]))["reflection"]
        report = self.report(legacy)["report"]
        before = {p.relative_to(self.workspace).as_posix(): p.read_bytes()
                  for p in self.workspace.rglob("*") if p.is_file()}
        resumed = self.call("resume")
        self.assertFalse(resumed["needs_review"])
        self.assertEqual(resumed["reports"][-1]["reflection_status"], "mixed")
        request = {"request": "Check current report sources only, without running or changing anything.",
                   "scope": {"goal": "Current report evidence", "authorized_behaviors": ["check"], "read_only": True},
                   "items": [{"id": "grounded-report", "requirement": "Current grounded source report",
                              "status": "passed", "basis": "Read formula, current sources and both complete paragraphs",
                              "evidence": [{"kind": "report", "id": report["id"], "require_accepted": True,
                                            "note": "Legacy flag retained; current evidence inspected"}],
                              "missing": [], "affected_scope": ["report"]}]}
        checked = self.call("check", request)
        self.assertEqual(checked["status"], "passed")
        self.assertEqual(checked["context"]["state"]["reflections"][-1], legacy)
        self.assertEqual(before, {p.relative_to(self.workspace).as_posix(): p.read_bytes()
                                for p in self.workspace.rglob("*") if p.is_file()})
        (self.workspace / "solution.py").write_text("def sum_to(n):\n    return 0\n", encoding="utf-8")
        stale = self.call("check", request)
        self.assertEqual(stale["items"][0]["status"], "pending_update")
        self.assertEqual(stale["context"]["state"]["reflections"][-1], legacy)

    def reply(self, reflection, answers, text="Synthetic fixture reply, not real human consent."):
        return {**self.context(), "reflection_id": reflection["id"], "reply": {"text": text,
                "source": {"kind": "synthetic", "locator": "test_reflection_workflow fixture"}}, "answers": answers}

    def test_accept_edit_replace_keep_original_recommendations_and_update_real_report(self):
        request = self.prepare()
        request["questions"].append({"id": "Q3", "question": "What should a later check add?",
                "recommendation": "I would include zero and a large integer in later checks; no such runs are claimed here.",
                "basis": "solution.py accepts an integer; no execution is recorded", "source_paths": ["solution.py"]})
        original = self.call("reflection", request)["reflection"]
        first_report = self.report(original)["report"]
        edited = "The formula describes nonnegative integers; I would document that input contract before adding other types."
        replaced = "I would compare a few known answers with an independent sum; runtime measurements are outside this report."
        actual = self.call("reflection-reply", self.reply(original, [
                {"question_ids": ["Q1"], "action": "accept"},
                {"question_ids": ["Q2"], "action": "edit", "answer": edited},
                {"question_ids": ["Q3"], "action": "replace", "answer": replaced}]))
        updated = actual["reflection"]
        self.assertEqual([q["status"] for q in updated["questions"]], ["accepted"] * 3)
        self.assertEqual([q["content"] for q in updated["questions"]], [original["questions"][0]["content"], edited, replaced])
        self.assertEqual(updated["questions"][1]["recommendation"], original["questions"][1]["recommendation"])
        self.assertEqual(updated["questions"][2]["decisions"][-1]["source"]["kind"], "synthetic")
        self.assertEqual(next(r for r in actual["reports"] if r["id"] == first_report["id"])["status"], "pending_update")
        final = self.report(updated)
        self.assertEqual(final["report"]["reflection_status"], "accepted_content")
        self.assertIn(replaced, (self.workspace / final["report"]["project"] / "main.tex").read_text())
        resumed = self.call("resume")
        self.assertEqual(resumed["state"]["reflections"][-1]["questions"][1]["content"], edited)

    def test_batch_accept_is_explicit_and_empty_reply_never_accepts_anything(self):
        original = self.call("reflection", self.prepare())["reflection"]
        bad = self.call("reflection-reply", self.reply(original, [{"question_ids": ["Q1", "Q2"], "action": "accept"}], text=""), ok=False)
        self.assertEqual(bad.returncode, 2)
        self.assertEqual(len(self.call("resume")["state"]["reflections"]), 1)
        accepted = self.call("reflection-reply", self.reply(original, [{"question_ids": ["Q1", "Q2"], "action": "accept"}], text="Fixture: accept both recommended answers."))
        self.assertEqual([q["status"] for q in accepted["reflection"]["questions"]], ["accepted", "accepted"])
        self.assertEqual(accepted["reflection"]["questions"][0]["decisions"][-1]["reply"], "Fixture: accept both recommended answers.")

    def test_report_using_q1_survives_unused_q2_reply_and_basis_change(self):
        request = self.prepare()
        request["questions"][1]["source_paths"] = ["brief.md"]
        original = self.call("reflection", request)["reflection"]
        accepted = self.call("reflection-reply", self.reply(original, [{"question_ids": ["Q1"], "action": "accept"}]))["reflection"]
        report = self.report(accepted, ["Q1"])["report"]
        changed = self.call("reflection-reply", self.reply(accepted, [{"question_ids": ["Q2"], "action": "replace", "answer": "I would document the input contract explicitly."}]))["reflection"]
        resumed = self.call("resume")
        checked = next(r for r in resumed["reports"] if r["id"] == report["id"])
        self.assertEqual(checked["status"], "source_only")
        self.assertEqual(checked["reflection_status"], "accepted_content")
        self.assertEqual(self.report(accepted, ["Q1"])["report"]["reflection_status"], "accepted_content")
        (self.workspace / "brief.md").write_text("Explain limitations; source only. Clarified unrelated wording.\n", encoding="utf-8")
        checked = next(r for r in self.call("results")["reports"] if r["id"] == report["id"])
        # The report itself also depends on brief.md, so check its selected thought separately.
        self.assertFalse(any(i.get("kind") == "reflection" for i in checked["issues"]))
        self.assertEqual(changed["questions"][0]["decisions"], accepted["questions"][0]["decisions"])

    def test_unused_question_snapshot_damage_does_not_invalidate_selected_q1(self):
        original = self.call("reflection", self.prepare())["reflection"]
        report = self.report(original, ["Q1"])["report"]
        snapshot = original["questions"][1]["source_snapshots"][0]["snapshot_path"]
        (self.workspace / snapshot).write_text("damaged unused Q2 snapshot", encoding="utf-8")
        actual = self.call("results")
        reflection = next(r for r in actual["reflections"] if r["current"])
        self.assertEqual([q["evidence_status"] for q in reflection["questions"]], ["valid", "needs_review"])
        self.assertEqual(next(r for r in actual["reports"] if r["id"] == report["id"])["status"], "source_only")

    def test_accepting_unchanged_selected_paragraph_updates_provenance_without_invalidating_source(self):
        original = self.call("reflection", self.prepare())["reflection"]
        report = self.report(original, ["Q1"])["report"]
        actual = self.call("reflection-reply", self.reply(original, [{"question_ids": ["Q1"], "action": "accept"}]))
        checked = next(r for r in actual["reports"] if r["id"] == report["id"])
        self.assertEqual(checked["status"], "source_only")
        self.assertEqual(checked["reflection_status"], "accepted_content")

    def test_review_of_selected_q1_does_not_require_repair_of_unused_q2_snapshot(self):
        request = self.prepare()
        request["questions"][1]["source_paths"] = ["brief.md"]
        original = self.call("reflection", request)["reflection"]
        accepted = self.call("reflection-reply", self.reply(original, [{"question_ids": ["Q1"], "action": "accept"}]))["reflection"]
        snapshot = accepted["questions"][1]["source_snapshots"][0]["snapshot_path"]
        (self.workspace / snapshot).write_text("damaged unused Q2 snapshot", encoding="utf-8")
        (self.workspace / "solution.py").write_text("# comment only\ndef sum_to(n):\n    return n * (n + 1) // 2\n", encoding="utf-8")
        actual = self.call("reflection-review", {**self.context(), "reflection_id": accepted["id"], "reviews": [
            {"question_id": "Q1", "disposition": "still_supported", "basis": "Only comment added; formula and cautious no-execution claim unchanged.", "source_paths": ["solution.py"]}]})
        checked = next(r for r in actual["reflections"] if r["current"])
        self.assertEqual([q["evidence_status"] for q in checked["questions"]], ["valid", "needs_review"])
        self.assertEqual(actual["reflection"]["questions"][0]["decisions"], accepted["questions"][0]["decisions"])
        current = actual["reflection"]
        (self.workspace / current["questions"][0]["source_snapshots"][0]["snapshot_path"]).write_text("damaged selected Q1", encoding="utf-8")
        rejected = self.call("reflection-review", {**self.context(), "reflection_id": current["id"], "reviews": [
            {"question_id": "Q1", "disposition": "still_supported", "basis": "Must not clear damaged selected evidence", "source_paths": ["solution.py"]}]}, ok=False)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("damaged immutable selected-question evidence", rejected.stderr)

    def test_changed_evidence_flags_only_affected_question_and_preserves_accepted_answer(self):
        request = self.prepare()
        request["questions"][1]["source_paths"] = ["brief.md"]
        original = self.call("reflection", request)["reflection"]
        accepted = self.call("reflection-reply", self.reply(original, [{"question_ids": ["Q1", "Q2"], "action": "accept"}]))["reflection"]
        self.report(accepted)
        (self.workspace / "solution.py").write_text("def sum_to(n):\n    return sum(range(n + 1))\n", encoding="utf-8")
        actual = self.call("resume")
        current = next(r for r in actual["reflections"] if r["current"])
        self.assertEqual([q["evidence_status"] for q in current["questions"]], ["needs_review", "valid"])
        self.assertEqual(current["questions"][0]["status"], "accepted")
        self.assertEqual(current["questions"][0]["content"], original["questions"][0]["content"])
        self.assertEqual(actual["reports"][0]["status"], "pending_update")
        self.assertEqual(self.report(accepted, ["Q2"])["report"]["reflection_status"], "accepted_content")
        bad = self.call("reflection-reply", self.reply(accepted, [{"question_ids": ["Q1"], "action": "replace", "answer": "Unreviewed changed basis"}]), ok=False)
        self.assertEqual(bad.returncode, 2)
        review = {**self.context(), "reflection_id": accepted["id"], "reviews": [{"question_id": "Q1", "disposition": "still_supported",
                  "basis": "Compared old formula and current summation; both compute nonnegative integer sums, and neither supplies actual test evidence. Existing cautious answer remains applicable.",
                  "source_paths": ["solution.py"]}]}
        reviewed = self.call("reflection-review", review)["reflection"]
        self.assertEqual(reviewed["questions"][0]["status"], "accepted")
        self.assertEqual(reviewed["questions"][0]["content"], original["questions"][0]["content"])
        self.assertEqual(len(reviewed["questions"][0]["decisions"]), 1)
        self.assertEqual(self.report(reviewed)["report"]["reflection_status"], "accepted_content")

    def test_selected_basis_review_preserves_acceptance_without_reasking_and_revise_reopens_only_it(self):
        original = self.call("reflection", self.prepare())["reflection"]
        accepted = self.call("reflection-reply", self.reply(original, [{"question_ids": ["Q1"], "action": "accept"}]))["reflection"]
        report = self.report(accepted, ["Q1"])["report"]
        (self.workspace / "solution.py").write_text("# equivalent formula, clarified name\ndef sum_to(n):\n    return n * (n + 1) // 2\n", encoding="utf-8")
        checked = next(r for r in self.call("results")["reports"] if r["id"] == report["id"])
        self.assertTrue(any(i.get("kind") == "reflection" for i in checked["issues"]))
        reviewed = self.call("reflection-review", {**self.context(), "reflection_id": accepted["id"], "reviews": [
            {"question_id": "Q1", "disposition": "still_supported", "basis": "Read old/current source: only a comment was added; formula and no-execution limitation unchanged.", "source_paths": ["solution.py"]}]})["reflection"]
        checked = next(r for r in self.call("results")["reports"] if r["id"] == report["id"])
        self.assertFalse(any(i.get("kind") == "reflection" for i in checked["issues"]))
        self.assertEqual(reviewed["questions"][0]["decisions"], accepted["questions"][0]["decisions"])
        (self.workspace / "solution.py").write_text("def sum_to(n):\n    return sum(range(n + 1))\n", encoding="utf-8")
        revised = self.call("reflection-review", {**self.context(), "reflection_id": reviewed["id"], "reviews": [
            {"question_id": "Q1", "disposition": "revise", "basis": "Formula replaced by traversal; old formula wording no longer applies.", "recommendation": "The implementation now sums a range; there is still no execution evidence for universal test claims.", "source_paths": ["solution.py"]}]})["reflection"]
        checked = next(r for r in self.call("results")["reports"] if r["id"] == report["id"])
        self.assertTrue(any(i.get("kind") == "reflection" for i in checked["issues"]))
        self.assertEqual(revised["questions"][0]["decisions"], accepted["questions"][0]["decisions"])
        self.assertEqual(revised["questions"][0]["status"], "recommended")
        self.assertEqual(revised["questions"][1], reviewed["questions"][1])

    def test_preserves_user_index_unknown_state_and_rejects_bad_proposals_before_writing(self):
        def git(*args):
            actual = subprocess.run(["git", "-C", str(self.workspace), *args], capture_output=True)
            self.assertEqual(actual.returncode, 0, actual.stderr)
            return actual.stdout
        git("init", "-q")
        git("add", "brief.md")
        staged = git("diff", "--cached", "--binary")
        (self.workspace / "brief.md").write_text("Student's unstaged clarification.\n", encoding="utf-8")
        request = self.prepare()
        request["questions"][0]["recommendation"] = " "
        self.assertEqual(self.call("reflection", request, ok=False).returncode, 2)
        self.assertFalse((self.workspace / ".coursework").exists())
        first = self.call("reflection", self.prepare())["reflection"]
        state_path = self.workspace / ".coursework/state.json"
        state = json.loads(state_path.read_text())
        state["future_namespace"] = {"keep": [1, 2, 3]}
        state_path.write_text(json.dumps(state), encoding="utf-8")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-q", "-m", "fixture: preserve future namespace", "--only", ".coursework/state.json")
        actual = self.call("reflection-reply", self.reply(first, [{"question_ids": ["Q1"], "action": "accept"}]))
        self.assertEqual(actual["state"]["future_namespace"], {"keep": [1, 2, 3]})
        self.assertEqual(git("diff", "--cached", "--binary"), staged)
        self.assertEqual((self.workspace / "brief.md").read_text(), "Student's unstaged clarification.\n")
        self.assertNotIn(b"brief.md", git("show", "--pretty=", "--name-only", "HEAD"))
        self.assertEqual([q["status"] for q in actual["reflection"]["questions"]], ["accepted", "recommended"])

    def test_review_only_scope_never_persists_recommendations_or_acceptance(self):
        request = self.prepare()
        request["scope"] = {**request["scope"], "report_mode": "review"}
        self.assertEqual(self.call("reflection", request, ok=False).returncode, 2)
        self.assertFalse((self.workspace / ".coursework").exists())
        original = self.call("reflection", self.prepare())["reflection"]
        before = (self.workspace / ".coursework/state.json").read_bytes()
        reply = self.reply(original, [{"question_ids": ["Q1"], "action": "accept"}])
        reply["scope"] = request["scope"]
        self.assertEqual(self.call("reflection-reply", reply, ok=False).returncode, 2)
        review = {**self.context(), "scope": request["scope"], "reflection_id": original["id"], "reviews": []}
        self.assertEqual(self.call("reflection-review", review, ok=False).returncode, 2)
        self.assertEqual((self.workspace / ".coursework/state.json").read_bytes(), before)

    def test_replaced_result_and_damaged_receipt_cannot_be_hidden_as_accepted_thoughts(self):
        data = self.workspace / "provided.csv"
        data.write_text("n,sum\n3,6\n", encoding="utf-8")
        external = {**self.context(), "result_key": "provided", "data_paths": ["provided.csv"],
                    "provenance": {"provided_by": "fixture", "location": "provided.csv", "description": "Synthetic external row; generating run unverified"}}
        result = self.call("import-result", external)["result"]
        request = self.prepare()
        request["questions"][0]["source_paths"] = []
        request["questions"][0]["result_ids"] = [result["id"]]
        original = self.call("reflection", request)["reflection"]
        self.report(original)
        self.call("import-result", external)
        current = next(r for r in self.call("results")["reflections"] if r["current"])
        self.assertEqual([q["evidence_status"] for q in current["questions"]], ["needs_review", "valid"])
        self.assertEqual(self.call("results")["reports"][0]["status"], "pending_update")
        receipt = self.workspace / original["receipt"]["path"]
        receipt.write_text("damaged immutable receipt", encoding="utf-8")
        review = {**self.context(), "reflection_id": original["id"], "reviews": [{"question_id": "Q1", "disposition": "still_supported",
                  "basis": "Do not accept this attempted unsupported reset", "source_paths": ["solution.py"], "result_ids": []}]}
        rejected = self.call("reflection-review", review, ok=False)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("damaged immutable", rejected.stderr)

    def test_revised_basis_reopens_only_affected_recommendation_without_reconfirming_other_answers(self):
        request = self.prepare()
        request["questions"][1]["source_paths"] = ["brief.md"]
        original = self.call("reflection", request)["reflection"]
        accepted = self.call("reflection-reply", self.reply(original, [{"question_ids": ["Q1", "Q2"], "action": "accept"}]))["reflection"]
        (self.workspace / "solution.py").write_text("def sum_to(n):\n    return sum(range(n + 1))\n", encoding="utf-8")
        paragraph = "The new implementation traverses a range instead of using the earlier closed formula. I would now explain that loop and keep execution claims limited to recorded evidence."
        revised = self.call("reflection-review", {**self.context(), "reflection_id": accepted["id"], "reviews": [
            {"question_id": "Q1", "disposition": "revise", "basis": "The current source replaced the direct formula with sum(range(n+1)); old method wording needs revision.",
             "recommendation": paragraph, "source_paths": ["solution.py"]}]})["reflection"]
        self.assertEqual([q["status"] for q in revised["questions"]], ["recommended", "accepted"])
        self.assertEqual(revised["questions"][0]["content"], paragraph)
        self.assertEqual(len(revised["questions"][0]["decisions"]), 1)
        self.assertEqual(revised["questions"][1], accepted["questions"][1])
        self.assertEqual(self.report(revised)["report"]["reflection_status"], "mixed")
        final = self.call("reflection-reply", self.reply(revised, [{"question_ids": ["Q1"], "action": "accept"}], text="Fixture: accept the revised Q1 only."))["reflection"]
        self.assertEqual([q["status"] for q in final["questions"]], ["accepted", "accepted"])
        self.assertEqual(len(final["questions"][1]["decisions"]), 1)


if __name__ == "__main__":
    unittest.main()
