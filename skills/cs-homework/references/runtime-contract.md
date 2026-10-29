# Optional coursework companion contract (schema 1)

The Agent reads materials, interprets requests, edits actual files and judges content. Ordinary notes, real files and execution evidence are the default; no unified state, IDs, imports or semantic-review API are required. Use this reference only when choosing a helper for mechanical benefit or reading legacy records. The companion checks file identity, captures execution facts and can commit explicit task outputs. It has no language model API, natural-language classifier or semantic validator. Online creation commands have retired; actual online reading uses available reader tools. Students use normal conversation; only a deliberately selected structured helper needs its internal JSON.

For LaTeX, read [report.md](report.md): edit the stable main project directly, preserve originals before editing, compile into fresh per-attempt outputs and inspect every final rendered page. Optional `compile-project --workspace --input` captures real compilation/rendering without a plan or registry; ordinary commands with the same evidence are sufficient. Source-only requests do not compile; advice remains read-only. Historical `report`/`review-report` records remain readable but are not continuation prerequisites. Keep current request/scope stable across supporting work. Necessary existing-code report runs identify missing task evidence and exact existing workload, under the same budget/execution rules; implementation changes or extra experiments need authorization.

For personal thoughts, read [reflection.md](reflection.md): compose grounded judgments autonomously from requirements, actual code/results and principles; preserve genuine existing judgments, literal reply provenance and selected-paragraph notes. Missing replies or acceptance records do not block the report. Direct report editing needs no thought IDs or API. The explicitly optional historical companion preserves old records and exposes per-question acceptance separately from evidence validity; it cannot establish semantic support or real human consent.

For acceptance, use ordinary requirements, actual files and relevant evidence first. Targeted necessary execution can use normal tools or optional capture-run under the same current scope and budget; compilation uses isolated outputs and preserves originals. Explicit read-only/no-run requests leave missing proof unverified. For the optional check fact assistant only, read [acceptance.md](acceptance.md): it checks agent-authored items without Git, state writes or execution, even without context. It neither performs semantic acceptance nor starts follow-ups. Its legacy scope fields do not authorize work beyond the current request. Historical personal acceptance remains provenance, not a readiness prerequisite; inspect selected current content/evidence, while unrelated recommendations/history do not invalidate the current goal.

## Package and commands

All seven entry points share [current task, tool hints and assignment-local handoffs](continuity.md). `handoff --workspace --input` saves model-authored Markdown for an authorized writing task without rewriting structured state; `resume.handoffs` lists readable note paths/hashes without interpreting them as permission. A note-only `.coursework/` can precede the first structured behavior. An empty or otherwise unrecognized directory remains protected.

For native assignment edits, original-byte protection and optional standalone exact run receipts, see [coding.md](coding.md). Normal tools edit the actual files; legacy `code-start`/`code-step` sessions are optional existing-session interfaces. No helper writes an algorithm or diagnoses failures for the model.

Keep the sibling `cs-homework*` Skill folders together. The shared Python standard-library runtime lives inside `cs-homework/scripts/`; it does not depend on the source repository or a fixed installation path. Use an available Python 3.12+ and Git executable. Resolve the script from the loaded Skill's location:

```text
python <cs-homework>/scripts/coursework.py plan --workspace <assignment> --input <record.json> [--new]
python <cs-homework>/scripts/coursework.py resume --workspace <assignment> [--offline]
python <cs-homework>/scripts/coursework.py run --workspace <assignment> --input <run.json>
python <cs-homework>/scripts/coursework.py run --workspace <assignment> --confirm <run-id> --confirmation <actual-user-reply>
```

All path arguments are literal process arguments, not shell fragments. `--new` requires a nonexistent assignment directory and initializes an independent local Git repository there. Mutating commands otherwise reuse the exact directory and its enclosing Git repository, or initialize a local repository if none exists. Read-only commands never initialize Git. No files are moved. External local sources stay where the user put them.

