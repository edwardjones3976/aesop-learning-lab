import copy
import unittest

from aesop_lab.contrast.protocol import BASELINE, VARIANT
from aesop_lab.sim import learner, pooling, scenario

BASE = {"schema": "sim-scenario/1", "id": "pool", "learners": {"seeds": [1, 2, 3], "per_seed": 20},
        "model": {"kind": "half-life", "method_logit_mean": 1.0, "method_logit_sd": 0.2}}


class PoolingTests(unittest.TestCase):
    def test_personal_estimate_is_the_beta_posterior_difference(self):
        d, var = pooling.personal_estimate({BASELINE: (0, 0), VARIANT: (0, 0)})
        self.assertEqual(d, 0.0)
        self.assertAlmostEqual(var, 2 * (1 / 12))
        d, _ = pooling.personal_estimate({BASELINE: (2, 8), VARIANT: (8, 2)})
        self.assertAlmostEqual(d, 9 / 12 - 3 / 12)

    def test_counts_match_the_fast_path_at_the_final_look(self):
        from aesop_lab.sim import fastpath
        s = scenario.normalize(copy.deepcopy(BASE))
        t = learner.simulate(s, 1, 0)
        judged = fastpath.judge(t)
        if judged["decision_day"] == 28:
            self.assertEqual({r: tuple(c) for r, c in pooling.counts_at(t, 28).items()}, judged["looks"][-1]["counts"])

    def test_shared_effect_makes_the_population_order_beat_individual_data(self):
        result = pooling.evaluate(scenario.normalize(copy.deepcopy(BASE)), 28)
        self.assertGreater(result["accuracy"]["population"], result["accuracy"]["individual"])
        self.assertGreaterEqual(result["accuracy"]["pooled"], result["accuracy"]["individual"])
        self.assertLess(result["median_personal_weight"], 0.5)

    def test_population_dispute_monitor_flags_one_arm_bias_but_not_clean_data(self):
        biased = copy.deepcopy(BASE)
        biased["behaviour"] = {"false_negative_rate": {"variant": 0.3}, "dispute_rate": 0.5, "dispute_false_rate": 0.05}
        clean = copy.deepcopy(BASE)
        clean["behaviour"] = {"dispute_false_rate": 0.05}
        self.assertEqual(pooling.evaluate(scenario.normalize(biased), 28)["withheld_share"], 1.0)
        self.assertEqual(pooling.evaluate(scenario.normalize(clean), 28)["withheld_share"], 0.0)

    def test_dispute_flag_needs_a_real_between_arm_difference(self):
        cohort = [{BASELINE: [0, 10], VARIANT: [5, 10]}] * 30
        self.assertTrue(pooling.dispute_flag(cohort))
        self.assertFalse(pooling.dispute_flag([{BASELINE: [1, 10], VARIANT: [1, 10]}] * 30))


if __name__ == "__main__":
    unittest.main()
