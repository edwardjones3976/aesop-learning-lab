from datetime import datetime, timezone
import unittest

from aesop_lab.assessment import (
    AnswerKey,
    AssessmentError,
    Hint,
    HintLadder,
    ItemSpec,
    Rubric,
    RubricCriterion,
    assess,
    build_attempt,
    build_self_review,
)
from aesop_lab.assessment.engine import EXACT_KEY_METHOD, PENDING_REVIEW_METHOD
from aesop_lab.domain.models import (
    Activity,
    ActivityType,
    EvidenceKind,
    HintLevel,
    OutsideStudy,
    ScoreStatus,
    CriterionReview,
    ReviewRating,
)

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)

LADDER = HintLadder((
    Hint(HintLevel.NUDGE, "Find the stopping condition."),
    Hint(HintLevel.TARGETED, "Evaluate f(0), then f(1)."),
    Hint(HintLevel.WORKED_SOLUTION, "f(0)=1, f(1)=1, f(2)=2."),
))


def trace_item(hints: HintLadder = LADDER) -> ItemSpec:
    activity = Activity("base-case-01", "base-case", "v1", "base-case-trace-a",
                        ActivityType.TRACE, EvidenceKind.APPLICATION)
    return ItemSpec(activity, answer_key=AnswerKey(("2",)), hints=hints)


def choice_item() -> ItemSpec:
    activity = Activity("base-case-02", "base-case", "v1", "base-case-choice-a",
                        ActivityType.CHOICE, EvidenceKind.RECOGNITION)
    return ItemSpec(activity, choices=("A", "B", "C"), answer_key=AnswerKey(("B",)))


def explanation_item() -> ItemSpec:
    activity = Activity("base-case-03", "base-case", "v1", "base-case-explain-a",
                        ActivityType.EXPLANATION, EvidenceKind.EXPLANATION)
    rubric = Rubric("explain-base-case", (
        RubricCriterion("stopping", "Names the condition that stops the recursion."),
        RubricCriterion("return", "Says what the base case returns and why."),
    ))
    return ItemSpec(activity, rubric=rubric)


class ItemSpecTests(unittest.TestCase):
    def test_choice_and_trace_items_require_a_reviewed_key(self) -> None:
        activity = Activity("t", "c", "v1", "f", ActivityType.TRACE, EvidenceKind.RECALL)
        with self.assertRaisesRegex(ValueError, "answer key"):
            ItemSpec(activity)

    def test_ungraded_items_cannot_carry_an_answer_key(self) -> None:
        activity = Activity("e", "c", "v1", "f", ActivityType.EXPLANATION, EvidenceKind.EXPLANATION)
        with self.assertRaisesRegex(ValueError, "cannot have an answer key"):
            ItemSpec(activity, answer_key=AnswerKey(("x",)),
                     rubric=Rubric("r", (RubricCriterion("c", "d"),)))

    def test_ungraded_items_need_a_rubric(self) -> None:
        activity = Activity("e", "c", "v1", "f", ActivityType.CODE_DESIGN, EvidenceKind.TRANSFER,
                            held_out=True)
        with self.assertRaisesRegex(ValueError, "rubric"):
            ItemSpec(activity)

    def test_choice_key_must_name_exactly_one_listed_option(self) -> None:
        activity = Activity("c", "c", "v1", "f", ActivityType.CHOICE, EvidenceKind.RECOGNITION)
        with self.assertRaisesRegex(ValueError, "listed choice"):
            ItemSpec(activity, choices=("A", "B"), answer_key=AnswerKey(("Z",)))
        with self.assertRaisesRegex(ValueError, "exactly one"):
            ItemSpec(activity, choices=("A", "B"), answer_key=AnswerKey(("A", "B")))

    def test_only_choice_items_may_list_choices(self) -> None:
        with self.assertRaisesRegex(ValueError, "only choice"):
            ItemSpec(trace_item().activity, choices=("A", "B"), answer_key=AnswerKey(("2",)))

    def test_answer_keys_normalize_whitespace_and_reject_duplicates(self) -> None:
        self.assertEqual(AnswerKey(("  f(2) =   2 ",)).accepted, ("f(2) = 2",))
        with self.assertRaisesRegex(ValueError, "unique"):
            AnswerKey(("2", " 2 "))


