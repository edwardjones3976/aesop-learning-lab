"""Immutable pilot rules and pure analysis over recorded learning events.

The unit of assignment is a concept for one learner. A local database contains
one learner, so its stored :class:`ExperimentAssignment` uses the concept ID as
``item_family_id`` (an assignment key), independently of exercise family IDs.
The same explanation and retrieval activities must be used in both conditions;
only a labeled diagram is added to the diagram condition.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from math import sqrt
from typing import Mapping, Sequence

from aesop_lab.domain.models import (
    Activity, Attempt, EvidenceKind, ExperimentAssignment, HintLevel, ScoreStatus,
)


@dataclass(frozen=True, slots=True)
class Protocol:
    id: str
    version: str
    seed: int
    content_version: str
    primary_family_by_concept: tuple[tuple[str, str], ...]
    primary_delay_days: int
    primary_window_days: int
    minimum_per_arm: int
    exposure_duration_controlled: bool
    exposure_rule: str
    missing_data_rule: str
    analysis_rule: str

    @property
    def primary_families(self) -> dict[str, str]:
        return dict(self.primary_family_by_concept)

    def public(self) -> dict:
        return {
            "id": self.id,
            "version": self.version,
            "seed": self.seed,
            "assignmentMethod": (
                "For each persisted local learner ID, rank the five concept IDs "
                "by SHA-256 of protocol ID, version, seed, learner ID, and concept ID; "
                "alternate text and diagram in that order, with the starting arm "
                "set by another learner-specific SHA-256 bit. Persist the first "
                "assignment; never reassign an enrolled concept."
            ),
            "contentVersion": self.content_version,
            "conditions": {
                "text": "Text explanation followed by retrieval practice",
                "diagram": "The same text and retrieval practice, plus a labeled diagram",
            },
            "primaryOutcome": (
                "First independent, deterministically graded response to a held-out "
                "unfamiliar application or transfer family about seven days after exposure"
            ),
            "primaryFamilyByConcept": dict(self.primary_family_by_concept),
            "primaryDelayDays": self.primary_delay_days,
            "primaryWindowDays": self.primary_window_days,
            "minimumPerArm": self.minimum_per_arm,
            "exposureDurationControlled": self.exposure_duration_controlled,
            "exposureRule": self.exposure_rule,
            "missingDataRule": self.missing_data_rule,
            "analysisRule": self.analysis_rule,
            "requiresIndependentContentReview": True,
        }


PROTOCOL = Protocol(
    id="text-vs-labeled-diagram",
    version="v1",
    seed=20261015,
    content_version="v4",
    primary_family_by_concept=(
        ("function-definition-and-return", "def-return-shipping-week-v4"),
        ("parameters-and-local-scope", "scope-combined-default-local-week-v4"),
        ("recursion-as-self-call", "recursion-return-order-week-v4"),
        ("base-case", "base-case-threshold-halving-week-v4"),
        ("recursive-case-and-trace", "recursive-case-week-a"),
    ),
    primary_delay_days=7,
    primary_window_days=14,
    minimum_per_arm=20,
    exposure_duration_controlled=False,
    exposure_rule=(
        "Count a concept only after its versioned lesson was marked complete; "
        "record all item families seen in instruction, examples, or practice. "
        "Instructional time is self-paced and not equivalently controlled in v1."
    ),
    missing_data_rule=(
        "Missing, late, assisted, ungraded, or previously seen primary checks are "
        "excluded and counted as missing, never as incorrect. Outside study and "
        "confidence may be unknown; they never create a correct outcome."
    ),
    analysis_rule=(
        "Describe independent primary outcomes by arm with Wilson 95% intervals. "
        "Do not name a winning method. Draft content, uncontrolled exposure "
        "duration, or fewer than 20 eligible outcomes per arm returns "
        "insufficient_evidence. A controlled-exposure comparison requires "
        "a new protocol version."
    ),
)


def _aware(instant: datetime) -> bool:
    return instant.tzinfo is not None and instant.utcoffset() is not None


@dataclass(frozen=True, slots=True)
class Exposure:
    """Versioned lesson exposure for one concept in a local learner database."""

    concept_id: str
    content_version: str
    condition_id: str
    exposed_at: datetime
    encountered_family_ids: tuple[str, ...]
    protocol_id: str = PROTOCOL.id
    protocol_version: str = PROTOCOL.version
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.concept_id not in PROTOCOL.primary_families:
            raise ValueError("exposure concept is outside the fixed protocol")
        if self.content_version != PROTOCOL.content_version:
            raise ValueError("exposure content version differs from protocol")
        if self.condition_id not in ("text", "diagram"):
            raise ValueError("exposure condition is unknown")
        if (self.protocol_id, self.protocol_version) != (PROTOCOL.id, PROTOCOL.version):
            raise ValueError("exposure protocol version differs from fixed protocol")
        if not _aware(self.exposed_at) or (self.completed_at and not _aware(self.completed_at)):
            raise ValueError("exposure times need timezones")
        if self.completed_at is not None and self.completed_at < self.exposed_at:
            raise ValueError("exposure completion precedes start")
        if len(set(self.encountered_family_ids)) != len(self.encountered_family_ids):
            raise ValueError("exposure family IDs must be unique")


def assign_condition(concept_id: str, learner_id: str, *, seed: int = PROTOCOL.seed) -> str:
    """Choose a stable arm without process-global RNG state or Python hash salt.

    The caller persists the first returned assignment and reuses it thereafter.
    The learner ID must be a locally persisted random identifier. It ensures
    that the same concept is not permanently tied to one arm across learners.
    The first result is saved using the concept ID as the assignment key.
    """

    if concept_id not in PROTOCOL.primary_families or not learner_id:
        raise ValueError("a fixed-protocol concept and learner ID are required")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    def rank(cid: str) -> bytes:
        payload = f"{PROTOCOL.id}\0{PROTOCOL.version}\0{seed}\0{learner_id}\0{cid}"
        return sha256(payload.encode("utf-8")).digest()
    ordered = sorted(PROTOCOL.primary_families, key=lambda cid: (rank(cid), cid))
    start_payload = f"{PROTOCOL.id}\0{PROTOCOL.version}\0{seed}\0{learner_id}\0starting-arm"
    starting_bit = sha256(start_payload.encode("utf-8")).digest()[0] & 1
    return "diagram" if (ordered.index(concept_id) + starting_bit) % 2 else "text"


def qualifies_primary_outcome(
    attempt: Attempt,
    activity: Activity,
    exposure: Exposure,
    prior_family_ids: frozenset[str] | set[str] | tuple[str, ...],
    *,
    now: datetime,
) -> bool:
    """Check the protocol's delayed, unfamiliar, independent outcome rules."""

    if not _aware(now):
        raise ValueError("now needs a timezone")
    if exposure.completed_at is None or now < attempt.occurred_at:
        return False
    if (activity.concept_id != exposure.concept_id or
            activity.content_version != exposure.content_version or
            attempt.activity_id != activity.id or
            attempt.content_version != activity.content_version):
        return False
    if (activity.family_id != PROTOCOL.primary_families[exposure.concept_id] or
            not activity.held_out or activity.check_delay_days != PROTOCOL.primary_delay_days or
            activity.evidence_kind not in (EvidenceKind.APPLICATION, EvidenceKind.TRANSFER)):
        return False
    if (activity.family_id in exposure.encountered_family_ids or
            activity.family_id in prior_family_ids):
        return False
    if (attempt.hint_level is not HintLevel.NONE or
            attempt.score_status not in (ScoreStatus.CORRECT, ScoreStatus.INCORRECT) or
            attempt.grading_method != "reviewed_exact_key"):
        return False
    elapsed = attempt.occurred_at - exposure.completed_at
    return (timedelta(days=PROTOCOL.primary_delay_days) <= elapsed <=
            timedelta(days=PROTOCOL.primary_window_days))


