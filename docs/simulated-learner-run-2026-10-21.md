# Simulated learner run, 2026-10-21

**Simulation only.** The learner was Antigravity, an AI model that already knows Python. Nothing here is evidence of human learning, retention or a method effect. The owner decided there is no real learner. Antigravity is the learner, Grok reviews and Cursor oversees.

## Setup
- **Harness:** `scripts/simulated_learner_run.py` drives the real `Preview` on a fresh database with a simulated clock. The software is master `d027498`: content `m2-draft.11`, protocol v8, consent gate v16.
- **What the learner saw:** each round showed only what a learner would see, a lesson or one question with its choices. Antigravity answered through the agent bridge from an empty folder, with no repository access, so it could not read answer keys.
- **Notebook:** the learner kept its own one-line lesson takeaways, plus whether each earlier answer matched. Keys and correct answers were never added.
- **Visits:** days 0, 1, 2, 4, 7, 8 and 10, with 50 rounds in total. Consent was recorded through the app (`consent-v1`), and outside study was answered "none" every time.
- **Data:** run data is kept outside the repository, in `C:\Users\edwar\aesop-sim-run-2026-10-21`: the transcript, prompts, export and findings.

## Results

| Measure | Value |
|---|---|
| Rounds | 50, with no harness or learner errors; average 22 s per round |
| Lessons | 5 on day 0. Methods: text for function-definition-and-return, parameters-and-local-scope and recursive-case-and-trace; diagram for recursion-as-self-call and base-case |
| Graded answers | 37, all matched the draft keys |
| Self-review items | 8, ungraded by design |
| Day-1 delayed checks | 5 of 5 matched |
| Day-7 delayed checks | 5 of 5 matched, including the new `recursion-week-01-v11` (`meet(0, 8)`, key 6) |
| Primary classification | all 5 concepts `provisional` (draft keys); report status `insufficient_evidence` |

The quoted answers (`'cba'`, `'[map]!:map'`) were accepted as stored quote variants. The lesson takeaways were accurate one-line summaries of each lesson.

## What this shows
1. **The software works end to end with an independent answering agent.** It covered consent, lessons, the method assignment, practice gating, both delayed checks at the right times, classification and export.
2. **The AI learner is at ceiling.** It matched every key under both methods. An AI learner that already knows the material cannot show any difference between methods, so this run cannot test the owner's goal of ranking methods per user.
3. **Ranking needs a different test.** It must be validated with synthetic learners whose accuracy depends on the method, with a known best method. That recovery study is part of the method-ranking design work (owner goal, 2026-10-21).

## Limits
- The learner is an AI with prior knowledge; it never asked for hints and reported no outside study.
- The same model answered every round, and its notebook was the only memory between rounds.
- There was no real elapsed time: the clock was simulated.
