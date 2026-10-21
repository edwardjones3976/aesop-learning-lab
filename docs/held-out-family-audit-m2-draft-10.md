# Held-out family delta audit: m2-draft.10

Date: 2026-10-20. Auditor: Codex, Team B (audit only).
Baseline: `15e58d675eaefb9cb5a6716a72b1db4b6cf27783`, branch `docs/held-out-audit-v10`.

## Scope and result

Compared the complete v9 and v10 packs in `content/packs/python-functions-recursion/`, including all five lessons, diagrams, all 33 items, choices, hints, worked answers, explanations, common mistakes and rubrics. Sources also include [protocol v7](descriptive-pilot-v7.md), its inherited [v6 requirements](descriptive-pilot-v6.md), `src/aesop_lab/foreman.py` (`CURRENT_PACK_PATH` selects v10 for fresh learners), `experiment/descriptive_v7.py`, the shared `experiment/descriptive_v2.py` classifier, and `assessment/items.py` scoring normalization.

This is a delta to the [v9 audit](held-out-family-audit-m2-draft-9.md), not human approval. V7 uses content v10 prospectively; historical assignments remain pinned. All ten held-out items retain their literal `-v9` item IDs, family IDs, code (`body`), prompt, complete candidate answer key, check expression `result`, held-out flag and day-one/day-seven delay. Their `content_version` changes from `v9` to `v10`. All ten have supporting prose changes, quoted below; therefore all ten receive fresh manual traces and separation checks here. None has changed assessment code, prompt or key. No new or removed items or families were found.

## Item-by-item comparison and traces

In every row, item ID and family ID are identical in v9 and v10, and code, prompt and key are identical. The common prompt is “After this code runs, what is the value of result?” String keys accept the listed bare value and the same value enclosed in ASCII single or double quotes; integer keys accept only the listed decimal string. Key status remains `candidate`.

| Delay | Item ID (both packs) | Family ID (both packs) | Candidate value | Fresh manual trace |
|---|---|---|---|---|
| 1 | `def-return-transfer-01-v9` | `def-return-transfer-a` | `10` | `area(3, 4)` returns 12; caller subtracts 2, giving 10. |
| 1 | `scope-keyword-transfer-01-v9` | `scope-keyword-transfer-a` | `Hi Ana?` | Explicit `punctuation="?"` replaces `!`; joining `Hi `, `Ana`, `?` gives `Hi Ana?`. |
| 1 | `recursion-halving-transfer-01-v9` | `recursion-halving-transfer-a` | `16` | Despite its ID, input decrements: levels 4,3,2,1,0; returned values at levels 0–4 are 1,2,4,8,16. |
| 1 | `base-case-transfer-01-v9` | `base-case-grow-threshold-day-v6` | `24` | Inputs 3,10,17,24; 24 first satisfies `n >= 20`; earlier calls pass back 24 unchanged. |
| 1 | `recursive-case-transfer-01-v9` | `recursive-case-transfer-a` | `cba` | `reverse("c")` returns `c`; `reverse("bc")` returns `cb`; `reverse("abc")` returns `cba`. |
| 7 | `def-return-week-01-v9` | `def-return-shipping-week-v4` | `16` | `shipping(4)` gives `5 + 2 * 3 = 11`; `shipping(1)` gives 5; sum 16. |
| 7 | `scope-week-01-v9` | `scope-caller-local-default-week-v5` | `[map]!:map` | Local `word` becomes `[map]`, omitted suffix adds `!`; caller `note` stays `map`; join with `:`. |
| 7 | `recursion-week-01-v9` | `recursion-nested-wrap-week-v5` | `[[[core]]]` | Returns at n=0,1,2,3: `core`, `[core]`, `[[core]]`, `[[[core]]]`. |
| 7 | `base-case-week-01-v9` | `base-case-threshold-halving-week-v4` | `small!!!` | Inputs 20,10,5,2; 2 returns `small`; three waiting calls each append `!`. |
| 7 | `recursive-case-week-01-v9` | `recursive-case-lamp-toggle-week-v6` | `on` | States at presses 0–5: off,on,off,on,off,on. |

All ten computed values are unambiguous and deterministically scorable against the stored accepted strings. The revised hints and worked answers agree with these traces. Scoring collapses whitespace, preserves case and punctuation, and does not evaluate arbitrary equivalent expressions. No key error found; no key fix proposed.

