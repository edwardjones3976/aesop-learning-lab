# Held-out family audit: m2-draft.9

Date: 2026-10-20. Auditor: Codex, Team B, ratified plan step 7 (audit only).
Baseline: `4d6baf37261eedb4350ea240a258b951eaabe8b2`, branch `docs/held-out-audit`.

## Scope and decision standard

Sources: `docs/descriptive-pilot-v6.md`, the complete lessons (including diagrams), items, hints, worked solutions, rubrics and explanations in `content/packs/python-functions-recursion/pack-m2-draft.9.json`; primary mapping inherited through `src/aesop_lab/experiment/descriptive_v6.py` to `descriptive_v3.py`; answer normalization in `src/aesop_lab/assessment/items.py`.

V6 requires the first unassisted, unfamiliar, deterministically scored primary response at days 7–14. A distinct family ID alone does not prove unfamiliarity. This audit compares semantic structure as well as names, numbers and surface. Reusing basic function/recursion syntax is necessary for assessing the same concept; a renamed or renumbered studied solution is insufficient. The protocol does not prescribe a numerical threshold for structural distance, so borderline judgments are explicitly reserved for human review.

All five mapped primary families occur once, are marked held out, have delay 7, and use trace items with candidate keys and a `result` check expression. No primary family ID occurs in lesson encountered-family metadata or another item. Those metadata checks pass; they cannot establish a particular learner's actual exposure history. Comparisons below conservatively include every non-held-out item and all five day-one held-out items, because these could precede day seven. Worked answers are included even if a particular learner never reveals them. All five lessons and diagrams were compared across concepts, not just within the target concept.

## Summary

| Concept | Primary item | Primary family | Candidate value | Family judgment | Defect severity |
|---|---|---|---|---|---|
| Function definition and return | `def-return-week-01-v9` | `def-return-shipping-week-v4` | `16` | Separate | None found |
| Parameters and local scope | `scope-week-01-v9` | `scope-caller-local-default-week-v5` | `[map]!:map` | Separate | None found |
| Recursion as self-call | `recursion-week-01-v9` | `recursion-nested-wrap-week-v5` | `[[[core]]]` | Borderline structural distance; human decision needed | Medium concern |
| Base case | `base-case-week-01-v9` | `base-case-threshold-halving-week-v4` | `small!!!` | Separate | None found |
| Recursive case and trace | `recursive-case-week-01-v9` | `recursive-case-lamp-toggle-week-v6` | `on` | Separate | None found |

No incorrect candidate key or ambiguous computed value was found. This is an author-side audit, not qualified non-author validation, human approval, or evidence of a verified learning effect. No review receipt or `human_reviewed` status is conferred.

## 1. Function definition and return

Item `def-return-week-01-v9`; family `def-return-shipping-week-v4`.

The shipping surface, `shipping`/`weight` names and piecewise rule differ from the lesson's `price_with_tax(20)` and `show_total(5)` examples (`lesson-price-with-tax-v4` and `def-return-recall-v4`). Compared with `def-return-choice-a`, `def-return-recall-v4` and `def-return-explain-v4`, this requires computed return values rather than identifying `return`, recalling `None`, or explaining print versus return. Compared with `def-return-trace-a` (`double(7) + 1`) and day-one `def-return-transfer-a` (`area(3, 4) - 2`), it evaluates two independent calls, takes different branches, and adds their results. Inputs 4 and 1, threshold 2, base fee 5 and rate 3 form a new calculation; individual constants overlap other content, but the rule and call structure are not copied. The scope lesson's tax helper also lacks branching and two-call combination. No other lesson, practice, rubric or worked solution teaches this shipping calculation.

Candidate accepted list: `["16"]`. `shipping(4) = 5 + (4 - 2) * 3 = 11`; `shipping(1) = 5`; result is 16. Unambiguous integer, deterministically scorable. Hints and explanation agree. Defect: none found; no fix proposed.

## 2. Parameters and local scope

Item `scope-week-01-v9`; family `scope-caller-local-default-week-v5`.

