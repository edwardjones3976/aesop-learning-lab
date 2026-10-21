import math
import random
import unittest
from unittest.mock import patch

from aesop_lab.ranking.method_ranking import rank_methods
from scripts import method_ranking_recovery as recovery


class MethodRankingTests(unittest.TestCase):
    def test_empty_and_invalid_inputs(self):
        for data in ({}, {"": []}, {1: []}, {"a": [(1, 1)]},
                     {"a": [(True, True)]}, {"a": [(True, "1")]},
                     {"a": [(True, -0.1)]}, {"a": [(True, 1.1)]},
                     {"a": [(True, math.nan)]}, {"a": [(True, math.inf)]}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                rank_methods(data)
        for draws in (0, 255, True, 1.5):
            with self.assertRaises(ValueError):
                rank_methods({"a": []}, draws=draws)

    def test_prior_and_single_method(self):
        result = rank_methods({"a": []})
        self.assertEqual(result.methods[0].posterior_mean, 0.5)
        self.assertEqual(result.methods[0].probability_best, 1)
        self.assertFalse(result.show_ranking)
        self.assertEqual(rank_methods({"a": [(True, 1)] * 40}).confidence,
                         "tentative")

    def test_fractional_likelihood_and_zero_weight(self):
        row = rank_methods({"a": [(True, 0.5), (False, 0.25), (False, 0)]}).methods[0]
        self.assertEqual((row.alpha, row.beta, row.effective_checks), (1.5, 1.25, 0.75))
        self.assertAlmostEqual(row.posterior_mean, 1.5 / 2.75)

    def test_probability_best_against_analytic_two_arm_case(self):
        # P(Beta(2,1) > Beta(1,2)) = integral 2*x*(2*x-x*x) dx = 5/6.
        result = rank_methods({"a": [(True, 1)], "b": [(False, 1)]}, draws=16384)
        self.assertAlmostEqual(result.methods[0].probability_best, 5 / 6, delta=0.015)

    def test_clear_floor_uses_weight_not_number_of_answers(self):
        for weight, expected in ((0.95, "likely"), (1, "clear")):
            data = {"a": [(True, weight)] * 20, "b": [(False, weight)] * 20}
            self.assertEqual(rank_methods(data).confidence, expected)

    def test_recovery_waits_for_delayed_feedback_and_balances_warmup(self):
        original = recovery.choose_method
        seen, choices = [], []

        def record(alpha, beta, assigned, rng):
            seen.append(sum(alpha) + sum(beta))
            chosen = original(alpha, beta, assigned, rng)
            choices.append(chosen)
            return chosen

        with patch.object(recovery, "CHECKPOINTS", (8,)), patch.object(
                recovery, "choose_method", side_effect=record):
            result = recovery.recover((.8, .65, .55, .45), 1, 123, 256)
        self.assertEqual(seen[:7], [8] * 7)
        self.assertEqual(seen[7], 9)  # day seven receives only the first check
        self.assertEqual([choices[:8].count(i) for i in range(4)], [2] * 4)
        self.assertIn(result[0][8], (0, 1))

    def test_n_methods_unseen_and_display_boundary(self):
        data = {str(i): [] for i in range(6)}
        data["0"] = [(False, 1)] * 11
        self.assertFalse(rank_methods(data).show_ranking)
        data["0"].append((False, 1))
        result = rank_methods(data)
        self.assertTrue(result.show_ranking)
        self.assertEqual(result.confidence, "tentative")
        self.assertEqual(len(result.methods), 6)
        self.assertAlmostEqual(sum(row.probability_best for row in result.methods), 1)

    def test_symmetry_reproducibility_and_no_side_effects(self):
        data = {"b": [(True, 1), (False, 1)], "a": [(True, 1), (False, 1)]}
        before = repr(data)
        state = random.getstate()
        result = rank_methods(data)
        self.assertEqual(result, rank_methods(dict(reversed(list(data.items())))))
        self.assertEqual(random.getstate(), state)
        self.assertEqual(repr(data), before)
        self.assertEqual(result.methods[0].method, "a")
        self.assertAlmostEqual(result.methods[0].probability_best, 0.5, delta=0.025)

    def test_labels_and_reversal(self):
        strong = {"good": [(True, 1)] * 20, "bad": [(False, 1)] * 20}
        self.assertEqual(rank_methods(strong).confidence, "clear")
        self.assertEqual(rank_methods({"good": [(True, 1)] * 5,
                                       "bad": [(False, 1)] * 5}).confidence, "likely")
        self.assertEqual(rank_methods({"good": [(True, 1)] * 4,
                                       "bad": [(False, 1)] * 4}).confidence, "tentative")
        strong["good"] += [(False, 1)] * 100
        strong["bad"] += [(True, 1)] * 100
        self.assertEqual(rank_methods(strong).methods[0].method, "bad")
        balanced = {"a": [(True, 1), (False, 1)] * 30,
                    "b": [(True, 1), (False, 1)] * 30}
        self.assertEqual(rank_methods(balanced).confidence, "tentative")


if __name__ == "__main__":
    unittest.main()
