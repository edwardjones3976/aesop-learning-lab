"""Prospective v8 recursive-case practice and historical-content checks."""

from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
from pathlib import Path
import unittest

from aesop_lab.assessment import AnswerKey, ItemSpec, assess
from aesop_lab.content import load_pack
from aesop_lab.domain.models import ActivityType, EvidenceKind, ScoreStatus


ROOT = Path(__file__).resolve().parents[1] / "content/packs/python-functions-recursion"
V7 = ROOT / "pack-m2-draft.7.json"
V8 = ROOT / "pack-m2-draft.8.json"
V7_SHA256 = "f745652b76f2297cab78649bf1ecdf66acb7e7f2f173a0eb174aefbf16225af0"
NEW_ID = "recursive-case-application-02-v8"


class M2ContentV8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = load_pack(V7)
        cls.pack = load_pack(V8)
        cls.items = {item.id: item for item in cls.pack.items}

    def test_v7_bytes_and_v8_version_identity(self):
        self.assertEqual(sha256(V7.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                         V7_SHA256)
        self.assertEqual((self.pack.pack_version, self.pack.status), ("m2-draft.8", "draft"))
        self.assertFalse(self.pack.receipts)
        self.assertEqual((len(self.pack.lessons), len(self.pack.items)), (5, 33))
        self.assertEqual({c.content_version for c in self.pack.concepts}, {"v8"})
        self.assertEqual({item.activity.content_version for item in self.pack.items}, {"v8"})
        self.assertFalse({item.id for item in self.pack.items} &
                         {item.id for item in self.old.items})
        self.assertFalse({lesson.id for lesson in self.pack.lessons} &
                         {lesson.id for lesson in self.old.lessons})
        self.assertTrue(all(item.answer_key.status == "candidate"
                            for item in self.pack.items if item.answer_key))

    def test_only_new_practice_changes_stimulus_and_held_out_families_stay_fixed(self):
        old_items = {item.id.removesuffix("-v7"): item for item in self.old.items}
        for item in self.pack.items:
            if item.id == NEW_ID:
                continue
            prior = old_items[item.id.removesuffix("-v8")]
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

    def test_new_independent_practice_has_correct_key_and_separate_family(self):
        item = self.items[NEW_ID]
        self.assertEqual((item.activity.activity_type, item.activity.evidence_kind,
                          item.activity.held_out),
                         (ActivityType.TRACE, EvidenceKind.APPLICATION, False))
        lesson = next(lesson for lesson in self.pack.lessons
                      if lesson.concept_id == item.activity.concept_id)
        held = {other.activity.family_id for other in self.pack.items
                if other.activity.held_out}
        self.assertNotIn(item.activity.family_id, lesson.encountered_family_ids)
        self.assertNotIn(item.activity.family_id, held)
        self.assertNotEqual(item.activity.family_id,
                            self.items["recursive-case-trace-01-v8"].activity.family_id)
        self.assertIn("if scores[0] >= 60", item.body)
        self.assertIn("scores[1:]", item.body)
        namespace = {}
        with redirect_stdout(StringIO()):
            exec(item.body, namespace)
        self.assertEqual(eval(item.check_expression, namespace), 2)
        self.assertEqual(item.answer_key.accepted, ("2",))
        spec = ItemSpec(item.activity, answer_key=AnswerKey(item.answer_key.accepted),
                        hints=None)
        self.assertIs(assess(spec, "2").score_status, ScoreStatus.CORRECT)
        self.assertIs(assess(spec, "127").score_status, ScoreStatus.INCORRECT)
        self.assertEqual([hint.level for hint in item.hints],
                         ["nudge", "targeted", "worked_solution"])


if __name__ == "__main__":
    unittest.main()
