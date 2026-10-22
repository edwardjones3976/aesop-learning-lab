import statistics
import unittest

from aesop_lab.sim import learner, run, scenario

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


def rows():
    return {r["id"].split("/", 1)[1]: r for r in scenario.load("adversarial")}


def gaps(row, count=100):
    seeds = row["learners"]["seeds"][:2]
    return [learner.simulate(row, s, i).true_gap for s in seeds for i in range(count // len(seeds))]


class AdversarialSuiteTests(unittest.TestCase):
    def test_all_14_rows_load_in_order(self):
        self.assertEqual([r["id"].split("/", 1)[1] for r in scenario.load("adversarial")], EXPECTED_ROW_IDS)

    def test_every_row_agrees_with_the_engine(self):
        for rid, row in rows().items():
            with self.subTest(row=rid):
                result = run.parity_sample(row, 5)
                self.assertEqual(result["checked"], 5)
                self.assertEqual(result["mismatches"], [])

    def test_day1_winner_really_loses_at_day7(self):
        self.assertLess(statistics.fmean(gaps(rows()["day1-winner-loses-at-day7"], 50)), 0.0)

    def test_reversal_row_has_20_to_40_percent_reversed_learners(self):
        share = sum(g < 0 for g in gaps(rows()["reversal-30"])) / 100
        self.assertTrue(0.20 <= share <= 0.40, share)

    def test_harder_items_in_one_arm_is_not_a_true_gap(self):
        # Personal effects (SD 0.3 logit) remain, but the item shift adds no average method advantage.
        self.assertLess(abs(statistics.fmean(gaps(rows()["harder-items-in-one-arm"]))), 0.01)

    def test_novelty_gap_fades_over_the_course(self):
        t = learner.simulate(rows()["novelty-fades"], 1, 0)
        early = statistics.fmean(u.p_variant - u.p_baseline for u in t.units[:10])
        late = statistics.fmean(u.p_variant - u.p_baseline for u in t.units[-10:])
        self.assertGreater(early, late)


if __name__ == "__main__":
    unittest.main()
