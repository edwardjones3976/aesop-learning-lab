# First real learner run: runbook

This runbook covers one real person using the Foreman preview on content `m2-draft.10` (protocol v7, the default for a fresh database) over at least 14 days. It records first answers and actual delays faithfully. It does not test whether the method works: one learner gives dependent, descriptive observations, and the answer keys are still candidates until independent human review.

Three software gaps found while reviewing this runbook have been fixed in the app; they are listed at the end.

## Before day 0

1. **Confirm consent before anything is opened.** Opening the preview already records a learner identity, an experiment assignment and a lesson exposure time, so consent comes first. The learner agrees to all of the following:
   - Their answers, hint use, confidence, outside-study notes and timing are stored **on this computer only**.
   - The data is not sent to any outside service, including AI models. Only a de-identified aggregate summary, written locally by the owner, may leave this computer or appear in a project report.
   - They can stop at any time.
   - They can ask for deletion of the database, the export and the run log (step 16).
2. **Set the run variables.** Paste this block at the start of **every** PowerShell window used for this run, on day 0, at each return, and in any second window. Every later command depends on it.

   ```powershell
   $code   = 'L01'                                # this learner's code; must be new
   $sha    = '<approved 40-character commit SHA>'  # the revision approved for this run
   $wt     = "$HOME\aesop-learner-$code"          # dedicated worktree for this run
   $db     = ".local/learner-$code.sqlite3"       # database path, relative to $wt
   $runDir = "$HOME\aesop-runs\$code"             # run data, outside every repository
   ```

   The owner chooses `$sha` before day 0: a specific reviewed commit, never a moving branch such as `origin/master`.
3. **Create a fresh, pinned setup, and refuse anything already in use.** The preview silently reopens an existing database, and an existing run folder would mix two learners' files. So the setup stops if either one exists, or if the pinned worktree does not match:

   ```powershell
   if (Test-Path $wt)     { throw "$wt already exists: choose a new learner code" }
   if (Test-Path $runDir) { throw "$runDir already exists: choose a new learner code" }
   git worktree add $wt --detach $sha
   cd $wt
   if ((git rev-parse HEAD) -ne $sha) { throw 'worktree is not at the approved SHA' }
   if (git status --porcelain) { throw 'worktree has local changes' }
   if (Test-Path $db) { throw "$db already exists: choose a new learner code" }
   New-Item -ItemType Directory $runDir | Out-Null
   py scripts/run_foreman.py --port 8780 --db $db
   ```

   Only then open <http://127.0.0.1:8780/>. The server binds to loopback only, and it keeps this window busy while it runs.
4. **At every return,** paste the step 2 block, then verify before starting the server. Stop and do not run the session if a check fails:

   ```powershell
   cd $wt
   if ((git rev-parse HEAD) -ne $sha) { throw 'worktree is not at the approved SHA' }
   if (git status --porcelain) { throw 'worktree has local changes: do not run' }
   if (-not (Test-Path $db)) { throw "$db is missing" }
   py scripts/run_foreman.py --port 8780 --db $db
   ```
5. **Record the setup in a run log** kept in `$runDir`: the learner code, the approved SHA, the worktree path, the **exact database path** (`$wt\$db`), the start date and time zone, the content version shown in the notice (`m2-draft.10`), and the browser. If the notice shows any other version, stop: the setup is not the approved one.
6. **Brief the learner, and say nothing more:**
   - Answer first, before opening any hint.
   - Confidence is optional.
   - Please **don't study these topics outside the app** during the run. If you do, choose **some** in the app's outside-study question when it is offered, and tell the owner which concept. That concept's later checks will be excluded.
   - There are no grades: matches are compared with draft keys.

## Day 0: study and first practice

7. For each concept the learner chooses to start, they read the worked answer, press **I've studied the worked answer**, and answer the next question **before** opening any hint. Record the date each concept's lesson is completed: that concept's delayed checks are timed from it.
8. Do not help, explain answers or show the key. If they are stuck, they may use the in-app hints; the hints are recorded as assistance.
9. **Note in the run log** any interruption: closing the tab, a crash, or a restart.
   - If the answer had already been saved, confirm after the restart that it still shows as **Saved first answer to resume**.
   - If the tab closed **before** the learner pressed **Save first answer**, nothing was stored. Log that first answer as **lost before save**. Do not ask the learner to retype it as if it were the first answer.
   - A first answer must never be rewritten.

## Return checks

**Every interval is counted per concept, from that concept's own lesson completion, not from the first day of the run.** Concepts started on different days have different windows. Keep a small table in the run log with one row per concept: lesson date, day 1 date, and the day 7 to day 14 window.

Delayed checks are offered only when their prerequisites are met:
- A **day-1 check** needs an unassisted candidate-key match on the concept's practice.
- A **week check** needs that, **and** an answered day-1 check. Any score counts, so that poor retention is still measured.

If the prerequisites are not met, the app offers practice or the still-unused earlier check instead. That is the system working as designed. Never coach the learner or retry anything to create a qualifying answer.

10. **Day 1 of each concept:** return at least 24 hours after that concept's lesson, without reviewing its answer first.
    - If a day-1 check is scheduled, the review box reads **Delayed review due** on the first day after the due time, and **Delayed review overdue** after that. The learner takes the offered check unaided first.
    - If not, record "no qualifying day-0 answer, no day-1 check offered", and let the learner continue with what the app suggests.
