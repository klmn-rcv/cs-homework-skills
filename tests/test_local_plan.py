"""Public workflow checks: actual materials, assignment directories and Git."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[1] / "skills/cs-homework/scripts/coursework.py"


class LocalPlanWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.materials = self.root / "materials"
        self.materials.mkdir()
        fixtures = Path(__file__).parent / "fixtures/local-plan"
        for name in ["brief.md", "interface.md"]:
            shutil.copyfile(fixtures / name, self.materials / name)

    def record(self):
        # Semantic reading is performed by the agent, not inferred by the helper.
        return {
            "assignment": {"title": "有向图最短路径"},
            "request": "只梳理要求和计划，先不要写代码或报告。保留当前项目。",
            "scope": {"goal": "保存可继续的实现与验证计划", "authorized_behaviors": ["plan"],
                      "deliverables": ["要求与计划"], "checkpoints": ["实现前查看计划"]},
            "sources": [
                {"id": "brief", "kind": "local", "path": str(self.materials / "brief.md")},
                {"id": "api", "kind": "local", "path": str(self.materials / "interface.md")},
                {"id": "chat", "kind": "chat", "content": "只规划；不生成报告。"},
            ],
            "requirements": [
                {"id": "R1", "category": "language", "text": "使用 Python 3",
                 "sources": [{"source_id": "brief", "locator": "第1行"}]},
                {"id": "R2", "category": "algorithm", "text": "使用广度优先搜索求最短路径",
                 "sources": [{"source_id": "brief", "locator": "第1行"}]},
                {"id": "R3", "category": "dependencies", "text": "不使用第三方图算法库",
                 "sources": [{"source_id": "brief", "locator": "第1行"}]},
                {"id": "R4", "category": "interface", "text": "shortest_path(edges, start, end)",
                 "sources": [{"source_id": "api", "locator": "第1行"}]},
                {"id": "R5", "category": "output", "text": "返回节点列表；不可达返回 []",
                 "sources": [{"source_id": "api", "locator": "第1行"}]},
                {"id": "R6", "category": "scope", "text": "本次只提供规划，不实现或写报告",
                 "sources": [{"source_id": "chat", "locator": "当前请求"}]},
            ],
            "decisions": [{"id": "D1", "text": "用户确认本次只规划", "status": "confirmed",
                           "sources": [{"source_id": "chat", "locator": "当前请求"}]}],
            "questions": [],
            "plan": {
                "implementation": [{"description": "按接口构建邻接表并用 BFS 记录前驱", "requirements": ["R1", "R2", "R3", "R4"]}],
                "validation": [{"description": "使用教师样例，核对 A 到 C 返回 [A,C]；另检查不可达与起终点相同", "requirements": ["R5"]}],
            },
            "next_steps": [{"behavior": "code", "description": "用户查看计划后再按授权实现和验证"}],
        }

    def cli(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(CLI), *map(str, args)],
                                capture_output=True, text=True, encoding="utf-8")
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def plan(self, workspace, record=None, *args):
        path = self.root / "input.json"
        path.write_text(json.dumps(record or self.record(), ensure_ascii=False), encoding="utf-8")
        return self.cli("plan", "--workspace", workspace, "--input", path, *args)

    def git(self, workspace, *args):
        result = subprocess.run(["git", "-C", str(workspace), *args], capture_output=True,
                                text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_plan_only_creates_resumable_sourced_plan_in_independent_directory(self):
        workspace = self.root / "图算法作业"
        self.plan(workspace, None, "--new")
        resumed = json.loads(self.cli("resume", "--workspace", workspace).stdout)
        state = resumed["state"]
        self.assertEqual(state["scope"]["authorized_behaviors"], ["plan"])
        self.assertEqual(state["scope"]["checkpoints"], ["实现前查看计划"])
        self.assertEqual([r["category"] for r in state["requirements"]],
                         ["language", "algorithm", "dependencies", "interface", "output", "scope"])
        self.assertEqual(state["requirements"][4]["sources"], [{"source_id": "api", "locator": "第1行"}])
        self.assertEqual(state["decisions"][0]["status"], "confirmed")
        self.assertEqual([m["status"] for m in resumed["materials"]], ["unchanged", "unchanged", "recorded"])
        self.assertTrue((workspace / ".coursework/plan.md").is_file())
        self.assertEqual(sorted(p.name for p in workspace.iterdir()), [".coursework", ".git"])
        self.assertEqual(self.git(workspace, "status", "--porcelain"), "")
        self.assertEqual(self.git(workspace, "log", "--format=%s"), "coursework: save plan revision 1")

    def test_existing_project_keeps_staged_and_unstaged_work_and_confirmed_decisions(self):
        workspace = self.root / "existing"
        workspace.mkdir()
        self.git(workspace, "init", "-q")
        code = workspace / "student.py"
        code.write_text("# baseline\n", encoding="utf-8")
        self.git(workspace, "add", "student.py")
        self.git(workspace, "-c", "user.name=Student", "-c", "user.email=student@example.invalid",
                 "commit", "-qm", "original work")
        original_head = self.git(workspace, "rev-parse", "HEAD")
        code.write_text("# staged student change\n", encoding="utf-8")
        self.git(workspace, "add", "student.py")
        code.write_text("# staged student change\n# unstaged student change\n", encoding="utf-8")
        notes = workspace / "private-notes.txt"
        notes.write_text("unfinished user notes", encoding="utf-8")
        staged_before = self.git(workspace, "diff", "--cached", "--binary")
        self.plan(workspace)
        revised = self.record()
        revised["request"] = "继续原来的计划，已确认的决定不用再问。"
        revised["decisions"] = []
        self.plan(workspace, revised)
        resumed = json.loads(self.cli("resume", "--workspace", workspace).stdout)
        self.assertEqual(resumed["state"]["revision"], 2)
        self.assertEqual(resumed["state"]["decisions"], self.record()["decisions"])
        self.assertEqual(self.git(workspace, "diff", "--cached", "--binary"), staged_before)
        self.assertEqual(code.read_text(encoding="utf-8"), "# staged student change\n# unstaged student change\n")
        self.assertEqual(notes.read_text(encoding="utf-8"), "unfinished user notes")
        self.assertEqual(self.git(workspace, "rev-parse", "HEAD~2"), original_head)
        committed = self.git(workspace, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD")
        self.assertTrue(all(path.startswith(".coursework/") for path in committed.splitlines()))
        self.assertTrue((workspace / ".coursework/history/0001.json").is_file())

    def test_user_edits_to_saved_plan_are_preserved_instead_of_overwritten(self):
        workspace = self.root / "assignment"
        self.plan(workspace)
        plan = workspace / ".coursework/plan.md"
        plan.write_text("学生补充的计划，不得覆盖。", encoding="utf-8")
        self.git(workspace, "add", ".coursework/plan.md")
        before_index = self.git(workspace, "diff", "--cached", "--binary")
        before_head = self.git(workspace, "rev-parse", "HEAD")
        path = self.root / "input.json"
        result = self.cli("plan", "--workspace", workspace, "--input", path, ok=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(plan.read_text(encoding="utf-8"), "学生补充的计划，不得覆盖。")
        self.assertEqual(self.git(workspace, "diff", "--cached", "--binary"), before_index)
        self.assertEqual(self.git(workspace, "rev-parse", "HEAD"), before_head)
        self.assertEqual(json.loads(self.cli("resume", "--workspace", workspace).stdout)["state"]["revision"], 1)

    def test_resume_reports_changed_and_missing_materials_before_reusing_the_plan(self):
        workspace = self.root / "assignment"
        self.plan(workspace)
        (self.materials / "brief.md").write_text("课程更新：必须使用 C++。", encoding="utf-8")
        (self.materials / "interface.md").unlink()
        resumed = json.loads(self.cli("resume", "--workspace", workspace).stdout)
        self.assertEqual([item["status"] for item in resumed["materials"]], ["changed", "missing", "recorded"])
        self.assertTrue(resumed["needs_review"])
        self.assertEqual(resumed["state"]["requirements"][0]["text"], "使用 Python 3")
        self.assertEqual(resumed["state"]["revision"], 1)
        self.assertEqual(self.git(workspace, "status", "--porcelain"), "")

    def test_conflicting_sources_preserve_a_specific_blocking_question_and_independent_plan(self):
        workspace = self.root / "assignment"
        with (self.materials / "interface.md").open("a", encoding="utf-8") as stream:
            stream.write("评分补充：必须使用 Dijkstra 算法。\n")
        record = self.record()
        record["questions"] = [{
            "id": "Q1", "blocking": True,
            "text": "任务说明要求 BFS，评分补充却要求 Dijkstra；应以哪一条算法要求为准？",
            "facts_checked": "已经检查两份完整本地材料，没有给出优先级或适用题号。",
            "sources": [{"source_id": "brief", "locator": "第1行"},
                        {"source_id": "api", "locator": "第3行"}],
        }]
        record["next_steps"] = [{"behavior": "plan", "description": "先确认算法冲突；独立整理接口和已知样例"}]
        self.plan(workspace, record)
        resumed = json.loads(self.cli("resume", "--workspace", workspace).stdout)
        self.assertEqual(resumed["blocking_questions"], record["questions"])
        self.assertEqual(resumed["state"]["plan"]["validation"], record["plan"]["validation"])
        self.assertEqual(resumed["state"]["scope"]["authorized_behaviors"], ["plan"])

    def test_invalid_plan_is_rejected_before_creating_an_assignment(self):
        workspace = self.root / "assignment"
        record = self.record()
        record["next_steps"] = [{"description": "This step omitted the behavior"}]
        path = self.root / "invalid-input.json"
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        result = self.cli("plan", "--workspace", workspace, "--input", path, ok=False)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(workspace.exists())


if __name__ == "__main__":
    unittest.main()
