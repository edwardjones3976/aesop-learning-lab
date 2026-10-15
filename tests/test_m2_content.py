"""Contract checks for the expanded, still-unreviewed five-concept pack."""

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from aesop_lab.content import load_pack
from aesop_lab.domain.models import ActivityType, EvidenceKind, HintLevel


PACK = Path(__file__).resolve().parents[1] / "content/packs/python-functions-recursion/pack-m2-draft.4.json"
PRIOR = PACK.with_name("pack-m1-draft.3.json")


class M2ContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = load_pack(PACK)
        cls.prior = load_pack(PRIOR)

    def test_immutable_new_version_and_five_substantive_lessons(self):
        self.assertEqual(self.pack.pack_version, "m2-draft.4")
        self.assertEqual(self.pack.status, "draft")
        self.assertEqual(len(self.pack.concepts), 5)
        self.assertEqual({c.content_version for c in self.pack.concepts}, {"v4"})
        self.assertEqual({l.content_version for l in self.pack.lessons}, {"v4"})
        self.assertEqual({i.activity.content_version for i in self.pack.items}, {"v4"})
        self.assertFalse({l.id for l in self.pack.lessons} & {l.id for l in self.prior.lessons})
        self.assertFalse({i.id for i in self.pack.items} & {i.id for i in self.prior.items})
        for lesson in self.pack.lessons:
            with self.subTest(lesson=lesson.id):
                self.assertGreater(len(lesson.body), 1400)
                for section in ("Learning objectives", "Before you begin", "How it works", "Common misconceptions", "Practice path"):
                    self.assertIn(section, lesson.body)
                self.assertIn("```python", lesson.body)
                self.assertTrue(lesson.diagram.strip())

    def test_comparable_diagram_adds_no_assessment_answer_or_alternative_text(self):
        for lesson in self.pack.lessons:
            with self.subTest(lesson=lesson.id):
                self.assertNotIn("held-out", lesson.diagram.lower())
                self.assertNotIn("week", lesson.diagram.lower())
                self.assertLess(len(lesson.diagram), len(lesson.body))

    def test_worked_example_families_are_recorded_and_not_held_out(self):
        raw = json.loads(PACK.read_text(encoding="utf-8"))
        expected = {
            "function-definition-and-return": ["lesson-price-with-tax-v4", "def-return-recall-v4"],
            "parameters-and-local-scope": ["lesson-keyword-default-global-v4"],
            "recursion-as-self-call": ["lesson-countdown-prepend-v4"],
            "base-case": ["lesson-decrement-to-zero-v4"],
            "recursive-case-and-trace": ["recursive-case-trace-a"],
        }
        held_out = {item["family_id"] for item in raw["items"] if item["held_out"]}
        for lesson in raw["lessons"]:
            with self.subTest(lesson=lesson["id"]):
                families = lesson["encountered_family_ids"]
                self.assertEqual(families, expected[lesson["concept_id"]])
                self.assertEqual(len(families), len(set(families)))
                self.assertFalse(set(families) & held_out)

    def test_five_concepts_have_progressive_evidence_and_protected_delayed_families(self):
        for concept in self.pack.concepts:
            with self.subTest(concept=concept.id):
                items = self.pack.items_for(concept.id)
                self.assertGreaterEqual(len(items), 6)
                self.assertTrue(any(i.activity.evidence_kind is EvidenceKind.RECOGNITION and not i.activity.held_out for i in items))
                self.assertTrue(any(i.activity.evidence_kind is EvidenceKind.RECALL and not i.activity.held_out for i in items))
                self.assertTrue(any(i.activity.evidence_kind is EvidenceKind.APPLICATION and not i.activity.held_out for i in items))
                self.assertTrue(any(i.activity.evidence_kind is EvidenceKind.EXPLANATION and not i.activity.held_out for i in items))
                checks = [i for i in items if i.activity.held_out]
                self.assertEqual({i.activity.check_delay_days for i in checks}, {1, 7})
                self.assertFalse({i.activity.family_id for i in checks} & {i.activity.family_id for i in items if not i.activity.held_out})
                old_week = next(i for i in self.prior.items_for(concept.id) if i.activity.check_delay_days == 7)
                new_week = next(i for i in checks if i.activity.check_delay_days == 7)
                replaced = {
                    "base-case": "base-case-threshold-halving-week-v4",
                    "parameters-and-local-scope": "scope-combined-default-local-week-v4",
                    "function-definition-and-return": "def-return-shipping-week-v4",
                    "recursion-as-self-call": "recursion-return-order-week-v4",
                }
                if concept.id in replaced:
                    self.assertEqual(new_week.activity.family_id, replaced[concept.id])
                    self.assertNotEqual(new_week.activity.family_id, old_week.activity.family_id)
                else:
                    self.assertEqual(new_week.activity.family_id, old_week.activity.family_id)

    def test_scored_keys_remain_candidates_and_free_text_remains_ungraded(self):
        self.assertFalse(self.pack.receipts)
        for item in self.pack.items:
            self.assertEqual(tuple(h.level for h in item.hints),
                             (HintLevel.NUDGE, HintLevel.TARGETED, HintLevel.WORKED_SOLUTION))
            if item.activity.activity_type in (ActivityType.EXPLANATION, ActivityType.CODE_DESIGN):
                self.assertIsNone(item.answer_key)
                self.assertIsNotNone(item.rubric)
            else:
                self.assertEqual(item.answer_key.status, "candidate")

    def test_item_objectives_difficulty_and_explanations_are_explicit(self):
        raw = json.loads(PACK.read_text(encoding="utf-8"))
        for item in raw["items"]:
            with self.subTest(item=item["id"]):
                self.assertTrue(item["learning_objective"].strip())
                self.assertIn(item["difficulty"], ("introductory", "intermediate", "advanced"))
                self.assertGreater(len(item["explanation"]), 20)
                self.assertEqual(item["explanation"], item["hints"][-1]["text"])
                if item["held_out"]:
                    self.assertEqual(item["difficulty"], "advanced")

    def test_all_candidate_trace_keys_match_trusted_snippets(self):
        for item in self.pack.items:
            if item.activity.activity_type is not ActivityType.TRACE:
                continue
            with self.subTest(item=item.id):
                self.assertIsNotNone(item.check_expression)
                scope = {}
                with redirect_stdout(StringIO()):
                    exec(item.body, scope)
                actual = str(eval(item.check_expression, scope))
                self.assertIn(actual, item.answer_key.accepted)


if __name__ == "__main__":
    unittest.main()
