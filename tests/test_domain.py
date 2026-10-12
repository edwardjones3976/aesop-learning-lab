from datetime import datetime, timezone
import unittest

from aesop_lab.domain.models import Activity, ActivityType, Attempt, EvidenceKind, HintLevel, ScoreStatus


class DomainContractTests(unittest.TestCase):
    def test_transfer_item_must_be_held_out(self) -> None:
        with self.assertRaisesRegex(ValueError, "held out"):
            Activity("a1", "recursion", "v1", "family-1", ActivityType.TRACE,
                     EvidenceKind.TRANSFER)

    def test_revealed_solution_cannot_be_scored_correct(self) -> None:
        with self.assertRaisesRegex(ValueError, "revealed solution"):
            Attempt("t1", "a1", "v1", datetime.now(timezone.utc), "answer",
                    HintLevel.WORKED_SOLUTION, ScoreStatus.CORRECT, "exact",
                    "baseline", "scheduled review")

    def test_attempt_keeps_assistance_and_missing_context_distinct(self) -> None:
        attempt = Attempt("t1", "a1", "v1", datetime.now(timezone.utc), "answer",
                          HintLevel.NUDGE, ScoreStatus.UNGRADED, "self review pending",
                          "baseline", "scheduled review")
        self.assertFalse(attempt.unassisted)
        self.assertIsNone(attempt.confidence)
        self.assertIsNone(attempt.outside_study)


if __name__ == "__main__":
    unittest.main()
