"""Assessable item specifications: reviewed answer keys, hint ladders, and rubrics.

Content owns the text of an item. These records hold only what scoring needs,
and they refuse shapes that would let an ungraded item look graded.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aesop_lab.domain.models import Activity, ActivityType, HintLevel

from .errors import AssessmentError

LADDER_ORDER: tuple[HintLevel, ...] = (
    HintLevel.NONE,
    HintLevel.NUDGE,
    HintLevel.TARGETED,
    HintLevel.WORKED_SOLUTION,
)


def normalize_answer(text: str) -> str:
    """Collapse runs of whitespace and trim. Case and punctuation still matter."""
    return " ".join(text.split())


@dataclass(frozen=True, slots=True)
class AnswerKey:
    """Accepted answers for a choice or trace item, already normalized."""

    accepted: tuple[str, ...]

    def __post_init__(self) -> None:
        cleaned = tuple(normalize_answer(answer) for answer in self.accepted)
        if not cleaned or not all(cleaned):
            raise ValueError("an answer key needs at least one non-empty accepted answer")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("accepted answers must be unique")
        object.__setattr__(self, "accepted", cleaned)


@dataclass(frozen=True, slots=True)
class Hint:
    level: HintLevel
    text: str

    def __post_init__(self) -> None:
        if self.level is HintLevel.NONE:
            raise ValueError("the none level is not a hint")
        if not self.text.strip():
            raise ValueError("hint text is required")


@dataclass(frozen=True, slots=True)
class HintLadder:
    """Rungs in ladder order. The learner opens one rung at a time, never skipping."""

    hints: tuple[Hint, ...] = ()

    def __post_init__(self) -> None:
        positions = [LADDER_ORDER.index(hint.level) for hint in self.hints]
        if positions != sorted(set(positions)):
            raise ValueError("hints must appear once each, in ladder order")

    @property
    def levels(self) -> tuple[HintLevel, ...]:
        return tuple(hint.level for hint in self.hints)

    def next_level(self, viewed: HintLevel) -> HintLevel | None:
        """The rung the learner may open next after viewing `viewed`, or None if exhausted."""
        viewed_position = LADDER_ORDER.index(viewed)
        for hint in self.hints:
            if LADDER_ORDER.index(hint.level) > viewed_position:
                return hint.level
        return None

    def reveal(self, viewed: HintLevel, requested: HintLevel) -> Hint:
        expected = self.next_level(viewed)
        if expected is None:
            raise AssessmentError("hint_exhausted", "There are no more hints for this activity.")
        if requested is not expected:
            raise AssessmentError(
                "hint_out_of_order",
                f"The next hint is '{expected.value}'. Hints open one level at a time.",
            )
        return next(hint for hint in self.hints if hint.level is requested)


@dataclass(frozen=True, slots=True)
class RubricCriterion:
    id: str
    description: str
    shown_description: str = "Clearly demonstrates this criterion."
    partial_description: str = "Addresses this criterion but leaves an important gap."

    def __post_init__(self) -> None:
        if not self.id or not all((self.description.strip(), self.shown_description.strip(),
                                   self.partial_description.strip())):
            raise ValueError("rubric criteria need an id and a description")


@dataclass(frozen=True, slots=True)
class Rubric:
    """Review criteria for ungraded explanation and code-design answers."""

    id: str
    criteria: tuple[RubricCriterion, ...]
    version: str = "v1"
    annotated_example: str = ""
    common_mistakes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id or not self.version or not self.criteria:
            raise ValueError("a rubric needs an id and at least one criterion")
        ids = [criterion.id for criterion in self.criteria]
        if len(set(ids)) != len(ids):
            raise ValueError("rubric criterion ids must be unique")


@dataclass(frozen=True, slots=True)
class ItemSpec:
    """One assessable activity with the scoring material it needs.

    Choice and trace items are scored against a reviewed key. Explanation and
    code-design items carry a rubric and are never scored automatically.
    """

    activity: Activity
    choices: tuple[str, ...] = ()
    answer_key: AnswerKey | None = None
    rubric: Rubric | None = None
    hints: HintLadder = field(default_factory=HintLadder)

    def __post_init__(self) -> None:
        kind = self.activity.activity_type
        if kind in (ActivityType.CHOICE, ActivityType.TRACE):
            if self.answer_key is None:
                raise ValueError("choice and trace items need a reviewed answer key")
            if self.rubric is not None:
                raise ValueError("auto-scored items do not take a rubric")
        else:
            if self.answer_key is not None:
                raise ValueError("explanation and code design items cannot have an answer key")
            if self.rubric is None:
                raise ValueError("ungraded items need a review rubric")

        if kind is ActivityType.CHOICE:
            if len(self.choices) < 2 or len(set(self.choices)) != len(self.choices):
                raise ValueError("choice items need at least two distinct choices")
            if len(self.answer_key.accepted) != 1 or self.answer_key.accepted[0] not in self.choices:
                raise ValueError("a choice item needs exactly one correct listed choice")
        elif self.choices:
            raise ValueError("only choice items may list choices")
