"""Clock-controlled behavior for continued practice and delayed checks."""

from datetime import datetime, timedelta, timezone
import unittest

from aesop_lab.domain.models import (Activity, ActivityType, Attempt, EvidenceKind,
                                     HintLevel, ScoreStatus)
from aesop_lab.scheduler import LearnerState, recommend


LESSON_TIME = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


def activity(id: str, family: str, *, held_out: bool = False) -> Activity:
    return Activity(id, "recursion", "v1", family, ActivityType.TRACE,
                    EvidenceKind.APPLICATION, held_out)


PRACTICE_A = activity("practice-a", "family-a")
PRACTICE_B = activity("practice-b", "family-b")
CHECK = activity("held-out", "family-c", held_out=True)
WEEK_CHECK = Activity("week-check", "recursion", "v1", "family-d",
                      ActivityType.TRACE, EvidenceKind.TRANSFER, True, 7)


def attempt(id: str, item: Activity, *, correct: bool = True,
            hint: HintLevel = HintLevel.NONE, at: datetime | None = None) -> Attempt:
    return Attempt(id, item.id, "v1", at or LESSON_TIME + timedelta(minutes=10), "2",
                   hint, ScoreStatus.CORRECT if correct else ScoreStatus.INCORRECT,
                   "reviewed_exact_key", "assessment-v1", "practice")


def state(now: datetime, attempts: tuple[Attempt, ...] = (),
          activities: tuple[Activity, ...] = (PRACTICE_A, PRACTICE_B, CHECK),
          encountered: frozenset[str] = frozenset()) -> LearnerState:
    return LearnerState("recursion", "v1", LESSON_TIME, now, activities,
                        attempts, encountered)