The word-marking surface (`mark`, `word`, `suffix`, `note`, `map`, brackets and colon) replaces the lesson's numeric tax helper (`lesson-keyword-default-global-v4`: global rate 99, default .05, explicit .10, price 40). It uses an omitted default and a caller variable retained after local rebinding, rather than an explicit keyword override and matching global/local names. Against `scope-local-trace-a` (both local-return and global-choice items), it changes arithmetic to string construction and combines the returned value with the unchanged caller value. `scope-parameter-choice-v4` and `scope-local-explain-v4` teach binding principles but contain no equivalent composite trace. Day-one `scope-keyword-transfer-a` is the nearest string example: `greet("Ana", punctuation="?")` overrides its default and returns a single greeting; the primary instead uses its default, rebinds the local argument name, and then reuses the original caller binding. It is not a name-only rewrite. There are no numeric inputs to vary here. The recursion primary also uses brackets, but has a recursive nesting structure, not local rebinding; none of the earlier cross-concept examples supplies this answer.

Candidate accepted list: `["[map]!:map", "'[map]!:map'", "\"[map]!:map\""]`. Local `word` becomes `[map]`; default suffix adds `!`; caller `note` remains `map`; colon joins the two. All accepted spellings denote the same answer, with optional surrounding quotes. Unambiguous and deterministically scorable. Hints and explanation agree. Defect: none found; no fix proposed.

## 3. Recursion as self-call

Item `recursion-week-01-v9`; family `recursion-nested-wrap-week-v5`.

`nest` and the `core`/bracket surface differ from `countdown` and its numbered `go` message (`lesson-countdown-prepend-v4`). The lesson uses `str(n) + ", " + countdown(n - 1)`; the primary puts a constant on each side of the recursive result. Its base string is new and its requested depth is 3 rather than the lesson's 2. However, `recursion-application-v4` already asks for a three-level string result from `'*' + repeat_mark(n - 1)` with an empty-string base. The primary retains the zero test, decrement-by-one chain, three waiting calls and concatenated return. The additional suffix and nonempty center require tracking nesting, but the control structure is substantially studied. This is not a literal copy, yet changed names and symbols alone would not prove an unfamiliar family.

Other same-concept families are less close: `recursion-recognize-a` identifies a terminating self-call, `recursion-explain-a` explains it, `recursion-call-order-v4` follows entries 2, 1, 0, and day-one `recursion-halving-transfer-a` actually doubles the returned numeric value over decremented levels. Cross-concept day-one `recursive-case-transfer-a` returns `reverse(text[1:]) + text[0]`, so suffix concatenation on unwind may also have been seen, although input shrinking and the output reversal differ. Numeric sum/factorial/threshold examples elsewhere do not directly supply nested bracket output.

Candidate accepted answers are `[[[core]]]`, `'[[[core]]]'`, and `"[[[core]]]"` (ordinary ASCII surrounding quotes for the latter two). Returns at n=0,1,2,3 are `core`, `[core]`, `[[core]]`, `[[[core]]]`. Unambiguous and deterministically scorable; hints and explanation agree.

Defect/concern: **Medium — uncertain structural separation**, not a demonstrated key error or literal duplicate. Proposal: a qualified human reviewer should explicitly accept or reject two-sided wrapping as enough new application relative to countdown, repeat-mark and reverse. If rejected, prospectively replace the item with a task that changes the input reduction and return operation beyond concatenation around an n-minus-one chain, assign a new family/version, and re-audit all earlier examples. Do not silently relabel the existing family or alter historical assignments. No fix applied.

## 4. Base case

Item `base-case-week-01-v9`; family `base-case-threshold-halving-week-v4`.

`label_depth(20)` halves its integer input, stops below 4, returns `small`, and adds punctuation on unwind. The lesson's `steps_to_zero(3)` (`lesson-decrement-to-zero-v4`) subtracts one to zero and counts calls. Its prerequisite `17 // 4` example teaches floor-division syntax, not this algorithm. `base-case-trace-a` computes factorial by decrementing and multiplying; `base-case-choice-a` and `base-case-explain-a` identify/explain stopping rather than trace this threshold. `base-case-recognize-v4` stops `pulse` at nonpositive values; `base-case-reachability-v4` tests parity under subtraction by two. Day-one `base-case-grow-threshold-day-v6` increases 3 by 7 until at least 20 and passes the result unchanged. The primary reverses the direction, uses halving and a strict lower threshold, and transforms returned strings. Its 20 overlaps the day-one threshold, but serves as the starting input instead, not an answer substitution.

