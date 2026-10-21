# Held-out family delta audit: m2-draft.11

This is a bounded delta against [the v10 audit](held-out-family-audit-m2-draft-10.md), not independent human approval. The owner's step-7 review rejected the unfamiliar-family claim for `recursion-week-01-v9` (`recursion-nested-wrap-week-v5`): `repeat_mark` practice already teaches essentially the same decrement-to-zero string construction.

V11 replaces it with `recursion-week-01-v11`, family `recursion-converge-week-v8`, concept `recursion-as-self-call`, a held-out day-seven trace with candidate key `6`. Calls are `(0,8) -> (2,7) -> (4,6) -> (6,5)`. The last call returns low, 6; earlier calls pass it back unchanged. Each common mistake gives a different answer: returning high gives 5, stopping one call early gives 4, and moving only low gives 8. Integration changed the call from Codex's `meet(1, 10)`, where the final call was `(7,7)` and returning high also gave the key. Both arguments must change at each self-call.

Compared all five lesson bodies and diagrams and all 33 item bodies, choices, hints, explanations, mistakes and rubrics against v10. No other learner-visible example uses two converging arguments. The removed `nest` occurs only in the historical v10 pack. No lesson encountered-family list or other v11 metadata references its removed family, so no such list required editing.

The recursive shapes verified in the actual pack are:

- Decrement-to-zero string builders: lesson `countdown` and practice `repeat_mark`; `nest` is the removed v10 check.
- Numeric accumulation: lesson `steps_to_zero`, practice `total_to`, lesson `sum_first`, list summation and factorial practice. These combine a smaller return with other work.
- Doubling: day-one `leaf_count`; savings practice doubles a smaller result and adds the current month.
- Halving: day-seven `label_depth` reduces one argument and adds punctuation to the returned string.
- Slicing: day-one `reverse` and list-sum design practice reduce a sequence and combine its parts.
- Single-argument growth: day-one base-case `reach_target` grows by seven to a fixed threshold, passing the reached value back unchanged. This is the closest return shape, but it has one changing argument and a fixed boundary, rather than two changing boundaries.
- Lamp toggling: the other day-seven recursive-case check flips a returned state.
- Single-argument unchanged returns: call-order `down` decrements to zero; recognition `pulse` decrements to a nonpositive cutoff and returns a literal. Neither changes two inputs.
- Recognition and reachability choices include unchanged inputs, subtraction, zero tests and parity failures. None introduces two changing arguments converging on each other.

The remaining nonrecursive material covers definition/return, printing versus None, arithmetic return/caller arithmetic, local/global binding, keyword/default arguments, area, shipping and string marking. The two-parameter examples such as tax, area, greeting and marking do not self-call or update two boundaries. Their prose and diagrams supply no converging-call trace. This comparison includes every other held-out item conservatively, regardless of check order. The target's own hints and reveal are assistance, not prior independent exposure.

All other nine held-outs are unchanged apart from `content_version`: `def-return-transfer-01-v9`, `scope-keyword-transfer-01-v9`, `recursion-halving-transfer-01-v9`, `base-case-transfer-01-v9`, `recursive-case-transfer-01-v9`, `def-return-week-01-v9`, `scope-week-01-v9`, `base-case-week-01-v9`, and `recursive-case-week-01-v9`. All other 23 items and all lessons are also unchanged apart from version fields. The new regression test compares the complete pack after removing the one replacement and version fields, and compares serialized bytes of every retained item.

Protocol v8 selects the new primary family prospectively. Historical v10/v7 material remains frozen. Scoring, normalization, UI and storage are unchanged. Static separation is not proof of unfamiliarity for a real learner; prior exposure and independent content/key review remain required. The earlier audit's unrelated concerns remain unresolved by this bounded replacement.

## Verification and integration handoff

Python: `PYTHONPATH=src python -m unittest discover -s tests -q`, Node contracts and the browser smoke test: see the PR for the integrated counts. The browser smoke test now takes the learner's assignment from the protocol instead of assuming one.

Mutation proof: changing only the new candidate key to `5` makes `test_new_key_executes_to_six` fail; the content tests pass with the key restored.

## Intentionally retained historical references

Every retained literal `m2-draft.10` or standalone `v7` is confined to these locations (including baseline comparisons in this audit):

