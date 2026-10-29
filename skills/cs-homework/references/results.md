# Result versions, reuse and handoff

Read this when continuing from prior runs, accepting supplied results, or recording analysis/report provenance. The helper verifies declared files and conditions; the agent assesses semantic relevance. A hash is not proof of correctness, and a saved completion flag is not proof of current validity.

## Native file reuse

Direct analysis and report work can use actual files and readable provenance without result IDs or registration. Read [analysis.md](analysis.md) for the direct calculation path. Check the relevant exact bytes, generation conditions, method and product correspondence; keep external attribution and independent verification status visible in working records. Report prose follows the language-first [shared standard](report-quality.md); these records do not require appended qualifications in the report. Only affected files and conclusions need updating. The registered commands below are optional retained interfaces for existing registered workflows, not prerequisites for native continuation.

## Registered reuse and selective update

Add these fields to a normal `run` input:

```json
{
  "result_key": "small-sample",
  "execution": {
    "argv": ["<actual-python>", "solution.py", "input-a.txt"],
    "source_paths": ["solution.py", "requirements.lock"],
    "input_paths": ["input-a.txt"],
    "capture_env": ["OMP_NUM_THREADS"],
    "parameters": {"seed": 17},
    "material_ids": ["assignment-brief"],
    "dependency_coverage": {
      "status": "complete",
      "note": "Read the program and dependency declarations; these are all files, parameters and environment conditions that affect this result."
    },
    "purposes": ["example"],
    "basis": "The user requested this existing sample."
  }
}
```

Supply the usual `assignment`, `request` and current `scope`; see the execution section of [runtime-contract.md](runtime-contract.md). `parameters` records additional conditions; it does not automatically pass arguments to the program. `material_ids` identifies relevant already-read requirement sources. Do not invent coverage: use `partial` or `unknown` with a concrete gap when relevant dependencies, dynamic reads, packages, random seeds or execution conditions cannot be established. Missing coverage in older records remains `needs_review` until actually assessed.

Use one stable `result_key` for each independent workload/input group across revisions. Without a key, an exact-specification digest is used; give a stable key before changing that workload's parameters so its previous version can be marked pending. Keys are labels, not filenames. Scope does not grant future work merely by appearing in a past record.

With the same specification and valid declared files/conditions, `run` returns `reused: true`, the original `run` and `result`, with no new process, history revision or Git commit. It never pretends a reused command ran again. Failed runs, changed/missing/corrupt evidence, changed executable, relevant conditions or dependencies, incomplete coverage, and unreviewed source changes prevent reuse. An explicit decision to repeat a valid workload may use `force_rerun: true`; record why repetition is required in the request. Do not set it simply to bypass a validity question.

Git HEAD/status are execution history, not reuse identity. Committing evidence or unrelated student edits does not invalidate results. The executable path/hash, explicit `env` overrides and keys named in `capture_env` are compared; unrelated inherited session variables are not. Declare relevant package/configuration files and conditions yourself. Budget confirmation retains its stricter identity check for the saved pending plan.

`resume` is read-only and now returns `results` and `artifacts` alongside the full state and material checks. Each result has `id`, `key`, `origin`, `current`, `status`, `issues`, `verification`, `record_path`, and optional `applicability_review`. Statuses are `valid`, `pending_update`, `needs_review` and `failed`. Validity concerns current applicability/integrity; `verification` separately preserves passed, failed or unverified correctness facts. Only `current: true` versions are candidates for ordinary current analysis. Historical pending versions remain available without making the whole assignment permanently incomplete.

To compare intended current parameters without executing, changing scope or writing state:

```text
python <cs-homework>/scripts/coursework.py results --workspace <assignment> --input <inspection.json> [--offline]
```

```json
{
  "scope": {"authorized_behaviors": ["analyze"]},
  "requested_results": [{"key": "small-sample", "specification": {"...": "complete current execution specification"}}]
}
```

The returned `update_action` distinguishes reuse, semantic review, an explicit scope decision, and a targeted new run subject to its budget. Inspection does not authorize execution. Code-only scope allows only necessary correctness validation. Update only affected keys: run authorization and budget/trial rules still apply; keep unrequested, over-budget or uncertain parts pending and continue independent work. A production source/input change during a run is recorded as inconsistent even if the process exited successfully.

The current specification is saved in `state.result_requests` when a run is actually planned/recorded. `results --input` is only a read-only comparison and does not change those saved requests. Inspect current arguments when continuing in a new chat; parameters that exist only in a new user request cannot be inferred from old files.

## Semantic non-impact review

Byte changes can be harmless, such as a Python comment or a requirement spelling correction. First compare the actual current file with the original snapshots, the inputs, expected outputs and relevant conditions. If that comparison establishes no effect on the result, record the rationale instead of needlessly rerunning:

```text
python <cs-homework>/scripts/coursework.py review-result --workspace <assignment> --input <review.json>
```

