# Stable LaTeX project and actual builds

The Agent reads, writes and reviews the report directly in the assignment's stable main project. Use existing ordinary data, plots, code and notes, keeping provenance in working records; no plan/result/analysis/report registry is required. Apply the language-first [shared report standard](report-quality.md), including its deletion-first choices, default omission of limitations discussion and task-dependent total and section lengths. Current request and scope govern every supporting action. For advice-only or explicit read-only work, read and reply in chat without edits, Git, computation or compilation; see [report-prose.md](report-prose.md).

## Edit and preserve

Identify the main file from the actual project or explicit user choice. Reuse that path, normally `report/main.tex`; keep included sources, bibliography, styles and images in an editable layout. Before editing, inspect Git/index/unstaged/untracked files and preserve exact original bytes of files being changed. Use the shared optional `protect-edits` with `role: "report"`, or ordinary copies and Git/patches. If an optional helper/interpreter fails, copy the original with normal file tools before changing it. A dirty-path inventory alone is not recovery evidence. Commit only this task's changes and evidence while preserving preexisting user content and staging; see [native protection and capture](coding.md) and [continuity.md](continuity.md).

Edit with normal patch/editor tools inside the main project. Source-only requests end with editable sources and an accurate uncompiled status: do not run the compiler or renderer. Template content and chapter sequence are not requirements; use only its format. Choose structure from explicit current requirements or sensible course-report organization. Keep the retained core methods and results grounded in the actual work, and keep citations and historical judgments intact. Optional claims and details may be deleted under the shared standard. Do not treat every existing condition or qualification as text that must survive or be expanded. Record meaningful findings in notes rather than treating a filled review field as proof.

For source-only edits as well, checkpoint new task-owned notes and recovery evidence through explicit own-path commits, preserving the user's original staged diff as described in [continuity.md](continuity.md). Keep a source file already containing user changes outside the commit and retain its task patch or snapshot separately; existing user staging does not prevent committing independent new evidence.

## Compile only when requested

Ordinary compiler commands are sufficient when they retain exact argv/cwd/environment, input identities or bytes, logs, exit status and current output identity. Use a fresh build output directory per attempt, keep source/main stable, and include all actual TeX/styles/images/bibliography inputs and any external includes in evidence. Run from the actual source project so relative assets resolve. PDF success needs the current attempt's successful execution, valid current PDF, unchanged inputs during execution and resolved references/glyphs. Keep failure logs and clearly identify older PDFs as historical; never publish them as current success.

For repeated reliable compilation, this optional mechanical helper reuses engine arguments, raw execution capture, diagnostics and Poppler:

```text
python <cs-homework>/scripts/coursework.py compile-project --workspace <assignment> --input <options.json>
```

```json
{
  "request": "Continue the existing report and deliver LaTeX plus PDF",
  "scope": {"goal": "Current report", "authorized_behaviors": ["report"]},
  "project": "report", "main_file": "main.tex",
  "source_paths": ["brief.md", "data/results.csv"],
  "compiler": {
    "engine": "tectonic", "executable": "<verified executable>",
    "env": {"TECTONIC_CACHE_DIR": "<verified cache>", "FONTCONFIG_FILE": "<verified config>"}
  },
  "renderer": {"executable": "<verified pdftoppm>", "dpi": 120}
}
```

Options may be a small internal file; it is not a required report-writing protocol. `project` names an existing assignment-local directory; `main_file` is relative to it. `source_paths` names additional actual supporting materials, especially dependencies outside the project. All project files except Git/metadata/generated build/page trees and log/auxiliary output (PDF figure inputs are included) are captured automatically; the Agent still checks coverage of outside includes. Supported engines are `tectonic`, `xelatex`, `pdflatex`, `lualatex`, `latexmk`; compiler `args`, `env` and `capture_env` are literal values. Verify tools before use and keep environment changes local. No new tool installation is implied.

The helper writes only fresh `.coursework/native/builds/<attempt>/` evidence/output, retains the existing source layout, and does not create unified state or register results. It initializes/reuses Git as needed but does not substitute for the Agent's before-edit protection or task checkpoint. Return status `awaiting_review` means compilation/rendering succeeded, not semantic or visual approval. `failed` retains diagnostics and never returns an old PDF. A renderer failure is also failed. Save the receipt location in readable handoff notes.

## Review and delivery

Read the final prose against the shared language requirements first, then check task coverage, the core method/results and total and section lengths as needed. Avoid turning report review into a full technical or evidence audit, or adding qualifications to make every statement exhaustive. Open every final rendered page and inspect text, equations, glyphs, plot labels/units/legend, tables, code, page numbers and cross-references for clipping, overlap or `??`. Extracted text or logs cannot replace page inspection. Record every actual page path, specific findings and remaining limitations in ordinary notes. Rendering alone is not review. After repairs, compile/render fresh and normally inspect all final pages again.

For necessary missing evidence, run only existing code within current report-support scope, with exact purpose/input and independent expectations; retain trial/estimate and budget rules in [runtime-contract.md](runtime-contract.md). Extra experiments or course-implementation repairs need current authorization. Three targeted repairs without progress pause that issue with evidence; continue independent work. Do not weaken correct expected answers to make prose agree.

Deliver stable editable main project plus the actual current PDF and evidence when requested. If compilation fails, deliver sources and precise diagnostics, marking PDF/visual checks failed or unverified. Advice and source-only branches never require a PDF. Save current scope, provenance, review findings and unresolved questions in readable handoff, and checkpoint meaningful authorized progress without including user changes.

## Historical records

Existing `report`/`review-report` staged version records remain readable and their commands remain available for explicitly chosen legacy work. They use their historical IDs and registry constraints. They are not prerequisites for direct editing, compilation, continuation, prose review or current report acceptance; do not migrate an ordinary project just to use them.