Across concepts, countdown/repeat-mark teach string accumulation, while leaf-count multiplies return values rather than halving inputs; reverse shrinks a string by slicing. None combines halving, a below-four stop and return-path punctuation. Names, surface and structure therefore differ meaningfully even though individual syntax and constants have been taught.

Candidate accepted list: `["small!!!", "'small!!!'", "\"small!!!\""]`. Inputs are 20,10,5,2; 2 returns `small`; the other three calls append `!`. Unambiguous and deterministically scorable. Hints and explanation agree. Defect: none found; no fix proposed.

## 5. Recursive case and trace

Item `recursive-case-week-01-v9`; family `recursive-case-lamp-toggle-week-v6`.

The lamp/presses surface, `lamp_state`/`previous` names, `off`/`on` values and depth 5 differ from the lesson's sum-first trace of 3 (`recursive-case-trace-a`). The lesson diagram, `recursive-case-trace-a` practice on 4, and `recursive-case-explain-v4` all add the current input to a smaller sum. `recursive-case-choice-a` concerns progress; `recursive-case-recognize-v4` counts with `1 +` a smaller result. `recursive-case-design-a` and its worked answer add a list head to a recursively summed tail. Day-one `recursive-case-transfer-a` reverses text using slicing and concatenation.

The nearest practice is `recursive-case-savings-growth-a`: it also stores a smaller return in a local variable, but doubles that number and adds the month (base 5, input 3, result 51). The primary instead branches on the returned state and alternates two strings; a learner cannot reuse the studied arithmetic recurrence. Other lessons/practices and day-one examples use arithmetic, concatenation or unchanged returns, never conditional state flipping on the return path. Zero-base/decrement syntax is shared; the combination rule is new. Depth 5 and the base string `off` do not reproduce an earlier solution.

Candidate accepted list: `["on", "'on'", "\"on\""]`. States at 0 through 5 are off,on,off,on,off,on. Unambiguous and deterministically scorable; hints and explanation agree. Defect: none found; no fix proposed.

## Scoring, verification and limitations

Scoring normalizes whitespace, while retaining case and punctuation; these are finite accepted-string keys, not a general evaluator accepting all equivalent Python expressions. For these prompts, optional surrounding quotes are covered on strings; numeric keys use plain decimal integers. No scoring ambiguity was found. This audit manually traced all five results and checked their candidate keys, hints and explanations; it did not execute content code or run tests. No content, code or tests were changed.

All practice and lesson families were inspected. The most relevant families are listed above; the remaining cross-concept families cover return/print identification, local binding, numeric sums, factorial, progress recognition and list summation rather than an additional copy of any primary task. Day-one families are included conservatively; other day-seven primaries are separate outcomes and are not assumed to have been studied first. Actual item order, prior attempts, hints/reveals, outside study and elapsed time remain learner-record eligibility checks, not facts established by a static pack audit. Embedded held-out worked solutions are not themselves evidence of prior exposure; revealing one before the primary response would make that response assisted/ineligible under v6.

The pack is draft, all five keys are candidate, and review receipts are empty. Human key review and qualified non-author validation remain gates. This audit does not approve, merge, or change those gates. The only unresolved family concern is recursion wrapping; there is no code-execution or learner-session evidence claimed here.

## Human key reviewer: exact decisions required

Record a written accept, edit or reject for each of these five keys; the following recommendations are provisional:

- `def-return-week-01-v9`: accept candidate `16` if the shipping trace is confirmed.
- `scope-week-01-v9`: accept `[map]!:map` and its stored single-/double-quoted variants if caller/local reasoning is confirmed.
- `recursion-week-01-v9`: confirm `[[[core]]]` and its stored single-/double-quoted variants; separately decide whether nested wrapping is sufficiently unfamiliar after countdown, repeat-mark and day-one reverse. If not, reject the family for prospective primary use pending replacement and re-audit.
- `base-case-week-01-v9`: accept `small!!!` and its stored single-/double-quoted variants if the three unwind steps are confirmed.
- `recursive-case-week-01-v9`: accept `on` and its stored single-/double-quoted variants if the five toggles are confirmed.
