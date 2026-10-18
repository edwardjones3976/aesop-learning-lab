"""Prospective v6 descriptive protocol; v1/v2 histories remain pinned.

The v6 held-out recursive-case family differs from earlier instructional and
review families. V3 enrolls only new learners, before their first v6 lesson.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

from aesop_lab.domain.models import Activity, Attempt, ExperimentAssignment

from .descriptive_v2 import (
    DescriptiveProtocolV2, _analyze, _assign_condition, _aware,
)


DESCRIPTIVE_V3 = DescriptiveProtocolV2(
    id="text-vs-labeled-diagram",
    version="v3",
    seed=20261019,
    content_version="v6",
    primary_family_by_concept=(
        ("function-definition-and-return", "def-return-shipping-week-v4"),
        ("parameters-and-local-scope", "scope-caller-local-default-week-v5"),
        ("recursion-as-self-call", "recursion-nested-wrap-week-v5"),
        ("base-case", "base-case-threshold-halving-week-v4"),
        ("recursive-case-and-trace", "recursive-case-lamp-toggle-week-v6"),
    ),
    primary_delay_days=7,
    primary_window_days=14,
    target_exposure_minutes=10,
    minimum_independent_learners_per_arm=20,
)


@dataclass(frozen=True, slots=True)
class ExposureV3:
    concept_id: str
    content_version: str
    condition_id: str
    exposed_at: datetime
    encountered_family_ids: tuple[str, ...]
    protocol_id: str = DESCRIPTIVE_V3.id
    protocol_version: str = DESCRIPTIVE_V3.version
    completed_at: datetime | None = None
    observed_seconds: int | None = None

    def __post_init__(self) -> None:
        if self.concept_id not in DESCRIPTIVE_V3.primary_families:
            raise ValueError("exposure concept is outside v3")
        if self.content_version != DESCRIPTIVE_V3.content_version:
            raise ValueError("exposure content version differs from v3")
        if self.condition_id not in ("text", "diagram"):
            raise ValueError("exposure condition is unknown")
        if (self.protocol_id, self.protocol_version) != (DESCRIPTIVE_V3.id,
                                                        DESCRIPTIVE_V3.version):
            raise ValueError("exposure protocol identity differs from v3")
        if not _aware(self.exposed_at) or (self.completed_at is not None and
                                           not _aware(self.completed_at)):
            raise ValueError("exposure timestamps require timezones")
        if self.completed_at is not None and self.completed_at < self.exposed_at:
            raise ValueError("exposure completion precedes start")
        if self.observed_seconds is not None and (type(self.observed_seconds) is not int or
                                                  self.observed_seconds < 0):
            raise ValueError("observed seconds must be nonnegative or missing")
        if (len(set(self.encountered_family_ids)) != len(self.encountered_family_ids) or
                any(not family for family in self.encountered_family_ids)):
            raise ValueError("exposure family IDs must be unique and nonempty")


def assign_condition_v3(
    concept_id: str, learner_id: str, *, seed: int = DESCRIPTIVE_V3.seed,
) -> str:
    """Seeded condition for a new v6 learner, persisted at first assignment."""

    return _assign_condition(DESCRIPTIVE_V3, concept_id, learner_id, seed)


def analyze_v3(
    assignments: Sequence[ExperimentAssignment],
    exposures: Sequence[ExposureV3],
    attempts: Sequence[Attempt],
    activities: Mapping[str, Activity],
    *,
    learner_id: str,
    now: datetime,
    content_review_status: str = "draft",
) -> dict:
    """Report v6 observations without merging earlier protocol histories."""

    return _analyze(
        assignments, exposures, attempts, activities, learner_id=learner_id,
        now=now, content_review_status=content_review_status,
        protocol=DESCRIPTIVE_V3, exposure_type=ExposureV3,
    )
