"""Prospective, descriptive v2 pilot rules.

V1 remains immutable. V2 is for new enrollment only; callers must not relabel
earlier v1 assignments or exposures. This local-first application stores one
learner per database. Five outcomes from that learner are five correlated
concept observations, never five independent people.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Mapping, Sequence

from aesop_lab.domain.models import (
    Activity, Attempt, EvidenceKind, ExperimentAssignment, HintLevel, ScoreStatus,
)


@dataclass(frozen=True, slots=True)
class DescriptiveProtocolV2:
    id: str
    version: str
    seed: int
    content_version: str
    primary_family_by_concept: tuple[tuple[str, str], ...]
    primary_delay_days: int
    primary_window_days: int
    target_exposure_minutes: int
    minimum_independent_learners_per_arm: int

    @property
    def primary_families(self) -> dict[str, str]:
        return dict(self.primary_family_by_concept)

    def public(self) -> dict:
        return {
            "id": self.id,
            "version": self.version,
            "seed": self.seed,
            "contentVersion": self.content_version,
            "assignmentMethod": (
                "For each persisted local learner ID, rank the five fixed concepts "
                "by SHA-256 of protocol ID, version, seed, learner ID, and concept ID. "
                "Alternate arms in that order and choose the starting arm with a "
                "separate learner-specific SHA-256 bit. Save first assignments; "
                "never reassign or migrate v1 enrollments."
            ),
            "conditions": {
                "text": "The same text explanation plus retrieval practice",
                "diagram": "The same text explanation and retrieval practice, plus a labeled diagram",
            },
            "primaryFamilyByConcept": dict(self.primary_family_by_concept),
            "primaryOutcome": (
                "First independently answered, deterministically graded, held-out "
                "unfamiliar application or transfer item about seven days after instruction"
            ),
            "primaryDelayDays": self.primary_delay_days,
            "primaryWindowDays": self.primary_window_days,
            "targetExposureMinutes": self.target_exposure_minutes,
            "exposureGuidance": (
                "Offer the same target study time and retrieval opportunity in both "
                "arms. Learners may proceed at their own pace. Record observed time "
                "when available; current local timing does not verify equivalent exposure."
            ),
            "exposureDurationControlled": False,
            "analysisUnit": "independent_learner",
            "minimumIndependentLearnersPerArm": self.minimum_independent_learners_per_arm,
            "analysisRule": (
                "Report concept observations and unique learner counts separately. "
                "Never use multiple concepts from one learner as independent samples "
                "or compute a concept-level confidence interval. Draft keys, unverified "
                "exposure duration, and too few independent learners require "
                "insufficient_evidence. No method winner is inferred."
            ),
            "missingDataRule": (
                "Missing, early, late, assisted, ungraded, and previously seen checks "
                "remain missing primary outcomes, not incorrect answers. An incorrect "
                "independent first response is an observed incorrect outcome."
            ),
            "prospectiveOnly": True,
            "requiresIndependentContentReview": True,
        }


DESCRIPTIVE_V2 = DescriptiveProtocolV2(
    id="text-vs-labeled-diagram",
    version="v2",
    seed=20261017,
    content_version="v5",
    primary_family_by_concept=(
        ("function-definition-and-return", "def-return-shipping-week-v4"),
        ("parameters-and-local-scope", "scope-caller-local-default-week-v5"),
        ("recursion-as-self-call", "recursion-nested-wrap-week-v5"),
        ("base-case", "base-case-threshold-halving-week-v4"),
        ("recursive-case-and-trace", "recursive-case-week-a"),
    ),
    primary_delay_days=7,
    primary_window_days=14,
    target_exposure_minutes=10,
    minimum_independent_learners_per_arm=20,
)


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True, slots=True)
class ExposureV2:
    concept_id: str
    content_version: str
    condition_id: str
    exposed_at: datetime
    encountered_family_ids: tuple[str, ...]
    protocol_id: str = DESCRIPTIVE_V2.id
    protocol_version: str = DESCRIPTIVE_V2.version
    completed_at: datetime | None = None
    observed_seconds: int | None = None

    def __post_init__(self) -> None:
        if self.concept_id not in DESCRIPTIVE_V2.primary_families:
            raise ValueError("exposure concept is outside v2")
        if self.content_version != DESCRIPTIVE_V2.content_version:
            raise ValueError("exposure content version differs from v2")
        if self.condition_id not in ("text", "diagram"):
            raise ValueError("exposure condition is unknown")
        if (self.protocol_id, self.protocol_version) != (DESCRIPTIVE_V2.id,
                                                        DESCRIPTIVE_V2.version):
            raise ValueError("exposure protocol identity differs from v2")
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


def assign_condition_v2(
    concept_id: str, learner_id: str, *, seed: int = DESCRIPTIVE_V2.seed,
) -> str:
    """Deterministic balanced-within-learner assignment for *new* enrollment."""

    if concept_id not in DESCRIPTIVE_V2.primary_families:
        raise ValueError("concept is outside fixed v2 protocol")
    if not isinstance(learner_id, str) or not learner_id:
        raise ValueError("persisted learner ID is required")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")

    def digest(suffix: str) -> bytes:
        payload = (f"{DESCRIPTIVE_V2.id}\0{DESCRIPTIVE_V2.version}\0{seed}\0"
                   f"{learner_id}\0{suffix}")
        return sha256(payload.encode("utf-8")).digest()

    order = sorted(DESCRIPTIVE_V2.primary_families,
                   key=lambda cid: (digest(cid), cid))
    starting_bit = digest("starting-arm")[0] & 1
    return "diagram" if (order.index(concept_id) + starting_bit) % 2 else "text"


def _qualifies(
    first: Attempt, activity: Activity, exposure: ExposureV2,
    prior_families: set[str], now: datetime,
) -> bool:
    if exposure.completed_at is None or first.occurred_at > now:
        return False
    if (first.activity_id != activity.id or
            first.content_version != activity.content_version or
            activity.content_version != exposure.content_version or
            activity.concept_id != exposure.concept_id or
            activity.family_id != DESCRIPTIVE_V2.primary_families[exposure.concept_id]):
        return False
    if (not activity.held_out or
            activity.check_delay_days != DESCRIPTIVE_V2.primary_delay_days or
            activity.evidence_kind not in (EvidenceKind.APPLICATION, EvidenceKind.TRANSFER)):
        return False
    if (activity.family_id in exposure.encountered_family_ids or
            activity.family_id in prior_families):
        return False
    if (first.hint_level is not HintLevel.NONE or
            first.score_status not in (ScoreStatus.CORRECT, ScoreStatus.INCORRECT) or
            first.grading_method != "reviewed_exact_key"):
        return False
    elapsed = first.occurred_at - exposure.completed_at
    return (timedelta(days=DESCRIPTIVE_V2.primary_delay_days) <= elapsed <=
            timedelta(days=DESCRIPTIVE_V2.primary_window_days))


def analyze_v2(
    assignments: Sequence[ExperimentAssignment],
    exposures: Sequence[ExposureV2],
    attempts: Sequence[Attempt],
    activities: Mapping[str, Activity],
    *,
    learner_id: str,
    now: datetime,
    content_review_status: str = "draft",
) -> dict:
    """Summarize one local learner without pseudoreplication or efficacy claims."""

    if not isinstance(learner_id, str) or not learner_id:
        raise ValueError("persisted learner ID is required")
    if not _aware(now):
        raise ValueError("now needs a timezone")
    if content_review_status not in ("draft", "reviewed"):
        raise ValueError("content review status must be draft or reviewed")
    if any(not isinstance(exposure, ExposureV2) for exposure in exposures):
        raise ValueError("v1 or foreign exposure cannot be analyzed as v2")
    by_concept = {exposure.concept_id: exposure for exposure in exposures}
    if len(by_concept) != len(exposures):
        raise ValueError("duplicate v2 exposure for concept")
    arms = {name: {"assigned": 0, "exposed": 0, "eligible": 0,
                   "correct": 0, "missing": 0, "correctRate": None,
                   "interval95": None, "independentLearners": 0,
                   "observedExposureSeconds": []}
            for name in ("text", "diagram")}
    seen: set[str] = set()
    for assignment in assignments:
        if (assignment.protocol_id, assignment.protocol_version) != (
                DESCRIPTIVE_V2.id, DESCRIPTIVE_V2.version):
            raise ValueError("v1 or foreign assignment cannot be analyzed as v2")
        if assignment.concept_id in seen:
            raise ValueError("duplicate v2 assignment for concept")
        seen.add(assignment.concept_id)
        if (assignment.concept_id not in DESCRIPTIVE_V2.primary_families or
                assignment.item_family_id != assignment.concept_id or
                assignment.seed != DESCRIPTIVE_V2.seed or
                assignment.condition_id != assign_condition_v2(
                    assignment.concept_id, learner_id)):
            raise ValueError("assignment does not match fixed v2 seed or learner")
        arm = arms[assignment.condition_id]
        arm["assigned"] += 1
        exposure = by_concept.get(assignment.concept_id)
        if (exposure is None or exposure.completed_at is None or
                exposure.condition_id != assignment.condition_id or
                exposure.exposed_at < assignment.assigned_at):
            arm["missing"] += 1
            continue
        arm["exposed"] += 1
        if exposure.observed_seconds is not None:
            arm["observedExposureSeconds"].append(exposure.observed_seconds)
        family = DESCRIPTIVE_V2.primary_families[assignment.concept_id]
        relevant = sorted((attempt for attempt in attempts
                           if (activity := activities.get(attempt.activity_id)) is not None
                           and activity.concept_id == assignment.concept_id
                           and activity.family_id == family),
                          key=lambda attempt: (attempt.occurred_at, attempt.id))
        # First encounter with the primary family is decisive. A later correct
        # response cannot replace an early, assisted, or incorrect one.
        if not relevant:
            arm["missing"] += 1
            continue
        first = relevant[0]
        prior_families = {activity.family_id for attempt in attempts
                          if attempt.occurred_at < first.occurred_at
                          and (activity := activities.get(attempt.activity_id)) is not None}
        if not _qualifies(first, activities[first.activity_id], exposure, prior_families, now):
            arm["missing"] += 1
            continue
        arm["eligible"] += 1
        arm["correct"] += int(first.score_status is ScoreStatus.CORRECT)
    for arm in arms.values():
        arm["correctRate"] = (round(arm["correct"] / arm["eligible"], 4)
                              if arm["eligible"] else None)
        arm["independentLearners"] = int(arm["eligible"] > 0)
    return {
        "protocol": DESCRIPTIVE_V2.public(),
        "status": "insufficient_evidence",
        "reason": (
            "One local learner supplies at most one independent learner unit per arm; "
            "the fixed minimum of 20 independent learners per arm is unreachable "
            "in this local analysis. Instructional duration remains unverified and "
            "draft answer keys lack independent review. No method benefit is established."
            if content_review_status == "draft" else
            "One local learner supplies at most one independent learner unit per arm; "
            "the fixed minimum of 20 independent learners per arm is unreachable "
            "in this local analysis. Instructional duration remains unverified. "
            "No method benefit is established."
        ),
        "analysisUnit": "independent_learner",
        "independentLearnersTotal": int(bool(seen)),
        "independentLearnersEnrolled": int(bool(seen)),
        "independentLearnersWithOutcome": int(any(arm["eligible"] for arm in arms.values())),
        "conceptObservationsTotal": sum(arm["eligible"] for arm in arms.values()),
        "contentReviewStatus": content_review_status,
        "evidenceOrigin": "local_records_unverified",
        "arms": arms,
        "syntheticResultsAreLearningEvidence": False,
    }


def effect_policy_gate_v2(
    report: Mapping[str, object],
    *,
    content_reviewed: bool,
    exposure_verified: bool,
    independent_learners_per_arm: Mapping[str, int],
) -> dict:
    """Decide only whether a future policy amendment merits manual review.

    This function changes no recommendation or scheduler behavior. A positive
    result never establishes causal superiority or authorizes deployment.
    Local v2 reports cannot pass: they contain one learner, unverified exposure,
    and ``insufficient_evidence``. Synthetic reports cannot pass either.
    """

    def reject(reason: str) -> dict:
        return {"eligible": False, "reason": reason,
                "action": "keep_current_policy"}

    if not isinstance(report, Mapping) or not isinstance(independent_learners_per_arm, Mapping):
        return reject("A report and per-arm independent learner counts are required.")
    protocol = report.get("protocol")
    if not isinstance(protocol, Mapping) or (
            protocol.get("id"), protocol.get("version")) != (
                DESCRIPTIVE_V2.id, DESCRIPTIVE_V2.version):
        return reject("Report does not match the prospective v2 protocol.")
    if report.get("analysisUnit") != "independent_learner":
        return reject("Report does not identify independent learners as its analysis unit.")
    if report.get("status") != "descriptive_only":
        return reject("Report does not contain sufficient descriptive evidence.")
    if report.get("evidenceOrigin") != "real_human_observations":
        return reject("Real human observations with audited provenance are required.")
    if content_reviewed is not True:
        return reject("Independent content review is required.")
    if exposure_verified is not True:
        return reject("Comparable instructional exposure must be verified.")
    arms = report.get("arms")
    if not isinstance(arms, Mapping):
        return reject("Report is missing per-arm learner counts.")
    for condition in ("text", "diagram"):
        count = independent_learners_per_arm.get(condition)
        arm = arms.get(condition)
        reported_count = arm.get("independentLearners") if isinstance(arm, Mapping) else None
        if (type(count) is not int or type(reported_count) is not int or
                count != reported_count or
                count < DESCRIPTIVE_V2.minimum_independent_learners_per_arm):
            return reject("Each arm needs at least 20 verified independent learners, "
                          "consistent with the report.")
    return {
        "eligible": True,
        "reason": (
            "The prespecified descriptive and verification gates are met. "
            "An independent reviewer may consider a new, versioned policy amendment; "
            "no causal method benefit is established and no policy changed."
        ),
        "action": "request_independent_policy_review",
    }
