"""Assignment-local diagnosis survives a new read without accepting permission."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / "skills/cs-homework/scripts/coursework.py"


class AssignmentHandoff(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "assignment"
        self.workspace.mkdir()
        (self.workspace / "solution.py").write_text("print(25)\n", encoding="utf-8")
        self.note = self.root / "note.md"
        self.note.write_text("## 诊断\n实际25；教师预期15。来源：题目第2行与已有运行stdout.bin。\n"
                             "## 已完成\n已解释接口；未依赖该结果的提纲完成。\n"
                             "## 等待用户决定\n是否允许修复循环上界？建议修复后重验教师样例；尚未获得权限。\n"
                             "## 下一步\n收到真实回复后再决定；等待时复用已有证据，不重跑。\n", encoding="utf-8")

    def cli(self, command, record=None, ok=True):
        argv = [sys.executable, "-B", str(CLI), command, "--workspace", str(self.workspace)]
        if record is not None:
            path = self.root / "input.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            argv += ["--input", str(path)]
        actual = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(actual.returncode, 0 if ok else 2, actual.stderr or actual.stdout)
        return json.loads(actual.stdout if ok else actual.stderr)

    def request(self):
        return {"request": "只写报告；不改实现。", "scope": {"goal": "报告", "authorized_behaviors": ["report"]},
                "note_path": str(self.note)}

    def test_blocked_writing_saves_diagnosis_actual_scope_and_unaccepted_question_without_code_or_state_changes(self):
        original = (self.workspace / "solution.py").read_bytes()
        actual = self.cli("handoff", self.request())
        self.assertEqual(actual["handoff"]["path"], ".coursework/handoff.md")
        saved = self.workspace / actual["handoff"]["path"]
        self.assertIn(self.note.read_text(encoding="utf-8"), saved.read_text(encoding="utf-8"))
        self.assertIn("只写报告；不改实现。", saved.read_text(encoding="utf-8"))
        self.assertIn('"authorized_behaviors": [', saved.read_text(encoding="utf-8"))
        self.assertEqual((self.workspace / "solution.py").read_bytes(), original)
        self.assertFalse((self.workspace / ".coursework/state.json").exists())
        self.assertIsNotNone(actual["git"]["commit"])

    def test_note_only_assignment_can_enter_run_directly_and_resume_lists_all_preserved_handoffs_read_only(self):
        self.cli("handoff", self.request())
        original = self.workspace / ".coursework/handoff.md"
        original.write_text(original.read_text(encoding="utf-8") + "\n学生补充，保留。\n", encoding="utf-8")
        dirty_bytes = original.read_bytes()
        saved = self.cli("handoff", self.request())
        self.assertEqual(saved["handoff"]["path"], ".coursework/handoff-0001.md")
        self.assertEqual(original.read_bytes(), dirty_bytes)
        run = {"assignment": {"title": "已有程序"}, "request": "现在只运行已有程序并保存证据。",
               "scope": {"goal": "运行证据", "authorized_behaviors": ["run"]},
               "execution": {"argv": [sys.executable, "-B", "solution.py"], "source_paths": ["solution.py"],
                             "purposes": ["example"], "basis": "当前真实请求", "expected": {
                                 "stdout": "25" + os.linesep, "exit_code": 0, "basis": "明确常量输出25"}}}
        self.cli("run", run)
        before = {p.relative_to(self.workspace).as_posix(): p.read_bytes()
                  for p in self.workspace.rglob("*") if p.is_file() and ".git" not in p.parts}
        resumed = self.cli("resume")
        self.assertEqual([n["path"] for n in resumed["handoffs"]],
                         [".coursework/handoff-0001.md", ".coursework/handoff.md"])
        self.assertEqual(original.read_bytes(), dirty_bytes)
        self.assertEqual(before, {p.relative_to(self.workspace).as_posix(): p.read_bytes()
                                 for p in self.workspace.rglob("*") if p.is_file() and ".git" not in p.parts})

    def test_resume_plain_notes_and_real_output_without_registration_preserves_every_byte(self):
        (self.workspace / "notes.txt").write_text("Only analyze stdout.txt; do not run or fix. Pending: may I fix?", encoding="utf-8")
        (self.workspace / "stdout.txt").write_text("25\n", encoding="utf-8")
        before = {p.relative_to(self.workspace).as_posix(): p.read_bytes() for p in self.workspace.rglob("*") if p.is_file()}
        actual = self.cli("resume")
        self.assertEqual(actual["context_status"], "absent")
        self.assertEqual({p["path"] for p in actual["files"]}, set(before))
        self.assertEqual(actual["results"], [])  # Discovery does not certify a run.
        self.assertEqual(before, {p.relative_to(self.workspace).as_posix(): p.read_bytes() for p in self.workspace.rglob("*") if p.is_file()})

    def test_resume_foreign_and_partial_context_preserves_notes_and_original_context(self):
        directory = self.workspace / ".coursework"
        directory.mkdir()
        note = directory / "my-notes.md"
        note.write_text("Keep my decisions and exact pending question.", encoding="utf-8")
        state = directory / "state.json"
        for content, status in [("{foreign", "unrecognized"),
                                ('{"schema_version": 1, "kind": "coursework-context", "request": "old broad scope", "questions": [{"text": "May I fix?"}]}', "incomplete")]:
            state.write_text(content, encoding="utf-8")
            actual = self.cli("resume")
            self.assertEqual(actual["context_status"], status)
            self.assertEqual(state.read_text(encoding="utf-8"), content)
            self.assertEqual(note.read_text(encoding="utf-8"), "Keep my decisions and exact pending question.")
            if status == "incomplete":
                self.assertEqual(actual["state"]["questions"][0]["text"], "May I fix?")
        self.assertFalse((self.workspace / ".git").exists())

    def test_check_only_and_advice_only_cannot_create_handoff_or_git(self):
        for scope in [{"goal": "验收", "authorized_behaviors": ["check"]},
                      {"goal": "只读组合检查", "authorized_behaviors": ["report", "check"], "read_only": True},
                      {"goal": "只给语言建议", "authorized_behaviors": ["report"], "report_mode": "review"}]:
            record = self.request()
            record["scope"] = scope
            self.cli("handoff", record, ok=False)
            self.assertFalse((self.workspace / ".coursework").exists())
            self.assertFalse((self.workspace / ".git").exists())


if __name__ == "__main__":
    unittest.main()
