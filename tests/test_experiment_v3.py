"""Controlled v3 fixtures verify prospective mechanics, not human benefit."""

from datetime import datetime, timedelta, timezone
import unittest

from aesop_lab.domain.models import (
    Activity, ActivityType, Attempt, EvidenceKind, ExperimentAssignment,
    HintLevel, ScoreStatus,
)
from aesop_lab.experiment import PROTOCOL as V1
from aesop_lab.experiment.descriptive_v2 import DESCRIPTIVE_V2 as V2, ExposureV2
from aesop_lab.experiment.descriptive_v3 import (
    DESCRIPTIVE_V3 as V3, ExposureV3, analyze_v3, assign_condition_v3,
)


NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
LEARNER = "v3-isolated-learner"
CONCEPT = "recursive-case-and-trace"
FAMILY = "recursive-case-lamp-toggle-week-v6"
ITEM = Activity("recursive-case-week-01-v6", CONCEPT, "v6", FAMILY,
                ActivityType.TRACE, EvidenceKind.TRANSFER, True, 7)


def assignment():
    return ExperimentAssignment(V3.id, V3.version, CONCEPT, CONCEPT,
                                assign_condition_v3(CONCEPT, LEARNER), V3.seed, NOW)


def exposure():
    return ExposureV3(CONCEPT, "v6", assignment().condition_id, NOW, (),
                      completed_at=NOW)


def attempt(when=NOW + timedelta(days=7), status=ScoreStatus.CORRECT,
            method="reviewed_exact_key"):
    return Attempt("v3-attempt", ITEM.id, "v6", when, "result", HintLevel.NONE,
                   status, method, "assessment-v1", "v3 held-out check")


class ProspectiveV3Tests(unittest.TestCase):
    def test_v3_freezes_new_v6_family_and_preserves_historical_protocols(self):
        self.assertEqual((V1.version, V1.content_version), ("v1", "v4"))
        self.assertEqual((V2.version, V2.content_version), ("v2", "v5"))
        self.assertEqual((V3.version, V3.content_version), ("v3", "v6"))
        self.assertEqual(V3.primary_families[CONCEPT], FAMILY)
        self.assertNotEqual(V3.primary_families[CONCEPT], V2.primary_families[CONCEPT])
        self.assertNotEqual(V3.seed, V2.seed)
        self.assertTrue(V3.public()["prospectiveOnly"])

    def test_assignment_is_deterministic_and_balanced_for_each_learner(self):
        self.assertEqual(assign_condition_v3(CONCEPT, LEARNER),
                         assign_condition_v3(CONCEPT, LEARNER))
        arms = [assign_condition_v3(cid, LEARNER) for cid in V3.primary_families]
        self.assertEqual(set(arms), {"text", "diagram"})
        self.assertIn(arms.count("text"), (2, 3))

    def test_draft_candidate_matches_are_provisional_in_v3(self):
        result = analyze_v3([assignment()], [exposure()],
                            [attempt(method="development_fixture_exact_key")],
                            {ITEM.id: ITEM}, learner_id=LEARNER,
                            now=NOW + timedelta(days=8))
        arm = result["arms"][assignment().condition_id]
        self.assertEqual((arm["eligible"], arm["correct"], arm["provisional"]),
                         (0, 0, 1))
        self.assertEqual(arm["candidateKeyMatches"], 1)
        self.assertEqual(result["independentLearnersWithOutcome"], 0)
        self.assertEqual(result["status"], "insufficient_evidence")
        reviewed = analyze_v3([assignment()], [exposure()],
                              [attempt(method="development_fixture_exact_key")],
                              {ITEM.id: ITEM}, learner_id=LEARNER,
                              now=NOW + timedelta(days=8),
                              content_review_status="reviewed")
        self.assertEqual(reviewed["arms"][assignment().condition_id]["eligible"], 0)
        self.assertEqual(reviewed["arms"][assignment().condition_id]["ungraded"], 1)

    def test_reviewed_on_time_primary_and_late_nonprimary_remain_separate(self):
        on_time = analyze_v3([assignment()], [exposure()], [attempt()],
                             {ITEM.id: ITEM}, learner_id=LEARNER,
                             now=NOW + timedelta(days=8),
                             content_review_status="reviewed")
        self.assertEqual(on_time["arms"][assignment().condition_id]["eligible"], 1)
        delay = timedelta(days=16, hours=2, milliseconds=500)
        late = analyze_v3([assignment()], [exposure()], [attempt(NOW + delay)],
                          {ITEM.id: ITEM}, learner_id=LEARNER,
                          now=NOW + delay, content_review_status="reviewed")
        arm = late["arms"][assignment().condition_id]
        self.assertEqual((arm["late"], arm["eligible"]), (1, 0))
        self.assertEqual(arm["observations"][0]["elapsedSeconds"], delay.total_seconds())

    def test_v2_records_cannot_be_analyzed_as_v3(self):
        prior_assignment = ExperimentAssignment(V2.id, V2.version, CONCEPT, CONCEPT,
                                                "text", V2.seed, NOW)
        with self.assertRaisesRegex(ValueError, "cannot be analyzed as v3"):
            analyze_v3([prior_assignment], [], [], {}, learner_id=LEARNER, now=NOW)
        prior_exposure = ExposureV2(CONCEPT, "v5", "text", NOW, (), completed_at=NOW)
        with self.assertRaisesRegex(ValueError, "cannot be analyzed as v3"):
            analyze_v3([], [prior_exposure], [], {}, learner_id=LEARNER, now=NOW)


if __name__ == "__main__":
    unittest.main()
