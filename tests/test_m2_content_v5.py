"""Focused checks for the immutable v5 content-correction draft."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import unittest

from aesop_lab.content import load_pack
from aesop_lab.domain.models import ActivityType, HintLevel


ROOT = Path(__file__).resolve().parents[1] / "content/packs/python-functions-recursion"
V4 = ROOT / "pack-m2-draft.4.json"
V5 = ROOT / "pack-m2-draft.5.json"


class M2ContentV5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = load_pack(V4)
        cls.pack = load_pack(V5)
        cls.items = {item.id: item for item in cls.pack.items}

    def test_new_immutable_version_retains_five_concepts_and_candidate_status(self):
        self.assertEqual(self.pack.pack_version, "m2-draft.5")
        self.assertEqual(self.pack.status, "draft")
        self.assertEqual(len(self.pack.concepts), 5)
        self.assertEqual(len(self.pack.items), 32)
        self.assertEqual({c.content_version for c in self.pack.concepts}, {"v5"})
        self.assertEqual({l.content_version for l in self.pack.lessons}, {"v5"})
        self.assertEqual({i.activity.content_version for i in self.pack.items}, {"v5"})
        self.assertFalse({l.id for l in self.pack.lessons} & {l.id for l in self.old.lessons})
        self.assertFalse({i.id for i in self.pack.items} & {i.id for i in self.old.items})
        self.assertFalse(self.pack.receipts)
        for item in self.pack.items:
            self.assertEqual(tuple(h.level for h in item.hints),
                             (HintLevel.NUDGE, HintLevel.TARGETED, HintLevel.WORKED_SOLUTION))
            if item.answer_key:
                self.assertEqual(item.answer_key.status, "candidate")
            else:
                self.assertIsNotNone(item.rubric)

    def test_all_authored_trace_keys_still_match_their_snippets(self):
        for item in self.pack.items:
            if item.activity.activity_type is not ActivityType.TRACE:
                continue
            with self.subTest(item=item.id):
                namespace = {}
                with redirect_stdout(StringIO()):
                    exec(item.body, namespace)
                actual = str(eval(item.check_expression, namespace))
                self.assertIn(actual, item.answer_key.accepted)

    def test_corrected_hint_explanations_and_observable_objectives(self):
        hint = self.items["base-case-recognize-v5"].hints[1].text
        self.assertIn("nonpositive", hint)
        self.assertIn("'done'", hint)
        self.assertNotIn("empty list", hint)
        objectives = {
            "scope-local-trace-01-v5": "locally rebound parameter",
            "scope-parameter-choice-v5": "parameter name",
            "scope-keyword-transfer-01-v5": "keyword argument",
            "base-case-reachability-v5": "which input",
            "base-case-week-01-v5": "integer halving",
        }
        for item_id, phrase in objectives.items():
            with self.subTest(item=item_id):
                self.assertIn(phrase, self.items[item_id].learning_objective)
        self.assertIn('reverse("c")', self.items["recursive-case-transfer-01-v5"].explanation)
        self.assertIn('replaces the default', self.items["scope-keyword-transfer-01-v5"].explanation)

    def test_new_week_item_is_distinct_from_ordinary_and_lesson_families(self):
        week = self.items["recursion-week-01-v5"]
        self.assertEqual(week.activity.family_id, "recursion-nested-wrap-week-v5")
        self.assertEqual(week.activity.check_delay_days, 7)
        self.assertTrue(week.activity.held_out)
        self.assertIn("'[' + nest(n - 1) + ']'", week.body)
        self.assertNotIn(week.activity.family_id,
                         {item.activity.family_id for item in self.pack.items if not item.activity.held_out})
        self.assertNotIn(week.activity.family_id,
                         {family for lesson in self.pack.lessons for family in lesson.encountered_family_ids})
        previous = next(item for item in self.old.items if item.id == "recursion-week-01-v4")
        self.assertNotEqual(week.activity.family_id, previous.activity.family_id)
        for concept in self.pack.concepts:
            checks = [item for item in self.pack.items_for(concept.id) if item.activity.held_out]
            self.assertEqual({item.activity.check_delay_days for item in checks}, {1, 7})

    def test_unmodified_families_remain_stable_across_versions(self):
        old_by_base = {item.id.removesuffix("-v4"): item for item in self.old.items}
        for item in self.pack.items:
            old = old_by_base[item.id.removesuffix("-v5")]
            with self.subTest(item=item.id):
                if item.id == "recursion-week-01-v5":
                    self.assertNotEqual(item.activity.family_id, old.activity.family_id)
                else:
                    self.assertEqual(item.activity.family_id, old.activity.family_id)

    def test_syntax_prerequisites_have_official_sources_without_answer_leak(self):
        lesson = next(l for l in self.pack.lessons if l.concept_id == "base-case")
        self.assertIn("items[1:]", lesson.body)
        self.assertIn("17 // 4", lesson.body)
        self.assertIn("py-std-sequence-operations", lesson.source_ids)
        self.assertIn("py-std-numeric-operations", lesson.source_ids)
        for item in self.pack.items:
            if item.activity.held_out:
                self.assertNotIn(item.body, lesson.body)
                self.assertNotIn(item.activity.family_id, lesson.encountered_family_ids)


if __name__ == "__main__":
    unittest.main()
