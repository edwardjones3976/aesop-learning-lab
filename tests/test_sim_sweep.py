import unittest

from aesop_lab.sim import scenario, sweep


def summary(row_id, wrong_upper, usable=0.0, day=None, abstained=0):
    return dict(id=row_id, wrong_upper=wrong_upper, wrong_ok=wrong_upper < 0.05, usable=usable,
                median_decision_day=day, abstained=abstained, learners=500)


class SweepTests(unittest.TestCase):
    def test_designs_override_a_row_and_are_validated(self):
        row = scenario.load("realistic")[0]
        both = sweep.apply_design(row, "both", {"promising_both_ways": True})
        self.assertEqual(both["id"], "both::realistic/gap0")
        self.assertTrue(both["design"]["promising_both_ways"])
        self.assertFalse(scenario.is_v1(both))
        self.assertTrue(scenario.is_v1(sweep.apply_design(row, "v1", {})))
        with self.assertRaises(scenario.ScenarioError):
            sweep.apply_design(row, "bad", {"looks": [28, 14]})
        for name in ("round2-sweep", "round2-sweep-2"):
            for candidate in sweep.load_designs(name)["designs"]:
                sweep.apply_design(row, candidate["id"], candidate["design"])

    def test_one_unsafe_row_makes_a_design_unsafe_and_safe_designs_rank_first(self):
        safe = sweep.summarize("safe", [summary("safe::adversarial/x", 0.02),
                                        summary("safe::realistic/gap10", 0.01, 0.10, 28)])
        risky = sweep.summarize("risky", [summary("risky::adversarial/x", 0.08),
                                          summary("risky::realistic/gap10", 0.01, 0.40, 21)])
        self.assertTrue(safe["safe"])
        self.assertFalse(risky["safe"])
        self.assertEqual(risky["worst_row"], "adversarial/x")
        self.assertEqual([d["design"] for d in sweep.rank([risky, safe])], ["safe", "risky"])

    def test_usable_answers_and_symmetry_come_from_realistic_rows_only(self):
        result = sweep.summarize("d", [summary("d::adversarial/x", 0.01, 0.9),
                                       summary("d::realistic/gap0", 0.01, 0.02),
                                       summary("d::realistic/gap5", 0.01, 0.20, 28),
                                       summary("d::realistic/minus5", 0.01, 0.10, 21)])
        self.assertEqual(set(result["usable"]), {"gap0", "gap5", "minus5"})
        self.assertAlmostEqual(result["mean_usable_nonzero"], 0.15)
        self.assertAlmostEqual(result["symmetry_gap"][5], 0.10)
        self.assertEqual(result["median_decision_day"], 24.5)


if __name__ == "__main__":
    unittest.main()