## Renewed family separation checks

Conservatively include all lessons and diagrams across concepts, all non-held-out items with their worked answers/rubrics, and every other held-out item that could precede the target, including reveals. Day-seven checks include all five day-one checks and all four other day-seven primaries. For day-one checks, other held-outs are also considered conservatively, without assuming the scheduler protects unfamiliarity. The target's own revealed answer cannot precede an unassisted target response. Different IDs alone do not prove separation.

### Day-seven primaries

The unchanged assessment material inherits the detailed family comparisons in v9 audit sections 1–5 and all ten cross-primary pair comparisons in its “Scoring, verification and limitations” section. Those comparisons carry over to v10; the renewed checks against rewritten prose give these results:

- `def-return-week-01-v9`: separate. Shipping/weight, 4 and 1, threshold 2, fee 5 and rate 3 still require two independent calls taking different branches. Tax lessons, double practice and day-one area do not teach that composite branch calculation. Neither string binding, wrapping, halving nor lamp toggling supplies its solution.
- `scope-week-01-v9`: separate. `mark`, `word`, `suffix`, `note`, `map`, brackets and colon still combine an omitted default, local rebinding and preservation of the caller's string. Numeric local/global practice and tax instruction do not reproduce this combination; day-one greeting overrides a default instead. Other held-outs expose brackets or punctuation, but not this binding structure.
- `recursion-week-01-v9`: **medium structural-separation concern carries over**. Two-sided brackets and `core` differ from countdown's numbered prefix, repeat-mark's stars/empty base and day-one reverse's sliced input. Yet repeat-mark already teaches a zero/decrement chain with three waiting calls concatenating strings. Base-case primary first teaches a nonempty base and three punctuation-producing returns. Names, symbols and depth do not settle unfamiliarity. Qualified human review must decide whether two-sided nesting adds enough new structure.
- `base-case-week-01-v9`: separate from practice, but **medium cross-primary concern carries over**. `label_depth(20)` halves to below 4 and appends marks, unlike decrement-to-zero/counting, factorial, parity reachability and growing-by-seven day-one work. The floor-division prerequisite teaches syntax only. Nesting first nevertheless teaches a nonempty string returning through three punctuation-producing calls; human review must decide whether halving/threshold and suffix-only construction remain sufficiently unfamiliar in that ordering.
- `recursive-case-week-01-v9`: separate. Lamp/presses, off/on and depth 5 require conditional flipping of the smaller call's returned state. Savings also stores a smaller return but doubles a number and adds a month; sums, factorial, leaf-count, reverse, wrapping and halving do not teach flipping. Shared decrement/zero syntax does not supply the return rule.

Proposed fix for either medium concern, if rejected by the human: prospectively replace the affected assessment with a materially different reduction/return task, assign a new family/version, and re-audit exposure and order. Do not relabel historical assignments. No fix applied.

### Day-one held-outs

The v9 audit considered these as prior exposure to day seven; it did not independently certify their own unfamiliarity. The following judgments extend that scope rather than claiming prior approval:

- `def-return-transfer-01-v9`: **medium near-transfer concern**. Area uses new names, two parameters, inputs 3 and 4, multiplication and caller subtraction; however `double(7) + 1` practice already teaches a single arithmetic-return call followed by caller arithmetic. New numbers, arity and surface may be insufficient structural distance. Shipping adds branching/two calls but also exposes combining return values. No string or recursive example duplicates area. Human must decide whether area is unfamiliar application or only a close arithmetic variant; if rejected, replace prospectively with a structurally different task/new family.
- `scope-keyword-transfer-01-v9`: separate on static comparison. Greeting/Ana/punctuation, string joining and `?` differ from the numeric tax default override, local arithmetic and global-binding practice. The same keyword/default principle is taught, but the greeting computation is not copied. The day-seven scope task uses an omitted default and local rebinding, rather than an override; bracket/wrapping examples lack keyword arguments. No additional defect found.
- `recursion-halving-transfer-01-v9`: **medium near-transfer concern**. Leaf-count's level 4/base 1/constant doubling differs from stars, countdown, sums and factorial, but factorial already multiplies a smaller return (by current n), and savings doubles a smaller return then adds month. Constant doubling may be too small a structural change after those worked answers. Other held-outs teach recursion but not this numeric recurrence. Human must adjudicate distance; if insufficient, replace prospectively with a different reduction/combine structure and new family. The misleading “halving” ID does not change the code or key.
- `base-case-transfer-01-v9`: separate. `reach_target` starts at 3, grows by 7 toward at least 20 and returns the reached input unchanged. Lessons/practice generally shrink toward zero or test parity; day-seven base-case shrinks by halving and transforms returned strings. A shared 20 is a threshold here, a starting input there. Other held-outs do not teach this increasing-input/unchanged-return combination. No additional defect found.
- `recursive-case-transfer-01-v9`: separate. Reverse uses `abc`, string slicing, a length-at-most-one base and suffixing the removed first character. List-sum practice teaches slicing but adds numeric heads; countdown/repeat-mark prepend symbols using integer decrements. Wrapping and halving accumulate constant punctuation, not reversal of input characters. Other held-outs lack this input-dependent return arrangement. No additional defect found.