class SchedulerTests(unittest.TestCase):
    def test_distinct_week_check_waits_for_day_one_and_seven_days(self) -> None:
        activities = (PRACTICE_A, CHECK, WEEK_CHECK)
        day_six = LESSON_TIME + timedelta(days=6)
        first = attempt("practice", PRACTICE_A)
        initial = recommend(state(day_six, (first,), activities), 10, "pilot-v1")
        self.assertEqual(initial.recommendation.activity_id, CHECK.id)
        day_one = attempt("day-one", CHECK, correct=False,
                          at=LESSON_TIME + timedelta(days=1))
        waiting = recommend(state(day_six, (first, day_one), activities), 10, "pilot-v1")
        self.assertEqual(waiting.next_check_at, LESSON_TIME + timedelta(days=7))
        self.assertNotEqual(waiting.recommendation.activity_id, WEEK_CHECK.id)
        due = recommend(state(LESSON_TIME + timedelta(days=7), (first, day_one), activities),
                        10, "pilot-v1")
        self.assertEqual(due.recommendation.activity_id, WEEK_CHECK.id)
        self.assertEqual(due.recommendation.due_at, LESSON_TIME + timedelta(days=7))
        used = recommend(state(LESSON_TIME + timedelta(days=8),
                               (first, day_one, attempt("week", WEEK_CHECK,
                                                        at=LESSON_TIME + timedelta(days=7))), activities),
                         10, "pilot-v1")
        self.assertIsNone(used.next_check_at)

    def test_practice_remains_available_before_delayed_check(self) -> None:
        decision = recommend(state(LESSON_TIME + timedelta(hours=2),
                                   (attempt("a1", PRACTICE_A),)), 10, "pilot-v1")
        self.assertEqual(decision.recommendation.activity_id, PRACTICE_B.id)
        self.assertEqual(decision.next_check_at, LESSON_TIME + timedelta(hours=24))
        self.assertIsNone(decision.recommendation.due_at)
        self.assertIn("Continue practice now", decision.reason)

    def test_due_check_uses_unseen_held_out_family(self) -> None:
        decision = recommend(state(LESSON_TIME + timedelta(hours=24),
                                   (attempt("a1", PRACTICE_A),)), 10, "pilot-v1")
        self.assertEqual(decision.recommendation.activity_id, CHECK.id)
        self.assertEqual(decision.recommendation.evidence_attempt_ids, ("a1",))
        self.assertEqual(decision.recommendation.due_at,
                         LESSON_TIME + timedelta(hours=24))

    def test_learner_can_choose_practice_when_check_is_due(self) -> None:
        learner = state(LESSON_TIME + timedelta(hours=25),
                        (attempt("a1", PRACTICE_A),))
        decision = recommend(learner, 10, "pilot-v1", mode="practice")
        self.assertEqual(decision.recommendation.activity_id, PRACTICE_B.id)
        self.assertIsNone(decision.recommendation.due_at)
        self.assertEqual(decision.next_check_at, LESSON_TIME + timedelta(hours=24))
        self.assertIn("by choice", decision.reason)
        # Choosing practice does not consume the held-out item.
        later = recommend(learner, 10, "pilot-v1")
        self.assertEqual(later.recommendation.activity_id, CHECK.id)

    def test_unknown_mode_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "mode"):
            recommend(state(LESSON_TIME), 10, "pilot-v1", mode="quiz")

    def test_assisted_or_incorrect_answer_does_not_open_check(self) -> None:
        for prior in (attempt("a1", PRACTICE_A, hint=HintLevel.NUDGE),
                      attempt("a1", PRACTICE_A, correct=False)):
            with self.subTest(prior=prior):
                decision = recommend(state(LESSON_TIME + timedelta(hours=25),
                                           (prior,)), 10, "pilot-v1")
                self.assertEqual(decision.recommendation.activity_id, PRACTICE_B.id)
                self.assertIsNone(decision.next_check_at)

    def test_prelesson_attempt_does_not_open_delayed_check(self) -> None:
        prior = Attempt("pretest", PRACTICE_A.id, "v1", LESSON_TIME - timedelta(hours=1),
                        "2", HintLevel.NONE, ScoreStatus.CORRECT,
                        "reviewed_exact_key", "assessment-v1", "pretest")
        decision = recommend(state(LESSON_TIME + timedelta(hours=25), (prior,)),
                             10, "pilot-v1")
        self.assertEqual(decision.recommendation.activity_id, PRACTICE_B.id)
        self.assertIn("build evidence", decision.reason)
        self.assertIsNone(decision.next_check_at)

    def test_held_out_check_is_not_reused_after_attempt(self) -> None:
        prior = (attempt("a1", PRACTICE_A), attempt("a2", CHECK))
        decision = recommend(state(LESSON_TIME + timedelta(hours=25), prior),
                             10, "pilot-v1")
        self.assertEqual(decision.recommendation.activity_id, PRACTICE_B.id)
        self.assertIsNone(decision.next_check_at)

    def test_familiar_family_is_not_called_independent(self) -> None:
        decision = recommend(state(LESSON_TIME + timedelta(hours=25),
                                   (attempt("a1", PRACTICE_A),),
                                   encountered=frozenset({"family-c"})),
                             10, "pilot-v1")
        self.assertEqual(decision.recommendation.activity_id, PRACTICE_B.id)
        self.assertIsNone(decision.next_check_at)

    def test_no_qualifying_evidence_has_no_promised_check_time(self) -> None:
        decision = recommend(state(LESSON_TIME + timedelta(hours=2)), 10, "pilot-v1")
        self.assertIsNone(decision.next_check_at)
        self.assertIn("also requires unassisted evidence", decision.reason)

    def test_exhausted_practice_rotates_instead_of_locking(self) -> None:
        prior = (attempt("a1", PRACTICE_A), attempt("a2", PRACTICE_B))
        decision = recommend(state(LESSON_TIME + timedelta(hours=2), prior),
                             10, "pilot-v1")
        self.assertEqual(decision.recommendation.activity_id, PRACTICE_A.id)

    def test_short_session_returns_clear_reason(self) -> None:
        decision = recommend(state(LESSON_TIME), 3, "pilot-v1")
        self.assertIsNone(decision.recommendation)
        self.assertIn("five minutes", decision.reason)

    def test_future_attempt_cannot_open_a_check(self) -> None:
        with self.assertRaisesRegex(ValueError, "future"):
            state(LESSON_TIME, (attempt("a1", PRACTICE_A),))


if __name__ == "__main__":
    unittest.main()
