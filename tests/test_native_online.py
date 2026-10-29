"""Native-note compatibility and historical results through the public CLI.

These authored fixtures test persistence/inspection, not an assertion that a browser read occurred.
Actual Agent reading is validated separately with a fresh-context task.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

import test_results_workflow as fixtures


class NativeOnlineWorkflow(unittest.TestCase):
    setUp = fixtures.ResultsWorkflow.setUp
    cli = fixtures.ResultsWorkflow.cli
    input = fixtures.ResultsWorkflow.input
    request = fixtures.ResultsWorkflow.request
    run_result = fixtures.ResultsWorkflow.run_result
    def plan_record(self, *, legacy=False):
        source = {"id": "brief", "kind": "online", "url": "https://docs.python.org/3/library/functions.html#sum",
                  "purpose": "function contract", "reading": {"status": "read", "read_at": "2026-10-26T10:00:00+08:00",
                  "note": "Fixture: sum(iterable, start=0) section; other sections not used."}}
        if legacy:
            directory = self.root / "legacy"
            directory.mkdir(exist_ok=True)
            body = b"Archived fixture: sum integers.\n"
            digest = hashlib.sha256(body).hexdigest()
            (directory / "body.bin").write_bytes(body)
            (directory / "content.txt").write_bytes(body)
            receipt = {"schema_version": 1, "kind": "online-material-receipt", "url": source["url"],
                       "method": "tool", "tool": "fixture", "tool_receipt": "synthetic-test-only",
                       "access_status": "fetched", "retrieved_at": "2026-10-25T10:00:00Z", "body_path": "body.bin",
                       "text_path": "content.txt", "body_sha256": digest, "text_sha256": digest, "size_bytes": len(body)}
            (directory / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            source["receipt"] = str(directory / "receipt.json")
            source["reading"]["content_sha256"] = digest
        return {"assignment": {"title": "Sum"}, "request": "Plan integer sum only.",
                "scope": {"goal": "Sourced plan", "authorized_behaviors": ["plan"]}, "sources": [source],
                "requirements": [{"id": "R1", "text": "Sum the supplied integers", "sources": [{"source_id": "brief", "locator": "sum section"}]}],
                "plan": {"implementation": [], "validation": []}, "next_steps": []}

    def save_plan(self, record):
        return self.cli("plan", "--workspace", self.workspace, "--input", self.input(record))

    def test_notes_need_no_snapshot_or_receipt_and_results_survive_unvisited_remote(self):
        record = self.plan_record()
        planned = self.save_plan(record)
        self.assertFalse((self.workspace / ".coursework/materials").exists())
        self.assertIn("sum section", (self.workspace / ".coursework/plan.md").read_text(encoding="utf-8"))
        request = self.request()
        request["execution"]["material_ids"] = ["brief"]
        first = self.run_result(request)
        resumed = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(resumed["materials"][0]["freshness"], "not_revisited")
        self.assertEqual(resumed["results"][0]["status"], "valid")
        self.assertFalse(resumed["needs_review"])
        self.assertTrue(self.run_result(request)["reused"])
        self.assertEqual((self.workspace / "executions.txt").read_text(), "a.txt\n")

    def test_legacy_snapshot_stays_readable_without_network_and_damage_is_not_verified(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        visits = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                visits.append(self.path)
                self.send_response(403)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        record = self.plan_record(legacy=True)
        source = record["sources"][0]
        source["url"] = f"http://127.0.0.1:{server.server_port}/protected"
        path = Path(source["receipt"])
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["url"] = source["url"]
        receipt["method"] = "http"
        path.write_text(json.dumps(receipt), encoding="utf-8")
        planned = self.save_plan(record)
        source = planned["state"]["sources"][0]
        cached = self.workspace / source["receipt"]
        original = cached.read_bytes()
        request = self.request()
        request["execution"]["material_ids"] = ["brief"]
        first = self.run_result(request)
        for command in ["resume", "results"]:
            view = self.cli(command, "--workspace", self.workspace)
            self.assertEqual(view["results"][0]["status"], "valid")
            self.assertEqual(view["materials"][0]["freshness"], "not_revisited")
            self.assertEqual(view["materials"][0]["cache_status"], "verified")
        self.assertTrue(self.run_result(request)["reused"])
        self.assertEqual(visits, [], "A query/reuse must not request even legacy HTTP sources")
        self.assertEqual(cached.read_bytes(), original)
        (cached.parent / "body.bin").write_bytes(b"damaged")
        damaged = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(damaged["materials"][0]["cache_status"], "damaged")
        self.assertEqual(damaged["materials"][0]["freshness"], "not_revisited")
        self.assertEqual(damaged["results"][0]["status"], "needs_review")
        self.assertEqual(visits, [])

    def test_legacy_browser_result_no_longer_deadlocks_on_not_revisited(self):
        self.save_plan(self.plan_record(legacy=True))
        request = self.request()
        request["execution"]["material_ids"] = ["brief"]
        first = self.run_result(request)
        resumed = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(resumed["results"][0]["status"], "valid")
        self.assertEqual(resumed["materials"][0]["freshness"], "not_revisited")
        self.assertTrue(self.run_result(request)["reused"])
        self.assertEqual((self.workspace / "executions.txt").read_text(), "a.txt\n")

    def test_actual_requirement_change_affects_related_result_but_not_other_output(self):
        record = self.plan_record()
        self.save_plan(record)
        request = self.request()
        request["execution"]["material_ids"] = ["brief"]
        first = self.run_result(request)
        independent = self.run_result(self.request("b", "30"))
        record["sources"][0]["reading"]["read_at"] = "2026-10-26T11:00:00+08:00"
        self.save_plan(record)
        same = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(same["results"][0]["status"], "valid", "A reread timestamp is not changed requirements")
        record["requirements"][0]["text"] = "Sum integers and add a required initial value of 10"
        self.save_plan(record)
        changed = self.cli("resume", "--workspace", self.workspace)
        by_id = {r["id"]: r for r in changed["results"]}
        self.assertEqual(by_id[first["result"]["id"]]["status"], "needs_review")
        self.assertEqual(by_id[independent["result"]["id"]]["status"], "valid")
        self.assertEqual((self.workspace / "executions.txt").read_text(), "a.txt\nb.txt\n")
        stdout = self.workspace / independent["run"]["execution"]["stdout"]["path"]
        stdout.write_text("not the original output", encoding="utf-8")
        damaged = self.cli("results", "--workspace", self.workspace)
        by_id = {r["id"]: r for r in damaged["results"]}
        self.assertEqual(by_id[independent["result"]["id"]]["status"], "pending_update")
        self.assertIn("evidence", [issue["kind"] for issue in by_id[independent["result"]["id"]]["issues"]])

    def test_incomplete_historical_reading_is_not_upgraded_to_verified(self):
        self.save_plan(self.plan_record())
        request = self.request()
        request["execution"]["material_ids"] = ["brief"]
        self.run_result(request)
        path = self.workspace / ".coursework/state.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["sources"][0]["reading"] = {"status": "read"}
        path.write_text(json.dumps(state), encoding="utf-8")
        view = self.cli("resume", "--workspace", self.workspace)
        self.assertEqual(view["materials"][0]["status"], "unread")
        self.assertEqual(view["results"][0]["status"], "needs_review")

    def test_unread_notes_cannot_supply_requirements_but_independent_plan_can_continue(self):
        record = self.plan_record()
        record["sources"][0]["reading"] = {"status": "unread", "read_at": "2026-10-26T11:00:00+08:00", "note": "Fixture: login wall, no assignment body visible"}
        rejected = self.cli("plan", "--workspace", self.workspace, "--input", self.input(record), ok=False)
        self.assertEqual(rejected.returncode, 2)
        self.assertFalse((self.workspace / ".coursework").exists())
        record["requirements"] = []
        record["questions"] = [{"id": "Q1", "text": "Please provide the inaccessible rubric", "sources": [{"source_id": "brief", "locator": "login wall"}]}]
        view = self.save_plan(record)
        self.assertEqual(view["materials"][0]["status"], "unread")
        self.assertTrue(view["needs_review"])
        self.assertEqual(len(view["blocking_questions"]), 1)


if __name__ == "__main__":
    unittest.main()
