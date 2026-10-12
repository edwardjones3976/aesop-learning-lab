"""Deterministic scoring of a first answer, with assistance and review limits.

The engine never executes learner code and never infers understanding from a
score. It scores only what it can check against a reviewed key, and it returns
an explicit ungraded result for everything else.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from aesop_lab.domain.models import (
    ActivityType,
    Attempt,
    HintLevel,
    OutsideStudy,
    ScoreStatus,
)

from .errors import AssessmentError
from .items import ItemSpec, Rubric, normalize_answer

METHOD_ID = "assessment-v1"
EXACT_KEY_METHOD = "reviewed_exact_key"
PENDING_REVIEW_METHOD = "ungraded_pending_review"

_EXACT_KEY_SCOPE = (
    "Checks the first answer against the reviewed key only. "
    "It does not show explanation, transfer, or code design."
)
_REVIEW_SCOPE = (
    "No automatic score. Credit requires self or human review against the rubric. "
    "Passing or failing says nothing about conceptual understanding."
)


@dataclass(frozen=True, slots=True)
class AssessmentResult:
    activity_id: str
    content_version: str
    score_status: ScoreStatus
    grading_method: str
    method_id: str
    hint_level: HintLevel
    reason: str
    scope: str
    review_required: bool = False
    rubric: Rubric | None = None

    @property
    def assisted(self) -> bool:
        return self.hint_level is not HintLevel.NONE

    @property
    def credited_unassisted(self) -> bool:
        """True only for a correct, unassisted, auto-scored first answer."""
        return self.score_status is ScoreStatus.CORRECT and not self.assisted


def assess(
    spec: ItemSpec,
    first_answer: str,
    hint_level: HintLevel = HintLevel.NONE,
) -> AssessmentResult:
    """Score the first answer. `hint_level` is the highest hint viewed on this activity."""
    if not isinstance(hint_level, HintLevel):
        raise AssessmentError("invalid_hint_level", "Unknown hint level.")
    answer = normalize_answer(first_answer)
    kind = spec.activity.activity_type

    if not answer:
        raise AssessmentError("answer_required", "Enter an answer before checking it.")

    if kind in (ActivityType.EXPLANATION, ActivityType.CODE_DESIGN):
        return AssessmentResult(
            activity_id=spec.activity.id,
            content_version=spec.activity.content_version,
            score_status=ScoreStatus.UNGRADED,
            grading_method=PENDING_REVIEW_METHOD,
            method_id=METHOD_ID,
            hint_level=hint_level,
            reason="Recorded for self or human review against the rubric. Not scored.",
            scope=_REVIEW_SCOPE,
            review_required=True,
            rubric=spec.rubric,
        )

    if kind is ActivityType.CHOICE and answer not in spec.choices:
        raise AssessmentError("invalid_choice", "Choose one of the listed options.")

    correct = answer in spec.answer_key.accepted
    if correct and hint_level is HintLevel.WORKED_SOLUTION:
        # The domain forbids a correct score after a revealed solution. Record the
        # attempt as not credited rather than claiming either a win or a miss.
        status = ScoreStatus.UNGRADED
        reason = "A worked solution was viewed, so this answer is not credited as correct."
    elif correct:
        status = ScoreStatus.CORRECT
        reason = (
            "Matches the reviewed key."
            if hint_level is HintLevel.NONE
            else "Matches the reviewed key. Hints were viewed, so this is an assisted success."
        )
    else:
        status = ScoreStatus.INCORRECT
        reason = "Does not match the reviewed key."

    return AssessmentResult(
        activity_id=spec.activity.id,
        content_version=spec.activity.content_version,
        score_status=status,
        grading_method=EXACT_KEY_METHOD,
        method_id=METHOD_ID,
        hint_level=hint_level,
        reason=reason,
        scope=_EXACT_KEY_SCOPE,
    )


def build_attempt(
    spec: ItemSpec,
    result: AssessmentResult,
    *,
    attempt_id: str,
    occurred_at: datetime,
    first_answer: str,
    selection_reason: str,
    confidence: float | None = None,
    outside_study: OutsideStudy | None = None,
    outside_study_detail: str | None = None,
    active_seconds: int | None = None,
) -> Attempt:
    """Turn a result into an immutable attempt record. Missing optional fields stay None."""
    if result.activity_id != spec.activity.id or result.content_version != spec.activity.content_version:
        raise AssessmentError("result_mismatch", "The result does not belong to this activity version.")
    return Attempt(
        id=attempt_id,
        activity_id=spec.activity.id,
        content_version=spec.activity.content_version,
        occurred_at=occurred_at,
        first_answer=first_answer,
        hint_level=result.hint_level,
        score_status=result.score_status,
        grading_method=result.grading_method,
        method_id=result.method_id,
        selection_reason=selection_reason,
        confidence=confidence,
        outside_study=outside_study,
        outside_study_detail=outside_study_detail,
        active_seconds=active_seconds,
    )