These are conservative static judgments, not evidence about any actual learner's prior knowledge. The two day-one concerns are newly explicit audit judgments, not v10 content regressions: the same structures existed in v9.

## Does simpler instruction increase held-out overlap?

All 33 item bodies, prompts, choices, answer keys and family IDs are unchanged. The five lessons retain the same Python examples; their encountered-family lists are unchanged. Lesson diagrams retain the same computations (three have wording changes). Rewritten hints, annotated examples, explanations and common mistakes add clarity but no new held-out algorithm or answer. There is no demonstrated increase in structural family overlap; wording may affect learning, as v7 explicitly acknowledges, so unchanged code alone is not proof of unchanged exposure effect.

Specific checks of the revised prose:

- Return instruction still traces `price_with_tax(20)` and `show_total(5)`, and practice still explains double and print/None. “The call then stands for the returned value” makes substitution clear but does not introduce shipping branches or area. The area proximity to double predates v10.
- Scope instruction retains `total(40, rate=0.10)`, default .05, global 99 and local 44.0. Explaining that the default applies when the argument is omitted supports both scope held-outs conceptually, as v9 already did; it does not add a greeting or caller/local string composite worked answer.
- Countdown's rewritten trace says the one call adds `"1, "` in front and the two call adds `"2, "` in front. V9 already traced these results. Repeat-mark's worked answer changes “The zero call returns an empty string; each of three waiting calls adds one `*`, so result is `***`.” to “The zero call returns an empty string. Each of the three waiting calls adds one `*`, so result is `***`.” Neither introduces two-sided wrapping, but both teach the three-waiting-call string construction behind the existing concern.
- Base-case instruction still uses `steps_to_zero(3)` and the separate `17 // 4` prerequisite. “For whole numbers of zero or more” replaces “for nonnegative integers”; neither demonstrates recursive halving or growing by seven. Its added definition of a branch does not expose a held-out answer.
- Sum-first instruction and diagram still show 3,2,1,0 returning 0,1,3,6. Savings still returns 5,11,24,51; its rewrite emphasizes each call's own `previous`. List-sum's annotated solution still removes a head and adds it to a recursive tail sum. This may aid transfer to leaf-count, reverse and lamp, but adds no reversal or conditional state-flip worked solution. The leaf-count proximity to savings/factorial is pre-existing.

The wrapping/base-case pair is unchanged in either order: both return a nonempty string through three calls that add punctuation. Halving/below-four versus decrement/zero, and suffix-only versus two-sided wrapping, remain their distinctions. Scope first can also expose brackets and `!`. All ten cross-primary comparisons in the v9 audit still apply; none can be dismissed by assuming other primaries are unseen.

## Eligibility and review limitations

The v9 audit's exact-family cross-primary limitation carries over: current `analyze_v7` delegates to `_analyze`, whose prior-family checks compare the exact target family. Distinct but structurally related held-outs do not automatically contaminate each other. Actual attempt/reveal ordering still needs review.

The v9 audit's outside-study implementation warning does **not** carry over as a statement of current behavior. At this baseline, `_classify_first` excludes `OutsideStudy.SOME` for protocol numbers at least 5. `_analyze` also passes reports through the primary response time from any item of the same concept. Thus v7 excludes a structured SOME report on the primary or an earlier same-concept attempt. Missing/UNKNOWN reports are not affirmative study reports, free-text detail does not override the structured value, and this is not proof that no outside study occurred. Static pack review cannot certify attentive study, actual exposure or session eligibility.

