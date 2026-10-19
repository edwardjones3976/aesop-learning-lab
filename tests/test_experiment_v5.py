"""V5 pins new content prospectively; synthetic records are not learning outcomes."""

from datetime import datetime, timezone
import unittest

from aesop_lab.domain.models import ExperimentAssignment
from aesop_lab.experiment.descriptive_v4 import DESCRIPTIVE_V4 as V4, ExposureV4
from aesop_lab.experiment.descriptive_v5 import (
    DESCRIPTIVE_V5 as V5, ExposureV5, analyze_v5, assign_condition_v5,
)


NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
LEARNER = "v5-isolated-learner"
CONCEPT = "recursive-case-and-trace"


class ProspectiveV5Tests(unittest.TestCase):
    def test_v5_pins_v8_without_changing_held_out_families(self):
        self.assertEqual((V5.version, V5.content_version), ("v5", "v8"))
        self.assertEqual(V5.primary_family_by_concept, V4.primary_family_by_concept)
        self.assertNotEqual(V5.seed, V4.seed)
        self.assertTrue(V5.public()["prospectiveOnly"])
        self.assertEqual({assign_condition_v5(cid, LEARNER) for cid in V5.primary_families},
                         {"text", "diagram"})

    def test_historical_assignment_and_exposure_cannot_enter_v5(self):
        prior = ExperimentAssignment(V4.id, V4.version, CONCEPT, CONCEPT,
                                     "text", V4.seed, NOW)
        with self.assertRaisesRegex(ValueError, "cannot be analyzed as v5"):
            analyze_v5([prior], [], [], {}, learner_id=LEARNER, now=NOW)
        old_exposure = ExposureV4(CONCEPT, "v7", "text", NOW, (), completed_at=NOW)
        with self.assertRaisesRegex(ValueError, "cannot be analyzed as v5"):
            analyze_v5([], [old_exposure], [], {}, learner_id=LEARNER, now=NOW)

    def test_v5_rejects_historical_content_identity(self):
        with self.assertRaisesRegex(ValueError, "content version differs from v5"):
            ExposureV5(CONCEPT, "v7", "text", NOW, ())


if __name__ == "__main__":
    unittest.main()
