"""Development data only. These keys have no human review receipts."""

from __future__ import annotations

from aesop_lab.assessment.items import AnswerKey, Hint, HintLadder, ItemSpec, Rubric, RubricCriterion
from aesop_lab.domain.models import (
    Activity, ActivityType, Concept, EvidenceKind, HintLevel,
)

from .service import CatalogItem


CONCEPT = Concept("dev-recursion", "Recursion development fixture", "dev-v1")


def fixture_items() -> tuple[CatalogItem, ...]:
    def trace(identifier: str, family: str, answer: str, prompt: str,
              *, held_out: bool = False) -> CatalogItem:
        activity = Activity(identifier, CONCEPT.id, CONCEPT.content_version, family,
                            ActivityType.TRACE, EvidenceKind.APPLICATION, held_out)
        spec = ItemSpec(activity, answer_key=AnswerKey((answer,)),
                        hints=HintLadder((Hint(HintLevel.NUDGE,
                                               "Trace from the smallest input first."),)))
        return CatalogItem(spec, prompt)

    return (
        trace("dev-trace-a", "dev-family-a", "1", "What does f(0) return?"),
        trace("dev-trace-b", "dev-family-b", "2", "What does f(2) return?"),
        trace("dev-trace-c", "dev-family-c", "6", "What does f(3) return?"),
        CatalogItem(ItemSpec(
            Activity("dev-z-explain", CONCEPT.id, CONCEPT.content_version,
                     "dev-family-explain", ActivityType.EXPLANATION, EvidenceKind.EXPLANATION),
            rubric=Rubric("dev-recursion-rubric", (
                RubricCriterion("base", "Identify the base case."),
                RubricCriterion("step", "Explain how each call moves toward it."),
            ), annotated_example="The base case stops at zero. Each call reduces n by one.",
                common_mistakes=("A recursive call without a stopping case never finishes.",)),
        ), "Explain why f(n) eventually stops when n is a nonnegative integer."),
        trace("dev-check-d", "dev-family-d", "24", "What does f(4) return?",
              held_out=True),
    )
