"""Plain-language v10 content has a new prospective protocol identity."""

from datetime import datetime, timezone
import unittest

from aesop_lab.domain.models import ExperimentAssignment
from aesop_lab.experiment.descriptive_v6 import DESCRIPTIVE_V6 as V6, ExposureV6
from aesop_lab.experiment.descriptive_v7 import (
    DESCRIPTIVE_V7 as V7, ExposureV7, analyze_v7, assign_condition_v7,
)


NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
LEARNER = "v7-isolated-learner"
CONCEPT = "recursive-case-and-trace"


class ProspectiveV7Tests(unittest.TestCase):
    def test_v7_pins_new_content_without_lowering_evidence_rules(self):
        self.assertEqual((V7.version, V7.content_version), ("v7", "v10"))
        self.assertEqual(V7.primary_family_by_concept, V6.primary_family_by_concept)
        self.assertEqual(V7.primary_delay_days, V6.primary_delay_days)
        self.assertEqual(V7.primary_window_days, V6.primary_window_days)
        self.assertEqual(V7.target_exposure_minutes, V6.target_exposure_minutes)
        self.assertEqual(V7.minimum_independent_learners_per_arm,
                         V6.minimum_independent_learners_per_arm)
        self.assertNotEqual(V7.seed, V6.seed)
        self.assertTrue(V7.public()["prospectiveOnly"])
        for cid in V7.primary_families:
            self.assertEqual(assign_condition_v7(cid, LEARNER),
                             assign_condition_v7(cid, LEARNER))

    def test_historical_assignment_and_exposure_cannot_enter_v7(self):
        prior = ExperimentAssignment(V6.id, V6.version, CONCEPT, CONCEPT,
                                     "text", V6.seed, NOW)
        with self.assertRaisesRegex(ValueError, "cannot be analyzed as v7"):
            analyze_v7([prior], [], [], {}, learner_id=LEARNER, now=NOW)
        old_exposure = ExposureV6(CONCEPT, "v9", "text", NOW, (), completed_at=NOW)
        with self.assertRaisesRegex(ValueError, "cannot be analyzed as v7"):
            analyze_v7([], [old_exposure], [], {}, learner_id=LEARNER, now=NOW)
        with self.assertRaisesRegex(ValueError, "content version differs from v7"):
            ExposureV7(CONCEPT, "v9", "text", NOW, ())


if __name__ == "__main__":
    unittest.main()
