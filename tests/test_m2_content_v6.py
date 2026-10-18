"""Content-only regression checks for the immutable v6 author draft."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import unittest

from aesop_lab.content import load_pack
from aesop_lab.domain.models import ActivityType, HintLevel


ROOT = Path(__file__).resolve().parents[1] / "content/packs/python-functions-recursion"
V5 = ROOT / "pack-m2-draft.5.json"
V6 = ROOT / "pack-m2-draft.6.json"


class M2ContentV6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = load_pack(V5)
        cls.pack = load_pack(V6)
        cls.raw = json.loads(V6.read_text(encoding="utf-8"))
        cls.items = {item.id: item for item in cls.pack.items}

    def test_v6_is_a_new_draft_with_five_lessons_and_new_activity_ids(self):
        self.assertEqual(self.pack.pack_version, "m2-draft.6")
        self.assertEqual(self.pack.status, "draft")
        self.assertFalse(self.pack.receipts)
        self.assertEqual(len(self.pack.concepts), 5)
        self.assertEqual(len(self.pack.lessons), 5)
        self.assertEqual(len(self.pack.items), 32)
        self.assertEqual({concept.content_version for concept in self.pack.concepts}, {"v6"})
        self.assertEqual({lesson.content_version for lesson in self.pack.lessons}, {"v6"})
        self.assertEqual({item.activity.content_version for item in self.pack.items}, {"v6"})
        self.assertFalse({lesson.id for lesson in self.pack.lessons} &
                         {lesson.id for lesson in self.old.lessons})
        self.assertFalse({item.id for item in self.pack.items} &
                         {item.id for item in self.old.items})

    def test_all_candidate_scored_items_have_reasoning_and_specific_mistakes(self):
        scored = 0
        for item in self.raw["items"]:
            with self.subTest(item=item["id"]):
                self.assertEqual([hint["level"] for hint in item["hints"]],
                                 ["nudge", "targeted", "worked_solution"])
                if item.get("answer_key") is None:
                    self.assertIsNotNone(item.get("rubric"))
                    self.assertNotIn("common_mistakes", item)
                    continue
                scored += 1
                self.assertEqual(item["answer_key"]["status"], "candidate")
                self.assertTrue(item["answer_key"]["accepted"])
                self.assertGreater(len(item["explanation"]), 25)
                self.assertEqual(item["explanation"], item["hints"][-1]["text"])
                self.assertTrue(item["common_mistakes"])
                self.assertTrue(all(len(mistake.strip()) > 20 for mistake in item["common_mistakes"]))
        self.assertEqual(scored, 26)

    def test_all_authored_trace_keys_match_their_code(self):
        for item in self.pack.items:
            if item.activity.activity_type is not ActivityType.TRACE:
                continue
            with self.subTest(item=item.id):
                namespace = {}
                with redirect_stdout(StringIO()):
                    exec(item.body, namespace)
                result = str(eval(item.check_expression, namespace))
                self.assertIn(result, item.answer_key.accepted)

    def test_choice_keys_and_rubrics_preserve_scoring_boundaries(self):
        for item in self.pack.items:
            with self.subTest(item=item.id):
                self.assertEqual(tuple(h.level for h in item.hints),
                                 (HintLevel.NUDGE, HintLevel.TARGETED, HintLevel.WORKED_SOLUTION))
                if item.activity.activity_type is ActivityType.CHOICE:
                    self.assertIn(item.answer_key.accepted[0], item.choices)
                if item.activity.activity_type in (ActivityType.EXPLANATION, ActivityType.CODE_DESIGN):
                    self.assertIsNone(item.answer_key)
                    self.assertIsNotNone(item.rubric)

    def test_held_out_families_do_not_overlap_examples_or_routine_practice(self):
        held_out = {item.activity.family_id for item in self.pack.items if item.activity.held_out}
        lesson_families = {family for lesson in self.pack.lessons
                           for family in lesson.encountered_family_ids}
        ordinary = {item.activity.family_id for item in self.pack.items if not item.activity.held_out}
        self.assertFalse(held_out & lesson_families)
        self.assertFalse(held_out & ordinary)
        for concept in self.pack.concepts:
            checks = [item for item in self.pack.items_for(concept.id) if item.activity.held_out]
            self.assertEqual({item.activity.check_delay_days for item in checks}, {1, 7})
        base = self.items["base-case-transfer-01-v6"]
        self.assertEqual(base.activity.family_id, "base-case-grow-threshold-day-v6")
        self.assertNotIn("[1:]", base.body)
        self.assertIn("n + 7", base.body)
        self.assertNotIn("//", base.body)
        week = self.items["recursive-case-week-01-v6"]
        self.assertEqual(week.activity.family_id, "recursive-case-lamp-toggle-week-v6")
        self.assertIn("previous = lamp_state(presses - 1)", week.body)
        self.assertNotIn("//", week.body)

    def test_identical_add_five_stimulus_is_one_family(self):
        self.assertEqual(self.items["scope-local-trace-01-v6"].activity.family_id,
                         self.items["scope-global-choice-01-v6"].activity.family_id)

    def test_lessons_remain_substantive_with_versioned_example_families(self):
        for lesson in self.pack.lessons:
            with self.subTest(lesson=lesson.id):
                self.assertGreater(len(lesson.body), 1400)
                self.assertIn("Learning objectives", lesson.body)
                self.assertIn("Common misconceptions", lesson.body)
                self.assertIn("```python", lesson.body)
                self.assertTrue(lesson.diagram)
                self.assertTrue(lesson.encountered_family_ids)
                self.assertTrue(lesson.source_ids)
                for item in self.pack.items:
                    if item.activity.held_out:
                        self.assertNotIn(item.body, lesson.body)


if __name__ == "__main__":
    unittest.main()