V10 remains draft, all ten keys are candidate and review receipts are empty. This audit grants no human-reviewed status, independent validation or learning-effect claim. No content, code or tests changed. No code snippets were executed and no test suite was run; ten traces were performed manually. The requested documentation verification is `git diff --check`; no regression tests are added under the explicit documentation-only scope.

## Exact held-out prose deltas

The assessment fields identified above are identical. For completeness, the following quotes record every changed supporting field of each held-out item, besides the common `content_version: "v9" -> "v10"`. Unlisted fields are identical. Array entries are quoted in JSON notation so punctuation and accepted spelling remain inspectable.

### `def-return-transfer-01-v9`

- `hints.worked_solution`: "area(3, 4) returns 3 * 4 = 12; the caller then subtracts 2, so result is 10." → "area(3, 4) returns 3 * 4 = 12. Then the caller subtracts 2, so result is 10."
- `learning_objective`: "Apply call-and-return reasoning in a previously unseen context." → "Use call-and-return thinking on an example you have not seen before."
- `explanation`: "area(3, 4) returns 3 * 4 = 12; the caller then subtracts 2, so result is 10." → "area(3, 4) returns 3 * 4 = 12. Then the caller subtracts 2, so result is 10."
- `common_mistakes`: ["The function multiplies width and height before the caller subtracts 2; adding 3 and 4 or skipping the subtraction changes result."] → ["The function multiplies width by height first. Then the caller subtracts 2. Adding 3 and 4, or skipping the subtraction, gives the wrong result."]

### `scope-keyword-transfer-01-v9`

- `hints.targeted`: "greet builds \"Hi \" + name + punctuation." → "greet joins \"Hi \" + name + punctuation."
- `hints.worked_solution`: "The explicit punctuation=\"?\" replaces the default \"!\". The function concatenates \"Hi \" + \"Ana\" + \"?\", so result is \"Hi Ana?\"." → "The call gives punctuation=\"?\", which replaces the default \"!\". The function joins \"Hi \" + \"Ana\" + \"?\", so result is \"Hi Ana?\"."
- `learning_objective`: "Apply a keyword argument to override a default value in an unfamiliar string-building call." → "Use a keyword argument to replace a default value in a new call that builds a string."
- `explanation`: "The explicit punctuation=\"?\" replaces the default \"!\". The function concatenates \"Hi \" + \"Ana\" + \"?\", so result is \"Hi Ana?\"." → "The call gives punctuation=\"?\", which replaces the default \"!\". The function joins \"Hi \" + \"Ana\" + \"?\", so result is \"Hi Ana?\"."
- `common_mistakes`: ["The explicit punctuation=\"?\" replaces the default \"!\" for this call."] → ["The call gives punctuation=\"?\", so this call uses \"?\" instead of the default \"!\"."]

### `recursion-halving-transfer-01-v9`

- `hints.targeted`: "Each level doubles the value returned by the smaller level." → "Each level doubles the value returned by the level below it."
- `learning_objective`: "Apply call-stack reasoning to an unfamiliar recursive process." → "Keep track of waiting calls in a new recursive example."
- `common_mistakes`: ["The base level returns 1, not 0; four outer levels double that value four times."] → ["The base level returns 1, not 0. Each of the four levels above it doubles that value."]

### `base-case-transfer-01-v9`

- `hints.nudge`: "Which call first satisfies n >= 20?" → "Which call is the first one where n >= 20 is true?"
- `hints.targeted`: "The inputs are 3, 10, 17, and 24; only the last meets the stopping condition." → "The inputs are 3, 10, 17, and 24. Only 24 meets the stopping condition."
- `hints.worked_solution`: "reach_target(24) meets n >= 20 and returns 24. Calls at 17, 10, and 3 return that value unchanged, so result is 24." → "reach_target(24) meets n >= 20 and returns 24. The calls at 17, 10, and 3 pass that value back without changing it, so result is 24."
- `learning_objective`: "Apply reachable base-case reasoning to a growing input and trace the returned value." → "Use base-case thinking on an input that grows, and trace the returned value."
- `explanation`: "reach_target(24) meets n >= 20 and returns 24. Calls at 17, 10, and 3 return that value unchanged, so result is 24." → "reach_target(24) meets n >= 20 and returns 24. The calls at 17, 10, and 3 pass that value back without changing it, so result is 24."
- `common_mistakes`: ["17 is still below the n >= 20 stopping threshold; the next call receives 24 and returns that value unchanged."] → ["17 is still below 20, so that call does not stop. The next call gets 24 and returns it, and the earlier calls pass it back unchanged."]

