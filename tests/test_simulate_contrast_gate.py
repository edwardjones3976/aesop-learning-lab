import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "simulate_contrast_gate.py"
spec = importlib.util.spec_from_file_location("simulate_contrast_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def row(scenario, outcome, winner=None):
    gap = gate.SCENARIOS[scenario]["gap"]
    return {"scenario": scenario, "outcome": outcome, "winner": winner,
            "truth": {gate.SPEC.baseline: 0.6, gate.SPEC.variant: 0.6 + gap}}


class GateRuleTests(unittest.TestCase):
    def test_wilson_bound_exactly_on_a_threshold_fails(self):
        lower, upper = gate.wilson(0, 500)
        self.assertEqual(lower, 0.0)
        self.assertLess(upper, 0.01)
        # Find a count whose upper bound sits just above 5%, and check strictness at the boundary.
        failing = next(k for k in range(500) if gate.wilson(k, 500)[1] >= 0.05)
        checks = gate.requirements("null", [row("null", "promising")] * failing
                                   + [row("null", "insufficient evidence")] * (500 - failing))
        self.assertFalse(checks[0]["passed"])

    def test_wrong_direction_includes_promising_against_a_better_baseline(self):
        self.assertEqual(gate.classify(row("minus10", "promising")), "wrong")
        self.assertEqual(gate.classify(row("plus10", "promising")), "correct")
        self.assertEqual(gate.classify(row("plus10", "repeated benefit", gate.SPEC.baseline)), "wrong")
        self.assertEqual(gate.classify(row("minus10", "repeated benefit", gate.SPEC.baseline)), "correct")
        self.assertEqual(gate.classify(row("null", "repeated benefit", gate.SPEC.variant)), "wrong")
        self.assertEqual(gate.classify(row("plus3", "insufficient evidence")), "neutral")

    def test_every_frozen_scenario_has_its_rows(self):
        names = [c["requirement"] for c in gate.requirements("plus3", [row("plus3", "insufficient evidence")] * 500)]
        self.assertEqual(len(names), 3)
        plus20 = gate.requirements("plus20", [row("plus20", "promising")] * 150 + [row("plus20", "insufficient evidence")] * 350)
        self.assertTrue(all(c["passed"] for c in plus20))
        self.assertEqual(set(gate.SCENARIOS), {"null", "plus3", "minus3", "plus10", "minus10", "plus20",
                                               "plus10_missed_days", "plus10_dropout"})
        self.assertEqual({s.get("missed", 0) for n, s in gate.SCENARIOS.items() if n != "plus10_missed_days"}, {0})
        self.assertEqual({s.get("dropout", 0) for n, s in gate.SCENARIOS.items() if n != "plus10_dropout"}, {0})


class GateRunTests(unittest.TestCase):
    def test_learner_runs_on_the_contrast_engine_and_repeats_exactly(self):
        first = gate.simulate_learner(("plus20", 3, 0))
        self.assertEqual(first, gate.simulate_learner(("plus20", 3, 0)))
        self.assertIn(first["outcome"], ("repeated benefit", "no meaningful difference detected",
                                         "promising", "insufficient evidence"))
        self.assertGreaterEqual(min(first["eligible_at_decision"].values()), 15)
        self.assertEqual(first["studied"], 66)

    def test_dropout_learner_stops_studying(self):
        rows = [gate.simulate_learner(("plus10_dropout", 1, i)) for i in range(40)]
        dropped = [r for r in rows if r["dropout_day"] is not None]
        self.assertTrue(dropped)
        for r in dropped:
            self.assertLessEqual(r["studied"], 3 * r["dropout_day"])

    def test_command_writes_a_verdict_first_report(self):
        with tempfile.TemporaryDirectory() as folder:
            subprocess.run([sys.executable, str(SCRIPT), "--out", folder, "--learners", "1",
                            "--scenarios", "null"], check=True, capture_output=True)
            report = (Path(folder) / "contrast-gate.html").read_text(encoding="utf-8")
            data = json.loads((Path(folder) / "contrast-gate.json").read_text(encoding="utf-8"))
        self.assertIn("partial run: not a gate result", report)
        self.assertFalse(data["gate_passed"])
        self.assertEqual(len(data["learners"]["null"]), 10)
        self.assertLess(report.index("Gate:"), report.index("Gate requirements"))


if __name__ == "__main__":
    unittest.main()
