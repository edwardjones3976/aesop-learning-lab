"""V6 pins new content prospectively; synthetic records are not learning outcomes."""

from datetime import datetime, timezone
import unittest

from aesop_lab.domain.models import ExperimentAssignment
from aesop_lab.experiment.descriptive_v5 import DESCRIPTIVE_V5 as V5, ExposureV5
from aesop_lab.experiment.descriptive_v6 import (
    DESCRIPTIVE_V6 as V6, ExposureV6, analyze_v6, assign_condition_v6,
)


NOW = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)
LEARNER = "v6-isolated-learner"
CONCEPT = "recursive-case-and-trace"


class ProspectiveV6Tests(unittest.TestCase):
    def test_v6_pins_v9_without_changing_held_out_families_or_thresholds(self):
        self.assertEqual((V6.version, V6.content_version), ("v6", "v9"))
        self.assertEqual(V6.primary_family_by_concept, V5.primary_family_by_concept)
        self.assertEqual(V6.primary_delay_days, V5.primary_delay_days)
        self.assertEqual(V6.primary_window_days, V5.primary_window_days)
        self.assertEqual(V6.target_exposure_minutes, V5.target_exposure_minutes)
        self.assertEqual(V6.minimum_independent_learners_per_arm,
                         V5.minimum_independent_learners_per_arm)
        self.assertNotEqual(V6.seed, V5.seed)
        self.assertTrue(V6.public()["prospectiveOnly"])
        self.assertEqual({assign_condition_v6(cid, LEARNER) for cid in V6.primary_families},
                         {"text", "diagram"})

    def test_historical_assignment_and_exposure_cannot_enter_v6(self):
        prior = ExperimentAssignment(V5.id, V5.version, CONCEPT, CONCEPT,
                                     "text", V5.seed, NOW)
        with self.assertRaisesRegex(ValueError, "cannot be analyzed as v6"):
            analyze_v6([prior], [], [], {}, learner_id=LEARNER, now=NOW)
        old_exposure = ExposureV5(CONCEPT, "v8", "text", NOW, (), completed_at=NOW)
        with self.assertRaisesRegex(ValueError, "cannot be analyzed as v6"):
            analyze_v6([], [old_exposure], [], {}, learner_id=LEARNER, now=NOW)

    def test_v6_rejects_historical_content_identity(self):
        with self.assertRaisesRegex(ValueError, "content version differs from v6"):
            ExposureV6(CONCEPT, "v8", "text", NOW, ())


if __name__ == "__main__":
    unittest.main()