def _wilson(correct: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    z = 1.959963984540054
    p = correct / total
    z2 = z * z
    denominator = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denominator
    half = z * sqrt(p * (1 - p) / total + z2 / (4 * total * total)) / denominator
    return [round(max(0, center - half), 4), round(min(1, center + half), 4)]


def analyze(
    assignments: Sequence[ExperimentAssignment],
    exposures: Sequence[Exposure],
    attempts: Sequence[Attempt],
    activities: Mapping[str, Activity],
    *,
    now: datetime,
    content_review_status: str = "draft",
) -> dict:
    """Report descriptive arm outcomes without treating absences as failures.

    This local analysis has at most one learner's observations. It is useful for
    checking the protocol and displaying honest coverage, not for causal claims.
    """

    if not _aware(now):
        raise ValueError("now needs a timezone")
    if content_review_status not in ("draft", "reviewed"):
        raise ValueError("content review status must be draft or reviewed")
    by_concept = {e.concept_id: e for e in exposures}
    if len(by_concept) != len(exposures):
        raise ValueError("duplicate exposure for concept")
    arm_counts = {arm: {"assigned": 0, "exposed": 0, "eligible": 0,
                        "correct": 0, "missing": 0, "interval95": None}
                  for arm in ("text", "diagram")}
    seen_concepts: set[str] = set()
    for assignment in assignments:
        if (assignment.protocol_id, assignment.protocol_version) != (PROTOCOL.id, PROTOCOL.version):
            continue
        if assignment.concept_id in seen_concepts:
            raise ValueError("duplicate assignment for concept")
        seen_concepts.add(assignment.concept_id)
        if (assignment.concept_id not in PROTOCOL.primary_families or
                assignment.item_family_id != assignment.concept_id or
                assignment.condition_id not in arm_counts or
                assignment.seed != PROTOCOL.seed):
            raise ValueError("assignment differs from fixed protocol")
        arm = arm_counts[assignment.condition_id]
        arm["assigned"] += 1
        exposure = by_concept.get(assignment.concept_id)
        if (exposure is None or exposure.completed_at is None or
                exposure.condition_id != assignment.condition_id or
                exposure.exposed_at < assignment.assigned_at):
            arm["missing"] += 1
            continue
        arm["exposed"] += 1
        candidates = sorted((a for a in attempts if a.occurred_at >= exposure.completed_at and
                             (activity := activities.get(a.activity_id)) is not None and
                             activity.concept_id == assignment.concept_id and
                             activity.family_id == PROTOCOL.primary_families[assignment.concept_id]),
                            key=lambda a: (a.occurred_at, a.id))
        # The first response to the primary family determines eligibility. A
        # later correct response cannot replace an assisted or early first one.
        first = candidates[0] if candidates else None
        if first is None:
            arm["missing"] += 1
            continue
        prior = frozenset(activity.family_id for a in attempts
                          if a.occurred_at < first.occurred_at
                          and (activity := activities.get(a.activity_id)) is not None)
        activity = activities[first.activity_id]
        if not qualifies_primary_outcome(first, activity, exposure, prior, now=now):
            arm["missing"] += 1
            continue
        arm["eligible"] += 1
        arm["correct"] += int(first.score_status is ScoreStatus.CORRECT)
    for arm in arm_counts.values():
        arm["interval95"] = _wilson(arm["correct"], arm["eligible"])
        arm["correctRate"] = (round(arm["correct"] / arm["eligible"], 4)
                              if arm["eligible"] else None)
    sufficient = (content_review_status == "reviewed" and
                  PROTOCOL.exposure_duration_controlled and
                  all(arm["eligible"] >= PROTOCOL.minimum_per_arm for arm in arm_counts.values()))
    return {
        "protocol": PROTOCOL.public(),
        "status": "descriptive_only" if sufficient else "insufficient_evidence",
        "reason": (
            "Draft instructional material and candidate answer keys lack independent "
            "content review; no human-learning improvement claim is warranted."
            if content_review_status == "draft" else
            "Instructional exposure duration was self-paced and not equivalently "
            "controlled; no method comparison or improvement claim is warranted."
            if not PROTOCOL.exposure_duration_controlled else
            "Arm outcomes meet the preset count for descriptive reporting; "
            "no causal superiority claim is made."
            if sufficient else
            f"Fewer than {PROTOCOL.minimum_per_arm} eligible delayed, independent "
            "outcomes per arm; no method comparison is warranted."
        ),
        "contentReviewStatus": content_review_status,
        "arms": arm_counts,
        "syntheticResultsAreLearningEvidence": False,
    }
