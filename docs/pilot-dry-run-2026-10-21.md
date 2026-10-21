# Pilot-readiness dry run — 2026-10-21

Result: **7 PASS, 2 FAIL, 7 OWNER-ONLY** across the 16 numbered steps in
`docs/real-learner-runbook.md`. This is software validation with synthetic inputs,
not learner evidence or authorization to recruit. No real person participated.

Tested revision: `23fa0e19bdbe5cdcfbce338167d7c7280adcce76`, branch
`docs/pilot-dry-run`, content `m2-draft.11`, content identity `v11`, protocol `v8`,
seed `20261021`. The ratified plan was read from the existing owner planning
directory, `C:/Users/edwar/aesop-declutter-plan/next12r2-final.md`; it is not in
this worktree. Four worktrees existed at task start; none was added to the
project. No push, PR, comment, approval or merge was performed.

## Method and step results

`scripts/pilot_readiness_dry_run.py` drives the actual `Preview` API against a
fresh temporary SQLite database and reopens it to simulate a restart. Its clock
starts at 2026-10-21 12:00 UTC. Four lessons finish at day 0; the fifth finishes
at day 0.25. Visits occur at days 1.001, 2.001, 6.999, 7.001, 14.001 and
14.251, so every started concept's window has closed before final export.
Candidate keys supply deterministic synthetic answers; this is never advice to
coach a learner. A separate fresh database serves real HTTP and Chromium checks.
Temporary databases, downloads and overview files are removed by the helpers.

OWNER-ONLY means the human action was not simulated as consent or an owner
decision; the associated software claims were checked as described. UI wording
below was checked through Chromium or the passing renderer contract tests; API
values were checked against live `Preview`/HTTP responses. Renderer checks do
not imply a 14-day browser session.