class HintLadderTests(unittest.TestCase):
    def test_hints_open_one_rung_at_a_time(self) -> None:
        self.assertIs(LADDER.next_level(HintLevel.NONE), HintLevel.NUDGE)
        with self.assertRaisesRegex(AssessmentError, "one level at a time") as ctx:
            LADDER.reveal(HintLevel.NONE, HintLevel.WORKED_SOLUTION)
        self.assertEqual(ctx.exception.code, "hint_out_of_order")

        nudge = LADDER.reveal(HintLevel.NONE, HintLevel.NUDGE)
        self.assertEqual(nudge.text, "Find the stopping condition.")
        self.assertIs(LADDER.next_level(HintLevel.NUDGE), HintLevel.TARGETED)

    def test_ladder_reports_exhaustion(self) -> None:
        self.assertIsNone(LADDER.next_level(HintLevel.WORKED_SOLUTION))
        with self.assertRaises(AssessmentError) as ctx:
            LADDER.reveal(HintLevel.WORKED_SOLUTION, HintLevel.WORKED_SOLUTION)
        self.assertEqual(ctx.exception.code, "hint_exhausted")

    def test_ladder_may_skip_missing_rungs(self) -> None:
        ladder = HintLadder((Hint(HintLevel.TARGETED, "Trace it."),))
        self.assertIs(ladder.next_level(HintLevel.NONE), HintLevel.TARGETED)

    def test_ladder_rejects_disordered_or_repeated_rungs(self) -> None:
        with self.assertRaisesRegex(ValueError, "ladder order"):
            HintLadder((Hint(HintLevel.TARGETED, "a"), Hint(HintLevel.NUDGE, "b")))
        with self.assertRaisesRegex(ValueError, "once each"):
            HintLadder((Hint(HintLevel.NUDGE, "a"), Hint(HintLevel.NUDGE, "b")))

    def test_none_is_not_a_hint(self) -> None:
        with self.assertRaisesRegex(ValueError, "not a hint"):
            Hint(HintLevel.NONE, "text")


class TraceAndChoiceScoringTests(unittest.TestCase):
    def test_unassisted_correct_answer_is_credited(self) -> None:
        result = assess(trace_item(), "2")
        self.assertIs(result.score_status, ScoreStatus.CORRECT)
        self.assertEqual(result.grading_method, EXACT_KEY_METHOD)
        self.assertTrue(result.credited_unassisted)
        self.assertFalse(result.review_required)

    def test_whitespace_differences_do_not_change_the_score(self) -> None:
        self.assertIs(assess(trace_item(), "  2\n").score_status, ScoreStatus.CORRECT)

    def test_wrong_answer_is_incorrect_and_not_credited(self) -> None:
        result = assess(trace_item(), "3")
        self.assertIs(result.score_status, ScoreStatus.INCORRECT)
        self.assertFalse(result.credited_unassisted)

    def test_case_and_punctuation_still_matter_for_trace_answers(self) -> None:
        self.assertIs(assess(trace_item(), "2.").score_status, ScoreStatus.INCORRECT)

    def test_nudge_makes_a_correct_answer_assisted_not_unassisted(self) -> None:
        result = assess(trace_item(), "2", HintLevel.NUDGE)
        self.assertIs(result.score_status, ScoreStatus.CORRECT)
        self.assertTrue(result.assisted)
        self.assertFalse(result.credited_unassisted)
        self.assertIn("assisted", result.reason)

    def test_revealed_solution_never_yields_a_correct_status(self) -> None:
        result = assess(trace_item(), "2", HintLevel.WORKED_SOLUTION)
        self.assertIsNot(result.score_status, ScoreStatus.CORRECT)
        self.assertIs(result.score_status, ScoreStatus.UNGRADED)
        self.assertFalse(result.credited_unassisted)
        self.assertFalse(result.review_required)

    def test_wrong_answer_after_solution_reveal_is_still_incorrect(self) -> None:
        self.assertIs(assess(trace_item(), "7", HintLevel.WORKED_SOLUTION).score_status,
                      ScoreStatus.INCORRECT)

    def test_choice_answer_must_be_a_listed_option(self) -> None:
        with self.assertRaises(AssessmentError) as ctx:
            assess(choice_item(), "D")
        self.assertEqual(ctx.exception.code, "invalid_choice")

    def test_choice_scoring_is_exact_against_the_key(self) -> None:
        self.assertIs(assess(choice_item(), "B").score_status, ScoreStatus.CORRECT)
        self.assertIs(assess(choice_item(), "C").score_status, ScoreStatus.INCORRECT)

    def test_empty_answer_is_rejected_not_scored_as_wrong(self) -> None:
        with self.assertRaises(AssessmentError) as ctx:
            assess(trace_item(), "   ")
        self.assertEqual(ctx.exception.code, "answer_required")

    def test_invalid_hint_level_is_rejected(self) -> None:
        with self.assertRaises(AssessmentError):
            assess(trace_item(), "2", "nudge")  # type: ignore[arg-type]


