# Optional read-only acceptance fact assistant

Default acceptance uses ordinary requirements, actual files, existing logs and a readable per-requirement assessment in chat. No state, IDs, import or semantic-review API is required. Select this helper only when its file/record identity checks are useful. The agent reads requirements and actual content, chooses relevant items, and supplies semantic assessments. This small helper checks explicit evidence identity and saved currentness. It never runs a program, compiler or model, creates directories, writes state/history/reviews, invokes Git, or repairs anything. It may be used with no saved context or repository.

```text
python <cs-homework>/scripts/coursework.py check --workspace <existing-assignment> --input <outside-assessment.json>
```

Prepare internal JSON **outside the assignment**; students provide ordinary requests. Stdout is the inspection, not a persisted acceptance receipt. Return it in chat or, only when already authorized by a separate mutating task, preserve the useful diagnosis in that task's normal handoff. `review-report` writes records and is not a substitute for this command.

The following scope/JSON protocol applies only when deliberately selecting legacy structured helpers. Ordinary necessary checks may instead use normal tools or capture-run with the same real evidence and budget. The command's read-only contract is distinct from the overall acceptance goal. An ordinary request such as “验收，不修实现” can include targeted necessary checks when valid evidence is missing, changed or doubtful. First inspect the actual gap; record the overall current scope with `authorized_behaviors: ["check", "run"]` only for the justified execution needed to resolve it, then call the existing `run` interface with unchanged request/scope, independent expected values, actual dependency coverage and a specific `execution.basis`. Reuse valid evidence and preserve implementation/report originals. The normal trial/budget rules apply; no extra experiments or repair authorization follow from acceptance. A necessary compile/render check uses existing tools and isolated outputs, recording actual diagnostics/pages without editing report sources. Explicit read-only, no-run or existing-evidence-only requests keep check-only scope and missing proof unverified; they do not gain execution from this route. `check` itself remains read-only even when the overall scope contains `run`.

```json
{
  "request": "Check the existing code and report source only; do not run or change anything.",
  "scope": {"goal": "Code and report-source acceptance", "authorized_behaviors": ["check"]},
  "items": [{
    "id": "R1-method", "requirement": "brief.md:3 requires a handwritten prefix-sum interface",
    "status": "passed",
    "basis": "Read solution.py:5-15: builds initial zero then accumulates values; query subtracts prefixes. No forbidden dependency is imported.",
    "evidence": [{"kind": "file", "path": "solution.py", "sha256": "<actually-read-sha256>", "note": "Actual interface, algorithm and imports inspected"}],
    "missing": [], "affected_scope": ["solution.py"]
  }, {
    "id": "R2-behavior", "requirement": "brief.md:5 teacher queries return 20/10/0",
    "status": "passed", "basis": "Read captured input, expected answers and stdout; all three answers agree with independent arithmetic.",
    "evidence": [{"kind": "result", "id": "<exact-current-result-id>", "require_verified": true, "note": "Inspected actual input, expected, stdout and check outcome"}],
    "missing": [], "affected_scope": ["required-prefix-example", "report results"], "route": "code"
  }]
}
```

Use all relevant requirements, not only this example. An empty `items` list permits fact gathering before assessment and returns `unverified`, never success. Each item needs a unique ID, requirement locator/description, status, concrete basis, `evidence`, `missing` and `affected_scope` lists. Four item statuses are `passed`, `failed`, `pending_update`, `unverified`. `route` optionally identifies `code`, `report` or `analyze` for a diagnosed failure. Specific missing evidence or dependency scope is more useful than a generic incomplete marker.

File evidence needs the exact path, actually read SHA-256 and concrete note. Missing files produce `unverified`; changed bytes produce `pending_update`. The helper does not infer meaning from the hash. For mathematical code inspection or supplied thoughts, explain actual reasoning and material provenance in the item basis.

Recorded evidence uses `kind: result|artifact|analysis|report|reflection`, exact `id`, and a concrete note. Output includes its factual check, saved receipt/currentness and issues. `require_verified: true` on **result** evidence requires an independently passed recorded check; use it for behavioral correctness. Valid external bytes with unverified generation do not pass that flag. Provenance/limited descriptive analysis can cite unverified data without it, truthfully limiting the claim. A recorded success alone never checks specified algorithms or content.

Report evidence may add `require_pdf_review: true` for a PDF goal: a `source_only` report then remains unverified. A source-only goal can pass its actual editable project without compilation. Legacy `require_accepted` is preserved as provenance in evidence, but does not downgrade report readiness. Inspect actual selected paragraphs and their current basis; recommended, mixed or not-linked status alone is not a blocker. Keep real replies, decisions and links; synthetic fixture replies remain synthetic. Changed relevant evidence still requires affected-content review.

If context exists, the helper reuses `results` inspection with online refresh disabled, exposing saved state, material checks, results, derived products, analyses, reports and reflection records. Online freshness remains explicitly `not_revisited`; independently verify relevant current sources as the request permits. `requested_results` can provide complete intended specifications under the existing [results contract](results.md), propagating parameter differences without executing or changing saved requests. Missing IDs, incomplete coverage, or missing review stay unverified; noncurrent or changed evidence is pending. Failed execution/review or a required failed correctness check cannot be upgraded by a passed assertion. A factual blocker downgrades a proposed passed item; original `agent_status` remains visible. Explicit agent failures remain failures with concrete evidence.

`assessment_origin: agent` distinguishes semantic judgments from factual checks. `mode: read_only` describes the command even if the current combined task permits later repair. `status` is passed only for a nonempty all-passed item set; a mixture with any passed items is partial. Per-item results determine affected scope: the context's broad needs_review does not determine current goal completion. The helper cannot prove the agent read everything or selected all relevant requirements; the Skill requires that semantic work.

For a nonpassing routed item, `follow_up.action` is `diagnose_then_route_within_current_scope` only if the **supplied current** scope includes that behavior and is not read_only; report_mode review forbids report repair. Otherwise it is `scope_decision_required`. No action is performed. Old saved authorization never grants repair. Program execution, budget confirmation and Git mutations remain governed by the target behavior's existing interfaces.

A useful failure packet is the item plus exact failing input, independent expected/actual output, real log/record paths and versions, diagnosed category or concrete remaining hypothesis, current request/scope, affected artifacts and necessary rechecks. Pass it to existing code/report/analysis Skills; do not build a parallel repair engine. An authorized mutating task preserves its normal evidence/handoff and per-issue no-progress history. Three no-progress attempts pause that issue; budget decisions continue to bind. After changes use a fresh scoped assessment of affected items, retaining independent passed items and history. The fact command and explicit read-only acceptance keep the packet in chat and leave assignment files, index and state unchanged.
