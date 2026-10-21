import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ai_run", ROOT / "scripts" / "ai_learner_contrast_run.py")
ai_run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_run)


class StubLearner:
    """Answers only from what a prompt shows: never guesses, copies meanings into notes."""

    def __init__(self):
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if prompt.startswith("Before any lessons"):
            return "\n".join(f"{w}: unknown" for w in prompt.split("\n\n", 1)[1].splitlines())
        if "Write one short line for your own notebook" in prompt:
            word, gloss = re.search(r"Answer: (\w+) means '([^']+)'", prompt).groups()
            return f"{word} = {gloss}"
        if prompt.startswith("Lesson, part 1"):
            return "unknown"
        word = re.search(r"What does (\w+) mean\?", prompt).group(1)
        note = re.search(rf"- {word} = (.+)", prompt)
        return note.group(1) if note else "unknown"


class AiLearnerRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.learner = StubLearner()
        cls.result = ai_run.run(Path(cls.temp.name) / "run", cls.learner)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_pretest_logs_every_item_and_a_blind_learner_scores_zero(self):
        self.assertEqual(len(self.result["pretest"]), 100)
        self.assertEqual(sum(i["correct"] for i in self.result["pretest"]), 0)

    def test_predict_first_asks_before_explaining_and_baseline_explains_first(self):
        firsts = [p for p in self.learner.prompts if p.startswith("Lesson, part 1 of 2:")]
        self.assertEqual(len(firsts), 66)
        explained = [p for p in firsts if "The invented word" in p]
        asked_first = [p for p in firsts if "The invented word" not in p]
        self.assertTrue(explained and asked_first)
        for prompt in firsts:
            self.assertNotIn("Answer:", prompt)  # feedback never precedes the learner's attempt
        for prompt in asked_first:
            self.assertTrue(prompt.split("\n")[1].startswith("Question:"))

    def test_checks_are_fresh_calls_without_lessons_keys_or_their_own_prompt_in_the_notebook(self):
        checks = [p for p in self.learner.prompts if p.startswith("Your notebook")]
        self.assertGreater(len(checks), 40)
        for prompt in checks:
            notebook = prompt.split("\n\nQuestion:")[0]
            self.assertNotIn("What does", notebook)
            self.assertNotIn("Lesson", prompt)
            self.assertLessEqual(notebook.count("\n- "), ai_run.NOTEBOOK_CAP)

    def test_day_28_status_comes_from_the_frozen_contrast(self):
        status = self.result["status"]
        self.assertEqual(status["contrast_id"], "order-v1")
        self.assertIn(status["outcome"], ("repeated benefit", "no meaningful difference detected",
                                          "promising", "insufficient evidence"))
        self.assertGreaterEqual(min(sum(c) for c in status["looks"][-1]["counts"].values()), 8)
        self.assertEqual(self.result["errors"], 0)
        self.assertEqual(self.result["calls"], len(self.learner.prompts))

    def test_bridge_failure_is_never_scored(self):
        calls = [0]

        def flaky(prompt):
            calls[0] += 1
            if prompt.startswith("Your notebook") and calls[0] % 5 == 0:
                raise ai_run.LearnerUnavailable("simulated outage")
            return StubLearner()(prompt)

        with tempfile.TemporaryDirectory() as folder:
            result = ai_run.run(Path(folder) / "run", flaky)
        self.assertGreater(result["errors"], 0)
        self.assertNotIn("simulated outage", str(result["status"]))


if __name__ == "__main__":
    unittest.main()