The input contains current `assignment`, `request`, `scope`, plus `result_id`, `assessment: "unaffected"`, a substantive `note`, and the complete current `specification` including complete dependency coverage. It snapshots current dependencies and binds the assessment to their exact hashes and current material versions. Re-read and update changed requirement sources through planning before recording this assessment. Missing dependencies, failed/inconsistent original execution, and damaged evidence cannot be repaired by a non-impact declaration.

This is an attributed **agent assessment**, not a proof of semantic equivalence and not a new execution. Original source snapshots, stdout, checks and run ID stay unchanged. It may authorize reuse only for the exact assessed current conditions; another change makes it pending again. If uncertain, leave `needs_review`/`pending_update` and ask a specific question with a recommended resolution. Do not use reviews to conceal a real algorithm/input/parameter change or to label old values as newly measured.

For an older supported schema-1 context with real `runs` but no result registry, use `run_id` and an unused `result_key` instead of `result_id`. The same command first adopts the existing immutable run evidence as `origin: "workflow-run"`, then records its current applicability assessment. It checks the saved run matches handoff state and the original captured evidence is intact; nothing is executed. Supply complete current coverage after actually reading the old source snapshots and current files. Existing registered runs are reviewed by `result_id` instead of being adopted twice.

## External data without forced execution

If a registered workflow benefits from immutable external-result records, it can optionally archive user-provided files without a plan or prior run:

```text
python <cs-homework>/scripts/coursework.py import-result --workspace <assignment> --input <external.json>
```

```json
{
  "assignment": {"title": "Existing results"},
  "request": "Analyze my supplied CSV without rerunning.",
  "scope": {"goal": "Supplied data analysis", "authorized_behaviors": ["analyze"]},
  "result_key": "provided-measurements",
  "data_paths": ["measurements.csv"],
  "provenance": {
    "provided_by": "user",
    "location": "User-provided file measurements.csv",
    "description": "User reports an earlier run; no command or source snapshot was supplied."
  },
  "verification": {"status": "unverified", "note": "Source bytes are available; the generating computation is not independently checked."}
}
```

The immutable result has `origin: "external"`, exact copied data bytes, original file locations and provenance; no workflow run is invented. `verification` defaults to unverified. An actual independent check can be recorded as `independently_checked` with a precise `note` and existing `evidence_paths`; these files are also captured. The helper checks their existence/identity, not whether that check was sound. Truthfully describe what was checked (e.g. three independently calculated rows, not the entire experiment).

For an external result, `valid` means the provided data bytes remain current and intact. It does **not** establish correspondence to the current implementation, authentic measurement conditions or correctness. Keep that verification status in the analysis or handoff record. Report wording follows the shared report standard instead of copying these limitations into the body. Replacement external data receives a new ID under the same key, preserving history.

## Bind charts, analysis and reports to exact sources

Native work records actual source/product paths and versions in readable notes or run evidence. In an optional registered workflow, after reading source evidence and producing an actual file, record its sources:

```text
python <cs-homework>/scripts/coursework.py link-results --workspace <assignment> --input <link.json>
```

The input contains current `assignment`, `request`, `scope`, plus:

```json
{"artifact": {"path": "analysis/summary.md", "kind": "analysis", "result_ids": ["<exact-current-result-id>"], "basis": "The table is computed from the captured CSV for these result IDs; units and columns were checked."}}
```

The helper snapshots the actual file and records its hash, exact result IDs/keys/origins and receipt paths. It rejects missing, non-current, invalid or mixed versions of one key. Use the same captured result bytes for numerical computation, plots, tables and report prose; recording a link is not a numerical-content check. The helper cannot detect that an agent typed a number from the wrong source, so inspect the actual content too. Intentional historical comparisons must be explained explicitly as historical and use clearly distinguished group keys; never relabel a historical version as current.

On resume an artifact is pending if its file/evidence changes, a source becomes invalid, or a newer result replaces one of its source versions. Other artifacts with independent current sources stay valid. Artifact snapshots retain prior contents even if a later task overwrites the visible output path.

Result records live under `.coursework/results/<id>/`; assessments under `.coursework/result-reviews/<id>/`; derived artifact receipts under `.coursework/artifacts/<id>/`. These paths and history are immutable. State adds `results`, `result_heads`, `result_requests`, optional `result_reviews`, `result_artifacts` and `artifact_heads`, preserving unrelated namespaces. Automatic Git commits cover new managed evidence/state/history only and preserve preexisting staged/unstaged files. A producing behavior must take its own task snapshot **before** generating outputs if it also wants a safe task-owned commit of those visible outputs; a later link never steals preexisting user changes into its commit.

## Remote freshness and historical output

Result inspection and reuse never request remote sources. `freshness: not_revisited` is independent of the integrity of saved outputs and historical snapshots; it does not itself invalidate a result or assert that current online requirements are unchanged. Revisit relevant content with native reading tools when the current request asks for latest requirements, a change clue appears, or prior coverage is insufficient. Actual related requirement changes, missing/changed execution evidence and unknown provenance still need specific review; do not upgrade all unknowns to valid. See [online material history](runtime-contract.md#online-materials-native-reading-and-optional-history).
