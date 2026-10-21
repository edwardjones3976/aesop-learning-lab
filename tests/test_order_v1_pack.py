"""Tests for the paired order-v1 micro-unit pack."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from aesop_lab.content.micro_unit import load_micro_unit_pack
from scripts.build_order_v1_pack import build_pack, generate_order_v1_pack_data, serialize_pack


PACK_PATH = Path("content/drafts/order-v1-invented-pack.json")
LEXICON_PATH = Path("content/drafts/invented-lexicon-v1.json")
AUTHORING_PATH = Path("content/drafts/invented-lexicon-authoring.json")


class TestOrderV1Pack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_data = json.loads(PACK_PATH.read_text(encoding="utf-8"))
        cls.lexicon_data = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
        cls.pack = load_micro_unit_pack(PACK_PATH)

    def test_pack_loads_and_schema_metadata(self):
        """1. The pack loads, with exactly those two methods and 100 units."""
        self.assertEqual(self.pack.kind, "micro_unit")
        self.assertEqual(self.pack.schema_version, "micro-unit-pack/1")
        self.assertEqual(self.pack.pack_id, "invented-vocabulary-order-v1")
        self.assertEqual(len(self.pack.methods), 2)
        method_ids = [m.id for m in self.pack.methods]
        self.assertEqual(method_ids, ["worked_then_retrieve", "predict_first"])
        for m in self.pack.methods:
            self.assertTrue(m.description)
            self.assertNotIn("\n", m.description)
        self.assertEqual(len(self.pack.units), 100)

    def test_variants_line_reordering_multiset(self):
        """2. For every unit, predict_first is exactly the same three lines as worked_then_retrieve,

        reordered as Q, E, F. The multiset of lines is equal and the line order is as specified.
        """
        for unit in self.raw_data["units"]:
            word = unit["id"]
            variants = unit["variants"]
            self.assertIn("worked_then_retrieve", variants)
            self.assertIn("predict_first", variants)

            w_lines = variants["worked_then_retrieve"].split("\n")
            p_lines = variants["predict_first"].split("\n")

            self.assertEqual(len(w_lines), 3, f"{word} worked_then_retrieve line count")
            self.assertEqual(len(p_lines), 3, f"{word} predict_first line count")

            e_line, q_line, f_line = w_lines[0], w_lines[1], w_lines[2]

            self.assertTrue(e_line.startswith(f"The invented word {word} means "), f"{word} E start")
            self.assertTrue(q_line.startswith(f"Question: in this sentence, what does {word} mean?"), f"{word} Q start")
            self.assertTrue(f_line.startswith(f"Answer: {word} means "), f"{word} F start")

            self.assertEqual(p_lines, [q_line, e_line, f_line], f"{word} line reordering mismatch")
            self.assertEqual(sorted(w_lines), sorted(p_lines), f"{word} multiset of lines mismatch")

    def test_word_count_ratio(self):
        """3. The word-count ratio max/min, using str.split over the whole variant,

        is <= 1.05 for every unit (it should be exactly 1.0).
        """
        for unit in self.raw_data["units"]:
            variants = unit["variants"]
            w_tokens = variants["worked_then_retrieve"].split()
            p_tokens = variants["predict_first"].split()

            w_len = len(w_tokens)
            p_len = len(p_tokens)

            ratio = max(w_len, p_len) / min(w_len, p_len)
            self.assertLessEqual(ratio, 1.05)
            self.assertEqual(w_len, p_len, f"Expected exact word count equality for {unit['id']}")

    def test_q_answer_leak_and_check_prompt_absence(self):
        """4. Q contains no accepted answer, whole word, case-insensitive.

        Neither variant contains the check prompt.
        """
        for unit in self.raw_data["units"]:
            word = unit["id"]
            variants = unit["variants"]
            w_lines = variants["worked_then_retrieve"].split("\n")
            q_line = w_lines[1]

            check_prompt = unit["check"]["prompt"]
            self.assertNotIn(check_prompt, variants["worked_then_retrieve"])
            self.assertNotIn(check_prompt, variants["predict_first"])

            accepted = unit["check"]["answer_key"]["accepted"]
            for ans in accepted:
                pattern = rf"(?<!\w){re.escape(ans)}(?!\w)"
                match = re.search(pattern, q_line, re.IGNORECASE)
                self.assertIsNone(
                    match,
                    f"Leak in Q for unit {word}: accepted answer '{ans}' matched in '{q_line}'"
                )

    def test_q_contains_invented_word_and_no_parens(self):
        """5. Every Q sentence still contains the invented word, and contains no '('."""
        for unit in self.raw_data["units"]:
            word = unit["id"]
            variants = unit["variants"]
            q_line = variants["worked_then_retrieve"].split("\n")[1]

            self.assertIn(word, q_line, f"Word {word} missing from Q")
            self.assertNotIn("(", q_line, f"Opening paren found in Q for {word}: {q_line}")
            self.assertNotIn(")", q_line, f"Closing paren found in Q for {word}: {q_line}")

    def test_determinism_and_committed_bytes(self):
        """6. Determinism: regenerating produces the committed file's exact bytes."""
        generated_data = generate_order_v1_pack_data(LEXICON_PATH, AUTHORING_PATH)
        generated_bytes = serialize_pack(generated_data).encode("utf-8")
        file_bytes = PACK_PATH.read_bytes()
        self.assertEqual(generated_bytes, file_bytes)

    def test_check_prompts_and_keys_match_lexicon(self):
        """7. Check prompts and keys match the lexicon's accepted lists."""
        lex_units = {u["word"]: u for u in self.lexicon_data["units"]}
        for unit in self.raw_data["units"]:
            word = unit["id"]
            self.assertIn(word, lex_units)
            lex_u = lex_units[word]

            self.assertEqual(unit["check"]["prompt"], f"What does {word} mean?")
            self.assertEqual(unit["check"]["id"], f"{word}-day7")
            self.assertEqual(unit["check"]["family_id"], f"{word}-meaning")
            self.assertEqual(unit["check"]["check_delay_days"], 7)
            self.assertIs(unit["check"]["held_out"], True)
            self.assertEqual(unit["check"]["answer_key"]["status"], "candidate")
            self.assertEqual(
                unit["check"]["answer_key"]["accepted"],
                lex_u["check"]["accepted"]
            )


    def test_pack_runs_on_the_frozen_order_v1_contrast(self):
        import tempfile
        from datetime import datetime, timezone
        from aesop_lab.contrast.protocol import ORDER_V1
        from aesop_lab.micro.engine import MicroUnitEngine
        from aesop_lab.storage.sqlite import SQLiteStore

        at = datetime(2026, 11, 2, 9, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            store = SQLiteStore(Path(folder) / "learner.db")
            try:
                store.confirm_consent(at)
                with store.connection:
                    store.connection.execute("INSERT INTO learner_identity VALUES (1, 'order-v1-pack-test')")
                engine = MicroUnitEngine(self.pack, store, lambda: at, contrast=ORDER_V1)
                lessons = [engine.start_unit(engine.next_activity()["unit_id"]) for _ in range(3)]
            finally:
                store.close()
        for lesson in lessons:
            self.assertIn(lesson["method_id"], ("worked_then_retrieve", "predict_first"))
            unit = next(u for u in self.pack.units if u.id == lesson["unit_id"])
            self.assertEqual(lesson["lesson"], unit.variants[lesson["method_id"]])


if __name__ == "__main__":
    unittest.main()