- Frozen packs `pack-m2-draft.7.json`, `pack-m2-draft.8.json`, `pack-m2-draft.10.json`: historical identities or prerequisites; untouched.
- Frozen protocols `descriptive_v4.py`, `descriptive_v7.py`: historical content v7 and protocol v7; untouched.
- Historical docs `content-correction-v8.md`, `content-review-v7.md`, `descriptive-pilot-v4.md`, `descriptive-pilot-v7.md`, `held-out-family-audit-m2-draft-10.md`, `personal-intelligence-pilot.md`: historical review and protocol records; untouched.
- Historical tests `test_personal_comparison.py`, `test_experiment_v4.py`, `test_experiment_v5.py`, `test_experiment_v7.py`, `test_m2_content_v7.py`, `test_m2_content_v8.py`, `test_m2_content_v10.py`: frozen fixture identities and regression expectations; untouched.
- `foreman.py`: V10_PACK_PATH/PACK_BY_VERSION; protocol-v7-to-content-v10 assignment pin; content-v7 historical routes; v10 policy and plain-language branches; v10 method/analysis routes; historical versions in shared version tuples. All preserve original learner behavior.
- `test_foreman.py`: historical content-v7/protocol-v4 test and the added content-v10/protocol-v7 restart test.
- `test_m2_content_v11.py`: v10 baseline file reads for exact comparison.
- `descriptive-pilot-v8.md` and this audit: explicit baseline, replacement rationale and historical-pinning documentation.

## Complete pack diff excluding version fields

```diff
--- v10 (version fields omitted)
+++ v11 (version fields omitted)
@@ -1075,37 +1075,35 @@
       ]
     },
     {
-      "id": "recursion-week-01-v9",
+      "id": "recursion-week-01-v11",
       "concept_id": "recursion-as-self-call",
-      "family_id": "recursion-nested-wrap-week-v5",
+      "family_id": "recursion-converge-week-v8",
       "activity_type": "trace",
       "evidence_kind": "transfer",
       "held_out": true,
       "check_delay_days": 7,
       "prompt": "After this code runs, what is the value of result?",
-      "body": "def nest(n):\n    if n == 0:\n        return 'core'\n    return '[' + nest(n - 1) + ']'\nresult = nest(3)",
-      "choices": [],
-      "answer_key": {
-        "status": "candidate",
-        "accepted": [
-          "[[[core]]]",
-          "'[[[core]]]'",
-          "\"[[[core]]]\""
+      "body": "def meet(low, high):\n    if low >= high:\n        return low\n    return meet(low + 2, high - 1)\nresult = meet(0, 8)",
+      "choices": [],
+      "answer_key": {
+        "status": "candidate",
+        "accepted": [
+          "6"
         ]
       },
       "check_expression": "result",
       "hints": [
         {
           "level": "nudge",
-          "text": "Find the innermost value, which nest(0) returns."
-        },
-        {
-          "level": "targeted",
-          "text": "Each waiting call puts one pair of brackets around the value from its smaller call."
-        },
-        {
-          "level": "worked_solution",
-          "text": "nest(0) returns 'core'; nest(1) returns '[core]', nest(2) returns '[[core]]', and nest(3) returns '[[[core]]]'."
+          "text": "Keep track of both arguments in each call. Check the stopping condition before making another call."
+        },
+        {
+          "level": "targeted",
+          "text": "Each new call adds 2 to low and subtracts 1 from high. When low >= high, return low and pass that value back unchanged."
+        },
+        {
+          "level": "worked_solution",
+          "text": "The calls use (0, 8), (2, 7), (4, 6), and (6, 5). At (6, 5), low >= high is true, so the call returns low, which is 6. Each waiting call passes that value back unchanged, so result is 6."
         }
       ],
       "source_ids": [
@@ -1113,9 +1111,11 @@
       ],
       "learning_objective": "Keep track of waiting calls in a new recursive example.",
       "difficulty": "advanced",
-      "explanation": "nest(0) returns 'core'; nest(1) returns '[core]', nest(2) returns '[[core]]', and nest(3) returns '[[[core]]]'.",
-      "common_mistakes": [
-        "Each outer call wraps one pair of brackets around its inner result. If you add all the opening brackets first and leave out the closing ones, you misread how the values come back."
+      "explanation": "The calls use (0, 8), (2, 7), (4, 6), and (6, 5). At (6, 5), low >= high is true, so the call returns low, which is 6. Each waiting call passes that value back unchanged, so result is 6. At (4, 6), the stopping condition is still false. The base case returns low, not high, and both arguments change in each self-call.",
+      "common_mistakes": [
+        "Stopping at low = 4 is one call too early: 4 is still below 6.",
+        "The base case returns low, not high. Returning high gives 5.",
+        "Change both arguments in every self-call: add 2 to low and subtract 1 from high. Moving only low gives (0, 8), (2, 8), (4, 8), (6, 8), (8, 8) and returns 8."
       ]
     },
     {
```
