import json
from pathlib import Path
import statistics
import unittest

from aesop_lab.sim import learner, run, scenario

ADVERSARIAL_PATH = Path(__file__).parent.parent / "src" / "aesop_lab" / "sim" / "scenarios" / "adversarial.json"

EXPECTED_ROW_IDS = [
    "null-differential-skip-dropout",
    "skip-when-failing-40",
    "outside-study-one-arm-undeclared",
    "outside-study-one-arm-declared",
    "frustration-dropout-one-arm",
    "day1-winner-loses-at-day7",
    "contamination-shrinks-20pt",
    "reversal-30",
    "preference-matches-worse",
    "novelty-fades",
    "one-arm-false-negatives",
    "harder-items-in-one-arm",
    "late-answers",
    "drift-reversal",
]


class AdversarialSuiteTests(unittest.TestCase):
    def test_all_14_row_ids_present(self):
        with open(ADVERSARIAL_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        row_ids = [r["id"] for r in raw.get("rows", [])]
        self.assertEqual(row_ids, EXPECTED_ROW_IDS)
        self.assertEqual(len(row_ids), 14)

    def _load_row(self, row_dict: dict, base: dict) -> dict:
        merged = {k: v for k, v in base.items() if k != "rows"}
        merged["id"] = f"{base['id']}/{row_dict['id']}"
        for section in ("model", "behaviour", "design"):
            if section in row_dict:
                merged[section] = {**merged.get(section, {}), **row_dict[section]}
        return scenario.normalize(merged)

    def test_suite_loads(self):
        with open(ADVERSARIAL_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        base = {k: v for k, v in raw.items() if k != "rows"}

        loaded_rows = []
        for row_dict in raw.get("rows", []):
            rid = row_dict["id"]
            try:
                norm = self._load_row(row_dict, base)
                loaded_rows.append(norm)
            except scenario.ScenarioError as e:
                if rid in ("novelty-fades", "harder-items-in-one-arm"):
                    # Expected skip until Claude's fix PR arrives with these fields
                    continue
                self.fail(f"Row {rid} failed to load unexpectedly: {e}")

        # At least the existing supported rows must load cleanly
        self.assertGreaterEqual(len(loaded_rows), 12)

    def test_every_loadable_row_parity(self):
        with open(ADVERSARIAL_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        base = {k: v for k, v in raw.items() if k != "rows"}

        for row_dict in raw.get("rows", []):
            rid = row_dict["id"]
            try:
                norm = self._load_row(row_dict, base)
            except scenario.ScenarioError as e:
                if rid in ("novelty-fades", "harder-items-in-one-arm"):
                    continue
                self.fail(f"Row {rid} failed to load: {e}")

            with self.subTest(row_id=rid):
                res = run.parity_sample(norm, 5)
                self.assertEqual(res["checked"], 5)
                self.assertEqual(res["mismatches"], [], f"Parity mismatch in row {rid}: {res['mismatches']}")

    def test_day1_winner_loses_at_day7_realised_gap_is_negative(self):
        with open(ADVERSARIAL_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        base = {k: v for k, v in raw.items() if k != "rows"}
        target = next(r for r in raw["rows"] if r["id"] == "day1-winner-loses-at-day7")
        norm = self._load_row(target, base)

        # check with 50 learners via aesop_lab.sim.learner.simulate(row, seed, i).true_gap
        seed = norm["learners"]["seeds"][0]
        gaps = [learner.simulate(norm, seed, i).true_gap for i in range(50)]
        mean_gap = statistics.fmean(gaps)
        self.assertLess(mean_gap, 0.0, f"Expected negative realised mean true gap, got {mean_gap}")

    def test_reversal_30_has_20_to_40_percent_negative_true_gap(self):
        with open(ADVERSARIAL_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        base = {k: v for k, v in raw.items() if k != "rows"}
        target = next(r for r in raw["rows"] if r["id"] == "reversal-30")
        norm = self._load_row(target, base)

        # Check across 100 learners (first 2 seeds of 50 each)
        seeds = norm["learners"]["seeds"][:2]
        per_seed = norm["learners"]["per_seed"]
        gaps = [learner.simulate(norm, s, i).true_gap for s in seeds for i in range(per_seed)]
        neg_count = sum(1 for g in gaps if g < 0)
        neg_share = neg_count / len(gaps)
        self.assertTrue(
            0.20 <= neg_share <= 0.40,
            f"Expected reversal share in [0.20, 0.40], got {neg_share:.3f} ({neg_count}/{len(gaps)})"
        )


if __name__ == "__main__":
    unittest.main()
