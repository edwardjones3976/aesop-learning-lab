"""Controlled v4 fixtures verify prospective mechanics, not human benefit."""

from datetime import datetime, timezone
import unittest

from aesop_lab.domain.models import ExperimentAssignment
from aesop_lab.experiment.descriptive_v3 import DESCRIPTIVE_V3 as V3, ExposureV3
from aesop_lab.experiment.descriptive_v4 import (
    DESCRIPTIVE_V4 as V4, ExposureV4, analyze_v4, assign_condition_v4,
)


NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
LEARNER = "v4-isolated-learner"
CONCEPT = "recursion-as-self-call"


class ProspectiveV4Tests(unittest.TestCase):
    def test_v4_pins_v7_with_unchanged_families_and_a_new_seed(self):
        self.assertEqual((V4.version, V4.content_version), ("v4", "v7"))
        self.assertEqual(V4.primary_family_by_concept, V3.primary_family_by_concept)
        self.assertNotEqual(V4.seed, V3.seed)
        self.assertTrue(V4.public()["prospectiveOnly"])
        arms = [assign_condition_v4(cid, LEARNER) for cid in V4.primary_families]
        self.assertEqual(set(arms), {"text", "diagram"})

    def test_v3_records_cannot_be_analyzed_as_v4(self):
        prior = ExperimentAssignment(V3.id, V3.version, CONCEPT, CONCEPT,
                                     "text", V3.seed, NOW)
        with self.assertRaisesRegex(ValueError, "cannot be analyzed as v4"):
            analyze_v4([prior], [], [], {}, learner_id=LEARNER, now=NOW)
        exposure = ExposureV3(CONCEPT, "v6", "text", NOW, (), completed_at=NOW)
        with self.assertRaisesRegex(ValueError, "cannot be analyzed as v4"):
            analyze_v4([], [exposure], [], {}, learner_id=LEARNER, now=NOW)

    def test_v4_exposure_rejects_the_v6_content_version(self):
        with self.assertRaisesRegex(ValueError, "content version differs from v4"):
            ExposureV4(CONCEPT, "v6", "text", NOW, ())


if __name__ == "__main__":
    unittest.main()