### `recursive-case-transfer-01-v9`

- `hints.worked_solution`: "reverse(\"c\") returns \"c\" at the base case. reverse(\"bc\") returns \"c\" + \"b\" = \"cb\"; reverse(\"abc\") returns \"cb\" + \"a\" = \"cba\"." → "reverse(\"c\") returns \"c\", because it is the base case. reverse(\"bc\") returns \"c\" + \"b\" = \"cb\". reverse(\"abc\") returns \"cb\" + \"a\" = \"cba\"."
- `learning_objective`: "Apply recursive-call tracing to an unfamiliar task." → "Trace recursive calls in a new task."
- `explanation`: "reverse(\"c\") returns \"c\" at the base case. reverse(\"bc\") returns \"c\" + \"b\" = \"cb\"; reverse(\"abc\") returns \"cb\" + \"a\" = \"cba\"." → "reverse(\"c\") returns \"c\", because it is the base case. reverse(\"bc\") returns \"c\" + \"b\" = \"cb\". reverse(\"abc\") returns \"cb\" + \"a\" = \"cba\"."
- `common_mistakes`: ["If every recursive case uses return text[0] + reverse(text[1:]), the function preserves the original order: \"abc\" for \"abc\", not \"cba\"."] → ["If each recursive case used return text[0] + reverse(text[1:]), the letters would keep their original order. That gives \"abc\" for \"abc\", not \"cba\"."]

### `def-return-week-01-v9`

- `hints.nudge`: "Find the returned value of each shipping call separately." → "Find the value returned by each shipping call on its own."
- `hints.targeted`: "The call with weight 4 takes the second branch; the call with weight 1 takes the first." → "The call with weight 4 takes the second branch. The call with weight 1 takes the first branch."
- `learning_objective`: "Apply call-and-return reasoning in a previously unseen context." → "Use call-and-return thinking on an example you have not seen before."
- `common_mistakes`: ["shipping(4) and shipping(1) take different branches; using one branch for both calls changes the total."] → ["shipping(4) and shipping(1) take different branches. Using one branch for both calls gives the wrong total."]

### `scope-week-01-v9`

- `hints.nudge`: "Keep the caller's note separate from the function's local word, and check whether suffix is supplied." → "Keep the caller's note separate from the function's local word. Check whether the call gives a suffix."
- `hints.targeted`: "mark(note) uses the default suffix '!'; inside the call, only the local word is rebound to '[map]'." → "mark(note) uses the default suffix '!'. Inside the call, only the local word changes, to '[map]'."
- `hints.worked_solution`: "mark(note) receives 'map' as local word and returns '[map]!' with the default suffix. The caller's note remains 'map', so result is '[map]!:map'." → "mark(note) gives the local word the value 'map'. It returns '[map]!' using the default suffix. The caller's note is still 'map', so result is '[map]!:map'."
- `learning_objective`: "Trace an omitted default argument and a locally rebound parameter without changing the caller's binding." → "Trace a call that leaves out an argument (so its default is used) and gives a parameter a new value, without changing the caller's name."
- `explanation`: "mark(note) receives 'map' as local word and returns '[map]!' with the default suffix. The caller's note remains 'map', so result is '[map]!:map'." → "mark(note) gives the local word the value 'map'. It returns '[map]!' using the default suffix. The caller's note is still 'map', so result is '[map]!:map'."
- `common_mistakes`: ["Rebinding local word does not rebind the caller’s note, and the omitted suffix argument uses its default \"!\"."] → ["Changing the local word does not change the caller's note. The call leaves out suffix, so it uses the default \"!\"."]

### `recursion-week-01-v9`

