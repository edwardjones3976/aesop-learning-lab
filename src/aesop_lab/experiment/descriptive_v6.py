"""Prospective v9 descriptive protocol; historical assignments remain pinned."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

from aesop_lab.domain.models import Activity, Attempt, ExperimentAssignment

from .descriptive_v2 import DescriptiveProtocolV2, _analyze, _assign_condition, _aware
from .descriptive_v5 import DESCRIPTIVE_V5


DESCRIPTIVE_V6 = DescriptiveProtocolV2(
    id="text-vs-labeled-diagram",
    version="v6",
    seed=20261022,
    content_version="v9",
    primary_family_by_concept=DESCRIPTIVE_V5.primary_family_by_concept,
    primary_delay_days=DESCRIPTIVE_V5.primary_delay_days,
    primary_window_days=DESCRIPTIVE_V5.primary_window_days,
    target_exposure_minutes=DESCRIPTIVE_V5.target_exposure_minutes,
    minimum_independent_learners_per_arm=DESCRIPTIVE_V5.minimum_independent_learners_per_arm,
)


@dataclass(frozen=True, slots=True)
class ExposureV6:
    concept_id: str
    content_version: str
    condition_id: str
    exposed_at: datetime
    encountered_family_ids: tuple[str, ...]
    protocol_id: str = DESCRIPTIVE_V6.id
    protocol_version: str = DESCRIPTIVE_V6.version
    completed_at: datetime | None = None
    observed_seconds: int | None = None

    def __post_init__(self) -> None:
        if self.concept_id not in DESCRIPTIVE_V6.primary_families:
            raise ValueError("exposure concept is outside v6")
        if self.content_version != DESCRIPTIVE_V6.content_version:
            raise ValueError("exposure content version differs from v6")
        if self.condition_id not in ("text", "diagram"):
            raise ValueError("exposure condition is unknown")
        if (self.protocol_id, self.protocol_version) != (DESCRIPTIVE_V6.id,
                                                        DESCRIPTIVE_V6.version):
            raise ValueError("exposure protocol identity differs from v6")
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


def assign_condition_v6(
    concept_id: str, learner_id: str, *, seed: int = DESCRIPTIVE_V6.seed,
) -> str:
    return _assign_condition(DESCRIPTIVE_V6, concept_id, learner_id, seed)


def analyze_v6(
    assignments: Sequence[ExperimentAssignment],
    exposures: Sequence[ExposureV6],
    attempts: Sequence[Attempt],
    activities: Mapping[str, Activity],
    *,
    learner_id: str,
    now: datetime,
    content_review_status: str = "draft",
) -> dict:
    return _analyze(
        assignments, exposures, attempts, activities, learner_id=learner_id,
        now=now, content_review_status=content_review_status,
        protocol=DESCRIPTIVE_V6, exposure_type=ExposureV6,
    )
