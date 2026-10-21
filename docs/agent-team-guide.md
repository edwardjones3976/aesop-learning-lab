# Agent team guide

How the AI agents working on this repository split, check and land work. It complements the owner's operating rules; it grants no authority.

## Roles

| Role | Who | Does |
|---|---|---|
| Owner | the repository owner | Approves plans and makes every reserved decision: screen sign-off, human content review, real learner sessions, credentials and config, deletion, deployment |
| Admin #1 and Foreman | Codex | Decides first under human-out-of-the-loop (HOOTL) operation; Team B admin; handles maintenance and repairs |
| Admin #2 and integrator | Claude | Team A admin; integrates and verifies work. **Never merges.** |
| Admin #3 and reviewer | Cursor | Independent reviewer and merger |
| Workers | Antigravity; Grok (read-only consults); others once enabled | Bounded tasks inside one worktree, no commits; their admin commits |

## Rules that never change

- **One author and one distinct non-author reviewer per PR.** The reviewer either merges the exact reviewed commit (`gh pr merge N --merge --match-head-commit <sha>`) or returns notes to the author. Nobody merges their own work. Never use `--admin`, delete the branch, or approve via `gh pr review`.
- **One writer per file at a time.** For example, `foreman_web/app.js` has a single owning team until it is released.
- **Every behavior change ships with tests.** A test counts only after it has been shown to fail on a deliberate break. Documentation-only changes need no test; instead, every factual claim about the app (UI strings, endpoints, file paths, protocol rules) is checked against the code or the protocol doc before review.
- **The Codex GitHub reviewer's findings are answered before merge.** Each finding is either fixed or declined with a written reason on the PR by an admin.
- **No history rewriting** (rebase plus force-push) of shared branches without the owner's authorization. Merge `master` into the branch instead.
- **The owner alone** handles credentials, config files, deletion, deployment and publishing. Silence or an unavailable provider is never approval.
- **If a PR depends on an owner-reserved decision** (for example a screen sign-off or human key review), that decision must be recorded before the reviewer merges the exact reviewed commit.
- **"Candidate-key match", never "mastery"**, until the answer keys are human-reviewed.

## How work flows

1. The owner approves the plan. Admins split it into teams with even worker counts and file ownership, recorded in a plan file and a contract file that lists frozen IDs, test-asserted strings and learning invariants.
2. Each task gets its own Git worktree and branch from `origin/master`.
3. Workers get a bounded order: what to read, which files they may edit, acceptance checks and tests. They do not commit.
4. The admin reviews the diff, re-runs the tests, breaks the code on purpose to prove each new test, then commits.
5. A second opinion where it is useful: Grok and Codex review read-only on a shared thread until both say PASS.
6. The PR is opened. The non-author reviewer merges after checking the exact commit, the tests, green CI, and that any owner decision the PR depends on has been recorded.
7. Claude integrates across teams, runs every suite and a browser walkthrough, and writes the acceptance record.

## The review lane

Each PR moves through these steps in order. Each step catches mistakes the earlier ones miss: round 1 had a mislabelled arm count, a key that a wrong answer could also produce, and stale version metadata, and each was caught at a later step.

### Capacity
- **At most two agent jobs at once** on this laptop. Bridge calls, worker runs, Cursor MCP calls and Playwright runs all count. A third job has been killed for low memory.
- A plan wave names its two jobs and the files each owns. Later steps wait until a slot frees.

### Worktrees
- **At the start of every task**, count the leftover worktrees (`git worktree list`). Keep them at **four or fewer** before adding one. A session can die before its merge, so cleanup at merge time alone is not enough.
- **In the merge session**, remove the PR's worktrees: the author's and the reviewer's. Keep the branch.

### Author preflight
Before handing work to the integrator, the author confirms:
- **Version pins:** the current pack, content version, protocol version and seed agree everywhere the change touches them.
- **Arm minimum:** 20 independent learners per arm, matching `minimum_independent_learners_per_arm`.
- **Wording:** "candidate-key match", never "mastery", "learned" or a bare "correct" for draft keys.
- **New or changed held-out item:** every common mistake gives an answer different from the key, and the structural-similarity guard (`tests/test_heldout_similarity.py`) passes.

### Integration
The integrator (Claude) reviews the diff, re-runs every suite (Python, node contract, Playwright), and **breaks each new test on purpose** to show it fails before committing.

### Review and merge
- **The non-author reviewer** (Cursor) checks the exact head commit against the PR's stated contract. It merges with `gh pr merge N --merge --match-head-commit <sha>`, or returns findings.
- **The GitHub Codex reviewer:** judge new findings by `created_at` after the latest commit, because old comments move onto new commits.
- **Convergence rule:** after about four review rounds, only P1 or factually wrong findings block. Other findings are fixed or declined with a written reason.
- **Bot stall rule:** if the Codex bot shows "running" for more than 30 minutes, comment `@codex review` once. If it is still stalled, the merge may go ahead on a non-author review, green CI and an exact-SHA merge. Any finding it posts later is still fixed or declined.

## Talking to other agents

Use the agent bridge, `C:\Users\edwar\.claude\skills\agent-bridge\ask.ps1`:
- `-Thread <name>` keeps a conversation going across calls and agents.
- `-Template <name> -Set "KEY=value;..."` builds the standard orders (`review-merge`, `fix-order`, `worker-task`, `consult`, `report`).
- `-ReplyOnly` returns just the answer.
- `-Relay "a,b"` lets two agents iterate until one says AGREED.
- `-Status` shows which tools are signed in.

Bridge calls are read-only. Edits go through the worker route and need a separate linked worktree. Cursor's edit work needs its approval-gated MCP tool.

### Known quirks
- Codex read-only cannot read files here, so paste content into the prompt.
- Grok in read-only mode stops if it tries to run a command, so tell it "no shell commands".
- Cursor in read-only mode can return an empty reply; ask it to "answer in your reply text".
- Antigravity may save its answer to its own folder; ask it to "reply in text".
- Copilot was out of monthly quota on 2026-10-20.
- Cursor in read-only mode cannot read the owner's plan folder, so paste briefs into the prompt.
- Grok runs out of turns if a prompt invites it to read files, so give it everything inline and say "do not read files".
- The worker route rejects text that looks like a credential, including `answer_key:`. Rephrase it as "the answer_key field is" until the filter is fixed.
