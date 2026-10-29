# Historical optional reflection records

Use these retained commands only for explicitly chosen legacy registry work. The default is [ordinary notes and direct report editing](reflection.md); the historical staged report interface below is optional and is not the stable native project path. The command checks file identity, not semantic support or human provenance.

Select this branch only when the current request explicitly concerns legacy question/reply records. Ordinary report creation, continuation and checking use autonomous grounded composition, including when existing material has no human reply. Historical statuses describe provenance and never require a new interview to finish a current valid report.

## Questions and complete paragraphs

Ask two or three concrete questions grounded in this assignment. Each question includes a complete recommended answer and actual basis with code line/result locators and limitations. Explain a small piece of implementation background **only when that question would otherwise be hard to understand**; omit background entirely for a directly understandable question. The recommendation itself remains complete in both cases. For example, asking what three passed examples can establish needs no implementation lecture; asking why a prefix table needs an initial zero may need one sentence about subtracting two prefix sums.

Use judgments, limitations and possible improvements grounded in observed code/results. Do not invent that the student debugged, ran programs, read references, struggled, enjoyed or learned something. A proposed future check stays future. Do not convert externally supplied output into verified execution. Read the actual source/evidence before offering its recommendation.

Present full answers together, allowing “accept Q1”, “change Q2's final sentence …”, a replacement answer, or “accept all”. Preserve the actual reply verbatim and resolve only its explicit selections. For an edit, retain the untouched meaning and prepare the complete resulting paragraph; for a replacement, use the user's actual alternative. Do not ask another routine confirmation when the decision is clear. Ask only about a material ambiguity, while proceeding with independent work. A timeout, missing reply or model-generated recommendation is never human acceptance.

Before asking, persist the questions and complete draft paragraphs. While waiting, write them into the actual report through the existing [report API](report.md), identifying their independent `recommended_draft`/`mixed` status in saved metadata and delivery. Do not put blank “待补充” paragraphs in the report. Status belongs in workflow metadata and the delivery explanation; the student-facing report prose should contain the useful complete paragraph, without internal commands or JSON. A compiled draft can have passed technical/page checks while its personal recommendations are still pending; describe the historical provenance truthfully; current grounded report readiness does not require acceptance. After an explicit reply, write a new report version using the accepted full paragraphs; retain prior drafts and recommendation history.

## Persistence companion

The model authors questions, answers and comparisons. This small companion only validates shape, records literal content/replies and checks evidence identity. It does not infer whether a question is understandable or whether an answer follows from its basis. Students never prepare these internal records. Resolve the CLI from the loaded sibling Skill, keep the actual human request/scope identical across these internal steps, and stage report sources **outside** the assignment before `report` takes its Git snapshot.

```text
python <cs-homework>/scripts/coursework.py reflection --workspace <assignment> --input <prepared.json>
python <cs-homework>/scripts/coursework.py reflection-reply --workspace <assignment> --input <reply.json>
python <cs-homework>/scripts/coursework.py reflection-review --workspace <assignment> --input <comparison.json>
```

Every input carries the same `assignment`, `request` and `scope` as [report.md](report.md); current scope authorizes `report`. An advice-only `scope.report_mode: review` or explicit `scope.read_only: true` does not authorize persistence or acceptance. In that mode return advice directly and keep the assignment untouched. Preparation adds:

```json
{
  "reflection_key": "method-limitations",
  "need_basis": "brief.md:8 requires personal judgment; existing material gives results but no judgment",
  "questions": [
    {"id": "Q1", "question": "What can these three examples establish?",
     "recommendation": "The three examples agree with the independent expected sums. They support these tested cases; broader correctness still needs a boundary argument or more checks.",
     "basis": "Exact result ID and actual stdout/expected comparison; three cases, not an exhaustive proof",
     "source_paths": ["solution.py", "brief.md"], "result_ids": ["<current-result-id>"]},
    {"id": "Q2", "question": "Why retain the zero at the start of the prefix table?",
     "background": "An interval sum is the difference of the prefixes just after its right edge and before its left edge.",
     "recommendation": "I would retain the initial zero so intervals starting at the first element use the same subtraction as other intervals, reducing special boundary handling.",
     "basis": "solution.py: actual prefix construction and query subtraction, including the first-element case",
     "source_paths": ["solution.py"]}
  ]
}
```

