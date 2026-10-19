# Scope comparison v2 content and engineering review

**Status:** Draft educational content. Nonauthor AI engineering review completed 2026-10-18; qualified human subject-matter validation has not occurred.

**Reviewed source:** `src/aesop_lab/api/personal_comparison.py`, SHA-256 `ac24275fbb6681151a142d9a01143ecf6dea5dd1b2b211ae34da2aadf002d351`. This receipt applies only while that exact source hash remains unchanged. The frozen historical v1 module has SHA-256 `3930248ed8cc63eb740f9145e9019094796878fc04083d93f6028f12e5516a16`.

**Subsequent source revision:** The current source SHA-256 is `98822a1434f10055fbaa269f0c80cd84158de361cd6047af5582f7255baae2e4`. Its fixed Python snippets, diagrams, keys, and item-family identifiers are unchanged. The revision records explicit candidate-solution openings after first answers and rejects malformed unit identifiers. The earlier source-hash receipt is historical; the revised exact commit requires its own engineering review receipt before integration. Qualified human content validation remains outstanding.

**Reviewer:** `/root/repo_science_audit`, a read-only nonauthor AI engineering agent. It authored no candidate content or source files. This is an AI technical review, not a credentialed human curriculum review.

**Scope:** The reviewer checked all twelve fixed Python snippets and numeric keys against trusted Python execution, the four worked binding/return diagrams, common misconceptions, worked and answer steps, the two practice hint levels, normalized statement/expression structure, held-out separation, approximate within-pair operation counts, old v1 routing, and evidence classifications. Learner-submitted code was never executed.

**Findings and dispositions:**

- V1 worked and practice tasks were chiefly renamings and numeric changes. V2 practice in each unit now requires additional branch or local-rebinding reasoning and has a distinct structure; old v1 content and assignments remain readable.
- A single generic hint did not form a ladder. V2 has two ordered hints, each persisted; either makes the later first answer assisted.
- The first implementation omitted the pre-exposure Open button. Browser verification exposed the blocker; the study card now offers the button before revealing content and has a frontend regression.
- A shared answer route initially passed v2 confidence to pinned v1. The frozen v1 handler now accepts and ignores that optional field, preserving the old response record. A route regression covers it.
- An override initially risked losing the chosen unit between study and practice. The saved choice now carries through practice, then reoffers the due held-out family. Regression and browser checks cover the transition.
- A delayed no-hint response classified contaminated or outside-study-unknown was initially described as independent retention. The dimension report now counts only eligible unfamiliar delayed responses there and keeps other recorded responses descriptive.

**Remaining limits:** The new practice introduces more control flow and local updates than the worked task; it is an application challenge, but empirical difficulty equivalence has not been established. Pair A/B and C/D are approximately matched structurally, not experimentally calibrated. Four units in one concept invite carryover. Technical key correctness and code-family separation do not demonstrate true learner unfamiliarity, educational validity, or a diagram effect. The report must remain `insufficient_evidence`.
