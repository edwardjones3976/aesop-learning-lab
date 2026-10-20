# First real learner run: runbook

This runbook covers one real person using the Foreman preview on content `m2-draft.9` over at least 14 days. It records first answers and actual delays faithfully. It does not test whether the method works: one learner gives dependent, descriptive observations, and the answer keys are still candidates until independent human review.

Known software gaps this runbook works around are listed at the end. Each is tracked for a fix.

## Before day 0

1. **Confirm consent before anything is opened.** Opening the preview already records a learner identity, an experiment assignment and a lesson exposure time, so consent comes first. The learner agrees to all of the following:
   - Their answers, hint use, confidence, outside-study notes and timing are stored **on this computer only**.
   - The data is not sent to any outside service, including AI models. Only a de-identified aggregate summary, written locally by the owner, may leave this computer or appear in a project report.
   - They can stop at any time.
   - They can ask for deletion of the database, the export and the run log (step 15).
2. **Pin one code revision for the whole run.** Run every session, day 0 and every return, from a dedicated worktree at one commit, so code and content cannot change mid-run:

   ```powershell
   git worktree add ..\aesop-learner-01 --detach origin/master
   cd ..\aesop-learner-01
   git rev-parse HEAD   # record this SHA in the run log
   ```

   At every return, run `git rev-parse HEAD` in that folder and confirm it matches the recorded SHA before starting the server.
3. **Use a fresh, separate database, and check that it really is unused.** The preview reopens an existing database silently, which would mix two sessions. Pick a new learner code, and stop if the file already exists:

   ```powershell
   if (Test-Path .local/learner-01.sqlite3) { throw 'learner-01 database already exists: choose a new learner code' }
   py scripts/run_foreman.py --port 8780 --db .local/learner-01.sqlite3
   ```

   Only then open <http://127.0.0.1:8780/>. For later returns, start the same command without the check; it must reopen this learner's file. The server binds to loopback only.
4. **Record the setup in a run log** kept outside the repository: the learner code (e.g. `L01`), the start date and time zone, the pinned SHA, the content version shown in the notice (`m2-draft.9`), and the browser.
5. **Brief the learner, and say nothing more:**
   - Answer first, before opening any hint.
   - Confidence is optional.
   - Please **don't study these topics outside the app** during the run. If you do, tell the owner which concept, and that concept's later checks will be excluded.
   - There are no grades: matches are compared with draft keys.

## Day 0: study and first practice

6. For each concept the learner chooses to start, they read the worked answer, press **I've studied the worked answer**, and answer the next question **before** opening any hint.
7. Do not help, explain answers or show the key. If they are stuck, they may use the in-app hints; the hints are recorded as assistance.
8. **Note in the run log** any interruption: closing the tab, a crash, or a restart.
   - If the answer had already been saved, confirm after the restart that it still shows as **Saved first answer to resume**.
   - If the tab closed **before** the learner pressed **Save first answer**, nothing was stored. Log that first answer as **lost before save**. Do not ask the learner to retype it as if it were the first answer.
   - A first answer must never be rewritten.

## Return checks

Delayed checks are offered only when their prerequisites are met:
- A **day-1 check** needs an unassisted candidate-key match on the concept's practice.
- A **week check** needs that, **and** an answered day-1 check. Any score counts, so that poor retention is still measured.

If the prerequisites are not met, the app offers practice or the still-unused earlier check instead. That is the system working as designed. Never coach the learner or retry anything to create a qualifying answer.

9. **Day 1:** return at least 24 hours after a lesson, without reviewing its answer first.
   - If a day-1 check is scheduled, the review box reads **Delayed review due**. The learner takes the offered check unaided first.
   - If not, record "no qualifying day-0 answer, no day-1 check offered", and let the learner continue with what the app suggests.
