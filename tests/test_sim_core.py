import copy
import unittest

from aesop_lab.contrast import protocol
from aesop_lab.sim import fastpath, learner, replay, run, scenario

BASE = {"schema": "sim-scenario/1", "id": "test", "learners": {"seeds": [1], "per_seed": 4},
        "model": {"kind": "half-life", "method_logit_mean": 0.6}}


def make(**sections):
    raw = copy.deepcopy(BASE)
    for key, value in sections.items():
        raw[key] = {**raw.get(key, {}), **value}
    return scenario.normalize(raw)


class ScenarioTests(unittest.TestCase):
    def test_defaults_unknown_fields_and_suites(self):
        s = make()
        self.assertEqual(s["behaviour"]["answer_rate"], 0.9)
        with self.assertRaises(scenario.ScenarioError):
            make(behaviour={"answer_rte": 0.5})
        with self.assertRaises(scenario.ScenarioError):
            scenario.normalize({**BASE, "model": {"kind": "magic"}})
        rows = scenario.expand({**BASE, "rows": [
            {"id": "a"}, {"id": "b", "behaviour": {"arm_skip": {"variant": 0.2}}}]})
        self.assertEqual([r["id"] for r in rows], ["test/a", "test/b"])
        self.assertEqual(rows[1]["behaviour"]["arm_skip"], {"baseline": 0.0, "variant": 0.2})
        self.assertNotEqual(scenario.scenario_hash(rows[0]), scenario.scenario_hash(rows[1]))

    def test_every_shipped_scenario_loads(self):
        names = scenario.available()
        self.assertIn("round1-gate", names)
        for name in names:
            self.assertTrue(scenario.load(name))


class LearnerTests(unittest.TestCase):
    def test_trajectories_repeat_exactly_and_differ_between_learners(self):
        s = make()
        a, b = learner.simulate(s, 1, 0), learner.simulate(s, 1, 0)
        self.assertEqual([(u.unit_id, u.role, u.studied_at) for u in a.units],
                         [(u.unit_id, u.role, u.studied_at) for u in b.units])
        self.assertEqual([(x.unit_id, x.at, x.correct) for x in a.answers],
                         [(x.unit_id, x.at, x.correct) for x in b.answers])
        self.assertNotEqual(a.true_gap, learner.simulate(s, 1, 1).true_gap)

    def test_blocks_balance_and_study_stops_at_day_zero_plus_21(self):
        t = learner.simulate(make(behaviour={"missed_day_rate": 0.3}), 2, 0)
        roles = [u.role for u in sorted(t.units, key=lambda u: u.position)]
        for block in range(len(roles) // 4):
            self.assertEqual(roles[4 * block:4 * block + 4].count(protocol.BASELINE), 2)
        day_zero = min(u.studied_at for u in t.units)
        self.assertTrue(all((u.studied_at - day_zero).days <= 21 for u in t.units))

    def test_truth_is_the_learners_own_gap_and_reversal_flips_it(self):
        reversed_ = make(model={"method_logit_mean": 1.0, "method_logit_sd": 0.0, "reversed_share": 1.0})
        self.assertLess(learner.simulate(reversed_, 1, 0).true_gap, 0)
        self.assertGreater(learner.simulate(make(model={"method_logit_sd": 0.0}), 1, 0).true_gap, 0)


class ParityTests(unittest.TestCase):
    def test_fast_path_matches_the_real_engine_under_messy_behaviour(self):
        messy = make(behaviour={"missed_day_rate": 0.2, "late_rate": 0.1, "answer_delay_days": [5, 12],
                                "outside_study_rate": {"baseline": 0.15, "variant": 0.0},
                                "outside_declared_share": 0.5, "dropout_hazard": 0.01},
                     learners={"seeds": [1, 2], "per_seed": 6})
        result = run.parity_sample(messy, 12)
        self.assertEqual(result["checked"], 12)
        self.assertEqual(result["mismatches"], [])

    def test_bernoulli_round1_rows_match_the_engine(self):
        row = scenario.load("round1-gate")[6]  # missed days
        self.assertEqual(run.parity_sample(row, 6)["mismatches"], [])


class VerdictTests(unittest.TestCase):
    def test_wrong_is_judged_against_each_learners_own_sign(self):
        better_variant = dict(outcome="repeated benefit", winner=protocol.VARIANT)
        self.assertEqual(run.verdict_class(better_variant, 0.08), "correct")
        self.assertEqual(run.verdict_class(better_variant, -0.02), "wrong")  # a reversed learner
        self.assertEqual(run.verdict_class(better_variant, 0.0), "wrong")
        self.assertEqual(run.verdict_class(dict(outcome="promising", winner=None), -0.01), "wrong")
        self.assertEqual(run.verdict_class(dict(outcome="no meaningful difference detected", winner=None), 0.06), "wrong")
        self.assertEqual(run.verdict_class(dict(outcome="no meaningful difference detected", winner=None), 0.01), "correct")
        self.assertEqual(run.verdict_class(dict(outcome="insufficient evidence", winner=None), -0.3), "neutral")

    def test_wilson_bounds(self):
        self.assertAlmostEqual(run.wilson(10, 500)[1], 0.0332, places=3)
        self.assertEqual(run.wilson(0, 0), (0.0, 1.0))


if __name__ == "__main__":
    unittest.main()
