"""The simulated-learner harness maps replies onto choices and never sees keys."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/simulated_learner_run.py"
spec = importlib.util.spec_from_file_location("simulated_learner_run", SCRIPT)
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class SimulatedLearnerHarnessTests(unittest.TestCase):
    def test_choice_replies_map_to_listed_options(self):
        choices = ["print(total)", "return total", "total = total + 1"]
        for reply, expected in [("return total", "return total"), ("`return total`", "return total"),
                                ("'Return Total'", "return total"), ("B", "return total"),
                                ("2", "return total"), ("b) return total", "return total"),
                                ("C.", "total = total + 1"), ("something else", None), ("D", None)]:
            with self.subTest(reply=reply):
                self.assertEqual(harness.match_choice(reply, choices), expected)

    def test_question_prompt_carries_no_key_or_hints(self):
        activity = {"prompt": "What is result?", "body": "result = 2 + 2", "choices": [],
                    "hints": [{"level": "nudge", "text": "SECRET HINT"}],
                    "answer_key": {"accepted": ["4"]}}
        prompt = harness.question_prompt(activity, ["[Lesson] my note"])
        self.assertNotIn("SECRET HINT", prompt)
        self.assertNotIn("answer_key", prompt)
        self.assertIn("my note", prompt)

    def test_first_line_strips_labels_and_backticks(self):
        self.assertEqual(harness.first_line("\n  Answer: `6`\nbecause..."), "6")


if __name__ == "__main__":
    unittest.main()
