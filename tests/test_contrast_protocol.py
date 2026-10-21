import hashlib
import json
import math
import random
import tempfile
import unittest
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aesop_lab.content.micro_unit import load_micro_unit_pack
from aesop_lab.contrast import protocol
from aesop_lab.contrast.protocol import BASELINE, VARIANT, ContrastSpec
from aesop_lab.micro.engine import MicroUnitEngine
from aesop_lab.storage.sqlite import SQLiteStore

FIXTURES = Path(__file__).parent / "fixtures"


def counts(baseline, variant):
    return {BASELINE: baseline, VARIANT: variant}


class AllocationTests(unittest.TestCase):
    def test_block_seed_matches_frozen_encoding(self):
        expected = hashlib.sha256(b'["learner-\\u00e9","pack-1","order-v1",3]').hexdigest()
        self.assertEqual(protocol.block_seed("learner-é", "pack-1", "order-v1", 3), expected)
        with self.assertRaises(ValueError):
            protocol.block_seed("learner", "pack", "order-v1", True)

    def test_every_block_is_two_and_two_and_follows_the_position_digests(self):
        for index in range(200):
            seed = protocol.block_seed("learner", "pack", "order-v1", index)
            roles = protocol.block_roles(seed)
            self.assertEqual(Counter(roles), {BASELINE: 2, VARIANT: 2})
            digests = [hashlib.sha256(f"{seed}:{p}".encode()).hexdigest() for p in range(4)]
            first_two = sorted(range(4), key=lambda p: (digests[p], p))[:2]
            self.assertEqual({p for p, r in enumerate(roles) if r == BASELINE}, set(first_two))


class EstimatorTests(unittest.TestCase):
    def test_two_uniform_posteriors_match_closed_form(self):
        for c in (0.0, 0.05, 0.3, -0.05, -0.4):
            exact = (1 - c) ** 2 / 2 if c >= 0 else 1 - (1 + c) ** 2 / 2
            value, error = protocol.p_diff_greater((1, 1), (1, 1), c)
            self.assertAlmostEqual(value, exact, delta=1e-9)
            self.assertLessEqual(error, protocol.TOLERANCE)
        p = protocol.probabilities(counts((0, 0), (0, 0)))
        self.assertAlmostEqual(p["equivalent"], 1 - 0.95 ** 2, delta=1e-9)

    def test_agrees_with_seeded_monte_carlo(self):
        rng, draws = random.Random(7), 200_000
        diffs = [rng.betavariate(21, 9) - rng.betavariate(18, 12) for _ in range(draws)]
        p = protocol.probabilities(counts((17, 11), (20, 8)))
        for key, rate in (("variant_superior", sum(d > 0.05 for d in diffs) / draws),
                          ("baseline_superior", sum(d < -0.05 for d in diffs) / draws),
                          ("equivalent", sum(abs(d) < 0.05 for d in diffs) / draws),
                          ("variant_ahead", sum(d > 0 for d in diffs) / draws)):
            self.assertAlmostEqual(p[key], rate, delta=0.005, msg=key)

    def test_probabilities_are_symmetric_under_arm_swap(self):
        p = protocol.probabilities(counts((9, 21), (14, 16)))
        q = protocol.probabilities(counts((14, 16), (9, 21)))
        self.assertAlmostEqual(p["variant_superior"], q["baseline_superior"], delta=protocol.TOLERANCE)
        self.assertAlmostEqual(p["equivalent"], q["equivalent"], delta=protocol.TOLERANCE)


class DecisionTests(unittest.TestCase):
    def test_superiority_in_both_directions_stops_at_day_14(self):
        up = protocol.decide(14, counts((3, 27), (27, 3)))
        self.assertEqual((up["status"], up["outcome"], up["winner"]), ("terminal", "repeated benefit", VARIANT))
        down = protocol.decide(14, counts((27, 3), (3, 27)))
        self.assertEqual((down["outcome"], down["winner"]), ("repeated benefit", BASELINE))

    def test_minimum_eight_per_arm_blocks_every_decision(self):
        early = protocol.decide(14, counts((0, 7), (30, 0)))
        self.assertEqual((early["status"], early["outcome"]), ("continue", None))
        final = protocol.decide(28, counts((0, 7), (30, 0)))
        self.assertEqual((final["status"], final["outcome"]), ("terminal", "insufficient evidence"))

    def test_equivalence_needs_far_more_than_one_learner(self):
        self.assertEqual(protocol.decide(28, counts((600, 400), (600, 400)))["outcome"],
                         "no meaningful difference detected")
        self.assertEqual(protocol.decide(28, counts((17, 11), (17, 11)))["outcome"], "insufficient evidence")
        self.assertEqual(protocol.decide(21, counts((17, 11), (17, 11)))["status"], "continue")

    def test_day_28_promising_is_variant_only(self):
        result = protocol.decide(28, counts((12, 16), (22, 6)))
        self.assertGreaterEqual(result["probabilities"]["variant_ahead"], protocol.PROMISING)
        self.assertLess(result["probabilities"]["variant_superior"], 0.999)
        self.assertEqual(result["outcome"], "promising")
        mirrored = protocol.decide(28, counts((22, 6), (12, 16)))
        self.assertEqual(mirrored["outcome"], "insufficient evidence")

    def test_only_scheduled_days_and_first_terminal_look_counts(self):
        with self.assertRaises(ValueError):
            protocol.decide(20, counts((10, 10), (10, 10)))
        judged = protocol.judge({14: counts((3, 27), (27, 3)), 21: counts((27, 3), (3, 27))})
        self.assertEqual((judged["decision_day"], judged["winner"], len(judged["looks"])), (14, VARIANT, 1))
        open_ = protocol.judge({14: counts((5, 5), (5, 5))})
        self.assertIsNone(open_["outcome"])


