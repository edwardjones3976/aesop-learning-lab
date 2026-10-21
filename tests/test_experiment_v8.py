"""Plain-language v11 content has a new prospective protocol identity."""

from datetime import datetime, timezone
import unittest

from aesop_lab.domain.models import ExperimentAssignment
from aesop_lab.experiment.descriptive_v6 import DESCRIPTIVE_V6 as V6, ExposureV6
from aesop_lab.experiment.descriptive_v8 import (
    DESCRIPTIVE_V8 as V8, ExposureV8, analyze_v8, assign_condition_v8,
)


NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
LEARNER = "v8-isolated-learner"
CONCEPT = "recursive-case-and-trace"


class ProspectiveV8Tests(unittest.TestCase):
    def test_v8_pins_new_content_without_lowering_evidence_rules(self):
        self.assertEqual((V8.version, V8.content_version), ("v8", "v11"))
        self.assertEqual(dict(V8.primary_family_by_concept), {
            **dict(V6.primary_family_by_concept),
            "recursion-as-self-call": "recursion-converge-week-v8",
        })
        self.assertEqual(V8.primary_delay_days, V6.primary_delay_days)
        self.assertEqual(V8.primary_window_days, V6.primary_window_days)
        self.assertEqual(V8.target_exposure_minutes, V6.target_exposure_minutes)
        self.assertEqual(V8.minimum_independent_learners_per_arm,
                         V6.minimum_independent_learners_per_arm)
        self.assertNotEqual(V8.seed, V6.seed)
        self.assertTrue(V8.public()["prospectiveOnly"])
        for cid in V8.primary_families:
            self.assertEqual(assign_condition_v8(cid, LEARNER),
                             assign_condition_v8(cid, LEARNER))

    def test_historical_assignment_and_exposure_cannot_enter_v8(self):
        prior = ExperimentAssignment(V6.id, V6.version, CONCEPT, CONCEPT,
                                     "text", V6.seed, NOW)
        with self.assertRaisesRegex(ValueError, "cannot be analyzed as v8"):
            analyze_v8([prior], [], [], {}, learner_id=LEARNER, now=NOW)
        old_exposure = ExposureV6(CONCEPT, "v9", "text", NOW, (), completed_at=NOW)
        with self.assertRaisesRegex(ValueError, "cannot be analyzed as v8"):
            analyze_v8([], [old_exposure], [], {}, learner_id=LEARNER, now=NOW)
        with self.assertRaisesRegex(ValueError, "content version differs from v8"):
            ExposureV8(CONCEPT, "v9", "text", NOW, ())

    def test_v8_findings_reason_mentions_minimum_independent_learners_per_arm(self):
        findings = analyze_v8([], [], [], {}, learner_id=LEARNER, now=NOW)
        self.assertIn(
            f"minimum of {V8.minimum_independent_learners_per_arm} independent learners",
            findings["reason"],
        )


if __name__ == "__main__":
    unittest.main()
