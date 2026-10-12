"""Pilot scheduling rules, separate from storage and transport.

The 24-hour interval gates an independent check, never access to practice.
This policy does not declare mastery or infer scores for ungraded answers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from aesop_lab.domain.models import (Activity, Attempt, EvidenceKind, HintLevel,
                                     Recommendation, ScoreStatus)

DELAY = timedelta(hours=24)
MINIMUM_MINUTES = 5


@dataclass(frozen=True, slots=True)
class LearnerState:
    concept_id: str
    content_version: str
    lesson_completed_at: datetime
    now: datetime
    activities: tuple[Activity, ...]
    attempts: tuple[Attempt, ...]
    # Families seen in lessons, examples, or previous practice, beyond attempts.
    encountered_family_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        for value in (self.lesson_completed_at, self.now):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("scheduler times must include a timezone")
        if self.now < self.lesson_completed_at:
            raise ValueError("current time cannot precede lesson completion")
        if any(item.concept_id != self.concept_id or
               item.content_version != self.content_version for item in self.activities):
            raise ValueError("activities must belong to the scheduled concept and version")
        if len({item.id for item in self.activities}) != len(self.activities):
            raise ValueError("activity IDs must be unique")
        known = {item.id for item in self.activities}
        if any(attempt.activity_id not in known or
               attempt.content_version != self.content_version for attempt in self.attempts):
            raise ValueError("attempts must reference activities in this concept version")
        if len({attempt.id for attempt in self.attempts}) != len(self.attempts):
            raise ValueError("attempt IDs must be unique")
        if any(attempt.occurred_at > self.now for attempt in self.attempts):
            raise ValueError("attempt time cannot be in the future")


@dataclass(frozen=True, slots=True)
class ScheduleDecision:
    recommendation: Recommendation | None
    reason: str
    next_check_at: datetime | None = None


def recommend(state: LearnerState, available_time: int, policy_version: str,
              mode: str = "recommended") -> ScheduleDecision:
    """Choose a due independent check or continued practice, deterministically.

    Attempts and time are inputs, so replaying the same state returns the same
    choice. ``mode="practice"`` honors a learner request for more practice
    even when an independent check is due. A held-out item is used once and
    is never selected for routine practice. Caller controls which reviewed
    activities enter this state.
    """
    if not policy_version:
        raise ValueError("policy version is required")
    if mode not in ("recommended", "practice"):
        raise ValueError("mode must be recommended or practice")
    if available_time < 0:
        raise ValueError("available time cannot be negative")
    if available_time < MINIMUM_MINUTES:
        return ScheduleDecision(None, "Set aside at least five minutes for an activity.")

    attempts_by_item: dict[str, list[Attempt]] = {item.id: [] for item in state.activities}
    for attempt in state.attempts:
        attempts_by_item[attempt.activity_id].append(attempt)
    seen_families = set(state.encountered_family_ids)
    seen_families.update(item.family_id for item in state.activities
                         if attempts_by_item[item.id])
    qualifying = [attempt for attempt in state.attempts
                  if attempt.score_status is ScoreStatus.CORRECT and
                  attempt.hint_level is HintLevel.NONE]
    due_at = state.lesson_completed_at + DELAY

    check_item: Activity | None = None
    if qualifying and state.now >= due_at:
        checks = [item for item in state.activities
                  if item.held_out and item.evidence_kind in
                  (EvidenceKind.APPLICATION, EvidenceKind.TRANSFER) and
                  not attempts_by_item[item.id] and item.family_id not in seen_families]
        if checks:
            check_item = min(checks, key=lambda candidate: candidate.id)
    if mode == "recommended" and check_item is not None:
        return _select(check_item, policy_version,
                       "A held-out independent application check is due.",
                       tuple(attempt.id for attempt in qualifying), due_at)

    practice = [item for item in state.activities if not item.held_out]
    if practice:
        # New items first; then rotate through the least practiced items.
        item = min(practice, key=lambda candidate:
                   (len(attempts_by_item[candidate.id]), candidate.id))
        if state.now < due_at:
            reason = "Continue practice now; the independent check opens after 24 hours."
        elif not qualifying:
            reason = "Continue practice to build evidence before an independent check."
        elif mode == "practice" and check_item is not None:
            reason = "Continue practice by choice; an independent check remains available."
        else:
            reason = "Continue practice; no unused independent check is available."
        recommendation = Recommendation(item.id, policy_version, reason,
                                        tuple(attempt.id for attempt in state.attempts))
        return ScheduleDecision(recommendation, reason,
                                due_at if state.now < due_at or check_item is not None else None)

    if state.now < due_at:
        return ScheduleDecision(None, "No practice activity is available yet.", due_at)
    if mode == "practice" and check_item is not None:
        return ScheduleDecision(None, "No practice activity is available; an independent check is due.", due_at)
    return ScheduleDecision(None, "No practice or unused independent check is available.")


def _select(item: Activity, policy_version: str, reason: str,
            evidence_ids: tuple[str, ...], due_at: datetime | None) -> ScheduleDecision:
    recommendation = Recommendation(item.id, policy_version, reason, evidence_ids, due_at)
    return ScheduleDecision(recommendation, reason, due_at)
