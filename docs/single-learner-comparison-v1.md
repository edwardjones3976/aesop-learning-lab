# Personal scope comparison v1 (prospective feasibility protocol)

This draft protocol asks whether adding a labeled diagram to the same worked Python explanation and retrieval-practice routine is associated with better delayed independent tracing for one learner. It is a software and content feasibility pilot, not a causal test of instructional superiority. Historical text-versus-diagram protocols v1–v4 and their records remain separate.

## Design fixed before observation

| Field | Precommitted rule |
| --- | --- |
| Protocol | `scope-text-diagram-single-learner`, version `v1` |
| Content | `scope-comparison-draft.1`; `parameters-and-local-scope` only |
| Unit | One instructional micro-unit, with one worked example, one practice family, and one delayed held-out family |
| Sequence | Four fixed units in two approximately matched pairs (bonus A/B, step C/D). The SHA-256 low bit of protocol ID, version, seed `20261018`, and learner ID selects ABBA or BAAB. One unit in each pair receives each condition. Assignment is persisted before exposure and never recalculated over a saved assignment. |
| Treatment | Text: worked code, correct answer, identical steps and misconceptions. Diagram: those exact materials plus a labeled binding/return flow diagram. Practice procedure, hint, feedback, and delay are shared. |
| Eligibility | Enroll before any recorded lesson, attempt, or exposure on this concept. No replacement of older assignments. Outside study is recorded when supplied, with absent left absent. |
| Exposure | Record start and completion timestamps, condition, content version, and worked/practice family IDs. No attentive time is inferred. A practice or delayed question's first display is separately timestamped. |
| Primary outcome | First response to the unit's unfamiliar held-out trace, unassisted and with an explicit report of no outside study at both exposure completion and delayed response, first viewed and answered within 30 minutes, at least seven and at most 14 actual days after completion of its worked exposure. The candidate key must pass independent technical review before being treated as eligible. |
| Secondary outcomes | Practice candidate match and assistance, delayed candidate match outside the window, completion and missingness, actual elapsed delay. |
| Practice first answer | Only submission records and locks the first practice answer. A hint opened before submission marks that first recorded response assisted. Typed but unsubmitted text is not evidence; the interface must not silently erase it. Delayed primary questions offer no hints. |
| Contamination | A previously encountered held-out family, reported outside study, use of the standard lesson/practice path after enrollment, assisted delayed response, or interrupted held-out question over 30 minutes is ineligible. Unknown outside-study status is separately ineligible. Preserve each response and report its reason. No held-out answer is shown before the first response. |
| Missingness | Assigned units without completed exposure or delayed response remain missing; no imputation. Early and late returns are retained descriptively, not silently counted as eligible. |
| Analysis | Show counts and candidate matches by arm, per-unit classifications, and missing/contaminated/assisted counts. Four responses from one learner are dependent observations. Do not treat them as four participants or compute a conventional independent-sample interval. Status remains `insufficient_evidence` regardless of observed direction. |
| Uncertainty | No effect estimate supports method superiority: unit, order, prior knowledge, and carryover remain confounded. The same concept across four units creates expected learning carryover. No human learning benefit is implied by synthetic tests. |

The assignment was chosen to exercise both conditions within one learner while keeping a balanced condition count in each pair. Delayed code has different normalized Python statement/expression structure from every worked and practice item and from the other delayed items. This only protects structural family separation; the target scope skill repeats and carryover remains likely. The small number of units and repeated concept exposure make the results descriptive only. A later milestone needs qualified human content validation and more independent comparable units or learners before effectiveness claims.

The fixed answer keys passed nonauthor AI engineering review documented in `scope-comparison-content-review.md`, but content remains draft and the keys remain candidates for qualified human subject-matter validation. The engineering review checks technical correctness and structural separation; it does not establish empirical difficulty equivalence or actual learner unfamiliarity.