- `hints.nudge`: "Find the innermost value returned by nest(0)." → "Find the innermost value, which nest(0) returns."
- `hints.targeted`: "Each waiting call places one pair of brackets around the value from its smaller call." → "Each waiting call puts one pair of brackets around the value from its smaller call."
- `learning_objective`: "Apply call-stack reasoning to an unfamiliar recursive process." → "Keep track of waiting calls in a new recursive example."
- `common_mistakes`: ["Each outer call adds one bracket pair around its inner result; appending all opening brackets first without closing them misreads the return path."] → ["Each outer call wraps one pair of brackets around its inner result. If you add all the opening brackets first and leave out the closing ones, you misread how the values come back."]

### `base-case-week-01-v9`

- `hints.nudge`: "Identify the first input below four." → "Find the first input that is below 4."
- `hints.targeted`: "Integer halving gives 20, 10, 5, 2. The call at 2 returns the starting label." → "Halving with // gives 20, 10, 5, 2. The call at 2 returns the starting label."
- `learning_objective`: "Apply a stopping threshold to recursive integer halving and trace returned values." → "Use a stopping cutoff with recursive whole-number halving, and trace the returned values."
- `common_mistakes`: ["Integer halving reaches n = 2 before returning small; the calls at 5, 10, and 20 add their marks afterward."] → ["Whole-number halving reaches n = 2 before it returns small. After that, the calls at 5, 10, and 20 add their marks."]

### `recursive-case-week-01-v9`

- `hints.targeted`: "Each waiting call flips the smaller call’s state; list states for 0, 1, 2, and onward." → "Each waiting call flips the state from the smaller call. List the states for 0, 1, 2, and so on."
- `hints.worked_solution`: "lamp_state(0) is off. The states for 1 through 5 presses are on, off, on, off, on; result is on." → "lamp_state(0) is off. The states for 1 to 5 presses are on, off, on, off, on. So result is on."
- `learning_objective`: "Trace a recursive step that combines a smaller result by toggling a state in an unfamiliar context." → "Trace a recursive step that flips the smaller call's state between on and off, in a new example."
- `explanation`: "lamp_state(0) is off. The states for 1 through 5 presses are on, off, on, off, on; result is on." → "lamp_state(0) is off. The states for 1 to 5 presses are on, off, on, off, on. So result is on."
- `common_mistakes`: ["The positive calls do not all return on; each call flips the state returned by the smaller call."] → ["The calls above zero do not all return on. Each call flips the state returned by the smaller call."]

## Human key reviewer: exact v10 decisions required

Record accept, edit or reject for each item below in its v10 context. For every string, decide on the bare value and both stored ASCII single-/double-quoted variants. The five day-seven key recommendations and wrapping/base-case decisions carry over from the v9 audit as pending decisions, not recorded approvals. The five day-one key decisions and two near-transfer concerns are explicitly added here.

| Item ID in v10 | Candidate value to decide | Family decision / carryover |
|---|---|---|
| `def-return-week-01-v9` | `16` | V9 key recommendation and separate-family judgment carry over. |
| `scope-week-01-v9` | `[map]!:map` | V9 key recommendation and separate-family judgment carry over. |
| `recursion-week-01-v9` | `[[[core]]]` | V9 decision carries over: accept/reject unfamiliarity after countdown, repeat-mark, reverse and any earlier primary, especially base-case. |
| `base-case-week-01-v9` | `small!!!` | V9 decision carries over: accept/reject unfamiliarity when wrapping comes first; assess both pair orderings. |
| `recursive-case-week-01-v9` | `on` | V9 key recommendation and separate-family judgment carry over. |
| `def-return-transfer-01-v9` | `10` | New explicit day-one review: decide whether area is sufficiently separate from double/caller arithmetic. |
| `scope-keyword-transfer-01-v9` | `Hi Ana?` | New explicit day-one key review; static family judgment separate. |
| `recursion-halving-transfer-01-v9` | `16` | New explicit day-one review: decide whether constant doubling is sufficiently separate from factorial and savings. |
| `base-case-transfer-01-v9` | `24` | New explicit day-one key review; static family judgment separate. |
| `recursive-case-transfer-01-v9` | `cba` | New explicit day-one key review; static family judgment separate. |

The human must also retain actual order/answer/reveal review for cross-primary exposure; the exact-family gate does not resolve structural overlap. The older outside-study warning is superseded by the current implementation qualification above. Qualified non-author content validation remains a separate repository gate; this audit and its candidate recommendations do not satisfy it.
