"""Versioned content records: lessons, items, sources, and review receipts.

Content holds text and candidate answer keys. It never grades anything; the
assessment module turns reviewed keys into scoring behavior.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from aesop_lab.domain.models import Activity, ActivityType, Concept, EvidenceKind, HintLevel

CONTENT_SCHEMA_VERSION = "content-pack/1"
PACK_STATUSES = ("draft", "in_review", "reviewed")
KEY_STATUSES = ("candidate", "reviewed")
RECEIPT_OUTCOMES = ("approved", "changes_requested")
PYTHON_DOCS_PREFIX = "https://docs.python.org/3.12/"
REQUIRED_HINT_LEVELS = (HintLevel.NUDGE, HintLevel.TARGETED, HintLevel.WORKED_SOLUTION)
MIN_FAMILIES_PER_CONCEPT = 2
SCORED_TYPES = (ActivityType.CHOICE, ActivityType.TRACE)
UNGRADED_TYPES = (ActivityType.EXPLANATION, ActivityType.CODE_DESIGN)
HELD_OUT_EVIDENCE = (EvidenceKind.APPLICATION, EvidenceKind.TRANSFER)


@dataclass(frozen=True, slots=True)
class Source:
    """An authoritative reference. Every lesson and item cites at least one."""

    id: str
    title: str
    url: str


@dataclass(frozen=True, slots=True)
class Lesson:
    id: str
    concept_id: str
    content_version: str
    title: str
    body: str
    source_ids: tuple[str, ...]
    diagram: str | None = None
    encountered_family_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnswerKeyCandidate:
    """Accepted answers for a scored item. `status` is `candidate` until a reviewer approves it."""

    accepted: tuple[str, ...]
    status: str


@dataclass(frozen=True, slots=True)
class CriterionSpec:
    id: str
    description: str


@dataclass(frozen=True, slots=True)
class RubricSpec:
    """Review criteria shown beside an ungraded explanation or code-design item."""

    id: str
    criteria: tuple[CriterionSpec, ...]
    annotated_example: str
    common_mistakes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HintSpec:
    level: HintLevel
    text: str


@dataclass(frozen=True, slots=True)
class ItemContent:
    """One activity's text plus the material scoring needs. The activity is a domain record."""

    activity: Activity
    prompt: str
    body: str
    choices: tuple[str, ...]
    answer_key: AnswerKeyCandidate | None
    check_expression: str | None
    rubric: RubricSpec | None
    hints: tuple[HintSpec, ...]
    source_ids: tuple[str, ...]
    learning_objective: str | None = None
    difficulty: str | None = None
    explanation: str | None = None
    common_mistakes: tuple[str, ...] = ()

    @property
    def id(self) -> str:
        return self.activity.id


@dataclass(frozen=True, slots=True)
class ReviewReceipt:
    """A recorded independent review. Only a reviewer's actual decision belongs here."""

    reviewer: str
    reviewed_on: date
    outcome: str
    scope_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ContentPack:
    schema_version: str
    pack_id: str
    pack_version: str
    topic: str
    status: str
    author: str
    concepts: tuple[Concept, ...]
    lessons: tuple[Lesson, ...]
    items: tuple[ItemContent, ...]
    sources: tuple[Source, ...]
    receipts: tuple[ReviewReceipt, ...]

    def concept(self, concept_id: str) -> Concept:
        for concept in self.concepts:
            if concept.id == concept_id:
                return concept
        raise KeyError(concept_id)

    def items_for(self, concept_id: str) -> tuple[ItemContent, ...]:
        return tuple(item for item in self.items if item.activity.concept_id == concept_id)

    def prerequisites_of(self, concept_id: str) -> frozenset[str]:
        """Every concept that must come first, direct or indirect."""
        direct = {concept.id: concept.prerequisite_ids for concept in self.concepts}
        found: set[str] = set()
        pending = list(direct[concept_id])
        while pending:
            prerequisite = pending.pop()
            if prerequisite not in found:
                found.add(prerequisite)
                pending.extend(direct[prerequisite])
        return frozenset(found)

    def learning_order(self) -> tuple[str, ...]:
        return topological_order({concept.id: concept.prerequisite_ids for concept in self.concepts})


def topological_order(prerequisites: Mapping[str, Sequence[str]]) -> tuple[str, ...]:
    """Order concepts so every prerequisite comes first. Raises ValueError on a cycle.

    Unknown prerequisite IDs are reported by the validator before this runs.
    """
    remaining = {node: set(parents) for node, parents in prerequisites.items()}
    order: list[str] = []
    while remaining:
        ready = [node for node in prerequisites if node in remaining and not remaining[node]]
        if not ready:
            raise ValueError("prerequisite cycle among: " + ", ".join(sorted(remaining)))
        for node in ready:
            order.append(node)
            del remaining[node]
        for parents in remaining.values():
            parents.difference_update(ready)
    return tuple(order)