Successful commands return UTF-8 JSON on stdout and exit 0. Errors return an `error` JSON object on stderr and exit 2. `resume` is optional and read-only. Missing, unrecognized or incomplete context returns `context_status` (`absent`, `unrecognized`, `incomplete`), readable handoff paths and an actual `files` path/hash inventory; original files remain untouched. Partial recognized state is returned for reading. Empty check arrays mean no structured checks were available, not that evidence passed. Read ordinary notes and actual evidence directly; missing IDs or this command are never prerequisites to continuation. Legacy mutating helpers may reject unknown state to preserve it; use normal tools without replacing that state. Do not run concurrent writers against one assignment directory.

## Agent-prepared planning input

This is a complete current plan, not a patch. Initial required fields are `assignment`, `request`, `scope`, `sources`, `requirements`, `plan`, `next_steps`. `decisions` and `questions` default to no new decisions and retained prior questions, respectively. Supply `questions: []` when all prior questions have been resolved. Unknown descriptive fields are retained, so later behaviors can add namespaced facts without rewriting prior data.

```json
{
  "assignment": {"title": "有向图最短路径"},
  "request": "只整理要求和计划，暂不实现。",
  "scope": {
    "goal": "可继续的实施与验证计划",
    "authorized_behaviors": ["plan"],
    "deliverables": ["要求与计划"],
    "checkpoints": ["实现前查看计划"]
  },
  "sources": [
    {"id": "brief", "kind": "local", "path": "materials/brief.md", "purpose": "题目"},
    {"id": "chat-1", "kind": "chat", "content": "只规划，不写报告。"}
  ],
  "requirements": [
    {"id": "R1", "category": "algorithm", "text": "使用 BFS",
     "sources": [{"source_id": "brief", "locator": "第1行"}]}
  ],
  "decisions": [
    {"id": "D1", "text": "本次只规划", "status": "confirmed",
     "sources": [{"source_id": "chat-1", "locator": "当前请求"}]}
  ],
  "questions": [],
  "plan": {
    "implementation": [{"description": "构建邻接表，用队列做 BFS", "requirements": ["R1"]}],
    "validation": [{"description": "使用题目已知答案检查最短路径，另查不可达节点", "requirements": ["R1"]}]
  },
  "next_steps": [{"behavior": "code", "description": "用户查看计划并授权后实现"}]
}
```

- IDs are stable within an assignment. Local source paths are relative to the assignment or absolute. The runtime resolves, reads and SHA-256 hashes their bytes, adding `sha256` and `size_bytes`; it does not claim their meaning was understood. In-directory paths are stored relative. Chat source content is saved verbatim. A different path, source kind or chat supplement needs a new ID. Re-read changed files before submitting an updated plan; a refreshed fingerprint represents the newly read version.
- Requirement categories normally distinguish `language`, `algorithm`, `interface`, `dependencies`, `input`, `output`, `scope` and `other`. Every requirement, decision and question must have a source ID and a useful locator (line, page, section or chat turn). The helper validates references, not whether the source supports the assertion. That is the agent's responsibility.
- `scope.authorized_behaviors` uses `plan`, `code`, `run`, `analyze`, `report`, `check`. A planning input must include `plan`. The command only saves a plan even if the overall scope authorizes later behaviors. A future `next_steps` entry never grants permission.
- Plan steps reference requirement IDs and describe proposed work; they are not execution evidence. Empty step lists are permitted for genuinely inapplicable work; explain why in an adjacent descriptive field.
- Decisions use `proposed`, `confirmed`, or `superseded`. Old decisions and sources are retained when omitted. A confirmed decision cannot silently change or disappear. To change it after a user decision, add a new ID with `supersedes: "old-ID"` and sourced explanation; the old record becomes `superseded`. The same source ID must not be reused for a different chat message.
- A question is `{ "id": "Q1", "text": "具体问题？", "blocking": true, "facts_checked": "已调查的事实", "sources": [...] }`. Mark only affected work blocked. Ask the student the semantic question, not for facts the agent can inspect. Facts checked and unresolved questions are preserved for a new chat.

