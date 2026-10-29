"""Report handoff through the CLI: actual files, compilation and provenance."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / "skills/cs-homework/scripts/coursework.py"


class ReportWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "assignment"
        self.workspace.mkdir()
        self.stage = self.root / "draft.tex"
        self.stage.write_text(r"\documentclass{article}\begin{document}Known report.\end{document}", encoding="utf-8")
        self.brief = self.workspace / "brief.md"
        self.brief.write_text("Explain the existing method. Source only.\n", encoding="utf-8")

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

    def request(self):
        return {"assignment": {"title": "Existing method report"}, "request": "Write the report source only.",
                "scope": {"goal": "Editable report source", "authorized_behaviors": ["report"]},
                "report_key": "coursework", "source_only": True,
                "main_file": "main.tex", "files": [{"source": str(self.stage), "path": "main.tex"}],
                "source_paths": ["brief.md"], "result_ids": [], "artifact_ids": [], "analysis_ids": [],
                "content_review": {"requirement_map": [{"requirement": "Explain method", "source": "brief.md:1", "location": "main.tex"}],
                                   "structure_basis": "Brief asks for method explanation; no fixed outline",
                                   "format_basis": "No format reference; ordinary article layout",
                                   "technical_review": "Read existing materials; no numerical claims",
                                   "voice_review": "Objective student prose; no invented experience",
                                   "thoughts_basis": "No personal reflection required by this short source-only task"}}

    def test_direct_source_only_report_preserves_user_index_and_needs_no_prior_stages(self):
        self.cli_git("init", "-q")
        self.cli_git("add", "brief.md")
        staged = self.cli_git("diff", "--cached", "--binary")
        self.brief.write_text("Explain the method; student's unstaged clarification.\n", encoding="utf-8")
        actual = self.call("report", self.request())
        report = actual["report"]
        self.assertEqual(report["status"], "source_only")
        self.assertEqual((self.workspace / report["project"] / "main.tex").read_bytes(), self.stage.read_bytes())
        self.assertNotIn("plan", actual["state"])
        self.assertEqual(actual["state"].get("runs", []), [])
        self.assertEqual(actual["state"].get("analyses", []), [])
        self.assertEqual(self.cli_git("diff", "--cached", "--binary"), staged)
        self.assertIn("student's unstaged", self.brief.read_text())
        self.assertNotIn("brief.md", self.cli_git("show", "--pretty=", "--name-only", "HEAD").decode().splitlines())
        self.assertEqual(actual["reports"][0]["status"], "source_only")

    def cli_git(self, *args):
        actual = subprocess.run(["git", "-C", str(self.workspace), *args], capture_output=True)
        self.assertEqual(actual.returncode, 0, actual.stderr)
        return actual.stdout

    def test_missing_compiler_retains_source_and_diagnostic_without_accepting_an_old_pdf(self):
        (self.workspace / "old.pdf").write_bytes(b"not a current compiled report")
        request = {**self.request(), "source_only": False,
                   "compiler": {"engine": "tectonic", "executable": "coursework-missing-compiler"}}
        actual = self.call("report", request)
        report = actual["report"]
        self.assertEqual(report["status"], "failed")
        self.assertIsNone(report["compilation"][0]["exit_code"])
        self.assertIn("Executable unavailable", report["compilation"][0]["diagnostic"])
        self.assertEqual(actual["reports"][0]["status"], "failed")
        self.assertTrue((self.workspace / report["project"] / "main.tex").is_file())
        self.assertNotIn("pdf", report)

    def compiled_request(self):
        return {**self.request(), "source_only": False,
                "compiler": {"engine": "tectonic", "executable": os.environ["COURSEWORK_TEST_TECTONIC"], "args": ["--only-cached"]},
                "renderer": {"executable": os.environ["COURSEWORK_TEST_PDFTOPPM"], "dpi": 90}}

    @unittest.skipUnless(os.environ.get("COURSEWORK_TEST_TECTONIC") and os.environ.get("COURSEWORK_TEST_PDFTOPPM"), "Real LaTeX/Poppler paths not supplied")
    def test_real_latex_requires_page_and_content_review_then_invalidates_when_a_source_changes(self):
        self.stage.write_text(r"\documentclass{article}\begin{document}\section{Method}\label{sec:m}See Section~\ref{sec:m}. The known sum is 6.\end{document}", encoding="utf-8")
        actual = self.call("report", self.compiled_request())
        report = actual["report"]
        self.assertEqual(report["status"], "awaiting_review")
        self.assertEqual(report["compilation"][-1]["exit_code"], 0)
        self.assertTrue((self.workspace / report["pdf"]["path"]).read_bytes().startswith(b"%PDF-"))
        self.assertEqual(len(report["pages"]), 1)
        checks = {field: {"status": "passed", "basis": "Known one-page method fixture independently checked"}
                  for field in ["technical", "numerical", "structure", "voice", "visual"]}
        request = {**self.request(), "report_id": report["id"], "checks": checks}
        missing = self.call("review-report", request, ok=False)
        self.assertEqual(missing.returncode, 2)
        checks["visual"]["pages"] = [p["path"] for p in report["pages"]]
        reviewed = self.call("review-report", request)
        self.assertEqual(reviewed["reports"][0]["status"], "valid")
        self.brief.write_text("Now require a different method.\n", encoding="utf-8")
        resumed = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(resumed["reports"][0]["status"], "pending_update")

    @unittest.skipUnless(os.environ.get("COURSEWORK_TEST_TECTONIC") and os.environ.get("COURSEWORK_TEST_PDFTOPPM"), "Real LaTeX/Poppler paths not supplied")
    def test_actual_undefined_reference_and_compile_error_retain_diagnostics_and_fail(self):
        self.stage.write_text(r"\documentclass{article}\begin{document}See Section~\ref{missing:actual}.\end{document}", encoding="utf-8")
        undefined = self.call("report", self.compiled_request())["report"]
        self.assertEqual(undefined["status"], "failed")
        self.assertTrue(undefined["diagnostics"]["undefined_reference"])
        self.assertNotIn("pdf", undefined)
        self.stage.write_text(r"\documentclass{article}\begin{document}\ThisCommandDoesNotExist\end{document}", encoding="utf-8")
        broken = self.call("report", self.compiled_request())["report"]
        self.assertEqual(broken["status"], "failed")
        self.assertNotEqual(broken["compilation"][-1]["exit_code"], 0)
        self.assertTrue((self.workspace / broken["project"] / "main.tex").is_file())

    def test_selected_analysis_damage_and_replaced_result_propagate_to_report_validity(self):
        data = self.workspace / "counts.csv"
        data.write_text("n,count\n3,6\n", encoding="utf-8")
        external = {**self.request(), "result_key": "counts", "data_paths": ["counts.csv"],
                    "provenance": {"provided_by": "user", "location": "counts.csv", "description": "Earlier output, generating execution unverified"}}
        result = self.call("import-result", external)["result"]
        script = self.root / "analysis.py"
        script.write_text("import sys\nfrom pathlib import Path\n(Path(sys.argv[2])/'summary.md').write_text('The supplied row has count 6; external execution unverified.')\n", encoding="utf-8")
        analysis = self.call("analyze", {**self.request(), "analysis_key": "counts",
                  "inputs": [{"result_id": result["id"], "path": result["data"][0]["snapshot_path"]}],
                  "assessment": {"goal": "Explain the row", "completeness": "One row", "units": "count", "anomalies": "No missing cells", "limitations": "External execution unverified"},
                  "computation": {"python": sys.executable, "script": str(script), "basis": "Read supplied row", "products": [{"path": "summary.md", "kind": "analysis"}]}})["analysis"]
        request = {**self.request(), "result_ids": [result["id"]], "analysis_ids": [analysis["id"]],
                   "artifact_ids": [analysis["products"][0]["artifact_id"]]}
        wrong_asset = {**request, "files": [*request["files"], {"source": str(self.brief), "path": "assets/summary.md",
                                                              "artifact_id": analysis["products"][0]["artifact_id"]}]}
        rejected = self.call("report", wrong_asset, ok=False)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("exact selected current artifact bytes", rejected.stderr)
        actual = self.call("report", request)
        self.assertEqual(actual["report"]["result_sources"][0]["verification"]["status"], "unverified")
        (self.workspace / analysis["script"]["path"]).write_text("# damaged computation")
        resumed = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(resumed["reports"][0]["status"], "pending_update")
        rejected = self.call("report", request, ok=False)
        self.assertEqual(rejected.returncode, 2)
        data.write_text("n,count\n3,7\n", encoding="utf-8")
        self.call("import-result", external)
        final = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(final["reports"][0]["status"], "pending_update")

    def test_report_can_supplement_missing_output_from_existing_code_without_implementation_scope(self):
        program = self.workspace / "known.py"
        program.write_text("print(6)\n", encoding="utf-8")
        request = {**self.request(), "execution": {"argv": [sys.executable, "known.py"], "source_paths": ["known.py"],
                   "purposes": ["example"], "basis": "Missing required example for the report",
                   "report_support": {"basis": "Existing program, exact required example; no implementation edit or extra experiment"},
                   "dependency_coverage": {"status": "complete", "note": "Single literal-output program"},
                   "expected": {"stdout": "6" + os.linesep, "basis": "Known literal answer"}}}
        actual = self.call("run", request)
        self.assertEqual(actual["run"]["execution"]["check"]["status"], "passed")
        self.assertEqual(program.read_text(), "print(6)\n")
        report = self.call("report", {**self.request(), "result_ids": [actual["result"]["id"]]})["report"]
        requested = {**actual["result"]["specification"], "parameters": {"new_condition": True}}
        inspected = self.call("results", {"scope": self.request()["scope"],
                              "requested_results": [{"key": actual["result"]["key"], "specification": requested}]})
        self.assertEqual(next(r for r in inspected["reports"] if r["id"] == report["id"])["status"], "pending_update")
        self.assertEqual(inspected["results"][0]["update_action"], "prepare_targeted_run_and_check_budget")
        resumed = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(resumed["reports"][0]["status"], "source_only")


if __name__ == "__main__":
    unittest.main()