| Step | Result | Action and actual software behavior; gap where applicable |
|---|---|---|
| 1 — Consent first | OWNER-ONLY | No consent conversation or enrollment of a person. Fresh overview/export created no identity or assignment. Opening a lesson created identity, assignment and exposure records. Browser boot calls that lesson endpoint automatically. Thus the warning about opening the preview is true; there is no in-app consent gate (G1). Local SQLite and loopback serving were checked, but a comprehensive network/privacy audit was not performed. |
| 2 — Run variables | PASS | Checked PowerShell expansion and every consumer against the repo. `$code`, `$sha`, `$wt`, relative `$db` and external `$runDir` are consistent; `$wt\$db` resolves the intended SQLite path when the current directory really is `$wt`. A real approved SHA must replace the placeholder. `L01` is a template, not proof of uniqueness. The synthetic run uses temporary paths instead of creating a learner worktree or owner run folder. |
| 3 — Fresh pinned setup | FAIL | `py scripts/run_foreman.py --port 8780 --db ...` works; the script exists and accepts both flags. The actual server binds `127.0.0.1`. Reviewed the existence, SHA and dirty checks. Also executed the setup block in an isolated nested synthetic Git repository with an impossible target beneath a file. Git emitted `fatal: could not create leading directories of ...`; `cd` emitted `Cannot find path ... because it does not exist.` Execution nevertheless reached a harmless `py` stub printing `WOULD CREATE DATABASE IN WRONG WORKTREE`. The current directory happened to be clean and at the pinned SHA. Gap: native-command and directory-change failures do not stop this block (G2). No extra project worktree or real server was created by this negative test. |
| 4 — Return setup | FAIL | Reopened the same synthetic database successfully, preserving answers. Then executed the return block from the clean nested synthetic repository with an absent `$wt`, matching SHA and an existing database sentinel. The failed `cd` left the old directory active; all subsequent guards passed and the harmless stub printed `WOULD START SERVER IN WRONG WORKTREE`. Paths/flags are correct, but the block does not reliably enforce the stated stop-on-failure rule (G2). |
| 5 — Setup log | OWNER-ONLY | No owner run log was created. Browser notice actually read `Draft content · m2-draft.11 · Candidate answer keys; independent review remains required. Results are for development, not mastery claims.` The version and exact temporary database path were checked; recording browser, zone and approved revision remains the owner's action. |
| 6 — Briefing | OWNER-ONLY | No learner was briefed. The app permits omitted confidence and offers outside-study value `some`, displayed as `Yes, some outside study`. Its question is `Since studying this concept here, have you studied it elsewhere?` An answer with that value classified the later outcome `contaminated`. Post-submit feedback is compared with candidate keys. |
| 7 — Lesson and first practice | PASS | Opened and completed all five lessons through `lesson` / `complete_lesson`, then saved first answers through `first_answer` before hints. Lesson completion and exposure records persisted. Chromium showed `I've studied the worked answer →` and then `Save first answer →`. Practice payloads withheld unrequested hint text and keys; the worked lesson itself remains intentionally visible. |
| 8 — Assistance | PASS | Saved an answer, requested a hint, and submitted. Hint API returned level `nudge`; submission reported `assisted: true`, and hint history survived storage. This assisted-only concept did not qualify for a day-1 check. Hints are available only after saving in the normal UI. No human assistance was given. |
| 9 — Interruptions | OWNER-ONLY | Run-log writing remains human. Closed/reopened the Preview store after saving: the session returned the identical `firstAnswer`; renderer tests showed `Saved first answer to resume`. A changed first answer was rejected with HTTP status 409 and exact API message `This answer ID already belongs to another answer.` Requesting a session without saving left no draft. Such an unsaved answer must be logged as `lost before save`; software cannot reconstruct it. |
| 10 — Day 1 | PASS | At day 1.001, a qualifying concept had `reviewSchedule.status: due`; renderer produced `Delayed review due`. At day 2.001 an unused day-1 check was `overdue`, rendered `Delayed review overdue`. Delayed activity had `checkDelayDays: 1`. Incorrect day-1 answers were retained. The concept with only hinted practice still received practice after its own day 1; no check was manufactured to qualify it. |
| 11 — Days 7–14 | PASS | At day 6.999 no week check was offered. At day 7.001 eligible concepts received `checkDelayDays: 7`. Another concept first answered its still-unused day-1 check incorrectly at day 7.001; immediately requesting the next session offered its week check, with exact reason `It is time for your day-7 question on something you have not seen before.` Left that week check unanswered and verified `missing` after its window closed. Another `missing` concept lacked qualifying practice. The overview also reported `missing` before closure, as the runbook explicitly warns. Early is a classifier-only fixture, explained below. |
| 12 — Return log | OWNER-ONLY | No human run log was fabricated. Session recommendation reasons and raw attempt context are available. The renderer labels these `Why this activity?`. After consuming both checks, the API reason was `Keep practicing. There is no new later question available.` Outside study is optional and defaults to `unknown`; the owner must record concept-specific declarations each visit. |
| 13 — After day 14 | PASS | At day 14.001, an unused day-1 check was still offered; after answering it, the unused week check was offered and recorded `late`. Resubmitting the same draft returned the same result without adding an attempt. The first response stayed decisive. No persisted timestamp was changed and no answered check was replayed to replace an outcome. |
| 14 — Local capture | PASS | Actual Chromium `Export data` download was named `aesop-foreman-data.json`; it included raw assignment/exposure records, `displayPreferences` and `derived.overview`. The controlled-clock export also included raw attempts/drafts/hints and matched `overview()` exactly. Real `curl.exe -s http://127.0.0.1:8780/api/v2/overview -o <temporary overview path>` succeeded and matched the browser download's overview. The runbook endpoint/path syntax is correct. Downloads were synthetic and temporary; no owner `$runDir` was used. |
| 15 — Report | OWNER-ONLY | No learner report or owner sharing decision was made. Checked exported categories and actual delays below. The export remained `insufficient_evidence`, with zero `eligible` observations and a fixed 20 independent learners per arm requirement. Owner aggregation must keep categories separate, omit answers/notes and reduce timestamps to days. Candidate-key review policy remains an owner prerequisite (G3). |
| 16 — Deletion | OWNER-ONLY | No decision about a person's data was made. On synthetic data, API deletion removed learner records, reopening preserved `deleted: true`, and opening a lesson failed with 409 `learner_deleted`. Chromium smoke tests showed `Your data was deleted`, retained the state across reload/settings changes, and enrolled again only after explicit `Start again`. The dry-run journey never pressed it. Actual file removal happened after connections/server closed. Browser site-data clearing, deleting every external copy and writing the deletion date remain owner actions, not verified by the app. |

## Export classifications

The final controlled-clock download payload (`Preview.export`, the same backend
used by `/api/v2/export`) contained these observations in `derived.overview.experiment`:

| Concept | Classification | Target / actual delay; reason |
|---|---|---|
| function-definition-and-return | `provisional` | Week target 7 days; actual 7.001 days (604886.4 seconds), unassisted candidate-key match with draft keys. |
| parameters-and-local-scope | `contaminated` | Week target 7 days; actual 7.001 days from raw attempt and lesson-completion records; structured outside-study report `some`. |
| recursion-as-self-call | `missing` | Week target 7 days; week check left unanswered after an incorrect day-1 response unlocked it; own window closed before final export. |
| base-case | `late` | Week target 7 days, window through day 14; actual 14.001 days (1209686.4 seconds). |
| recursive-case-and-trace | `missing` | Lesson completed at day 0.25; only hinted practice, so qualifying practice/day-1 prerequisites absent. Final export at day 14.251 is after this concept's own window. |

