"""Prospective v9 recursion practice and historical-family regression checks."""

from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
from pathlib import Path
import unittest

from aesop_lab.assessment import AnswerKey, ItemSpec, assess
from aesop_lab.content import load_pack
from aesop_lab.domain.models import ActivityType, EvidenceKind, ScoreStatus


ROOT = Path(__file__).resolve().parents[1] / "content/packs/python-functions-recursion"
V8 = ROOT / "pack-m2-draft.8.json"
V9 = ROOT / "pack-m2-draft.9.json"
V8_SHA256 = "f521793aba1b0b71e1436ec90d62e3540d26e70e6665c8e0ce511dd226bb38b9"
NEW_ID = "recursive-case-application-02-v9"


class M2ContentV9Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = load_pack(V8)
        cls.pack = load_pack(V9)
        cls.items = {item.id: item for item in cls.pack.items}

    def test_version_identity_and_historical_v8_bytes(self):
        self.assertEqual(sha256(V8.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                         V8_SHA256)
        self.assertEqual((self.pack.pack_version, self.pack.status), ("m2-draft.9", "draft"))
        self.assertFalse(self.pack.receipts)
        self.assertEqual((len(self.pack.lessons), len(self.pack.items)), (5, 33))
        self.assertEqual({c.content_version for c in self.pack.concepts}, {"v9"})
        self.assertEqual({item.activity.content_version for item in self.pack.items}, {"v9"})
        self.assertFalse({item.id for item in self.pack.items} &
                         {item.id for item in self.old.items})
        self.assertTrue(all(item.answer_key.status == "candidate"
                            for item in self.pack.items if item.answer_key))

    def test_held_out_families_and_other_stimuli_unchanged(self):
        old_items = {item.id.removesuffix("-v8"): item for item in self.old.items}
        for item in self.pack.items:
            if item.id == NEW_ID:
                continue
            prior = old_items[item.id.removesuffix("-v9")]
            self.assertEqual((item.activity.family_id, item.activity.held_out,
                              item.activity.check_delay_days, item.prompt, item.body,
                              item.choices, item.answer_key, item.check_expression,
                              item.hints, item.explanation, item.common_mistakes),
                             (prior.activity.family_id, prior.activity.held_out,
                              prior.activity.check_delay_days, prior.prompt, prior.body,
                              prior.choices, prior.answer_key, prior.check_expression,
                              prior.hints, prior.explanation, prior.common_mistakes), item.id)
        for concept in self.pack.concepts:
            old_held = {item.activity.family_id for item in self.old.items
                        if item.activity.concept_id == concept.id and item.activity.held_out}
            new_held = {item.activity.family_id for item in self.pack.items
                        if item.activity.concept_id == concept.id and item.activity.held_out}
            self.assertEqual(new_held, old_held)
            self.assertEqual(len(new_held), 2)

    def test_recursion_practice_traces_return_and_normalizes_whitespace(self):
        item = self.items[NEW_ID]
        self.assertEqual((item.activity.activity_type, item.activity.evidence_kind,
                          item.activity.held_out),
                         (ActivityType.TRACE, EvidenceKind.APPLICATION, False))
        self.assertEqual(item.prompt, "After this code runs, what is the value of result?")
        self.assertNotIn("[1:]", item.body)
        self.assertIn("previous = savings(month - 1)", item.body)
        lesson = next(lesson for lesson in self.pack.lessons
                      if lesson.concept_id == item.activity.concept_id)
        held = {other.activity.family_id for other in self.pack.items
                if other.activity.held_out}
        self.assertNotIn(item.activity.family_id, lesson.encountered_family_ids)
        self.assertNotIn(item.activity.family_id, held)
        self.assertNotEqual(item.activity.family_id,
                            self.items["recursive-case-trace-01-v9"].activity.family_id)
        namespace = {}
        with redirect_stdout(StringIO()):
            exec(item.body, namespace)
        self.assertEqual(eval(item.check_expression, namespace), 51)
        self.assertEqual(item.answer_key.accepted, ("51",))
        spec = ItemSpec(item.activity, answer_key=AnswerKey(item.answer_key.accepted),
                        hints=None)
        self.assertIs(assess(spec, "  51\n").score_status, ScoreStatus.CORRECT)
        self.assertIs(assess(spec, "5 1").score_status, ScoreStatus.INCORRECT)
        self.assertEqual([hint.level for hint in item.hints],
                         ["nudge", "targeted", "worked_solution"])

    def test_recursive_design_rubric_covers_prompt_and_alternatives(self):
        rubric = self.items["recursive-case-design-01-v9"].rubric
        self.assertEqual({c.id for c in rubric.criteria},
                         {"empty-zero", "correct-sum", "progress", "no-loop"})
        self.assertIn("index-based recursive helper", rubric.annotated_example)

    def test_recursion_explanation_rubric_separates_self_call_progress_and_stop(self):
        item = self.items["recursion-explain-01-v9"]
        self.assertIn("how should each call move", item.prompt)
        self.assertEqual({c.id for c in item.rubric.criteria},
                         {"self-call", "progress", "stopping"})
        self.assertIn("reachable stopping condition", item.rubric.annotated_example)


if __name__ == "__main__":
    unittest.main()
