# Direct analysis of existing files

Use actual CSV, logs or genuine earlier stdout at their existing locations. Ordinary notes, files and real execution facts suffice; no plan/state, result IDs, import step or analysis manifest is required. Preserve the actual origin: user-supplied measurements remain attributed and unverified as to their generating program; genuine old workflow output keeps its real saved execution provenance.

Read the selected data and relevant requirements first. Record source paths and exact versions (hashes or preserved bytes), provider, known generation conditions, units, omissions and assumptions. Hashes establish file identity, not numerical correctness or authenticity. Keep raw input unchanged. Reuse intact relevant prior calculations after checking their inputs, method and products; an absent internal ID alone warrants no rerun.

Write or patch the analysis script in the real assignment directory. Before changing existing files, preserve original bytes and Git boundaries using ordinary tools or optional `protect-edits` with `role: analyze`, as described in [coding.md](coding.md). Use normal execution or its optional `capture-run` with `role: analyze`: declare the script as `source_paths`, exact data as `input_paths`, literal command/cwd/environment and requested products as `output_paths`. Preserve actual stdout/stderr, exit status, script/input versions and product identities. This is a mechanical aid, not a compulsory analysis API. Output only what the current request needs; a table-only request needs no figure or metrics JSON.

Compute metrics, tables, figures and explanation from the same selected bytes and shared calculation variables. Independently check known rows, units and denominators (for example, milliseconds to seconds and passed/checked rather than passed/failed). Actually read the products and inspect any plots, including units, labels and suspicious values. Successful execution is not proof of correct arithmetic or interpretation. Record the inspected evidence and any limitations in readable notes; a new fixed-schema manifest adds no requirement.

If a calculation fails, retain its real log and partial products, diagnose and repair the analysis script within current scope. Mark failed or partial outputs clearly; old successful products do not represent the failed new attempt. If an input changed, compare exact versions and update only affected calculations and linked prose/figures, retaining historical evidence. A derived-script failure, a changed dataset and a demonstrated course-program defect are separate findings. Analyze-only authorization permits calculations, not course-program execution or implementation repairs; request a concrete scope decision when those are necessary and continue independent analysis.

For handoff retain the current request, actual script/data/product paths, exact input versions and attribution, formula/unit checks, real execution evidence, conclusions, limitations and pending work. These facts can live in ordinary notes and command receipts. Legacy records below remain readable and usable when useful; they do not gate this path.

---

# Optional legacy registered analysis

This retained API is optional for deliberately continuing registered analyses. It is not the default direct-file path. Read [results.md](results.md) for currentness, external attribution and selective updates. This helper executes a model-authored Python analysis, not coursework implementation or a language model. The agent reads data, selects methods and verifies conclusions. No plotting package is mandatory for the companion itself.

```text
python <cs-homework>/scripts/coursework.py analyze --workspace <assignment> --input <analysis.json>
```

Prepare the script and JSON outside the assignment, before the task's Git snapshot. The input contains current `assignment`, `request`, `scope` (authorizing `analyze`, or necessary figures for `report`) and:

```json
{
  "analysis_key": "provided-summary",
  "inputs": [{"result_id": "<exact-current-id>", "path": ".coursework/results/<id>/data/0000.bin"}],
  "assessment": {
    "goal": "Describe these supplied rows in response to requirement R3",
    "completeness": "Two columns present; one row per input size; no repetitions or machine conditions",
    "units": "n is a count; elapsed_ms is milliseconds, as stated in the provided material",
    "anomalies": "Read all rows; no missing or negative elapsed values; preserve all rows",
    "limitations": "External generating computation unverified; cannot establish complexity or causality"
  },
  "computation": {
    "python": "<available-python-with-needed-libraries>",
    "script": "<absolute-path-to-prepared-script.py>",
    "basis": "Arithmetic and plots read the exact captured CSV; independent known-row checks described here",
    "parameters": {"value_column": "elapsed_ms", "unit": "ms"},
    "env": {},
    "capture_env": [],
    "products": [
      {"path": "metrics.json", "kind": "metrics"},
      {"path": "table.csv", "kind": "table"},
      {"path": "figure.png", "kind": "figure"},
      {"path": "figure.pdf", "kind": "figure"},
      {"path": "analysis.md", "kind": "analysis"}
    ]
  }
}
```

