# Foreman local preview

This branch is a separate development preview of the draft Python functions and recursion pack. It does not modify `master` or the existing web app.

Start it from the repository root:

```powershell
py scripts/run_foreman.py
```

Open <http://127.0.0.1:8775/>. The server binds only to the loopback interface and keeps learner data in `.local/foreman.sqlite3` within this worktree. It has no cloud account or public address.

If that database contains v1 learner records, the preview stays on `m1-draft.1` to preserve their original content. Any database with v2 learner events likewise remains on `m1-draft.2`. An empty database now starts on v3. Each local database has separate learner records; export them separately if needed.

For the new two-interval v3 draft, use a third local record and open <http://127.0.0.1:8777/>:

```powershell
py scripts/run_foreman.py --port 8777 --db .local/foreman-v3.sqlite3
```

The pack remains `draft`, with candidate answer keys. The original `m1-draft.1` pack is frozen, and its [scoped independent review](independent-content-review.md) requested four corrections. `m1-draft.2` addresses those findings but has **no independent review receipt**. `m1-draft.3` adds a distinct held-out family per concept at seven days and likewise needs independent review. Fresh local records use v3; existing v1 and v2 learner records stay on their original packs until explicitly deleted, so a restart does not reinterpret saved answers. The preview displays the active pack version. Automatic matches are development feedback only. The interface records a lesson completion when the learner presses the lesson button, saves each first answer before opening hints, persists each hint view, and links an idempotent attempt to the saved answer. Export and deletion include saved answers and hint views. Held-out checks are not mastery decisions.

The path now suggests the next concept and explains why: finish a saved answer, take a due held-out check, build one unassisted candidate-key match, or read the next prerequisite-ready lesson. Learners can choose another concept in **Your Path**. **Inspect learning evidence** shows separate recognition, recall, explanation, application, and transfer attempt counts, assisted and unassisted matches, and observed one-day and one-week check status. A one-week check is offered after seven days from lesson completion and an attempted one-day check, regardless of its score. This preserves evidence about weak retention. Each interval says `insufficient_evidence` until its own check is recorded. Family familiarity remains `not_verified` because lesson and example exposure is not yet logged. Confidence counts include only independent scored attempts with confidence recorded; no confidence calibration or probabilistic mastery estimate is inferred.

## Personalization boundary

The primary goal is better learning for each person; Python is the first subject used to build and evaluate the method. The preview now shows attempt, unassisted match, and hint-use signals alongside the scheduling reason. It offers local controls for time available, text size, a quiet view, and Light, Dark, or System appearance. System follows changes to the device's color scheme. These controls improve access and comfort but do not suppress retrieval, reveal hints before a first answer, or remove delayed checks. They are preferences, not a diagnosis of a fixed learning style. Settings live in this browser's local storage; attempt data lives in SQLite. The UI export includes both, and the UI delete action clears both.

This pilot has **not** shown that its personalization improves outcomes. The rules are transparent hypotheses to evaluate using delayed, unassisted, unfamiliar tasks and sustainable participation.

Research informing these guardrails:

- [Dunlosky et al. (2013), review of learning techniques](https://pubmed.ncbi.nlm.nih.gov/26173288/): practice testing and distributed practice have broad support across the reviewed settings.
- [Karpicke and Roediger (2008), retrieval experiment](https://doi.org/10.1126/science.1152408): retrieval practice can support later retention.
- [Pashler et al. (2008), learning-styles evidence review](https://doi.org/10.1111/j.1539-6053.2009.01038.x): evidence does not justify assigning instruction by a fixed style label.
- [Soderstrom and Bjork (2015), learning versus performance review](https://www.psychologicalscience.org/journals/perspectives/1745691615569000/): immediate ease or performance should not be treated as lasting learning.

Run checks with:

```powershell
$env:PYTHONPATH='src'
py -m unittest discover -s tests -q
cd web
npm test
```
