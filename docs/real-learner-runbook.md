# First real learner run: runbook

This runbook covers one real person using the Foreman preview on content `m2-draft.9` over at least 14 days. It records first answers and actual delays faithfully. It does not test whether the method works: one learner gives dependent, descriptive observations, and the answer keys are still candidates until independent human review.

## Before day 0

1. **Use a fresh, separate database.** Do not reuse a development or test database:

   ```powershell
   py scripts/run_foreman.py --port 8780 --db .local/learner-01.sqlite3
   ```

   Open <http://127.0.0.1:8780/>. The server binds to loopback only, and the data stays on this computer.
2. **Confirm consent.** The learner agrees that their answers, hint use, confidence and timing are stored locally and may be summarized in a project report without their name. They can stop, export or delete at any time.
3. **Record the setup in a run log** kept outside the repository: the learner code (e.g. `L01`), the start date and time zone, the commit SHA (`git rev-parse HEAD`), the content version shown in the notice (`m2-draft.9`), and the browser.
4. **Brief the learner, and say nothing more:**
   - Answer first, before opening any hint.
   - Confidence is optional.
   - Study outside the app is fine but should be reported when asked.
   - There are no grades: matches are compared with draft keys.

## Day 0: study and first practice

5. For each concept the learner chooses to start, they read the worked answer, press **I've studied the worked answer**, and answer the next question **before** opening any hint.
6. Do not help, explain answers or show the key. If they are stuck, they may use the in-app hints; the hints are recorded as assistance.
7. **Note in the run log** any interruption: closing the tab, a crash, or a restart. After a restart, confirm the saved first answer still shows as **Saved first answer to resume**. A first answer must never be rewritten.

## Return checks

8. **Day 1:** return at least 24 hours after a lesson, without reviewing its answer first. The review box should read **Delayed review due**. The learner takes the offered check unaided first.
9. **Days 7 to 14:** return for the week check, which is the primary window for protocol v6.
   - A check taken before 7 days shows as **early**, and one after 14 days as **late**. Both are kept but excluded from the primary observation.
   - Prefer a return between day 7 and day 14.
10. **At each return, log:** the date and time, which activity was offered and why (the **Why this activity?** text), whether a hint was opened, and any outside study the learner reports.
11. **If the learner misses a window,** record it as missed. Do not back-fill or re-run it. Missing outcomes are reported, not imputed.

## After the run

12. **Export** from the preview's **Export data** control (it downloads `aesop-foreman-data.json` from `GET /api/v2/export`, including display preferences). Store the export with the run log, outside the repository.
13. **Write the report** under the rules in the [next section](#report-rules).
14. **Delete:** if the learner asks, use **Delete data** in the preview. Deletion is the learner's or owner's decision, never an agent's.

## Report rules

- Report independent (unassisted), assisted, early, late, missing and ungraded outcomes separately.
- Say "candidate-key match", never "mastery" or "learned", until the keys are human-reviewed.
- Keep `insufficient_evidence` wherever the protocol's thresholds are not met. One learner never meets the 20-learners-per-arm gate.
- Report the actual delay next to the target delay.
- List interruptions, outside study and any software problems found.
- No names or personal details in the repository or in PRs.

## Roles

| Step | Who |
|---|---|
| Steps 1 to 12: running the session and exporting | owner (with the learner) |
| Step 13: report draft | Codex, from the owner's export and log; reviewed by a non-author |
| Step 14: deletion | learner or owner only |
| Fixing software problems found | normal PR flow: one author and one non-author reviewer |
