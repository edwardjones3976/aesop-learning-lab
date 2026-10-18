# Scope comparison content review

**Status:** Draft content; nonauthor AI engineering review completed 2026-10-18. This is not qualified human subject-matter validation.

**Reviewed source:** `src/aesop_lab/api/personal_comparison.py`, SHA-256 `063409b48c843647d9beca7da102def4845c8fbea2c9fc388d9bb411ba98d30c`. The final Git commit must retain this hash for this receipt to apply.

**Reviewer:** `/root/independent_review`, read-only nonauthor engineering agent. The reviewer authored no candidate files.

**Scope examined:** All 12 fixed Python snippets and numeric answer keys, all four worked binding/return diagrams, misconceptions, approximate within-pair operation counts, normalized AST family separation, held-out answer protection, and evidence classification. The reviewer executed the trusted authored snippets through the focused test. No learner-submitted code was executed.

**Findings and dispositions:**

- A delayed submission could display feedback from a different unit. Feedback now selects the newest response by timestamp and event order.
- Delayed questions originally differed mainly by numbers and identifiers. They now have distinct statement/expression structures from every worked/practice item and each other, verified by a normalized-AST test.
- Due delayed checks could be held behind later new units. They now preempt new study when due.
- Worked completion initially claimed practice-family exposure before display. The family is now appended only when the practice question is opened.
- Unknown outside study and standard-path scope exposure could be mistaken for eligible evidence. They now receive ineligible classifications, including an opened but incomplete standard lesson and saved practice draft.
- Within-pair difficulty matching remains approximate. Each pair has similar statement and operation counts, but equivalence has not been established empirically.

**Review verdict:** No remaining blocking technical finding on the reviewed source and UI state. Candidate numeric keys and diagrams passed nonauthor AI engineering review. The content remains draft; true unfamiliarity, human difficulty comparability, and instructional effectiveness remain unvalidated. The software report must retain `insufficient_evidence` regardless of observed direction.
