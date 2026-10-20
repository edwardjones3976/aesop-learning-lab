# v6 content author audit

**Candidate:** `python-functions-recursion`, `m2-draft.6` (`v6` content). This is an author audit, not independent or human approval. The pack remains `draft`, all 26 scored keys remain `candidate`, and there are no approval receipts.

The v6 pack preserves the five v5 lessons, their common text and labeled diagrams, 32 activities, cited Python sources, and the one-day/seven-day review structure in a new immutable content version. Lesson and activity IDs end in `-v6`; v5 remains unchanged. Each scored item now has a specific `common_mistakes` list for post-submission feedback in addition to its candidate key and worked `explanation`. The six explanation/code-design items remain ungraded and retain rubrics. The API/UI must not expose keys, worked explanations, or mistake rationales before answer submission.

## Corrected evidence-family boundaries

| Item | Correction | Reason |
| --- | --- | --- |
| `scope-global-choice-01-v6` | Shares family `scope-local-trace-a` with `scope-local-trace-01-v6` | Both use the same `add_five(total)` stimulus; they cannot count as independent item families. |
| `base-case-transfer-01-v6` | New family `base-case-grow-threshold-day-v6`; traces 3 → 10 → 17 → 24 toward `n >= 20` | The prior list-slice recursion overlapped routine `sum_list` design practice. The new item uses neither list slicing nor the seven-day factor-of-two recurrence. |
| `recursive-case-week-01-v6` | New family `recursive-case-lamp-toggle-week-v6`; alternates `off`/`on` using the prior call's result | The v5 digit-count recurrence resembled another concept's seven-day floor-division-and-additive-unwind item. The new item requires a different combination rule. |

The other seven-day family IDs remain `def-return-shipping-week-v4`, `scope-caller-local-default-week-v5`, `recursion-nested-wrap-week-v5`, and `base-case-threshold-halving-week-v4`. A prospective protocol must explicitly pin the v6 pack and new recursive-case family; v1/v2 outcomes remain tied to their original materials.

## Verification and limits

The content regression test parses both versions; confirms new IDs, five lessons, 32 activities, 26 candidate scored keys, complete hint ladders, and separation between held-out families, worked examples, and routine practice; and executes only the repository-authored trace snippets to compare actual results with candidate keys. It does not execute learner-submitted code. The family check is a finite content audit, not proof that every human learner will find a problem unfamiliar. A non-author subject-matter reviewer must check the new item wording, pedagogical fit, candidate keys, hints, misconceptions, and family judgments before any reviewed-content claim or scoring receipt.