def simulate(gap, learners, seed):
    """Frozen gate model in miniature: Beta(12, 8) baseline, 3 units a day, 90% answered on days 7-10."""
    rng = random.Random(seed)
    tally = Counter()
    for _ in range(learners):
        base = rng.betavariate(12, 8)
        p = {BASELINE: base, VARIANT: min(0.98, max(0.02, base + gap))}
        learner = f"{seed}:{rng.random()}"
        roles = [role for index in range(21) for role in protocol.block_roles(
            protocol.block_seed(learner, "pack", "order-v1", index))]
        # 84 units in consecutive blocks of four, 3 a day.
        events = [(n // 3 + 7 + rng.random() * 3, role, rng.random() < p[role])
                  for n, role in enumerate(roles) if rng.random() < 0.9]
        snapshots = {}
        for look, _, _ in protocol.LOOKS:
            c = {BASELINE: [0, 0], VARIANT: [0, 0]}
            for at, role, correct in events:
                if at <= look:
                    c[role][not correct] += 1
            snapshots[look] = {r: tuple(v) for r, v in c.items()}
        judged = protocol.judge(snapshots)
        tally[(judged["outcome"], judged["winner"])] += 1
    return tally


def wilson_upper(k, n, z=1.6448536269514722):
    p = k / n
    return (p + z * z / (2 * n) + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


class StreamTests(unittest.TestCase):
    LEARNERS = 300

    def test_null_stream_rarely_claims_a_difference(self):
        tally = simulate(0.0, self.LEARNERS, seed=11)
        claims = sum(v for (outcome, _), v in tally.items() if outcome in ("repeated benefit", "promising"))
        self.assertLessEqual(wilson_upper(claims, self.LEARNERS), 0.05, tally)

    def test_ten_point_stream_never_favours_the_worse_arm(self):
        tally = simulate(0.10, self.LEARNERS, seed=12)
        wrong = tally[("repeated benefit", BASELINE)]
        self.assertLessEqual(wilson_upper(wrong, self.LEARNERS), 0.05, tally)
        right = tally[("repeated benefit", VARIANT)] + tally[("promising", None)]
        self.assertGreater(right, 0, tally)
        reverse = simulate(-0.10, self.LEARNERS, seed=13)
        wrong = reverse[("repeated benefit", VARIANT)] + reverse[("promising", None)]
        self.assertLessEqual(wilson_upper(wrong, self.LEARNERS), 0.05, reverse)


class ContrastEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SQLiteStore(Path(self.temp.name) / "learner.db")
        self.addCleanup(lambda: self.store.close())
        self.at = self.start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
        self.store.confirm_consent(self.at)
        self.store.connection.execute("INSERT INTO learner_identity VALUES (1, 'synthetic-contrast')")
        self.store.connection.commit()
        pack = load_micro_unit_pack(FIXTURES / "micro-unit-sample.json")
        base = pack.units[0]
        self.pack = replace(pack, units=tuple(replace(base, id=f"unit-{i:02}", check=replace(
            base.check, id=f"check-{i}", family_id=f"family-{i}")) for i in range(90)))
        self.spec = ContrastSpec("order-test", "cued_retrieval", "example_sentence")
        self.engine = self.make()

    def make(self):
        return MicroUnitEngine(self.pack, self.store, lambda: self.at, contrast=self.spec)

    def run_days(self, days, correct_by_method):
        """Study 3 new units a day; answer each check on day 7 after completion."""
        engine, key = self.engine, self.pack.units[0].check.answer_key.accepted[0]
        for _ in range(days):
            day_start = self.at
            while (activity := engine.next_activity()) is not None:
                if activity["kind"] == "check":
                    method = engine._exposures()[activity["unit_id"]]["method_id"]
                    engine.answer_check(activity["unit_id"], key if correct_by_method[method] else "wrong",
                                        outside_study="none")
                else:
                    engine.start_unit(activity["unit_id"])
                    engine.complete_unit(activity["unit_id"])
                self.at += timedelta(minutes=1)
            self.at = day_start + timedelta(days=1)

    def test_contrast_replaces_thompson_and_balances_every_block(self):
        self.run_days(10, {"cued_retrieval": True, "example_sentence": True})
        exposures = self.store.micro_exposures(self.pack.pack_id)
        self.assertEqual({r["policy_branch"] for r in exposures}, {"contrast-block"})
        self.assertEqual({r["method_id"] for r in exposures}, {"cued_retrieval", "example_sentence"})
        blocks = self.store.contrast_blocks(self.pack.pack_id, "order-test")
        ordered = [u.id for u in self.engine._ordered_units()]
        method = {r["unit_id"]: r["method_id"] for r in exposures}
        for block in blocks:
            allocation = json.loads(block["allocation"])
            self.assertEqual(Counter(m for _, m in allocation), {"cued_retrieval": 2, "example_sentence": 2})
            self.assertEqual([u for u, _ in allocation], ordered[4 * block["block_index"]:4 * block["block_index"] + 4])
            for unit_id, assigned in allocation:
                if unit_id in method:
                    self.assertEqual(method[unit_id], assigned)

    def test_whole_block_is_stored_before_its_first_exposure(self):
        first = self.engine.next_activity()["unit_id"]
        self.engine.start_unit(first)
        [block] = self.store.contrast_blocks(self.pack.pack_id, "order-test")
        self.assertEqual(len(json.loads(block["allocation"])), 4)
        self.assertEqual(len(self.store.micro_exposures(self.pack.pack_id)), 1)
        # A restarted engine replays the stored block, not a fresh computation.
        self.store.connection.execute(
            "UPDATE contrast_blocks SET allocation = ? WHERE block_index = 0",
            (json.dumps([[u, "cued_retrieval" if i % 2 else "example_sentence"]
                         for i, (u, _) in enumerate(json.loads(block["allocation"]))]),))
        self.store.connection.commit()
        restarted = self.make()
        second = next(u for u, _ in json.loads(self.store.contrast_blocks(self.pack.pack_id, "order-test")[0]["allocation"]) if u != first)
        expected = dict(json.loads(self.store.contrast_blocks(self.pack.pack_id, "order-test")[0]["allocation"]))[second]
        self.assertEqual(restarted.start_unit(second)["method_id"], expected)

    def test_large_effect_stops_at_day_14_then_routes_to_the_winner(self):
        self.run_days(15, {"cued_retrieval": False, "example_sentence": True})
        status = self.engine.contrast_status()
        self.assertEqual((status["outcome"], status["winner"], status["decision_day"]),
                         ("repeated benefit", "example_sentence", 14))
        self.assertEqual((status["scope"], status["contrast_id"], status["topic"]),
                         ("delayed-recall", "order-test", self.pack.pack_id))
        look = status["looks"][0]
        self.assertGreaterEqual(min(sum(c) for c in look["counts"].values()), protocol.MINIMUM_PER_ARM)
        self.run_days(1, {"cued_retrieval": False, "example_sentence": True})
        latest = self.store.micro_exposures(self.pack.pack_id)[-1]
        self.assertEqual((latest["policy_branch"], latest["method_id"]), ("post-decision", "example_sentence"))
        # Post-decision units never change the frozen finding.
        self.assertEqual(self.engine.contrast_status()["looks"], status["looks"])

    def test_late_evaluation_reproduces_the_on_time_snapshot(self):
        self.run_days(14, {"cued_retrieval": True, "example_sentence": True})
        self.at = self.start + timedelta(days=14, hours=1)
        on_time = self.make().contrast_status()["looks"]
        self.assertEqual(len(on_time), 1)
        self.run_days(10, {"cued_retrieval": True, "example_sentence": True})
        self.at = self.start + timedelta(days=21, hours=1)
        late = self.make().contrast_status()["looks"]
        self.assertEqual(late[0]["counts"], on_time[0]["counts"])
        self.assertEqual(late[0]["probabilities"], on_time[0]["probabilities"])

    def test_identical_arms_end_with_an_honest_inconclusive_result(self):
        self.run_days(29, {"cued_retrieval": True, "example_sentence": True})
        status = self.engine.contrast_status()
        self.assertEqual((status["outcome"], status["decision_day"]), ("insufficient evidence", 28))
        self.assertEqual(status["future_default"], "cued_retrieval")
        self.assertEqual([look["day"] for look in status["looks"]], [14, 21, 28])

    def test_contrast_methods_must_be_in_the_pack(self):
        with self.assertRaises(ValueError):
            MicroUnitEngine(self.pack, self.store, lambda: self.at,
                            contrast=ContrastSpec("x", "cued_retrieval", "predict_first"))


if __name__ == "__main__":
    unittest.main()