## Saved state and resume output

The reserved `.coursework/` namespace contains:

```text
.coursework/state.json          machine-readable current context
.coursework/plan.md             human-readable requirements, scope and plan
.coursework/history/0001.json   immutable planning revision, then 0002.json etc.
```

State contains the input plus `kind: "coursework-context"`, `schema_version: 1`, integer `revision`, UTC `updated_at`, and material fingerprints. Prior unrelated top-level state fields survive a planning save. Each successful save adds a revision, retaining historical requirements and source hashes. An unrecognized preexisting `.coursework/` is not overwritten. Managed output paths must not traverse filesystem links. Agent edits should be submitted through planning input, not by directly rewriting managed state or plans.

`resume` returns `{workspace, state, materials, needs_review, blocking_questions}`. `materials` contains `{source_id, status, current_sha256?}` for every registered source. Local status is `unchanged`, `changed`, `missing` or `recorded` (chat). Online checks add the statuses and provenance below. `needs_review` is true for changed/missing/unread/incomplete/unavailable/unverified material or pending source-impact reviews. `blocking_questions` lists persisted questions marked blocking (default true). Resume neither updates saved hashes nor clears questions. A change flag requires semantic review; it is not an automatic conclusion about which requirements changed. `needs_review=false` is not a correctness check.

`plan` returns the same context plus `deliverables` (state and readable plan paths) and `git: {commit, skipped_preexisting}`. Never infer a successful Git checkpoint from files existing alone. Commit failure returns an error; newly saved artifacts remain available for diagnosis and recovery.

## Shared Python interfaces for later behaviors

With `cs-homework/scripts` on the script search path, import `coursework_runtime.context` and `coursework_runtime.git`. Plan-specific policy remains in `coursework_runtime.planning`; later behaviors should not have to call `save_plan` to do their own work.

| Interface | Contract |
| --- | --- |
| `context.read_state(workspace)` | Read recognized schema-1 state; reject unsupported state. |
| `context.resume(workspace, refresh_online=False)` | Read saved context and verify local/evidence bytes only. The legacy refresh argument does not request remote sources; revisit relevant documents with native reading tools. |
| `context.fingerprint(path)` | Streaming SHA-256 of actual bytes. |
| `context.write_json(path, value)` | UTF-8 JSON via a temporary sibling and replace; caller owns the path and must preserve user changes. |
| `git.begin_task(workspace, independent=False)` | Before any edits, create/reuse Git and capture all staged, unstaged and untracked paths in the enclosing repository. Returns a `TaskSnapshot` with `root` and `dirty_paths`. |
| `git.checkpoint(workspace, paths, snapshot, message)` | Commit only explicit task-owned file paths, relative to the assignment. Return the commit and paths skipped because dirty before the task. |

Capture a fresh snapshot before **each task's edits**; do not reuse the planning snapshot for a later task. Paths already dirty at that boundary are preserved and excluded from commits, even if the agent later edits them. This can leave task changes uncommitted in an originally dirty user file; accurately report that limitation rather than mixing user content into a workflow commit. Callers must preserve the original content when editing such files. The generic checkpoint helper does not decide what edits are authorized.

The planning writer additionally refuses to overwrite any planned output dirty before this task, leaving both staged and working copies intact. Git uses `commit --only` on literal file pathspecs, preserving unrelated staging. New task paths are first registered with intent-to-add. It never resets, cleans, stashes, amends, changes branches, changes global config, pushes, or rewrites existing history. A per-command fallback identity is used only when Git has none configured. Files ignored by user Git rules or rejected by hooks are reported as checkpoint errors; do not force them into Git.

For future run/result/report records, preserve this context and extend it with explicit evidence rather than claiming command execution from plan entries. The schema is intentionally small; version migrations and result-validity policy belong to the behavior adding them.

