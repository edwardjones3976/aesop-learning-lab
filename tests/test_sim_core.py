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


class ReviewFixTests(unittest.TestCase):
    def test_misspelt_model_fields_are_rejected(self):
        with self.assertRaises(scenario.ScenarioError):
            make(model={"method_logit_men": 0.4})
        with self.assertRaises(scenario.ScenarioError):
            scenario.normalize({**BASE, "model": {"kind": "bernoulli", "half_life_days": [7, 21]}})

    def test_parity_sample_covers_every_seed_without_repeats(self):
        from unittest.mock import patch
        seen = []
        with patch.object(run, "_parity_one", side_effect=lambda job: seen.append(job[1:]) or None):
            run.parity_sample(make(learners={"seeds": list(range(1, 11)), "per_seed": 50}), 50)
        self.assertEqual(len(seen), 50)
        self.assertEqual(len(set(seen)), 50)
        self.assertEqual({s for s, _ in seen}, set(range(1, 11)))
        self.assertGreater(len({i for _, i in seen}), 1)

    def test_unknown_fields_fail_even_when_a_row_switches_kind(self):
        with self.assertRaises(scenario.ScenarioError):
            scenario.expand({**BASE, "model": {"kind": "half-life", "method_logit_men": 0.4},
                             "rows": [{"id": "x", "model": {"kind": "log-delay"}}]})
        with self.assertRaises(scenario.ScenarioError):
            make(learners={"seeds": [1], "per_seedd": 3})

    def test_unit_started_at_a_terminal_cutoff_matches_the_engine(self):
        row = [r for r in scenario.load("round1-gate") if r["id"].endswith("minus3")][0]
        t = learner.simulate(row, 4, 3)
        self.assertEqual(replay.compare(fastpath.judge(t), replay.engine_judge(t, 3)), [])

    def test_novelty_fades_and_arm_difficulty_is_an_imbalance_not_an_effect(self):
        novel = make(model={"method_logit_mean": 0.0, "method_logit_sd": 0.0,
                            "novelty_logit": 1.5, "novelty_half_life_units": 5})
        t = learner.simulate(novel, 1, 0)
        early = [u.p_variant - u.p_baseline for u in t.units[:5]]
        late = [u.p_variant - u.p_baseline for u in t.units[-5:]]
        self.assertGreater(sum(early), sum(late) + 0.2)
        shifted = make(model={"method_logit_mean": 0.0, "method_logit_sd": 0.0, "arm_difficulty_shift": 1.0})
        gaps = [learner.simulate(shifted, 1, i).true_gap for i in range(5)]
        self.assertTrue(all(abs(g) < 1e-12 for g in gaps))

    def test_scenarios_ship_as_package_data(self):
        import tomllib
        from pathlib import Path
        config = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertIn("sim/scenarios/*.json", config["tool"]["setuptools"]["package-data"]["aesop_lab"])
        self.assertIn("sim/designs/*.json", config["tool"]["setuptools"]["package-data"]["aesop_lab"])


class DesignTests(unittest.TestCase):
    def test_default_design_decides_exactly_like_protocol_v1(self):
        import random
        rng = random.Random(5)
        for _ in range(2000):
            counts = {protocol.BASELINE: (rng.randint(0, 40), rng.randint(0, 40)),
                      protocol.VARIANT: (rng.randint(0, 40), rng.randint(0, 40))}
            look = rng.randrange(3)
            day = scenario.DEFAULT_DESIGN["looks"][look]
            try:
                expected = protocol.decide(day, counts)
            except ArithmeticError:
                continue
            got = fastpath.decide(look, day, counts, scenario.DEFAULT_DESIGN)
            self.assertEqual((got["status"], got["outcome"], got["winner"]),
                             (expected["status"], expected["outcome"], expected["winner"]), counts)

    def test_v1_detection_and_candidate_designs(self):
        self.assertTrue(scenario.is_v1(make()))
        self.assertFalse(scenario.is_v1(make(design={"promising_both_ways": True})))
        with self.assertRaises(scenario.ScenarioError):
            make(design={"looks": [14, 28], "superiority": [0.999]})
        long = make(design={"looks": [14, 28, 42, 56], "superiority": [0.999] * 4, "equivalence": [0.9] * 4})
        self.assertEqual(len(learner.simulate(long, 1, 0).units), 3 * 50)

    def test_both_ways_promising_names_the_arm_and_abstention_blocks_unequal_data(self):
        both = dict(scenario.DEFAULT_DESIGN, promising_both_ways=True)
        counts = {protocol.BASELINE: (22, 6), protocol.VARIANT: (12, 16)}
        self.assertEqual(fastpath.decide(2, 28, counts, scenario.DEFAULT_DESIGN)["outcome"], "insufficient evidence")
        got = fastpath.decide(2, 28, counts, both)
        self.assertEqual((got["outcome"], got["winner"]), ("promising", protocol.BASELINE))
        skewed = make(model={"method_logit_mean": 3.0, "method_logit_sd": 0.0},
                      behaviour={"arm_skip": {"baseline": 0.4, "variant": 0.0}},
                      design={"abstain": {"missing_gap": 0.1}})
        results = [fastpath.judge(learner.simulate(skewed, 1, i), skewed["design"]) for i in range(10)]
        self.assertTrue(any(r["abstained"] for r in results))
        self.assertTrue(all(r["outcome"] == "insufficient evidence" for r in results if r["abstained"]))


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