class UngradedPathTests(unittest.TestCase):
    def test_explanation_is_never_scored_automatically(self) -> None:
        result = assess(explanation_item(), "The base case stops the recursion.")
        self.assertIs(result.score_status, ScoreStatus.UNGRADED)
        self.assertEqual(result.grading_method, PENDING_REVIEW_METHOD)
        self.assertTrue(result.review_required)
        self.assertFalse(result.credited_unassisted)
        self.assertIn("No automatic score", result.scope)

    def test_ungraded_result_exposes_the_rubric_for_review(self) -> None:
        result = assess(explanation_item(), "anything at all")
        self.assertIsNotNone(result.rubric)
        self.assertEqual([c.id for c in result.rubric.criteria], ["stopping", "return"])

    def test_ungraded_answer_is_not_judged_even_when_it_looks_plausible(self) -> None:
        # Passing a surface keyword is not evidence of understanding.
        result = assess(explanation_item(), "base case")
        self.assertIs(result.score_status, ScoreStatus.UNGRADED)

    def test_empty_explanation_is_still_rejected(self) -> None:
        with self.assertRaises(AssessmentError):
            assess(explanation_item(), "")


class AttemptRecordTests(unittest.TestCase):
    def test_attempt_records_first_answer_and_assistance_distinctly(self) -> None:
        spec = trace_item()
        result = assess(spec, "2", HintLevel.TARGETED)
        attempt = build_attempt(spec, result, attempt_id="t1", occurred_at=NOW,
                                first_answer="2", selection_reason="scheduled review")
        self.assertEqual(attempt.first_answer, "2")
        self.assertIs(attempt.hint_level, HintLevel.TARGETED)
        self.assertFalse(attempt.unassisted)
        self.assertEqual(attempt.method_id, "assessment-v1")
        self.assertEqual(attempt.content_version, "v1")

    def test_missing_confidence_and_outside_study_stay_none(self) -> None:
        spec = trace_item()
        attempt = build_attempt(spec, assess(spec, "2"), attempt_id="t2", occurred_at=NOW,
                                first_answer="2", selection_reason="scheduled review")
        self.assertIsNone(attempt.confidence)
        self.assertIsNone(attempt.outside_study)
        self.assertIsNone(attempt.active_seconds)

    def test_optional_context_is_recorded_when_supplied(self) -> None:
        spec = trace_item()
        attempt = build_attempt(spec, assess(spec, "2"), attempt_id="t3", occurred_at=NOW,
                                first_answer="2", selection_reason="comparison",
                                confidence=0.6, outside_study=OutsideStudy.SOME,
                                outside_study_detail="Read the chapter", active_seconds=40)
        self.assertEqual(attempt.confidence, 0.6)
        self.assertIs(attempt.outside_study, OutsideStudy.SOME)

    def test_ungraded_attempt_is_stored_as_ungraded(self) -> None:
        spec = explanation_item()
        attempt = build_attempt(spec, assess(spec, "my explanation"), attempt_id="t4",
                                occurred_at=NOW, first_answer="my explanation",
                                selection_reason="scheduled review")
        self.assertIs(attempt.score_status, ScoreStatus.UNGRADED)
        self.assertEqual(attempt.grading_method, PENDING_REVIEW_METHOD)

    def test_result_from_another_item_version_is_rejected(self) -> None:
        spec = trace_item()
        newer = Activity("base-case-01", "base-case", "v2", "base-case-trace-a",
                         ActivityType.TRACE, EvidenceKind.APPLICATION)
        other = ItemSpec(newer, answer_key=AnswerKey(("2",)))
        with self.assertRaises(AssessmentError) as ctx:
            build_attempt(other, assess(spec, "2"), attempt_id="t5", occurred_at=NOW,
                          first_answer="2", selection_reason="scheduled review")
        self.assertEqual(ctx.exception.code, "result_mismatch")

    def test_scoring_is_deterministic(self) -> None:
        spec = trace_item()
        self.assertEqual(assess(spec, "2", HintLevel.NUDGE), assess(spec, "2", HintLevel.NUDGE))

    def test_self_review_requires_complete_evidence_from_locked_answer(self) -> None:
        spec = explanation_item()
        attempt = build_attempt(spec, assess(spec, "n == 0 returns 1"), attempt_id="open-1",
                                occurred_at=NOW, first_answer="n == 0 returns 1",
                                selection_reason="practice")
        judgments = (
            CriterionReview("stopping", ReviewRating.SHOWN, "n == 0"),
            CriterionReview("return", ReviewRating.PARTIAL, "returns 1"),
        )
        review = build_self_review(spec, attempt, review_id="review-1", occurred_at=NOW,
                                   judgments=judgments, confidence=0.6)
        self.assertEqual(review.rubric_version, "v1")
        self.assertEqual(review.next_step, "targeted_retry")
        self.assertIs(attempt.score_status, ScoreStatus.UNGRADED)
        with self.assertRaisesRegex(ValueError, "first answer"):
            build_self_review(spec, attempt, review_id="bad", occurred_at=NOW,
                              judgments=(judgments[0], CriterionReview("return", ReviewRating.SHOWN,
                                                                        "invented evidence")))
        with self.assertRaisesRegex(ValueError, "every rubric"):
            build_self_review(spec, attempt, review_id="bad", occurred_at=NOW,
                              judgments=judgments[:1])


if __name__ == "__main__":
    unittest.main()
