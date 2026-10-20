"""Prospective v10 plain-language rewrite keeps every v9 stimulus, key, and ID."""

from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
from pathlib import Path
import json
import re
import unittest

from aesop_lab.content import load_pack


ROOT = Path(__file__).resolve().parents[1] / "content/packs/python-functions-recursion"
V9 = ROOT / "pack-m2-draft.9.json"
V10 = ROOT / "pack-m2-draft.10.json"
V9_SHA256 = "2affda559dae7cb15be0cb8570f6dd758331072ef77146cf452873e244544692"
CODE = re.compile(r"```python\n.*?```", re.S)
# Learner-facing prose fields that v10 may reword; everything else must match v9.
ITEM_PROSE = {"content_version", "hints", "explanation", "common_mistakes",
              "learning_objective", "rubric"}
LESSON_PROSE = {"content_version", "body", "diagram"}


def _raw(path):
    return json.loads(path.read_text(encoding="utf-8"))


class M2ContentV10Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_raw, cls.raw = _raw(V9), _raw(V10)
        cls.old, cls.pack = load_pack(V9), load_pack(V10)

    def test_version_identity_draft_status_and_historical_v9_bytes(self):
        self.assertEqual(sha256(V9.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                         V9_SHA256)
        self.assertEqual((self.pack.pack_version, self.pack.status), ("m2-draft.10", "draft"))
        self.assertFalse(self.pack.receipts)
        self.assertEqual({c.content_version for c in self.pack.concepts}, {"v10"})
        self.assertEqual({lesson.content_version for lesson in self.pack.lessons}, {"v10"})
        self.assertEqual({item.activity.content_version for item in self.pack.items}, {"v10"})
        self.assertTrue(all(item.answer_key.status == "candidate"
                            for item in self.pack.items if item.answer_key))
        for key in ("schema_version", "pack_id", "topic", "sources", "concepts"):
            if key != "concepts":
                self.assertEqual(self.raw[key], self.old_raw[key], key)
        self.assertEqual([{**c, "content_version": "v9"} for c in self.raw["concepts"]],
                         self.old_raw["concepts"])

    def test_items_keep_ids_stimuli_keys_and_hint_levels(self):
        self.assertEqual([i["id"] for i in self.raw["items"]],
                         [i["id"] for i in self.old_raw["items"]])
        for new, old in zip(self.raw["items"], self.old_raw["items"]):
            self.assertEqual(new.keys(), old.keys(), old["id"])
            for key in new.keys() - ITEM_PROSE:
                self.assertEqual(new[key], old[key], (old["id"], key))
            self.assertEqual([h["level"] for h in new["hints"]],
                             [h["level"] for h in old["hints"]], old["id"])
            self.assertEqual(len(new.get("common_mistakes", ())),
                             len(old.get("common_mistakes", ())), old["id"])
            if old.get("rubric"):
                rubric, old_rubric = new["rubric"], old["rubric"]
                self.assertEqual((rubric["id"], rubric["criteria"]),
                                 (old_rubric["id"], old_rubric["criteria"]), old["id"])
                self.assertEqual(len(rubric["common_mistakes"]),
                                 len(old_rubric["common_mistakes"]))
            else:
                self.assertEqual(new.get("rubric"), old.get("rubric"), old["id"])
        design = next(i for i in self.raw["items"] if i["id"] == "recursive-case-design-01-v9")
        code = "def sum_list(items):\n    if not items:\n        return 0\n"
        self.assertTrue(design["rubric"]["annotated_example"].startswith(code))

    def test_prose_was_rewritten_and_held_out_families_stay_out_of_lessons(self):
        old_items = {i["id"]: i for i in self.old_raw["items"]}
        changed = [i["id"] for i in self.raw["items"]
                   if i["hints"] != old_items[i["id"]]["hints"]
                   or i["learning_objective"] != old_items[i["id"]]["learning_objective"]]
        self.assertEqual(len(changed), len(self.raw["items"]))
        held = {item.activity.family_id for item in self.pack.items if item.activity.held_out}
        self.assertEqual(held, {item.activity.family_id for item in self.old.items
                                if item.activity.held_out})
        for new, old in zip(self.raw["lessons"], self.old_raw["lessons"]):
            for key in new.keys() - LESSON_PROSE:
                self.assertEqual(new[key], old[key], (old["id"], key))
            self.assertNotEqual(new["body"], old["body"])
            self.assertEqual(CODE.findall(new["body"]), CODE.findall(old["body"]), old["id"])
            self.assertEqual(new["diagram"].split("\n")[:-1], old["diagram"].split("\n")[:-1])
            self.assertFalse(held & set(new["encountered_family_ids"]))
        for item in self.pack.items:
            self.assertEqual(len(item.explanation.split(". ")) >= 1, True)

    def test_trace_answers_still_execute_to_the_unchanged_keys(self):
        for item in self.pack.items:
            if not item.check_expression:
                continue
            namespace = {}
            with redirect_stdout(StringIO()):
                exec(item.body, namespace)
            value = eval(item.check_expression, namespace)
            self.assertIn(str(value), item.answer_key.accepted, item.id)


if __name__ == "__main__":
    unittest.main()
