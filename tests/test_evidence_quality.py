"""Repeated misses are review candidates, not diagnoses of the learner or item."""

from datetime import datetime, timedelta, timezone
import unittest

from aesop_lab.domain.models import Activity, ActivityType, Attempt, EvidenceKind, HintLevel, ScoreStatus
from aesop_lab.evidence import summarize_evidence


class EvidenceQualityTests(unittest.TestCase):
    def test_repeated_miss_candidate_keeps_original_attempts(self):
        item = Activity("question", "concept", "v5", "family", ActivityType.CHOICE,
                        EvidenceKind.RECOGNITION)
        at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        attempts = tuple(Attempt(f"miss-{i}", item.id, "v5", at + timedelta(minutes=i),
                                 "wrong", HintLevel.NONE, ScoreStatus.INCORRECT,
                                 "development_fixture_exact_key", "assessment-v1", "practice")
                         for i in range(2))
        summary = summarize_evidence({item.id: item}, attempts, at)
        self.assertEqual(summary["byKind"]["recognition"]["incorrect"], 2)
        self.assertEqual(summary["contentQualityCandidates"][0]["attemptIds"],
                         ["miss-0", "miss-1"])
        self.assertIn("not proof", summary["contentQualityCandidates"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
