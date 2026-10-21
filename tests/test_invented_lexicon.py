"""Tests for the invented lexicon generator and draft content."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from scripts.generate_invented_lexicon import (
    DEFAULT_SEED,
    build_lexicon_data,
    load_excluded_words,
)


class TestInventedLexicon(unittest.TestCase):
    """Test suite verifying properties of the invented lexicon draft pack."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.json_path = Path("content/drafts/invented-lexicon-v1.json")
        with open(cls.json_path, "r", encoding="utf-8") as f:
            cls.data = json.load(f)
        cls.units = cls.data["units"]
        cls.excluded_words = load_excluded_words()

    def test_determinism(self) -> None:
        """Regenerating with the same seed reproduces the exact same data structure and byte content."""
        regenerated = build_lexicon_data(seed=self.data["seed"])
        self.assertEqual(self.data, regenerated)

        # Byte identical serialization
        original_bytes = self.json_path.read_bytes()
        recreated_bytes = (json.dumps(regenerated, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        self.assertEqual(original_bytes, recreated_bytes)

    def test_unique_words_and_glosses(self) -> None:
        """Exactly 100 unique words and 100 unique glosses."""
        self.assertEqual(len(self.units), 100)

        words = [u["word"] for u in self.units]
        glosses = [u["gloss"] for u in self.units]

        self.assertEqual(len(set(words)), 100)
        self.assertEqual(len(set(glosses)), 100)

        for u in self.units:
            self.assertEqual(u["id"], u["word"])

    def test_no_excluded_words(self) -> None:
        """No invented word appears in the committed excluded_words.txt list."""
        for u in self.units:
            word = u["word"].lower()
            self.assertNotIn(
                word,
                self.excluded_words,
                f"Invented word '{word}' was found in excluded_words.",
            )

    def test_methods_and_variants_presence(self) -> None:
        """Every unit has all 4 required method variants: retrieval, keyword, example_sentence, rule_drill."""
        expected_methods = {"retrieval", "keyword", "example_sentence", "rule_drill"}

        # Check top-level method IDs
        declared_methods = {m["id"] for m in self.data["methods"]}
        self.assertEqual(declared_methods, expected_methods)

        for u in self.units:
            self.assertEqual(set(u["variants"].keys()), expected_methods)

    def test_variants_contain_word_and_teach_gloss(self) -> None:
        """Every variant contains the word and makes the gloss learnable."""
        for u in self.units:
            word = u["word"]
            accepted = [a.lower() for a in u["check"]["accepted"]]

            for method_id, variant_text in u["variants"].items():
                self.assertIn(
                    word,
                    variant_text,
                    f"Unit {u['id']} variant '{method_id}' does not contain target word '{word}'.",
                )

                # Check variant teaches gloss (contains at least one accepted representation)
                teaches_gloss = any(acc in variant_text.lower() for acc in accepted)
                self.assertTrue(
                    teaches_gloss,
                    f"Unit {u['id']} variant '{method_id}' does not teach any accepted gloss: {accepted}",
                )

    def test_check_prompt_does_not_contain_answer(self) -> None:
        """Check prompt is 'What does <word> mean?' and does not leak the gloss or accepted answers."""
        family_ids = set()

        for u in self.units:
            word = u["word"]
            check = u["check"]
            prompt = check["prompt"]

            self.assertEqual(prompt, f"What does {word} mean?")
            self.assertEqual(check["check_delay_days"], 7)
            self.assertIs(check["held_out"], True)
            self.assertNotIn(check["family_id"], family_ids)
            family_ids.add(check["family_id"])

            # Prompt must not contain any accepted gloss/answer
            for acc in check["accepted"]:
                self.assertNotIn(
                    acc.lower(),
                    prompt.lower(),
                    f"Check prompt '{prompt}' leaks answer '{acc}' in unit {u['id']}.",
                )

    def test_wrong_example_not_accepted(self) -> None:
        """Each wrong_example is plausible (a gloss of another unit) and not in the accepted answers."""
        all_glosses = {u["gloss"] for u in self.units}

        for u in self.units:
            wrong = u["check"]["wrong_example"]
            accepted = [a.lower() for a in u["check"]["accepted"]]

            self.assertIn(
                wrong,
                all_glosses,
                f"Wrong example '{wrong}' is not one of the lexicon glosses in unit {u['id']}.",
            )
            self.assertNotIn(
                wrong.lower(),
                accepted,
                f"Wrong example '{wrong}' is accepted in unit {u['id']}.",
            )

    def test_word_count_parity_bounds(self) -> None:
        """Within each unit, every variant is 25-60 words and contains the word and gloss balanced roughly +-1."""
        for u in self.units:
            word = u["word"]
            gloss = u["gloss"]
            base = gloss[3:] if gloss.startswith("to ") else gloss

            for method_id, variant_text in u["variants"].items():
                wc = len(variant_text.split())
                self.assertGreaterEqual(
                    wc,
                    25,
                    f"Unit {u['id']} variant '{method_id}' word count {wc} < 25",
                )
                self.assertLessEqual(
                    wc,
                    60,
                    f"Unit {u['id']} variant '{method_id}' word count {wc} > 60",
                )

                w_cnt = len(re.findall(r"\b" + re.escape(word) + r"\b", variant_text, re.IGNORECASE))
                g_cnt = len(re.findall(r"\b" + re.escape(base) + r"\b", variant_text, re.IGNORECASE))
                self.assertLessEqual(
                    abs(w_cnt - g_cnt),
                    2,
                    f"Unit {u['id']} variant '{method_id}' word-to-gloss parity violated: word={w_cnt}, gloss={g_cnt}",
                )

    def test_no_to_to(self) -> None:
        """Ensure no grammar bugs such as 'to to' exist anywhere in variant texts."""
        for u in self.units:
            for method_id, variant_text in u["variants"].items():
                self.assertNotIn(
                    "to to",
                    variant_text.lower(),
                    f"Grammar error 'to to' detected in unit {u['id']} variant '{method_id}': {variant_text}",
                )

    def test_retrieval_first_sentence_does_not_contain_gloss(self) -> None:
        """The retrieval variant's first sentence must not reveal the gloss."""
        for u in self.units:
            retrieval_text = u["variants"]["retrieval"]
            first_sentence = retrieval_text.splitlines()[0]
            gloss = u["gloss"]
            base = gloss[3:] if gloss.startswith("to ") else gloss

            self.assertNotIn(
                base.lower(),
                first_sentence.lower(),
                f"Retrieval first sentence leaks gloss in unit {u['id']}: '{first_sentence}'",
            )
            for acc in u["check"]["accepted"]:
                self.assertNotIn(
                    acc.lower(),
                    first_sentence.lower(),
                    f"Retrieval first sentence leaks accepted answer '{acc}' in unit {u['id']}: '{first_sentence}'",
                )

    def test_no_example_sentence_frame_reused_more_than_twice(self) -> None:
        """No example-sentence frame (with word or gloss removed) is reused across more than 2 units."""
        authoring_path = Path("content/drafts/invented-lexicon-authoring.json")
        with open(authoring_path, "r", encoding="utf-8") as f:
            authoring = json.load(f)

        all_frames = []
        for gloss, item in authoring.items():
            for ex in item["example_sentences"]:
                frame = re.sub(r"\{w\}", "___", ex)
                frame = re.sub(r"\([^)]+\)", "___", frame)
                all_frames.append(frame)

        for frame in set(all_frames):
            count = all_frames.count(frame)
            self.assertLessEqual(
                count,
                2,
                f"Example sentence frame was reused {count} times (> 2): {frame}",
            )


if __name__ == "__main__":
    unittest.main()
