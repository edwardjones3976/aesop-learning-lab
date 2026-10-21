"""Key and outcome lock tests under current pack (m2-draft.11) and protocol (DESCRIPTIVE_V8)."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from aesop_lab.assessment.items import normalize_answer
from aesop_lab.content import load_pack
from aesop_lab.experiment.descriptive_v8 import (
    DESCRIPTIVE_V8,
    analyze_v8,
    assign_condition_v8,
)
from aesop_lab.foreman import CURRENT_PACK_PATH, Preview, VERSION_BY_CONTENT


# Plausible learner mistakes keyed by item id with a one-line reason each.
# Based on the item's own common_mistakes text where given.
DISTINCT_WRONG_ANSWERS = {
    # def area(width, height): return width * height; result = area(3, 4) - 2
    # common_mistakes: "Adding 3 and 4, or skipping the subtraction, gives the wrong result."
    "def-return-transfer-01-v9": (
        "12",
        "Skipping caller subtraction of 2 leaves 12 instead of 10",
    ),
    # def greet(name, punctuation="!"): return "Hi " + name + punctuation; result = greet("Ana", punctuation="?")
    # common_mistakes: "The call gives punctuation='?', so this call uses '?' instead of the default '!'."
    "scope-keyword-transfer-01-v9": (
        "Hi Ana!",
        "Using default punctuation '!' instead of explicit keyword argument '?' gives 'Hi Ana!'",
    ),
    # def leaf_count(level): if level == 0: return 1; return 2 * leaf_count(level - 1); result = leaf_count(4)
    # common_mistakes: "The base level returns 1, not 0. Each of the four levels above it doubles that value."
    "recursion-halving-transfer-01-v9": (
        "0",
        "Mistakenly returning 0 at base level produces 0 after repeated doubling",
    ),
    # def reach_target(n): if n >= 20: return n; return reach_target(n + 7); result = reach_target(3)
    # common_mistakes: "17 is still below 20, so that call does not stop. The next call gets 24..."
    "base-case-transfer-01-v9": (
        "17",
        "Stopping one step too early at 17 when threshold is 20",
    ),
    # def reverse(text): if len(text) <= 1: return text; return reverse(text[1:]) + text[0]; result = reverse("abc")
    # common_mistakes: "If each recursive case used return text[0] + reverse(text[1:])... That gives 'abc' for 'abc', not 'cba'."
    "recursive-case-transfer-01-v9": (
        "abc",
        "Preserving order with text[0] + reverse(text[1:]) produces 'abc' instead of 'cba'",
    ),
    # def shipping(weight): if weight <= 2: return 5; return 5 + (weight - 2) * 3; result = shipping(4) + shipping(1)
    # common_mistakes: "shipping(4) and shipping(1) take different branches. Using one branch for both calls gives the wrong total."
    "def-return-week-01-v9": (
        "10",
        "Using base tier branch 5 for both calls (weight 4 and 1) gives 10 instead of 16",
    ),
    # def mark(word, suffix='!'): word = '[' + word + ']'; return word + suffix; note = 'map'; result = mark(note) + ':' + note
    # common_mistakes: "Changing the local word does not change the caller's note."
    "scope-week-01-v9": (
        "[map]!:[map]",
        "Assuming local reassignment mutates caller note gives '[map]!:[map]'",
    ),
    # def meet(low, high): if low >= high: return low; return meet(low + 2, high - 1); result = meet(0, 8)
    # common_mistakes: "The base case returns low, not high. Returning high gives 5."
    "recursion-week-01-v11": (
        "5",
        "Returning high (5) instead of low (6) at convergence",
    ),
    # def label_depth(n): if n < 4: return 'small'; return label_depth(n // 2) + '!'; result = label_depth(20)
    # common_mistakes: "Whole-number halving reaches n = 2 before it returns small. After that, the calls at 5, 10, and 20 add their marks."
    "base-case-week-01-v9": (
        "small",
        "Omitting the exclamation marks accumulated from recursive unwind returns only 'small'",
    ),
    # def lamp_state(presses): if presses == 0: return 'off'; previous = lamp_state(presses - 1); return 'on' if previous == 'off' else 'off'
    # common_mistakes: "The calls above zero do not all return on. Each call flips the state returned by the smaller call."
    "recursive-case-week-01-v9": (
        "off",
        "Failing to toggle or miscounting flips for 5 presses yields 'off' instead of 'on'",
    ),
}


class KeyAndOutcomeLockTests(unittest.TestCase):
    """Lock tests ensuring distinct wrong answers, zero eligible outcomes on candidate keys,

    and strict preservation of primary transfer maps.
    """

    def setUp(self):
        with open(CURRENT_PACK_PATH, "r", encoding="utf-8") as f:
            self.pack_dict = json.load(f)

    # -------------------------------------------------------------------------
    # (a) DISTINCT WRONG ANSWERS
    # -------------------------------------------------------------------------
    def test_distinct_wrong_answers_for_held_out_items(self):
        held_out_items = [it for it in self.pack_dict.get("items", []) if it.get("held_out")]
        self.assertEqual(len(held_out_items), 10, "Current pack must have exactly 10 held-out items")

        held_out_ids = {it["id"] for it in held_out_items}
        self.assertEqual(
            held_out_ids,
            set(DISTINCT_WRONG_ANSWERS.keys()),
            "Mismatch between held-out items and DISTINCT_WRONG_ANSWERS mapping",
        )

        for item in held_out_items:
            item_id = item["id"]
            self.assertIn("check_expression", item, f"{item_id} missing check_expression")
            self.assertIn("body", item, f"{item_id} missing body")
            self.assertIn("answer_key", item, f"{item_id} missing answer_key")

            # Execute body and evaluate check_expression
            scope = {}
            exec(item["body"], scope)
            eval_result = eval(item["check_expression"], scope)

            accepted_raw = item["answer_key"].get("accepted", [])
            self.assertTrue(accepted_raw, f"{item_id} must have accepted answers")

            # Scorer normalization: normalize_answer applied to AnswerKey accepted values
            norm_accepted = {normalize_answer(a) for a in accepted_raw}
            norm_eval_result = normalize_answer(str(eval_result))

            # Executed result must be in item's accepted answers
            self.assertIn(
                norm_eval_result,
                norm_accepted,
                f"Evaluated result {eval_result!r} for {item_id} not in accepted {accepted_raw}",
            )

            # Plausible learner mistake must NOT be accepted
            wrong_value, reason = DISTINCT_WRONG_ANSWERS[item_id]
            self.assertTrue(reason, f"Reason must be provided for wrong answer of {item_id}")
            norm_wrong = normalize_answer(str(wrong_value))

            self.assertNotIn(
                norm_wrong,
                norm_accepted,
                f"Plausible mistake {wrong_value!r} for {item_id} was incorrectly accepted",
            )

    # -------------------------------------------------------------------------
    # (b) ELIGIBLE STAYS ZERO WITH CANDIDATE KEYS
    # -------------------------------------------------------------------------
    def test_eligible_stays_zero_with_candidate_keys(self):
        # Every item with an answer key in the current pack has status 'candidate'
        items_with_key = [
            it for it in self.pack_dict.get("items", [])
            if it.get("answer_key") is not None
        ]
        self.assertTrue(items_with_key, "Pack must contain items with answer_key")
        for item in items_with_key:
            self.assertEqual(
                item["answer_key"].get("status"),
                "candidate",
                f"Item {item.get('id')} status is not 'candidate'",
            )

        td = tempfile.TemporaryDirectory()
        try:
            db_path = Path(td.name) / "lock_test.db"
            t0 = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
            current_clock = [t0]

            preview = Preview(db_path, now=lambda: current_clock[0])
            pack = load_pack(CURRENT_PACK_PATH)
            item_map = {item.id: item for item in pack.items}

            concept_id = "function-definition-and-return"
            target_arm = "text"
            learner_id = next(
                f"synthetic-lock-{candidate}"
                for candidate in range(100)
                if assign_condition_v8(concept_id, f"synthetic-lock-{candidate}") == target_arm
            )
            with preview.store.connection:
                preview.store.connection.execute(
                    "INSERT INTO learner_identity (slot, id) VALUES (1, ?)",
                    (learner_id,),
                )

            preview.lesson(concept_id)
            preview.complete_lesson(concept_id)

            # Day 0 practice
            session_d0 = preview.session(concept_id, mode="practice")
            d0_item = session_d0["activity"]
            d0_did = str(uuid4())
            ans0 = item_map[d0_item["id"]].answer_key.accepted[0]
            preview.first_answer({
                "conceptId": concept_id,
                "activityId": d0_item["id"],
                "draftId": d0_did,
                "answer": ans0,
            })
            preview.submit({"draftId": d0_did, "outsideStudy": "none"})

            # Day 1 return
            current_clock[0] += timedelta(days=1, hours=2)
            session_d1 = preview.session(concept_id, mode="recommended")
            d1_item = session_d1.get("activity")
            if d1_item and d1_item.get("checkDelayDays") == 1:
                d1_did = str(uuid4())
                ans1 = item_map[d1_item["id"]].answer_key.accepted[0]
                preview.first_answer({
                    "conceptId": concept_id,
                    "activityId": d1_item["id"],
                    "draftId": d1_did,
                    "answer": ans1,
                })
                preview.submit({"draftId": d1_did, "outsideStudy": "none"})

            # Primary day-7 check correctly, unassisted, inside day 7-14 window
            primary_family = DESCRIPTIVE_V8.primary_families[concept_id]
            primary_pack_item = next(
                item for item in pack.items
                if item.activity.concept_id == concept_id and item.activity.family_id == primary_family
            )
            correct_key = primary_pack_item.answer_key.accepted[0]

            current_clock[0] = t0 + timedelta(days=7, hours=2)
            session_d7 = preview.session(concept_id, mode="recommended")
            d7_item = session_d7["activity"]
            self.assertEqual(d7_item["familyId"], primary_family)
            d7_did = str(uuid4())
            preview.first_answer({
                "conceptId": concept_id,
                "activityId": d7_item["id"],
                "draftId": d7_did,
                "answer": correct_key,
            })
            preview.submit({"draftId": d7_did, "outsideStudy": "none"})

            # Assert classification is 'provisional' and arm eligible count is 0
            findings = preview.experiment_findings()
            obs = findings["arms"][target_arm]["observations"][0]
            self.assertEqual(obs["classification"], "provisional")
            self.assertEqual(findings["arms"][target_arm]["eligible"], 0)

            # Inverse check: calling analyze_v8 (or _analyze) with content_review_status='reviewed'
            # on the same data (with reviewed key grading) gives 'eligible' with count 1
            version = preview.pack.concepts[0].content_version
            spec = VERSION_BY_CONTENT[version]
            protocol, _, Exposure, _ = spec.comparison.load()
            exposures = tuple(Exposure(
                row["concept_id"], row["content_version"], row["condition_id"],
                datetime.fromisoformat(row["exposed_at"]),
                tuple(json.loads(row["encountered_family_ids"])),
                row["protocol_id"], row["protocol_version"],
                datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            ) for row in preview.store.list_exposures()
                if row["protocol_id"] == protocol.id and row["protocol_version"] == protocol.version)
            attempts = tuple(a for concept in preview.pack.concepts
                             for a in preview.store.list_attempts(concept.id))
            activities = {item.activity.id: item.activity for item in preview.pack.items}
            assignments = tuple(a for a in preview.store.list_assignments(protocol.id)
                                if a.protocol_version == protocol.version)

            reviewed_attempts = tuple(
                replace(a, grading_method="reviewed_exact_key")
                if a.grading_method == "development_fixture_exact_key" else a
                for a in attempts
            )

            analyzed_reviewed = analyze_v8(
                assignments,
                exposures,
                reviewed_attempts,
                activities,
                learner_id=learner_id,
                now=current_clock[0],
                content_review_status="reviewed",
            )
            obs_rev = analyzed_reviewed["arms"][target_arm]["observations"][0]
            self.assertEqual(obs_rev["classification"], "eligible")
            self.assertEqual(analyzed_reviewed["arms"][target_arm]["eligible"], 1)

        finally:
            for s in preview.services.values():
                s.store.close()
            td.cleanup()

    # -------------------------------------------------------------------------
    # (c) DAY-1 NEAR-TRANSFER FAMILIES STAY OFF THE PRIMARY MAP
    # -------------------------------------------------------------------------
    def test_day1_near_transfer_families_stay_off_primary_map(self):
        primary_families_set = set(DESCRIPTIVE_V8.primary_families.values())

        # Neither def-return-transfer-a nor recursion-halving-transfer-a is in primary_families
        self.assertNotIn("def-return-transfer-a", primary_families_set)
        self.assertNotIn("recursion-halving-transfer-a", primary_families_set)

        # Every primary family is the family of a held-out item with check_delay_days 7
        held_out_d7 = [
            it for it in self.pack_dict.get("items", [])
            if it.get("held_out") and it.get("check_delay_days") == 7
        ]
        held_out_d7_families = {it["family_id"] for it in held_out_d7}

        self.assertEqual(
            primary_families_set,
            held_out_d7_families,
            "Every primary family must be the family of a held-out item with check_delay_days 7",
        )
