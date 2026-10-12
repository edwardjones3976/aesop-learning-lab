"""Validate a learner's rubric comparison without turning it into a score."""

from __future__ import annotations

from datetime import datetime

from aesop_lab.domain.models import (
    ActivityType, Attempt, CriterionReview, ScoreStatus, SelfReview,
)

from .items import ItemSpec


def build_self_review(
    spec: ItemSpec,
    attempt: Attempt,
    *,
    review_id: str,
    occurred_at: datetime,
    judgments: tuple[CriterionReview, ...],
    confidence: float | None = None,
) -> SelfReview:
    """Require complete, answer-grounded judgments for the exact attempted item."""
    if spec.activity.activity_type not in (ActivityType.EXPLANATION, ActivityType.CODE_DESIGN):
        raise ValueError("only open-ended attempts can receive a self review")
    if (attempt.activity_id, attempt.content_version) != (spec.activity.id, spec.activity.content_version):
        raise ValueError("review item does not match the attempt")
    if attempt.score_status is not ScoreStatus.UNGRADED:
        raise ValueError("self review requires an ungraded attempt")
    if occurred_at < attempt.occurred_at:
        raise ValueError("review cannot precede the attempt")
    assert spec.rubric is not None
    if {item.criterion_id for item in judgments} != {item.id for item in spec.rubric.criteria}:
        raise ValueError("review must address every rubric criterion")
    for item in judgments:
        if item.evidence and item.evidence.strip() not in attempt.first_answer:
            raise ValueError("review evidence must quote the first answer")
    return SelfReview(review_id, attempt.id, spec.rubric.id, spec.rubric.version,
                      occurred_at, judgments, confidence)