`analysis_key` is a stable label for one independently updated analysis group: 1–64 ASCII letters/digits/dots/underscores/hyphens, starting with a letter or digit. Use separate groups when independent data should not force each other's recomputation. `inputs` selects exact captured evidence, not the mutable original file or an invented ID. Workflow stdout, actual output snapshots and external data snapshots are all eligible; inspect the actual evidence and its text encoding to select the right bytes. Multiple selected files may belong to one result, but mixing current/historical versions of one key is rejected. Pending, unknown, damaged or superseded results are rejected before executing the analysis.

The agent's `assessment` records what was actually examined. It is not an automated data-quality judgment or proof of sound statistics. State `unknown` facts and concrete gaps rather than claiming a complete check that did not occur. A failed correctness check remains failed even if the supplied bytes can be analyzed.

The script receives exactly two positional arguments after its path:

1. A JSON manifest containing `inputs` with absolute captured file paths, hashes, exact result IDs/keys, origin, verification and supplied provenance, plus `parameters` and `assessment`.
2. An existing, empty output directory for this new version.

Use ordinary libraries to read the exact manifest paths and write the declared products into that output directory. This simple protocol permits arbitrary assignment-specific metrics instead of a fixed statistics menu. Do not import or execute coursework implementation just to analyze old results. The helper captures and executes a saved copy of the single script; make it self-contained apart from installed libraries. Record relevant library versions in metrics or the generated explanation. Literal `env` overrides and selected inherited environment keys are preserved with the computation; keep configuration process-local.

Products are nonempty, unique relative file paths with `kind` `metrics`, `table`, `figure` or `analysis`; only request what the current task needs. The helper supplies no fixed numerical schema, statistical assumptions or prose format. An analysis script can calculate values and interpolate them into its table and explanation to avoid manual transcription. The agent must still read actual outputs and inspect figures, compare known values, and assess the claims. No substring or numeric scanner substitutes for this content check.

Each call creates `analysis/<key>/<id>/` and immutable `.coursework/analyses/<id>/` evidence. It captures the executed script, input manifest, source snapshots, actual argv, environment/executable facts, raw stdout/stderr, exit/time and product snapshots. Git's task snapshot is taken **before output generation**, so both new visible products and managed evidence are task-owned checkpoints while prior staging and unrelated edits are preserved. This is ordinary local Python execution, **not a sandbox**; review the script so it only reads declared evidence and writes the new output directory.

Successful products are registered as derived artifacts in the existing result registry; all use exact source IDs and hashes. New versions retain old output directories, snapshots and history. A successful replacement retires the previous artifacts for that analysis key from current heads; other analysis keys stay current. Failure records retain actual logs and available partial files but accept no current products, and remain visible on resume as failed. Missing outputs, nonzero execution, or source changes during computation prevent success. Companion exit 0 means the outcome was recorded: inspect `analysis.status` and actual `execution.exit_code`.

`resume` returns `analyses` with `id`, `key`, `current`, `status`, `issues`, `record_path`. Analysis status is `valid`, `pending_update` or `failed`; it checks saved computation evidence, products and source versions, and only current issues affect overall `needs_review`. Source validity and external correctness verification remain separate. No call re-executes a coursework experiment, changes implementation, performs language analysis, or grants new scope. Update stale coursework data only through the authorized behavior and its budget rules.

For report continuation, select checks with `current: true` and `status: "valid"`; use their IDs to read `state.analyses` (full assessment, computation and products) and `state.analysis_heads` (one latest attempt per group). Each product's `artifact_id` resolves to `state.result_artifacts`; also require its matching `resume.artifacts` check to be current and valid. The stored analysis `status: "completed"` records the original outcome, while resume checks describe present validity. Computation evidence damage invalidates its products; read-only `results --input` parameter comparisons also recompute analysis validity against the requested conditions. Preserve origin and correctness verification when quoting these products.
