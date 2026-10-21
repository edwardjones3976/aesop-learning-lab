# Held-out family delta audit: m2-draft.11

This is a bounded delta against [the v10 audit](held-out-family-audit-m2-draft-10.md), not independent human approval. The owner's step-7 review rejected the unfamiliar-family claim for `recursion-week-01-v9` (`recursion-nested-wrap-week-v5`): `repeat_mark` practice already teaches essentially the same decrement-to-zero string construction.

V11 replaces it with `recursion-week-01-v11`, family `recursion-converge-week-v8`, concept `recursion-as-self-call`, a held-out day-seven trace with candidate key `7`. Calls are `(1,10) -> (3,9) -> (5,8) -> (7,7)`. The last call returns low, 7; earlier calls pass it back unchanged. At `(5,8)` the condition is false, so 5 is one call early. Returning high happens to produce the same final value here; the explanation still distinguishes the written return expression. Both arguments must change at each self-call.

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

Python: `PYTHONPATH=src python -m unittest discover -s tests -q` — 260 passed. Node contracts: 48 passed. Browser: 5 run, 3 passed and 2 failed at `foreman_smoke.spec.mjs:158`: the fixed `user_1` fixture expects diagram, but the required v8 seed assigns it text. Browser tests contain no pack-version assertion and remain unchanged per the work order. This browser gate remains failing for integration; no approval or merge is implied. Dependencies were installed with the existing browser lockfile, which is unchanged. Coverage: not applicable; no repository coverage setup or required coverage gate is configured.

Mutation proof: temporarily changed only the new candidate key from `7` to `5`; `test_new_key_executes_to_seven` failed (`accepted: [5]` versus executed result `[7]`), with 3 tests run and 1 failure. Restored the exact original bytes in a finally block and reran the three content tests: all passed.

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
+      "body": "def meet(low, high):\n    if low >= high:\n        return low\n    return meet(low + 2, high - 1)\nresult = meet(1, 10)",
+      "choices": [],
+      "answer_key": {
+        "status": "candidate",
+        "accepted": [
+          "7"
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
+          "text": "The calls use (1, 10), (3, 9), (5, 8), and (7, 7). At (7, 7), low >= high is true, so the call returns low, which is 7. Each waiting call passes that value back unchanged, so result is 7."
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
+      "explanation": "The calls use (1, 10), (3, 9), (5, 8), and (7, 7). At (7, 7), low >= high is true, so the call returns low, which is 7. Each waiting call passes that value back unchanged, so result is 7. At (5, 8), the stopping condition is still false. The base case returns low, not high, and both arguments change in each self-call.",
+      "common_mistakes": [
+        "Stopping at low = 5 is one call too early: 5 is still below 8.",
+        "The base case returns low, not high. They happen to be equal in the final call here, but use the return expression as written.",
+        "Change both arguments in every self-call: add 2 to low and subtract 1 from high. Moving only one argument follows different calls."
       ]
     },
     {

```