Use the actual question count (two or three) and evidence for this assignment; these are examples, never executable evidence. Each question can select `source_paths`, `result_ids`, `artifact_ids` and `analysis_ids`; at least one actual file or valid recorded evidence is required. Source bytes are captured per question. `background` is optional, never a mandatory field. `recommendation` is the complete proposed report paragraph. New questions start `status: recommended` with `content` equal to that paragraph; callers cannot turn them into accepted content by supplying a status.

The returned `reflection.id` identifies an immutable version. For an actual reply, supply this exact current `reflection_id` and:

```json
{
  "reply": {"text": "<verbatim actual reply>", "source": {"kind": "user", "locator": "<actual chat turn or supplied response file>"}},
  "answers": [
    {"question_ids": ["Q1"], "action": "accept"},
    {"question_ids": ["Q2"], "action": "edit", "answer": "<complete paragraph reflecting the requested local edit>"}
  ]
}
```

`replace` uses one question plus its complete `answer`; one `accept` entry can select multiple `question_ids`. Unselected questions retain their status and complete content. Actual reply, source, action, resulting answer and original recommendation remain available. Synthetic validation replies must use `source.kind: synthetic` with an honest fixture locator; never report them as real user consent. A later actual user edit or replacement may supersede their earlier decision. Do not re-accept an already accepted decision, silently retarget a historical ID, or re-prepare an existing key to erase decisions.

Link report paragraphs explicitly with `reflection_sources: [{"reflection_id": "<current-id>", "question_ids": ["Q1", "Q2"]}]` in the normal `report` input. Include the selected paragraphs in staged LaTeX and explain their actual provenance in `thoughts_basis`. The report and read-only checks expose `reflection_status`: `recommended_draft`, `accepted_content`, `mixed`, or `not_linked` for ordinary reports using existing material/no reflection branch. `accepted_content` records explicit attributed acceptance, not a claim that synthetic fixture replies were real. Inspect `state.reflections` for attribution. `not_linked` is not proof that required thoughts are missing or present; examine the report's actual requirement map, thoughts basis and supplied materials.

## Resume and relevant changes

`resume` and `results` return `reflections` plus full historical `state.reflections` and `reflection_heads`. Read each question's acceptance separately from evidence validity. Pending recommendations remain pending; original replies survive related evidence changes. Reports compare only selected content and the current selected evidence check: newer groups and unused questions alone do not invalidate them. Acceptance of unchanged text updates current reflection_status without invalidating report sources. A recorded still_supported comparison retains unchanged selected paragraph linkage and original acceptance. Changed selected text or unreviewed selected evidence becomes `pending_update`. No code/result rerun is implied by a reflection issue.

Actually compare changed code/results to the question's basis. If the accepted or recommended paragraph still applies, `reflection-review` records that attributed model comparison without creating any human decision: pass current `reflection_id`, and `reviews: [{"question_id": "Q1", "disposition": "still_supported", "basis": "<actual old/current comparison and why meaning remains valid>", "source_paths": ["<newly read sources>"], "result_ids": []}]`. Omitted evidence ID arrays retain their prior selection; supply all intended current IDs when replacing that selection. Supply the complete current source file set for that question. The command captures new evidence, keeps original content/acceptance and creates a new version for the next report.

If the meaning no longer applies, use the same per-question review with `disposition: revise` and a complete new `recommendation`, concrete comparison `basis` and current evidence. Only that question becomes `recommended` again; previous content, actual acceptance and history remain available. Use the grounded revised paragraph for the current report without waiting for acceptance; only an actual explicit reply may establish a new historical acceptance fact. Do not relabel revised content as previously accepted or re-confirm unrelated accepted answers. The initial interview still uses two or three questions; a later evidence correction concerns only the affected question. Continue unrelated report work. Damaged immutable evidence must be investigated and preserved, never cleared by a no-effect assertion. Technical content, question relevance, sufficient background and absence of fabricated experience require actual semantic review; helper success does not prove them.