10. **Days 7 to 14:** this is the primary window for protocol v6. Prefer a return between day 7 and day 14.
    - If the week check's prerequisites are met, it is offered. A check taken before day 7 shows as **early**, and one after day 14 as **late**. Both are kept but excluded from the primary observation.
    - If they are not met, record which prerequisite is missing, and let the learner take whatever is offered (practice, or the unused day-1 check). That concept has **no primary observation** for this run.
11. **At each return, log:** the date and time, the SHA check from step 2, which activity was offered and why (the **Why this activity?** text), whether a hint was opened, and **any outside study** of each concept since the last visit.
12. **If the learner returns after day 14** and the week check's prerequisites are met, the unused week check is still offered. Let them take it **once**. The app records that first response as **late**. An outcome is **missing** only when no check was ever taken. Never change a timestamp or re-run an answered check. Missing outcomes are reported, not imputed.

## After the run

13. **Capture the data locally,** while the server is still running:
    - **Export data** in the preview downloads `aesop-foreman-data.json`: raw records plus display preferences.
    - The computed classifications (provisional, contaminated, invalid, early, late, missing) are **not** in that export. Save them separately:

      ```powershell
      curl.exe -s http://127.0.0.1:8780/api/v2/overview -o overview-L01.json
      ```

    Store both files with the run log, outside the repository.
14. **Write the report locally,** under the [report rules](#report-rules).
    - The owner produces a **de-identified aggregate** on this computer: counts and delays per category, with no answer text, free-text notes or timestamps finer than a day.
    - Only that aggregate may be shared with an agent (e.g. Codex) for drafting or review.
    - Raw exports, the overview file and the run log never leave this computer unless the learner has explicitly consented to the specific processor and its retention.
15. **Delete,** if the learner asks. Deletion is the learner's or owner's decision, never an agent's. Do **not** use the preview's **Delete data** button: after deleting, it reloads the page, which immediately enrolls a new learner. Instead:
    1. Close the preview tab.
    2. Stop the server with Ctrl+C.
    3. Delete `.local/learner-01.sqlite3`, plus any `-wal` or `-shm` files beside it.
    4. Clear this site's data in the browser (site settings for `127.0.0.1:8780`).
    5. Delete `aesop-foreman-data.json`, `overview-L01.json`, the run log, and every copy of them.
    6. Record only that a deletion took place, with the date.

## Report rules

- Report each classification as its own category; never fold them together. That includes independent (unassisted), assisted, early, late, missing and ungraded, plus **provisional**, **contaminated** and **invalid**. With draft keys, otherwise eligible on-time answers are classified **provisional**, not eligible.
- **Outside study:** any delayed outcome on a concept the learner studied outside the app is **ineligible**. Label it "outside study" and exclude it from every primary count, even if the app shows it as provisional or eligible (see gap 3 below).
- Say "candidate-key match", never "mastery" or "learned", until the keys are human-reviewed.
- Keep `insufficient_evidence` wherever the protocol's thresholds are not met. One learner never meets the 20-learners-per-arm gate.
- Report the actual delay next to the target delay.
- List interruptions, lost-before-save answers, missing prerequisites and any software problems found.
- No names or personal details in the repository or in PRs.

## Roles

| Step | Who |
|---|---|
| Steps 1 to 13: consent, running the sessions, capturing data | owner (with the learner) |
| Step 14: de-identified aggregate | owner, locally |
| Step 14: report drafting from the aggregate only | owner, or an agent given only the aggregate; reviewed by a non-author |
| Step 15: deletion | learner or owner only |
| Fixing software problems found | normal PR flow: one author and one non-author reviewer |

## Known software gaps (tracked for fixes)

1. **Delete data re-enrolls immediately:** the button reloads the page after deleting, which creates a new learner. The workaround is step 15.
2. **The export omits computed classifications.** The workaround is step 13's overview capture.
3. **Outside study is not used by the classifier:** responses after reported outside study are not marked ineligible automatically. The workaround is the manual outside-study rule.
