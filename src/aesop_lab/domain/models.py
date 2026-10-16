"""Versioned records shared by all Learning Lab modules.

The records deliberately separate observed attempts from interpretation.
Modules may derive learner state, but they must not overwrite the original event.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ActivityType(StrEnum):
    CHOICE = "choice"
    TRACE = "trace"
    EXPLANATION = "explanation"
    CODE_DESIGN = "code_design"


class EvidenceKind(StrEnum):
    RECOGNITION = "recognition"
    RECALL = "recall"
    EXPLANATION = "explanation"
    APPLICATION = "application"
    TRANSFER = "transfer"


class HintLevel(StrEnum):
    NONE = "none"
    NUDGE = "nudge"
    TARGETED = "targeted"
    WORKED_SOLUTION = "worked_solution"


class ScoreStatus(StrEnum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNGRADED = "ungraded"


class OutsideStudy(StrEnum):
    NONE = "none"
    SOME = "some"
    UNKNOWN = "unknown"


class ReviewRating(StrEnum):
    SHOWN = "shown"
    PARTIAL = "partial"
    NOT_SHOWN = "not_shown"
    UNSURE = "unsure"


@dataclass(frozen=True, slots=True)
class Concept:
    id: str
    title: str
    content_version: str
    prerequisite_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id or not self.title or not self.content_version:
            raise ValueError("concept id, title, and content version are required")
        if self.id in self.prerequisite_ids:
            raise ValueError("a concept cannot be its own prerequisite")


@dataclass(frozen=True, slots=True)
class Activity:
    id: str
    concept_id: str
    content_version: str
    family_id: str
    activity_type: ActivityType
    evidence_kind: EvidenceKind
    held_out: bool = False
    check_delay_days: int | None = None

    def __post_init__(self) -> None:
        if not all((self.id, self.concept_id, self.content_version, self.family_id)):
            raise ValueError("activity identity and version fields are required")
        if self.evidence_kind is EvidenceKind.TRANSFER and not self.held_out:
            raise ValueError("transfer items must be held out")
        if self.check_delay_days is None:
            object.__setattr__(self, "check_delay_days", 1 if self.held_out else 0)
        if type(self.check_delay_days) is not int or self.check_delay_days < 0:
            raise ValueError("check delay must be a nonnegative number of days")
        if self.held_out != (self.check_delay_days > 0):
            raise ValueError("held-out items need a positive check delay; practice needs zero")


@dataclass(frozen=True, slots=True)
class Attempt:
    id: str
    activity_id: str
    content_version: str
    occurred_at: datetime
    first_answer: str
    hint_level: HintLevel
    score_status: ScoreStatus
    grading_method: str
    method_id: str
    selection_reason: str
    confidence: float | None = None
    outside_study: OutsideStudy | None = None
    outside_study_detail: str | None = None
    active_seconds: int | None = None

    def __post_init__(self) -> None:
        if not all((self.id, self.activity_id, self.content_version, self.grading_method,
                    self.method_id, self.selection_reason)):
            raise ValueError("attempt identity, method, and selection reason are required")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("attempt time must include a timezone")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between zero and one")
        if self.active_seconds is not None and self.active_seconds < 0:
            raise ValueError("active seconds cannot be negative")
        if self.hint_level is HintLevel.WORKED_SOLUTION and self.score_status is ScoreStatus.CORRECT:
            raise ValueError("a revealed solution cannot count as a correct attempt")

    @property
    def unassisted(self) -> bool:
        return self.hint_level is HintLevel.NONE


@dataclass(frozen=True, slots=True)
class CriterionReview:
    criterion_id: str
    rating: ReviewRating
    evidence: str = ""

    def __post_init__(self) -> None:
        if not self.criterion_id:
            raise ValueError("criterion id is required")
        if not isinstance(self.rating, ReviewRating):
            raise ValueError("review rating is not recognized")
        if self.rating in (ReviewRating.SHOWN, ReviewRating.PARTIAL) and not self.evidence.strip():
            raise ValueError("shown or partial ratings need evidence from the first answer")
        if self.rating in (ReviewRating.NOT_SHOWN, ReviewRating.UNSURE) and self.evidence.strip():
            raise ValueError("not shown or unsure ratings cannot claim evidence")


@dataclass(frozen=True, slots=True)
class SelfReview:
    id: str
    attempt_id: str
    rubric_id: str
    rubric_version: str
    occurred_at: datetime
    judgments: tuple[CriterionReview, ...]
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not all((self.id, self.attempt_id, self.rubric_id, self.rubric_version)):
            raise ValueError("review identity and rubric version are required")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("review time must include a timezone")
        if not self.judgments or len({item.criterion_id for item in self.judgments}) != len(self.judgments):
            raise ValueError("review needs one judgment per distinct criterion")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("review confidence must be between zero and one")

    @property
    def next_step(self) -> str:
        return ("independent_check" if all(item.rating is ReviewRating.SHOWN
                                           for item in self.judgments) else "targeted_retry")


@dataclass(frozen=True, slots=True)
class AnswerRevision:
    id: str
    review_id: str
    occurred_at: datetime
    answer: str

    def __post_init__(self) -> None:
        if not self.id or not self.review_id or not self.answer.strip():
            raise ValueError("revision identity and answer are required")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("revision time must include a timezone")


@dataclass(frozen=True, slots=True)
class Recommendation:
    activity_id: str
    policy_version: str
    reason: str
    evidence_attempt_ids: tuple[str, ...]
    due_at: datetime | None = None

    def __post_init__(self) -> None:
        if not all((self.activity_id, self.policy_version, self.reason)):
            raise ValueError("recommendation activity, policy, and reason are required")
        if self.due_at is not None and (self.due_at.tzinfo is None or self.due_at.utcoffset() is None):
            raise ValueError("due time must include a timezone")


@dataclass(frozen=True, slots=True)
class ExperimentAssignment:
    protocol_id: str
    protocol_version: str
    concept_id: str
    item_family_id: str
    condition_id: str
    seed: int
    assigned_at: datetime

    def __post_init__(self) -> None:
        if not all((self.protocol_id, self.protocol_version, self.concept_id,
                    self.item_family_id, self.condition_id)):
            raise ValueError("experiment identity and condition are required")
        if self.assigned_at.tzinfo is None or self.assigned_at.utcoffset() is None:
            raise ValueError("assignment time must include a timezone")
