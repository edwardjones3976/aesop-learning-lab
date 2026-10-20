"""Regression checks for the immutable v7 trace-key correction over v6."""

from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import unittest

from aesop_lab.assessment import AnswerKey, ItemSpec, assess
from aesop_lab.content import load_pack
from aesop_lab.domain.models import ActivityType, ScoreStatus


ROOT = Path(__file__).resolve().parents[1] / "content/packs/python-functions-recursion"
V5, V6, V7 = (ROOT / f"pack-m2-draft.{n}.json" for n in (5, 6, 7))
# Line endings are normalized so a CRLF checkout hashes like the committed LF blob.
V5_SHA256 = "e63c11335a9bbc11412b8aeeff403feb61136efa3e7c1fd577dba4959f3a0918"
V6_SHA256 = "446def007e3df36d3b4c68c275ec707d3f0c42f6bf71cf3fc5bb058637d10f34"


def _digest(path):
    return sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


class M2ContentV7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v6 = load_pack(V6)
        cls.pack = load_pack(V7)
        cls.items = {item.id: item for item in cls.pack.items}

    def test_historical_v5_and_v6_pack_bytes_are_unchanged(self):
        self.assertEqual(_digest(V5), V5_SHA256)
        self.assertEqual(_digest(V6), V6_SHA256)

    def test_v7_is_a_draft_with_new_ids_and_no_receipts(self):
        self.assertEqual((self.pack.pack_version, self.pack.status), ("m2-draft.7", "draft"))
        self.assertFalse(self.pack.receipts)
        self.assertEqual((len(self.pack.lessons), len(self.pack.items)), (5, 32))
        self.assertEqual({c.content_version for c in self.pack.concepts}, {"v7"})
        self.assertEqual({i.activity.content_version for i in self.pack.items}, {"v7"})
        self.assertFalse({i.id for i in self.pack.items} & {i.id for i in self.v6.items})
        self.assertFalse({l.id for l in self.pack.lessons} & {l.id for l in self.v6.lessons})
        self.assertTrue(all(i.answer_key.status == "candidate"
                            for i in self.pack.items if i.answer_key))

    def test_v7_changes_only_the_malformed_key_and_version_labels(self):
        old = {i.id.removesuffix("-v6"): i for i in self.v6.items}
        changed = []
        for item in self.pack.items:
            prior = old[item.id.removesuffix("-v7")]
            self.assertEqual(item.activity.family_id, prior.activity.family_id)
            self.assertEqual((item.prompt, item.body, item.choices, item.explanation),
                             (prior.prompt, prior.body, prior.choices, prior.explanation))
            if item.answer_key != prior.answer_key:
                changed.append(item.id)
        self.assertEqual(changed, ["recursion-week-01-v7"])

    def test_correctly_quoted_day_seven_result_is_credited(self):
        item = self.items["recursion-week-01-v7"]
        self.assertEqual(item.activity.check_delay_days, 7)
        spec = ItemSpec(item.activity, answer_key=AnswerKey(item.answer_key.accepted),
                        hints=None)
        for answer in ("[[[core]]]", "'[[[core]]]'", '"[[[core]]]"'):
            with self.subTest(answer=answer):
                self.assertIs(assess(spec, answer).score_status, ScoreStatus.CORRECT)
        self.assertIs(assess(spec, "'[[[core]]]").score_status, ScoreStatus.INCORRECT)
        old = next(i for i in self.v6.items if i.id == "recursion-week-01-v6")
        self.assertNotIn("'[[[core]]]'", old.answer_key.accepted)

    def test_every_trace_key_accepts_plain_and_quoted_python_results(self):
        for item in self.pack.items:
            if item.activity.activity_type is not ActivityType.TRACE:
                continue
            with self.subTest(item=item.id):
                namespace = {}
                with redirect_stdout(StringIO()):
                    exec(item.body, namespace)
                result = eval(item.check_expression, namespace)
                self.assertIn(str(result), item.answer_key.accepted)
                if isinstance(result, str):
                    self.assertIn(repr(result), item.answer_key.accepted)
                    self.assertIn(f'"{result}"', item.answer_key.accepted)
                for accepted in item.answer_key.accepted:
                    self.assertEqual(accepted.count("'") % 2, 0)
                    self.assertEqual(accepted.count('"') % 2, 0)


if __name__ == "__main__":
    unittest.main()
