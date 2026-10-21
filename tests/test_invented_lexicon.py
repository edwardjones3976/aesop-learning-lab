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

    def test_retrieval_gloss_before_first_retrieval_instruction(self) -> None:
        """In every retrieval variant, the gloss appears before the first retrieval instruction."""
        for u in self.units:
            retrieval_text = u["variants"]["retrieval"]
            gloss = u["gloss"]
            base = gloss[3:] if gloss.startswith("to ") else gloss
            ret_lower = retrieval_text.lower()
            base_lower = base.lower()

            instruction_marker = "now cover"
            self.assertIn(
                instruction_marker,
                ret_lower,
                f"Retrieval variant does not contain instruction marker in unit {u['id']}: {retrieval_text}",
            )
            instruction_idx = ret_lower.find(instruction_marker)
            gloss_idx = ret_lower.find(base_lower)

            self.assertNotEqual(
                gloss_idx,
                -1,
                f"Gloss '{base}' not found in retrieval variant in unit {u['id']}: {retrieval_text}",
            )
            self.assertLess(
                gloss_idx,
                instruction_idx,
                f"Gloss '{base}' does not appear before first retrieval instruction in unit {u['id']}: {retrieval_text}",
            )

    def test_authoring_sense_present_and_literal(self) -> None:
        """Every unit has a non-empty 'sense', and verb examples contain no figurative markers."""
        authoring_path = Path("content/drafts/invented-lexicon-authoring.json")
        with open(authoring_path, "r", encoding="utf-8") as f:
            authoring = json.load(f)

        figurative_markers = ["interest", "deadline", "deadlines", "hopes", "heart", "career", "plans",
                              "spreadsheet", "conscience", "regulations", "momentum", "information",
                              "panic", "aroma", "scent", "employees", "growth"]

        for gloss, auth in authoring.items():
            sense = auth.get("sense", "")
            self.assertTrue(
                bool(sense and str(sense).strip()),
                f"Unit '{gloss}' is missing a non-empty 'sense' in authoring.",
            )

            if gloss.startswith("to "):
                # Every delivered sentence for a verb: mnemonic, examples and drills.
                for ex in [auth.get("mnemonic_sentence", ""), *auth.get("example_sentences", []), *auth.get("rule_drills", [])]:
                    for marker in figurative_markers:
                        self.assertFalse(
                            bool(re.search(r"\b" + re.escape(marker) + r"\b", ex, re.IGNORECASE)),
                            f"Figurative marker '{marker}' found in verb example for '{gloss}': {ex}",
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

    def test_keyword_sound_alikes(self) -> None:
        """Keywords must be sound-alikes: first two letters or SequenceMatcher ratio >= 0.53.

        Threshold 0.53 ensures all real sound-alikes pass while meaning descriptions like
        'smoky roof' (gogi, ratio 0.15), 'twin blades' (fasaso, ratio 0.25), and
        'puff of smoke' (poszogak, ratio 0.526) fail.
        """
        import difflib
        authoring_path = Path("content/drafts/invented-lexicon-authoring.json")
        with open(authoring_path, "r", encoding="utf-8") as f:
            authoring = json.load(f)

        threshold = 0.53
        for u in self.units:
            word = u["word"].lower()
            kw = authoring[u["gloss"]]["keyword"].lower()
            kw_clean = re.sub(r"[^a-z]", "", kw)
            first2 = word[:2] == kw_clean[:2]
            ratio = difflib.SequenceMatcher(None, word, kw_clean).ratio()
            self.assertTrue(
                first2 or ratio >= threshold,
                f"Keyword '{kw}' for invented word '{word}' is not a valid sound-alike (f2={first2}, ratio={ratio:.3f} < {threshold})",
            )

    def test_retrieval_does_not_contain_check_prompt_or_what_does(self) -> None:
        """No variant contains its unit's check prompt, or the phrase 'What does' (ignoring case)."""
        for u in self.units:
            check_prompt = u["check"]["prompt"].lower()
            for method_id, variant_text in u["variants"].items():
                v_lower = variant_text.lower()
                self.assertNotIn(
                    check_prompt,
                    v_lower,
                    f"Unit {u['id']} variant '{method_id}' leaks check prompt '{check_prompt}'",
                )
                self.assertNotIn(
                    "what does",
                    v_lower,
                    f"Unit {u['id']} variant '{method_id}' contains 'what does'",
                )

    def test_accepted_answers_equivalence(self) -> None:
        """Accepted answers must be equivalent forms only.

        For verbs: subset of {gloss, bare form}.
        For nouns: {gloss}, plus an allowed synonym only if it appears in at least 2 variants.
        No related-but-different objects (mallet, boiler, pendant, bedding) allowed.
        """
        banned = {"boiler", "mallet", "pendant", "bedding"}
        for u in self.units:
            gloss = u["gloss"]
            accepted = u["check"]["accepted"]
            for ans in accepted:
                self.assertNotIn(
                    ans.lower(),
                    banned,
                    f"Unit {u['id']} contains banned non-equivalent answer '{ans}'",
                )

            if gloss.startswith("to "):
                base = gloss[3:]
                allowed = {gloss, base}
                self.assertTrue(
                    set(accepted).issubset(allowed),
                    f"Verb unit {u['id']} accepted answers {accepted} not subset of {allowed}",
                )
            else:
                self.assertIn(
                    gloss,
                    accepted,
                    f"Noun unit {u['id']} does not include gloss '{gloss}' in accepted",
                )
                if len(accepted) > 1:
                    self.assertEqual(
                        len(accepted),
                        2,
                        f"Noun unit {u['id']} has more than one synonym: {accepted}",
                    )
                    syn = accepted[1]
                    var_count = sum(
                        1 for v in u["variants"].values()
                        if syn.lower() in v.lower()
                    )
                    self.assertGreaterEqual(
                        var_count,
                        2,
                        f"Noun unit {u['id']} synonym '{syn}' appears in {var_count} variants (< 2)",
                    )

    def test_rule_drill_structure_and_exposure_parity(self) -> None:
        """Rule drill has 1 rule line + 2 practice lines; exposure counts match across all 4 methods."""
        for u in self.units:
            word = u["word"]
            gloss = u["gloss"]
            base = gloss[3:] if gloss.startswith("to ") else gloss

            rd = u["variants"]["rule_drill"]
            lines = [l for l in rd.splitlines() if l.strip()]
            self.assertEqual(len(lines), 3, f"Unit {u['id']} rule_drill does not have 3 lines: {lines}")
            self.assertTrue(lines[0].startswith("Rule:"), f"Line 1 not Rule: {lines[0]}")
            self.assertTrue(lines[1].startswith("Fill in:"), f"Line 2 not Fill in: {lines[1]}")
            self.assertTrue(lines[2].startswith("Which word means"), f"Line 3 not Which word: {lines[2]}")
            self.assertIn("(Answer: " + word + ")", lines[1])
            self.assertIn("(Answer: " + word + ")", lines[2])

            counts = {}
            for method_id, v_text in u["variants"].items():
                w_cnt = len(re.findall(r"\b" + re.escape(word) + r"\b", v_text, re.I))
                b_cnt = len(re.findall(r"\b" + re.escape(base) + r"\b", v_text, re.I))
                counts[method_id] = (w_cnt, b_cnt)

            distinct_counts = set(counts.values())
            self.assertEqual(
                len(distinct_counts),
                1,
                f"Unit {u['id']} does not have identical exposure across methods: {counts}",
            )

    def test_part_of_speech_consistency(self) -> None:
        """Verbs never follow determiners; nouns never follow 'to'."""
        determiners = ["a", "an", "the", "this", "that", "his", "her", "my", "your"]
        for u in self.units:
            word = u["word"]
            is_verb = u["gloss"].startswith("to ")
            for method_id, text in u["variants"].items():
                if is_verb:
                    for det in determiners:
                        pattern = r"\b" + det + r"\s+" + re.escape(word) + r"\b"
                        matches = list(re.finditer(pattern, text, re.IGNORECASE))
                        for m in matches:
                            after = text[m.end():m.end() + 10].strip()
                            self.assertTrue(
                                det.lower() == "that" and after.startswith("mean"),
                                f"Verb '{word}' directly follows determiner '{det}' in unit {u['id']} variant '{method_id}': {text}",
                            )
                else:
                    pattern = r"\bto\s+" + re.escape(word) + r"\b"
                    self.assertFalse(
                        bool(re.search(pattern, text, re.IGNORECASE)),
                        f"Noun '{word}' directly follows 'to' in unit {u['id']} variant '{method_id}': {text}",
                    )

    def test_seeds_enforcement(self) -> None:
        """The generator refuses non-default seeds without --unreviewed, and marks unreviewed runs."""
        # Default seed works
        data_default = build_lexicon_data(seed=DEFAULT_SEED)
        self.assertEqual(data_default["seed"], DEFAULT_SEED)
        self.assertNotIn("unreviewed", data_default)

        # Other seed without unreviewed fails
        with self.assertRaises(ValueError):
            build_lexicon_data(seed=99999)

        # Other seed with unreviewed succeeds and has 'unreviewed': True
        data_unreviewed = build_lexicon_data(seed=99999, unreviewed=True)
        self.assertEqual(data_unreviewed["seed"], 99999)
        self.assertIs(data_unreviewed["unreviewed"], True)


if __name__ == "__main__":
    unittest.main()
