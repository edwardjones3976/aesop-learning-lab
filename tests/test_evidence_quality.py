"""Repeated misses are review candidates, not diagnoses of the learner or item."""

from datetime import datetime, timedelta, timezone
import unittest

from aesop_lab.domain.models import Activity, ActivityType, Attempt, EvidenceKind, HintLevel, ScoreStatus
from aesop_lab.evidence import summarize_evidence


class EvidenceQualityTests(unittest.TestCase):
    def test_delayed_timing_and_familiarity_are_observations_not_mastery(self):
        item = Activity("week", "concept", "v5", "week-family", ActivityType.TRACE,
                        EvidenceKind.APPLICATION, True, 7)
        at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        answer = Attempt("late", item.id, "v5", at + timedelta(days=10), "x",
                         HintLevel.NONE, ScoreStatus.CORRECT,
                         "development_fixture_exact_key", "assessment-v1", "delayed_check")
        summary = summarize_evidence({item.id: item}, (answer,), at)
        observed = summary["delayedChecks"][0]
        self.assertEqual(observed["dueAt"], "2026-01-08T00:00:00Z")
        self.assertEqual(observed["actualDelayDays"], 10)
        self.assertEqual(observed["timingStatus"], "on_or_after_due")
        self.assertEqual(observed["familiarityStatus"], "unfamiliar")
        contaminated = summarize_evidence({item.id: item}, (answer,), at,
                                           frozenset({"week-family"}))
        self.assertEqual(contaminated["delayedChecks"][0]["familiarityStatus"], "familiar")

    def test_early_check_displays_less_than_target_delay(self):
        item = Activity("day", "concept", "v5", "day-family", ActivityType.TRACE,
                        EvidenceKind.APPLICATION, True, 1)
        at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        answer = Attempt("early", item.id, "v5", at + timedelta(days=1, seconds=-30), "x",
                         HintLevel.NONE, ScoreStatus.CORRECT,
                         "development_fixture_exact_key", "assessment-v1", "delayed_check")
        observed = summarize_evidence({item.id: item}, (answer,), at)["delayedChecks"][0]
        self.assertEqual(observed["timingStatus"], "early")
        self.assertLess(observed["actualDelayDays"], observed["checkDelayDays"])
        self.assertEqual(observed["actualDelayDays"], 0.999)

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