## Direct execution and evidence

`coursework_runtime.execution` owns `save_run(workspace, record)` and `confirm_run(workspace, run_id, confirmation)`, separate from planning. `run` requires an existing assignment directory and initializes/reuses context and Git without calling `save_plan`, inventing a planning stage, moving user files or editing implementation. The agent prepares this internal input after inspecting the actual program and current request:

```json
{
  "assignment": {"title": "已有求和程序"},
  "request": "只运行已有代码，核对教师样例。不要修改实现。",
  "scope": {"goal": "可复核运行证据", "authorized_behaviors": ["run"], "deliverables": ["运行证据"]},
  "execution": {
    "argv": ["<available-python>", "student.py", "--mode", "sum"],
    "cwd": ".",
    "stdin_text": "1 2 3\n",
    "source_paths": ["student.py"],
    "input_paths": [],
    "output_paths": [],
    "purposes": ["correctness", "example"],
    "basis": "当前用户请求及任务书第2节的教师样例",
    "expected": {"stdout": "6\n", "exit_code": 0, "basis": "教师给定样例答案；按实际程序平台提供精确换行"},
    "env": {},
    "capture_env": []
  }
}
```

`argv` is a nonempty list of literal arguments, never parsed as a shell command. Its first item is resolved through the child `PATH` (or an explicit executable path) and the resolved path is recorded. `cwd` defaults to the assignment; relative file references are relative to the assignment, including `stdin_path`, declared dependencies and output paths. `stdin_text` is UTF-8; alternatively, `stdin_path` supplies actual bytes and is automatically a fingerprinted dependency. With neither field, stdin is empty and closed. Do not supply both.

`source_paths` is a nonempty list; add every relevant implementation/configuration/dependency file. `input_paths`, `output_paths`, `capture_env` default to empty lists, and `env` is a string-to-string map of child-only overrides. The helper cannot infer undeclared files or implicit program side effects. Agents must choose commands/output locations that preserve user files and the authorized scope. Raw stdout/stderr are captured separately; declared file outputs are snapshotted after the process and linked to this run. A present output alone does not prove the command created it; use new output locations and inspect the program's actual behavior. These observations do not imply permission to rewrite implementation.

`purposes` contains `correctness`, `example`, `experiment`, or several purposes sharing one execution. `basis` records the assignment/user reason; the model must determine its actual support. The current scope must authorize `run`. A `code` task can run `purposes: ["correctness"]` as necessary validation without adding general experiment scope. No helper plans additional cases, scans parameters, interprets natural language or edits coursework code.

`expected` is optional and requires `basis` plus at least one of `stdout`, `stderr`, `exit_code`. Output comparisons use exact UTF-8 bytes, including line endings; the supplied text must represent the known independent expectation. A model must use an independent reference, never copy the implementation's output as its oracle. Missing expectations give `check.status: unverified`; they do not imply correctness. Completion requires the explicitly expected exit code (default 0) and no failed comparison. An intended nonzero boundary case with matching `expected.exit_code` and all supplied comparisons passed is successful test evidence; the actual nonzero exit and stderr remain unchanged. An unexpected nonzero exit or mismatched expected output remains failed.

The command returns exit 0 when the execution outcome has been recorded, including a failed/non-started child or a pending budget confirmation. Read `run.status`, `execution.exit_code`, diagnostics and `check.status` rather than treating companion exit 0 as a coursework pass. Invalid input, unsupported state, protected output conflicts or checkpoint failure use the common error/exit-2 contract. Child errors never become a fabricated exit 0. Missing declared inputs or executables produce `not_started`, a concrete diagnostic and `exit_code: null`; no process output is invented. A failed trial produces `trial_failed` and stops the full run. Failures retain `follow_up` with `needs_diagnosis` and whether the current scope includes `code`; the model diagnoses environment/input/oracle/implementation causes and asks before implementation changes when not already authorized.

