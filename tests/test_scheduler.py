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
    def test_plain_language_policy_keeps_selection_and_old_reasons(self) -> None:
        prior = (attempt("assisted", PRACTICE_A, hint=HintLevel.NUDGE),)
        learner = state(LESSON_TIME + timedelta(hours=2), prior)
        old = recommend(learner, 20, "pilot-v4")
        plain = recommend(learner, 20, "pilot-v5")
        self.assertEqual(plain.recommendation.activity_id,
                         old.recommendation.activity_id)
        self.assertEqual(plain.next_check_at, old.next_check_at)
        self.assertIn("hint-assisted", old.reason)
        self.assertIn("used a hint", plain.reason.lower())
        self.assertIn("without help", plain.reason.lower())

    def test_two_errors_across_items_target_shared_evidence_kind(self) -> None:
        recall = Activity("recall", "recursion", "v1", "recall-family",
                          ActivityType.CHOICE, EvidenceKind.RECALL)
        activities = (PRACTICE_A, PRACTICE_B, recall)
        prior = (attempt("wrong-a", PRACTICE_A, correct=False),
                 attempt("wrong-b", PRACTICE_B, correct=False))
        decision = recommend(state(LESSON_TIME + timedelta(hours=2), prior, activities),
                             20, "pilot-v1")
        self.assertIn(decision.recommendation.activity_id, (PRACTICE_A.id, PRACTICE_B.id))
        self.assertIn("Two incorrect answers on application", decision.reason)

    def test_repeated_misses_on_one_prompt_choose_another_and_flag_quality(self) -> None:
        prior = (attempt("wrong-1", PRACTICE_A, correct=False),
                 attempt("wrong-2", PRACTICE_A, correct=False))
        decision = recommend(state(LESSON_TIME + timedelta(hours=2), prior),
                             20, "pilot-v3")
        self.assertEqual(decision.recommendation.activity_id, PRACTICE_B.id)
        self.assertIn("unclear wording", decision.reason)
        self.assertIn("content review", decision.reason)

    def test_hint_assisted_answer_leads_to_fresh_independent_prompt(self) -> None:
        prior = (attempt("assisted", PRACTICE_A, hint=HintLevel.NUDGE),)
        decision = recommend(state(LESSON_TIME + timedelta(hours=2), prior),
                             20, "pilot-v3")
        self.assertEqual(decision.recommendation.activity_id, PRACTICE_B.id)
        self.assertIn("fresh first answer", decision.reason)
        self.assertIsNone(decision.next_check_at)

    def test_assisted_only_item_of_kind_falls_back_to_unseen_other_kind(self) -> None:
        recognition = Activity("recognition", "recursion", "v1", "recognition-family",
                               ActivityType.CHOICE, EvidenceKind.RECOGNITION)
        prior = (attempt("assisted", recognition, hint=HintLevel.NUDGE),)
        decision = recommend(state(LESSON_TIME + timedelta(hours=2), prior,
                                   (recognition, PRACTICE_A, CHECK)), 20, "pilot-v3")
        self.assertEqual(decision.recommendation.activity_id, PRACTICE_A.id)
        self.assertIn("fresh first answer", decision.reason)

    def test_repeated_unassisted_answer_after_hint_cannot_unlock_check(self) -> None:
        prior = (attempt("assisted", PRACTICE_A, hint=HintLevel.NUDGE),
                 attempt("repeated", PRACTICE_A,
                         at=LESSON_TIME + timedelta(minutes=20)))
        decision = recommend(state(LESSON_TIME + timedelta(days=2), prior), 20,
                             "pilot-v3")
        self.assertIsNone(decision.next_check_at)
        self.assertNotEqual(decision.recommendation.activity_id, CHECK.id)

    def test_answer_from_studied_family_cannot_unlock_unfamiliar_check(self) -> None:
        prior = (attempt("studied", PRACTICE_A),)
        decision = recommend(state(LESSON_TIME + timedelta(days=2), prior,
                                   (PRACTICE_A, PRACTICE_B, CHECK),
                                   frozenset({PRACTICE_A.family_id})), 20, "pilot-v4")
        self.assertIsNone(decision.next_check_at)
        self.assertNotEqual(decision.recommendation.activity_id, CHECK.id)

    def test_all_repeatedly_missed_items_are_skipped_when_clean_prompt_exists(self) -> None:
        third = activity("practice-c", "family-e")
        prior = (attempt("a1", PRACTICE_A, correct=False),
                 attempt("a2", PRACTICE_A, correct=False,
                         at=LESSON_TIME + timedelta(minutes=11)),
                 attempt("b1", PRACTICE_B, correct=False),
                 attempt("b2", PRACTICE_B, correct=False,
                         at=LESSON_TIME + timedelta(minutes=11)))
        decision = recommend(state(LESSON_TIME + timedelta(hours=2), prior,
                                   (PRACTICE_A, PRACTICE_B, third)), 20, "pilot-v3")
        self.assertEqual(decision.recommendation.activity_id, third.id)
        self.assertIn("content review", decision.reason)

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

    def test_familiar_only_check_does_not_promise_24_hour_opening(self) -> None:
        decision = recommend(state(LESSON_TIME + timedelta(hours=2),
                                   (attempt("a1", PRACTICE_A),),
                                   encountered=frozenset({"family-c"})),
                             10, "pilot-v1")
        self.assertIsNone(decision.next_check_at)
        self.assertIn("no unused independent check", decision.reason)
        self.assertNotIn("opens after 24 hours", decision.reason)

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
