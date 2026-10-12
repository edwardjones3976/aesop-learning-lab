# Module contracts and ownership

The dependency direction is `web -> api -> domain ports <- adapters`. The domain types and ports have no UI or database imports. Content, assessment, scheduling, and experiments communicate through versioned records. SQLite is an adapter, not the source of policy.

| Module | Owner | Public contract | Depends on |
|---|---|---|---|
| `domain` | Codex | Concept ID, content version, activity, attempt, hint event, outcome, learner evidence, recommendation, experiment assignment | Standard library only |
| `storage` | Codex | Repository ports for content, attempts, schedule, experiments; migrations; export and deletion | `domain` |
| `scheduler` | Codex | Pure `recommend(state, available_time, policy_version)` returning choice and reason | `domain` |
| `api` | Codex | Versioned HTTP or application service boundary; input validation and error shapes | Ports and services |
| `content` | Claude | Versioned programming pack and schema validator; source and review receipts | `domain` |
| `assessment` | Claude | Deterministic scoring, hint ladder, scoring limits, rubric hooks | `domain`, `content` |
| `experiments` | Claude | Fixed protocol, seeded assignment, exposure log, outcome summary with uncertainty | `domain`, repository ports |
| `web` | Cursor | Session, practice, review, and override screens | `api` only |
| `insights` | Cursor | Evidence view, comparison view, export/correction/deletion controls | `api` only |
| `authoring` | Cursor | Content preview and validation command/UI | `content` schema only |

## Contract rules

- IDs and content versions are immutable once attempts reference them. Corrections create a new content version.
- Every recorded attempt includes activity ID, content version, timestamp, first answer, assistance level, method, and selection reason. Optional confidence, response time, and outside-study notes remain explicitly optional.
- A score has a grading method and limits. An ungraded explanation stays ungraded until self or human review; passing code tests never asserts conceptual understanding.
- The experiment protocol is immutable during a run; policy changes create a new protocol version.
- API responses expose recommendation reasons and evidence scope. UI copy may explain them but may not invent unsupported conclusions.
- Add contract fixtures before modules depend on each other. Breaking changes require a version bump and all affected owner reviews.

## V1 decisions for independent implementation

- The content pack topic is **Python functions and recursion**. L1 owns a directed acyclic prerequisite graph and stable IDs. Every lesson, item, answer key, and source reference has a content version and a human review receipt with reviewer, date, and outcome.
- Activity types are `choice`, `trace`, `explanation`, and `code_design`. L1 tags each item with one evidence kind: `recognition`, `recall`, `explanation`, `application`, or `transfer`. Choice and trace can be deterministically scored against reviewed keys. Explanation and code design return `ungraded` pending rubric-based self or human review. No learner code is executed in V1.
- Hint levels are `none`, `nudge`, `targeted`, and `worked_solution`. Any hint beyond `none` makes the attempt assisted. Revealing a worked solution cannot create a correct first answer. Record first answer before any hint.
- L1 assigns an item family ID and marks held-out transfer items. An item is unfamiliar only when its family has not appeared in a prior lesson, example, practice item, or attempt for that learner. Transfer additionally requires a different context or application, documented by L1 and reviewed by L2.
- A concept reaches the V1 defined standard only after two correct, first-try, unassisted attempts from different item families, with one at least 24 hours after the prior lesson, plus one correct held-out application or transfer item. This is an operational pilot threshold, not a claim of permanent mastery.
- The first experiment compares a text explanation plus retrieval practice with the same explanation plus a labeled diagram and the same retrieval practice. L3 freezes versioned materials, time budget, assignment seed, matched concept pairs, primary outcome, and analysis rule before enrollment. Primary outcome is correctness on held-out, unassisted application items approximately seven days later. Report descriptive results and uncertainty; with too little data, report `insufficient_evidence` rather than a causal win.
- Within a comparison run, prompt for confidence before revealing the answer and prompt for outside study (`none`, `some`, `unknown`, plus optional detail). Outside comparison runs these fields remain optional. An unanswered prompt is recorded as missing, never silently interpreted as zero or none.

## Integration sequence

1. Codex lands domain records, ports, API examples, and a minimal SQLite migration.
2. Claude and Cursor build against the examples in isolated branches/worktrees; no shared-file edits during parallel work.
3. Integrate one vertical slice: lesson -> attempt -> hint -> score -> learner evidence -> next activity -> delayed review -> insights.
4. Integrate the fixed comparison only after the baseline slice passes. Re-run content validation and contract tests on the exact merge candidate.
5. Run a scripted local acceptance journey, keyboard check, export/delete check, and delayed-assessment clock simulation before release.