### Budget and confirmation

For a potentially long workload, the agent supplies a representative `trial`, `execution.workload_units`, optional `budget_seconds`, and explanatory `estimate_basis`:

```json
{
  "budget_seconds": 120,
  "estimate_basis": "相同条件下的独立重复工作，正式200单位；试跑2单位，计入试跑耗时。",
  "execution": {"argv": ["<executable>", "--count", "200"], "workload_units": 200, "requires_trial": true},
  "trial": {"argv": ["<executable>", "--count", "2"], "workload_units": 2}
}
```

This fragment supplements the complete input above. Budget and workload units must be positive finite numbers. Trial can vary argv, stdin, declared source/input files, expected output and workload units; it shares the production environment and working directory. It does not inherit the production expectation: provide `trial.expected` only when independently known. The estimate is actual trial elapsed × production units / trial units, plus the trial elapsed for total budget comparison. The agent chooses meaningful effective work units and explains scaling uncertainty; this arithmetic is not a complexity predictor or evidence that the full command ran. `requires_trial: true` rejects a missing trial before execution; agents must use a trial for potentially long experiments even though the runtime cannot infer duration from arbitrary code.

With no explicit budget, `budget.limit_seconds` is **1800**, `is_default` is true and `hard_timeout` is false. Exceeding estimated total time creates `awaiting_confirmation`; the full command is absent and has not executed. No timeout is passed to the child. The model shows actual trial evidence, full argv/workload, estimate/uncertainty and requested budget decision, then waits for the user's real response. It must not generate confirmation itself or treat silence as consent.

After explicit acceptance, `--confirm` uses the saved argv, inputs, scale, environment overrides and scope; it accepts no replacement input. It checks declared production/trial source/input hashes, production executable identity/hash, inherited environment digest and current request/scope before starting. Changed facts require a fresh plan; a confirmed/completed record cannot be confirmed again. The helper stores the supplied user reply as evidence but cannot authenticate conversational consent; truthful attribution remains the agent's responsibility. Acceptance covers this budget plan only. A changed requested command/workload is a new input and run ID, not a reuse of prior confirmation.

### Saved run records

`state.runs` adds current run records without removing unrelated context fields, requirements, decisions, sources or planning content. Each task save adds a shared state/history revision. Latest `evidence_path` and `summary_path` identify structured and readable evidence; after confirmation these point into a new immutable confirmation directory. The original pending record/summary and trial remain available.

```text
.coursework/runs/<id>/record.json
.coursework/runs/<id>/run.md
.coursework/runs/<id>/plan/              source/input snapshots and Git diffs at planning time
.coursework/runs/<id>/trial/             actual trial, if requested
.coursework/runs/<id>/execution/         actual full execution, if permitted
.coursework/runs/<id>/confirmations/<confirmation-id>/record.json
.coursework/runs/<id>/confirmations/<confirmation-id>/run.md
.coursework/runs/<id>/confirmations/<confirmation-id>/execution/
```

Execution records include requested/resolved argv, actual cwd, UTC times and elapsed seconds, actual stdin/stdout/stderr bytes, exit code, independent expected/check facts, platform/machine, companion Python version, executable path/hash, explicit environment overrides and selected inherited environment values. The entire child environment is represented additionally by a SHA-256 digest for confirmation identity; values beyond selected keys are not dumped. Capture additional relevant keys explicitly when needed for reproducibility. Exact bytes live in `.bin` artifacts with SHA-256 and length; JSON `text` is a preview labelled `text_decoding: {encoding: "utf-8", errors: "replace", lossless: ...}`. A non-lossless preview is not the original text; decode the captured bytes with the program's actual encoding when analyzing it.