Counts: provisional 1, contaminated 1, missing 2, late 1, eligible 0. Assistance
is also recorded in raw attempts and concept evidence; it must not be combined
with independent evidence. In the primary experiment classifier, a hinted
primary answer is `contaminated`, not a separate `assisted` primary category.

`early` cannot be generated by following the normal monotonic-clock scheduler:
it refuses week checks before day 7. The retained helper therefore constructs
one **in-memory** copy of the provisional attempt at day 6.999 and passes it to
the exact v8 analyzer used by export. It returned `early`, with no eligible
observation. A subsequent assertion verified the persisted export was unchanged.
This checks the classification rule, not an early browser journey. No stored
timestamp was edited. Existing boundary tests also cover early/late classification.

`derived.overview` has actual delay on provisional/late observations; contaminated
observations omit it there. Raw records still contain the required timestamps,
so the owner can calculate their delays without imputation (G4). No response
means no actual response delay for `missing`.

## Gaps

1. **BLOCKER — Consent is procedural only (G1).** Browser boot opens a lesson,
   creating identity, assignment and exposure before any in-app confirmation.
   The runbook's consent-first owner workaround is accurate, but this is not
   ready for an unattended real learner. **Ratified step 8** supplies the gate
   and consent wording; step 9 remains the owner's go/no-go.
2. **SHOULD-FIX — Setup/return blocks can continue in the wrong directory (G2).**
   Reproduced for runbook steps 3 and 4 under PowerShell's default nonterminating
   error behavior. Validate native exit codes, make directory changes terminate
   on failure, and verify the resolved worktree directory before starting. A
   matching clean SHA alone cannot distinguish two worktrees containing different
   learner databases. **No ratified step explicitly fixes these command guards.**
   Fix and recheck them before using these commands for a real learner.
3. **BLOCKER — Owner key-review/reporting policy decision remains outside this
   dry run (G3).** Software correctly returns `provisional` and
   `insufficient_evidence`; it does not supply the owner's written decision on
   qualified review versus permanent provisional reporting. **Ratified step 11**
   supplies that decision and is an explicit prerequisite for step 9. This is
   a governance dependency, not a classifier failure or a claim that an external
   owner decision was exhaustively searched for.
4. **NOTE — Some delay reporting requires raw-record arithmetic (G4).**
   `contaminated` observations omit `elapsedDays`/`elapsedSeconds` in the primary
   derived observation. The raw export makes the runbook's actual-delay report
   possible, but the owner must join the first attempt to its lesson completion.
   **No ratified step explicitly fixes this presentation gap.**
5. **NOTE — Early checks are defensive classifier coverage (G5).** The normal
   scheduler prevents early week responses; this dry run covered `early` with
   an in-memory v8 fixture rather than an impossible normal-path session.
   **No ratified fix required.** Browser clearing, consent, comprehensive privacy
   assurance and owner reporting remain outside automated software validation.

## Commands and verification

Commands ran in this worktree (PowerShell); supporting reads used `Get-Content`
and `rg` against the runbook, plan, server, scheduler, classifier, UI and tests:

```powershell
git status --short
git worktree list
git branch --show-current
git log -1 --format='%H'
py --version
py scripts/run_foreman.py --help
py scripts/pilot_readiness_dry_run.py
$env:PYTHONPATH='src'
py -m unittest discover -s tests -p test_foreman_http.py
py -m unittest discover -s tests -p test_personal_pilot_journey.py
py -m unittest discover -s tests -p test_key_outcome_locks.py
py -m unittest discover -s tests -p test_foreman.py
py -m unittest discover -s tests -p test_experiment_v2.py
node --test tests/foreman_web_contract.test.mjs
npm ci --prefix tests/browser --ignore-scripts
npm test --prefix tests/browser
node tests/browser/dry-run-download.mjs
git diff --check
```

Results: controlled-clock helper PASS; Python HTTP 1/1, journey 1/1, key locks
3/3, Preview 24/24, classifier/boundaries 13/13; renderer contracts 36/36; Chromium 5/5; actual browser
download/curl helper PASS. One initial helper run failed because its synthetic
wrong-answer generator assumed every item had choices; corrected the helper to
support text answers, then reran successfully. No application defect inferred
from that harness error. The full unrelated suite was not run.

The two command-negative reproductions used a clean nested Git repository under
`.local/dry-run-command-check`, local synthetic commits, and a PowerShell function
`py` that only printed the would-start marker. For step 3, `$wt` was an impossible
child of a file; for step 4, it was an absent directory. `$sha` matched that nested
repository. The numbered runbook blocks were otherwise used directly, including
their SHA/dirty/database checks. This setup never launched a server on the
sentinel file and never changed project worktree registration. The ignored
synthetic fixture was removed after the check.

Only this report and two reusable synthetic validation helpers are committed.
The runbook and application code are unchanged. Independent Claude review and
Cursor merge remain outstanding.