11. **Days 7 to 14 of each concept:** this is the primary window (protocol v7 keeps v6's windows). Plan a return inside it for every started concept.
    - If the week check's prerequisites are met, it is offered. A check taken before day 7 shows as **early**, and one after day 14 as **late**. Both are kept but excluded from the primary observation.
    - If they are not met yet, let the learner take whatever is offered (practice, or the unused day-1 check), then press **Continue** and look again. Answering the day-1 check completes that interval, so the week check may be offered straight away. If it is offered within that concept's days 7 to 14, it is a valid in-window observation: take it.
    - A concept's outcome is **missing** only if its week check is still unanswered when **that concept's** window closes. The overview may show `missing` earlier, before the window has even opened; ignore that until the window closes. Note which prerequisite was missing.
12. **At each return, log:** the date and time, the result of the step 4 checks, which activity was offered and why (the **Why this activity?** text), whether a hint was opened, and **any outside study** of each concept since the last visit.
13. **If the learner returns after a concept's day 14** and its week-check prerequisites are met, the unused week check is still offered. Let them take it **once**. The app records that first response as **late**. Never change a timestamp or re-run an answered check. Missing outcomes are reported, not imputed.

## After the run

The run ends only when the window of **every** started concept has closed.

14. **Capture the data locally,** while the server is still running. The server keeps its own window busy, so:
    1. Open a **second** PowerShell window.
    2. Paste the step 2 block there first; without it the paths below are empty.
    3. **Export data** in the preview downloads `aesop-foreman-data.json`: raw records, display preferences, and the computed classifications (`derived.overview`). Move it from the browser's download folder into `$runDir` straight away.
    4. Optional cross-check: save the live `/api/v2/overview` endpoint directly into `$runDir`, never into the worktree, because the file holds raw answers and timestamps:

       ```powershell
       if (-not (Test-Path $runDir)) { throw 'run variables are not set: paste the step 2 block' }
       curl.exe -s http://127.0.0.1:8780/api/v2/overview -o "$runDir\overview-$code.json"
       ```
15. **Write the report locally,** under the [report rules](#report-rules).
    - The owner produces a **de-identified aggregate** on this computer: counts and delays per category, with no answer text, free-text notes or timestamps finer than a day.
    - Only that aggregate may be shared with an agent (e.g. Codex) for drafting or review.
    - Raw exports, the overview file and the run log never leave this computer unless the learner has explicitly consented to the specific processor and its retention.
16. **Delete,** if the learner asks. Deletion is the learner's or owner's decision, never an agent's.
    1. In the preview, press **Delete data** and confirm. The page shows "Your data was deleted". Do **not** press **Start again**: that would enroll a new learner.
    2. Close the preview tab, then stop the server with Ctrl+C.
    3. Paste the step 2 block, then delete the database file (after the in-app delete it holds only the schema and the deletion marker) at the **exact path recorded in the run log** (`$wt\$db`), plus any `-wal` or `-shm` files beside it.
    4. Clear this site's data in the browser (site settings for `127.0.0.1:8780`).
    5. Delete everything in `$runDir` (the export, the overview and the run log) and every copy of them, including the browser's download folder.
    6. Record only that a deletion took place, with the date.

## Report rules

- Report each classification as its own category; never fold them together. That includes independent (unassisted), assisted, early, late, missing and ungraded, plus **provisional**, **contaminated** and **invalid**. With draft keys, otherwise eligible on-time answers are classified **provisional**, not eligible.
- **Outside study:** from protocol v5 the app classifies a delayed check given after outside study reported in the app as **contaminated**. If the learner told the owner about outside study but it was **not** entered in the app, exclude that concept's later outcomes by hand, labeled "outside study (reported to owner)".
- Say "candidate-key match", never "mastery" or "learned", until the keys are human-reviewed.
- Keep `insufficient_evidence` wherever the protocol's thresholds are not met. One learner never meets the 20-learners-per-arm gate.
- Report the actual delay next to the target delay.
- List interruptions, lost-before-save answers, missing prerequisites and any software problems found.
- No names or personal details in the repository or in PRs.

## Roles

| Step | Who |
|---|---|
| Steps 1 to 14: consent, running the sessions, capturing data | owner (with the learner) |
| Step 15: de-identified aggregate | owner, locally |
| Step 15: report drafting from the aggregate only | owner, or an agent given only the aggregate; reviewed by a non-author |
| Step 16: deletion | learner or owner only |
| Fixing software problems found | normal PR flow: one author and one non-author reviewer |

## Software gaps found in review, now fixed

These were found during review of this runbook. Each has been fixed in the app, so the earlier workarounds are no longer needed:

1. **Delete data re-enrolled the learner immediately** (fixed in #42). After deleting, the app shows "Your data was deleted", and the server refuses every enrollment (409 `learner_deleted`), even after a page reload or a settings change, until **Start again** is pressed.
2. **The export omitted the computed classifications** (fixed in #41). The download now includes them in `derived.overview`.
3. **The classifier ignored reported outside study** (fixed in #40). From protocol v5 onward, a delayed check given after outside study reported in the app for that concept is classified `contaminated`.
