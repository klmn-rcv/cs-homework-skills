"""Analysis through the student-facing CLI, actual data and produced artifacts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[1] / "skills/cs-homework/scripts/coursework.py"
SCRIPT = '''import csv, json, sys
from pathlib import Path
m = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out = Path(sys.argv[2])
rows = list(csv.DictReader(Path(m["inputs"][0]["path"]).open(encoding="utf-8", newline="")))
values = [float(r["elapsed_ms"]) for r in rows]
if not values or any(v < 0 for v in values): raise ValueError("Expected nonnegative elapsed_ms")
metrics = {"count": len(values), "total_ms": sum(values), "mean_ms": sum(values)/len(values)}
(out/"metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
(out/"table.csv").write_text("metric,value,unit\\nmean,"+str(metrics["mean_ms"])+",ms\\n", encoding="utf-8")
(out/"analysis.md").write_text("Observed "+str(metrics["count"])+" rows; mean "+str(metrics["mean_ms"])+" ms. Supplied external measurements, generating execution unverified. No causal or general performance conclusion.", encoding="utf-8")
'''


class AnalysisWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "assignment"
        self.workspace.mkdir()
        self.data = self.root / "measurements.csv"
        self.data.write_text("n,elapsed_ms\n1,2\n2,4\n3,6\n", encoding="utf-8")
        self.script = self.root / "compute.py"
        self.script.write_text(SCRIPT, encoding="utf-8")

    def cli(self, *args, ok=True):
        actual = subprocess.run([sys.executable, "-B", str(CLI), *map(str, args)],
                                capture_output=True, text=True, encoding="utf-8")
        if not ok:
            return actual
        self.assertEqual(actual.returncode, 0, actual.stderr)
        return json.loads(actual.stdout)

    def call(self, command, record, ok=True):
        path = self.root / "request.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        return self.cli(command, "--workspace", self.workspace, "--input", path, ok=ok)

    def context(self):
        return {"assignment": {"title": "Existing data analysis"},
                "request": "Analyze supplied measurements only; do not rerun or edit the program.",
                "scope": {"goal": "Numerical analysis and explanation", "authorized_behaviors": ["analyze"]}}

    def imported(self, key="measurements", data=None):
        return self.call("import-result", {**self.context(), "result_key": key,
                         "data_paths": [str(data or self.data)], "provenance": {
                             "provided_by": "user", "location": str(data or self.data),
                             "description": "Earlier measurements; command/source unavailable"}})["result"]

    def request(self, result, key="timing"):
        return {**self.context(), "analysis_key": key,
                "inputs": [{"result_id": result["id"], "path": result["data"][0]["snapshot_path"]}],
                "assessment": {"goal": "Describe these supplied rows, not algorithm complexity",
                               "completeness": "Three rows with n and elapsed_ms; no repetitions or machine conditions",
                               "units": "elapsed_ms in milliseconds, n dimensionless",
                               "anomalies": "No missing or negative values in these three rows",
                               "limitations": "External generating process unverified; no causal or population claim"},
                "computation": {"python": sys.executable, "script": str(self.script),
                                "parameters": {}, "basis": "Arithmetic over the captured CSV only",
                                "products": [{"path": "metrics.json", "kind": "metrics"},
                                             {"path": "table.csv", "kind": "table"},
                                             {"path": "analysis.md", "kind": "analysis"}]}}

    def test_existing_external_data_can_be_analyzed_directly_with_shared_metrics_and_provenance(self):
        result = self.imported()
        actual = self.call("analyze", self.request(result))
        analysis = actual["analysis"]
        self.assertEqual(analysis["status"], "completed")
        products = {p["kind"]: self.workspace / p["path"] for p in analysis["products"]}
        metrics = json.loads(products["metrics"].read_text())
        self.assertEqual(metrics, {"count": 3, "total_ms": 12.0, "mean_ms": 4.0})
        self.assertIn("mean,4.0,ms", products["table"].read_text())
        self.assertIn("mean 4.0 ms", products["analysis"].read_text())
        self.assertIn("unverified", products["analysis"].read_text())
        self.assertEqual(actual["state"].get("runs", []), [])
        self.assertNotIn("plan", actual["state"])
        self.assertEqual(analysis["inputs"][0]["verification"]["status"], "unverified")
        self.assertEqual(analysis["execution"]["exit_code"], 0)
        self.assertTrue(all(a["status"] == "valid" for a in actual["artifacts"]))
        self.assertTrue(all(a["result_ids"] == [result["id"]] for a in actual["artifacts"]))
        self.assertEqual(self.data.read_text(), "n,elapsed_ms\n1,2\n2,4\n3,6\n")

    def test_current_report_advice_cannot_execute_analysis_or_change_assignment(self):
        result = self.imported()  # Prior analysis authorization is history, not current permission.
        request = self.request(result)
        request.update(request="Only review my report and give advice; do not change or execute anything.",
                       scope={"goal": "Report advice", "authorized_behaviors": ["report"],
                              "report_mode": "review"})
        before = {p.relative_to(self.workspace).as_posix(): p.read_bytes()
                  for p in self.workspace.rglob("*") if p.is_file()}
        directories = sorted(str(p.relative_to(self.workspace)) for p in self.workspace.rglob("*") if p.is_dir())
        actual = self.call("analyze", request, ok=False)
        self.assertEqual(actual.returncode, 2, actual.stdout)
        self.assertEqual(before, {p.relative_to(self.workspace).as_posix(): p.read_bytes()
                                 for p in self.workspace.rglob("*") if p.is_file()})
        self.assertEqual(directories, sorted(str(p.relative_to(self.workspace))
                         for p in self.workspace.rglob("*") if p.is_dir()))

    def test_readonly_result_import_keeps_existing_git_and_acceptance_bytes(self):
        self.imported()
        (self.workspace / "student.txt").write_text("staged student work", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.workspace), "add", "student.txt"], check=True)
        (self.workspace / ".coursework" / "acceptance.json").write_text("existing acceptance", encoding="utf-8")
        for scope in [
            {"authorized_behaviors": ["check"]},
            {"authorized_behaviors": ["analyze", "report", "run", "code", "plan", "check"], "read_only": True},
            {"authorized_behaviors": ["report", "analyze"], "report_mode": "review"},
        ]:
            with self.subTest(scope=scope):
                before = {str(p.relative_to(self.workspace)): p.read_bytes()
                          for p in self.workspace.rglob("*") if p.is_file()}
                request = {**self.context(), "request": "Inspect existing evidence only",
                           "scope": {"goal": "Read existing evidence", **scope},
                           "result_key": "forbidden", "data_paths": [str(self.data)],
                           "provenance": {"provided_by": "user", "location": str(self.data),
                                          "description": "Existing measurements"}}
                actual = self.call("import-result", request, ok=False)
                self.assertEqual(actual.returncode, 2)
                self.assertEqual(before, {str(p.relative_to(self.workspace)): p.read_bytes()
                                         for p in self.workspace.rglob("*") if p.is_file()})

    def test_changed_one_data_group_updates_its_analysis_only_and_retains_history(self):
        first = self.imported()
        a = self.call("analyze", self.request(first))["analysis"]
        other = self.root / "other.csv"
        other.write_text("n,elapsed_ms\n1,10\n2,20\n", encoding="utf-8")
        second = self.imported("other", other)
        b = self.call("analyze", self.request(second, "other"))["analysis"]
        b_before = {p["path"]: (self.workspace / p["path"]).read_bytes() for p in b["products"]}
        self.data.write_text("n,elapsed_ms\n1,4\n2,8\n", encoding="utf-8")
        stale = self.call("analyze", self.request(first), ok=False)
        self.assertEqual(stale.returncode, 2)
        self.assertIn("current valid", json.loads(stale.stderr)["error"])
        refreshed = self.imported()
        final = self.call("analyze", self.request(refreshed))
        self.assertNotEqual(final["analysis"]["id"], a["id"])
        metrics = next(p for p in final["analysis"]["products"] if p["kind"] == "metrics")
        self.assertEqual(json.loads((self.workspace / metrics["path"]).read_text())["mean_ms"], 6.0)
        old_metrics = next(p for p in a["products"] if p["kind"] == "metrics")
        self.assertEqual(json.loads((self.workspace / old_metrics["path"]).read_text())["mean_ms"], 4.0)
        self.assertEqual(final["state"]["analysis_heads"]["other"], b["id"])
        for path, data in b_before.items():
            self.assertEqual((self.workspace / path).read_bytes(), data)
        self.assertFalse(final["needs_review"])
        previous_ids = {p["artifact_id"] for p in a["products"]}
        self.assertTrue(all(not p["current"] for p in final["artifacts"] if p["id"] in previous_ids))
        self.assertEqual(len(final["state"]["analyses"]), 3)

    def test_analysis_failure_is_recorded_and_tampered_computation_needs_review(self):
        result = self.imported()
        actual = self.call("analyze", self.request(result))
        (self.workspace / actual["analysis"]["script"]["path"]).write_text("# replaced", encoding="utf-8")
        checked = self.cli("resume", "--workspace", self.workspace)
        self.assertTrue(checked["needs_review"])
        self.assertEqual(checked["analyses"][0]["status"], "pending_update")
        self.assertTrue(all(a["status"] == "pending_update" for a in checked["artifacts"]))
        self.script.write_text("raise ValueError('Missing elapsed_ms values; no imputation allowed')", encoding="utf-8")
        failed = self.call("analyze", self.request(result, "missing-data"))
        self.assertEqual(failed["analysis"]["status"], "failed")
        self.assertNotEqual(failed["analysis"]["execution"]["exit_code"], 0)
        self.assertIn("Missing elapsed_ms", failed["analysis"]["execution"]["stderr"]["text"])
        self.assertEqual(failed["analysis"]["products"], [])
        self.assertEqual(failed["state"].get("runs", []), [])

    def test_analysis_commits_its_new_outputs_and_preserves_student_staging_and_code(self):
        result = self.imported()
        student = self.workspace / "solution.py"
        student.write_text("print('student baseline')\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.workspace), "add", "solution.py"], check=True, capture_output=True)
        staged = subprocess.run(["git", "-C", str(self.workspace), "diff", "--cached", "--binary"], check=True, capture_output=True).stdout
        student.write_text("print('student unstaged edit')\n", encoding="utf-8")
        actual = self.call("analyze", self.request(result))
        self.assertEqual(student.read_text(), "print('student unstaged edit')\n")
        final_staged = subprocess.run(["git", "-C", str(self.workspace), "diff", "--cached", "--binary"], check=True, capture_output=True).stdout
        self.assertEqual(final_staged, staged)
        committed = subprocess.run(["git", "-C", str(self.workspace), "show", "--pretty=", "--name-only", "HEAD"], check=True, capture_output=True, text=True).stdout
        for product in actual["analysis"]["products"]:
            self.assertIn(product["path"], committed)
        self.assertNotIn("solution.py", committed)

    def test_read_only_scope_and_unrelated_files_cannot_be_used_as_analysis_sources(self):
        result = self.imported()
        before = self.cli("resume", "--workspace", self.workspace)["state"]["revision"]
        request = self.request(result)
        request["scope"]["authorized_behaviors"] = ["check"]
        rejected = self.call("analyze", request, ok=False)
        self.assertEqual(rejected.returncode, 2)
        request = self.request(result)
        request["inputs"][0]["path"] = str(self.data)
        rejected = self.call("analyze", request, ok=False)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("captured evidence", json.loads(rejected.stderr)["error"])
        after = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(after["state"]["revision"], before)
        self.assertEqual(after["state"].get("analyses", []), [])

    def test_workflow_stdout_is_analyzed_without_importing_or_reexecuting_the_program(self):
        program = self.workspace / "examples.py"
        program.write_text("print('n,elapsed_ms\\n1,2\\n2,4\\n3,6')\n", encoding="utf-8")
        record = {**self.context(), "result_key": "existing-example",
                  "scope": {"goal": "Run the known arithmetic fixture", "authorized_behaviors": ["run"]},
                  "execution": {"argv": [sys.executable, "examples.py"], "source_paths": ["examples.py"],
                                "purposes": ["example"], "basis": "Known literal CSV fixture, not measured performance",
                                "dependency_coverage": {"status": "complete", "note": "This literal-output program reads no files"},
                                "expected": {"stdout": "n,elapsed_ms\n1,2\n2,4\n3,6\n".replace("\n", os.linesep),
                                             "basis": "Fixed known CSV rows"}}}
        run = self.call("run", record)
        request = self.request({**run["result"], "data": [{"snapshot_path": run["run"]["execution"]["stdout"]["path"]}]})
        actual = self.call("analyze", request)
        self.assertEqual(actual["analysis"]["inputs"][0]["origin"], "workflow-run")
        self.assertEqual(actual["analysis"]["inputs"][0]["verification"]["status"], "passed")
        self.assertEqual(len(actual["state"]["runs"]), 1)
        self.assertEqual(len(actual["state"]["results"]), 1)
        metrics = next(p for p in actual["analysis"]["products"] if p["kind"] == "metrics")
        self.assertEqual(json.loads((self.workspace / metrics["path"]).read_text())["mean_ms"], 4.0)
        intended = {**run["result"]["specification"], "parameters": {"requested_group": "different"}}
        inspected = self.call("results", {"scope": {"authorized_behaviors": ["analyze"]},
                              "requested_results": [{"key": "existing-example", "specification": intended}]})
        self.assertEqual(inspected["analyses"][0]["status"], "pending_update")
        self.assertTrue(all(p["status"] == "pending_update" for p in inspected["artifacts"]))
        unchanged = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(unchanged["analyses"][0]["status"], "valid")
        self.assertEqual(len(unchanged["state"]["runs"]), 1)


if __name__ == "__main__":
    unittest.main()