Both before and after execution, source records capture enclosing Git root, real HEAD (possibly null before the first commit), raw porcelain status, and snapshots/hash/length of declared source/input files, including untracked and dirty bytes. Stored staged/unstaged binary patches are restricted to the explicit declared files inside that Git root, using literal pathspecs listed in `patch_scope`; unrelated edits are not copied into evidence. External declared sources/inputs retain their exact byte snapshots and hashes without widening patch scope. An empty in-repository dependency set produces empty patches, not a repository-wide diff. Status may include unrelated path names, but not their contents. A commit ID alone never represents the running code. Runtime Git checkpoints commit only explicit `.coursework/` artifacts and preserve existing student staging. A dirty managed state/history path is refused before running, preserving its staged and working copies. No reset, stash, amend or force-add is used. Checkpoint failure leaves already written evidence available and reports an error; inspect the actual artifacts before retrying a side-effecting command.

Run evidence records facts at that time. Result validity, automatic reuse, version history, external data and downstream source links are specified in [results.md](results.md). Read it before reusing prior runs or recording analysis/report provenance. A completed command alone is not proof of current validity; preserve unknown fields and inspect actual evidence.

Direct computation uses ordinary files and scripts in the assignment; read [analysis.md](analysis.md) for native source/version checks and optional execution capture. The retained `analyze` command offers a registered source-manifest/script protocol for existing registered workflows; it is not required for CSV/log analysis. Neither path authorizes coursework implementation execution or requires a prior planning stage.
## Online materials: native reading and optional history

Use [cs-homework-plan](../../cs-homework-plan/SKILL.md) for actual reading, coverage notes and decisions to revisit. Ordinary Markdown notes with URL/path, actual read/attempt time, coverage/gaps and located requirements are sufficient. Snapshots/exports are optional. No helper authenticates a browser invocation or semantic understanding.

The custom `fetch-online` and `capture-online` creation commands have retired. Existing receipt/body/text directories and plan histories remain readable; no migration or fresh capture is required. The optional old `plan` helper can still import intact legacy receipts when deliberately used. It also accepts native reading notes without a receipt:

```json
{"id":"brief", "kind":"online", "url":"https://example.edu/brief", "purpose":"assignment",
 "reading":{"status":"partial", "read_at":"2026-10-26T10:00:00+08:00", "note":"Read section 2 and the sample table; appendix inaccessible."}}
```

For that optional helper, `read`, `partial`, `unread` describe recorded coverage; actual read/attempt time and concrete coverage/gap are required. Requirements need source locators and cannot cite an unread source as evidence. A partial source supports only observed content; the Agent checks this semantic boundary. A compact requirement digest binds native-note result versions to extracted claims, not note timestamps; it is not a hash of remote contents or proof they are unchanged. Legacy snapshots retain their existing byte identities.

`resume`, `results`, result reuse and all other inspections make **no remote requests**, including for legacy HTTP captures. `--offline` remains an accepted compatibility spelling with the same local-only behavior. A source has `freshness: not_revisited`, last recorded read time and coverage; `cache_status` distinguishes `not_saved`, `verified` historical bytes and `damaged`. `recorded` means the prior reading note is available, never that current remote contents have been verified. Missing/unread coverage and actual damaged evidence remain visible and reviewable. Unknown source IDs/versions do not become verified.

A preserved historical source with no new visit does not invalidate intact execution evidence. On a failed revisit, append the attempt/gap to ordinary notes while retaining the last actual reading and its extracted claims; do not replace historically read coverage with a claim that the source was never read. When actual reading finds relevant requirement changes, compare their impact and preserve still-useful results/history. In the optional structured helper, updating native extracted claims or a legacy snapshot creates a source change and dependent results remain reviewable until an actual comparison or new run supports current use. `source_reviews` documents source impact; `review-result` can record a grounded non-impact assessment for a specific result. Neither is required for native notes, and neither substitutes for actual evidence. Local/source/input/output/execution-identity checks remain in force. Snapshot damage is reported as historical evidence damage separately from `freshness`; investigate its actual relevance rather than inventing a remote change or forcing unrelated reruns.
