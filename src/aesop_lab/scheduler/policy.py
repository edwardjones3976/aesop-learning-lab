"""Pilot scheduling rules, separate from storage and transport.

One-day and one-week intervals gate independent checks, never practice.
This policy does not declare mastery or infer scores for ungraded answers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from aesop_lab.domain.models import (Activity, ActivityType, Attempt, EvidenceKind, HintLevel,
                                     Recommendation, ScoreStatus)

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
    attempts_by_item: dict[str, list[Attempt]] = {item.id: [] for item in state.activities}
    for attempt in state.attempts:
        attempts_by_item[attempt.activity_id].append(attempt)
    seen_families = set(state.encountered_family_ids)
    seen_families.update(item.family_id for item in state.activities
                         if attempts_by_item[item.id])
    # A later unassisted answer to a family already attempted with help (or
    # answered incorrectly) is practice, not fresh independent evidence.
    first_by_family: dict[str, Attempt] = {}
    item_by_id = {item.id: item for item in state.activities}
    for attempt in sorted(state.attempts, key=lambda a: (a.occurred_at, a.id)):
        first_by_family.setdefault(item_by_id[attempt.activity_id].family_id, attempt)
    qualifying = [attempt for attempt in first_by_family.values()
                  if attempt.score_status is ScoreStatus.CORRECT and
                  attempt.hint_level is HintLevel.NONE and
                  attempt.occurred_at >= state.lesson_completed_at]
    # An attempted earlier check unlocks the next interval regardless of score.
    # Conditioning the week check on day-one success would hide poor retention.
    completed_intervals = {item.check_delay_days for item in state.activities
                           if item.held_out and attempts_by_item[item.id]}
    checks = [item for item in state.activities
              if qualifying and item.held_out and item.evidence_kind in
              (EvidenceKind.APPLICATION, EvidenceKind.TRANSFER) and
              not attempts_by_item[item.id] and item.family_id not in seen_families and
              (item.check_delay_days == 1 or
               any(0 < interval < item.check_delay_days for interval in completed_intervals))]
    check_item = min(checks, key=lambda candidate: (candidate.check_delay_days, candidate.id)) if checks else None
    due_at = (state.lesson_completed_at + timedelta(days=check_item.check_delay_days)
              if check_item else None)
    next_check_at = due_at
    if available_time < MINIMUM_MINUTES:
        return ScheduleDecision(None, "Set aside at least five minutes for an activity.",
                                next_check_at)
    if mode == "recommended" and check_item is not None and state.now >= due_at:
        return _select(check_item, policy_version,
                       f"A held-out independent day-{check_item.check_delay_days} check is due.",
                       tuple(attempt.id for attempt in qualifying), due_at)

    practice = [item for item in state.activities if not item.held_out]
    if practice:
        # Target observable gaps; keep every choice replayable from attempts.
        target_kind = None
        adaptation_reason = None
        errors = [a for a in state.attempts if a.score_status is ScoreStatus.INCORRECT]
        assisted = [a for a in state.attempts if a.hint_level is not HintLevel.NONE]
        by_id = {item.id: item for item in state.activities}
        repeated_items = {item_id for item_id, prior in attempts_by_item.items()
                          if sum(a.score_status is ScoreStatus.INCORRECT for a in prior) >= 2}
        repeated_item = min(repeated_items) if repeated_items else None
        if repeated_item:
            # One learner cannot establish that an item is defective. Avoid
            # repeatedly drilling that same prompt or labeling a misconception.
            target_kind = by_id[repeated_item].evidence_kind
            adaptation_reason = ("Repeated misses on one item may reflect a concept gap "
                                 "or unclear wording; try a different item and flag the "
                                 "original for content review.")
        elif len(errors) >= 2:
            target_kind = next((item.evidence_kind for item in practice
                                if sum(by_id[a.activity_id].evidence_kind is item.evidence_kind
                                       for a in errors) >= 2), None)
            if target_kind:
                adaptation_reason = f"Two incorrect answers on {target_kind.value} practice suggest targeted remediation."
        if target_kind is None and assisted:
            last_assisted = max(assisted, key=lambda a: (a.occurred_at, a.id))
            target_kind = by_id[last_assisted.activity_id].evidence_kind
            adaptation_reason = ("A hint-assisted answer is recorded. Try a fresh "
                                 "first answer in this skill before requesting support; "
                                 "lower hint use alone does not prove understanding.")
        recall_success = any(item_by_id[a.activity_id].evidence_kind is EvidenceKind.RECALL
                             for a in qualifying)
        application_success = any(item_by_id[a.activity_id].evidence_kind is EvidenceKind.APPLICATION
                                  for a in qualifying)
        if target_kind is None and recall_success and not application_success:
            target_kind = EvidenceKind.APPLICATION
            adaptation_reason = "Independent recall is recorded, but independent application has not yet been shown."
        candidates = [item for item in practice if item.evidence_kind is target_kind] if target_kind else []
        if repeated_item:
            clean = [item for item in candidates if item.id not in repeated_items]
            candidates = clean or [item for item in practice if item.id not in repeated_items]
        if target_kind is not None and assisted and not repeated_item:
            # Gradually reduce scaffolding through a new prompt, rather than
            # treating a second view of the same answer as independent recall.
            unseen = [item for item in candidates if not attempts_by_item[item.id]]
            if not unseen:
                unseen = [item for item in practice if not attempts_by_item[item.id]]
                scored_unseen = [item for item in unseen if item.activity_type in
                                 (ActivityType.CHOICE, ActivityType.TRACE)]
                if scored_unseen:
                    unseen = scored_unseen
            if unseen:
                candidates = unseen
            else:
                adaptation_reason = ("No unused prompt remains. Repeating a previously assisted "
                                     "item is practice, not fresh independent evidence.")
        # New items first; then rotate through the least practiced items.
        item = min(candidates or practice, key=lambda candidate:
                   (len(attempts_by_item[candidate.id]), candidate.id))
        if due_at is not None and state.now < due_at:
            reason = "Continue practice now; the independent check opens at its scheduled time."
        elif not qualifying and state.now < state.lesson_completed_at + timedelta(days=1):
            reason = "Continue practice now; a delayed check also requires unassisted evidence."
        elif not qualifying:
            reason = "Continue practice to build evidence before an independent check."
        elif mode == "practice" and check_item is not None and state.now >= due_at:
            reason = "Continue practice by choice; an independent check remains available."
        else:
            reason = "Continue practice; no unused independent check is available."
        if adaptation_reason and candidates:
            reason = adaptation_reason + " " + reason
        recommendation = Recommendation(item.id, policy_version, reason,
                                        tuple(attempt.id for attempt in state.attempts))
        return ScheduleDecision(recommendation, reason, next_check_at)

    if due_at is not None and state.now < due_at:
        return ScheduleDecision(None, "No practice activity is available yet.",
                                next_check_at)
    if mode == "practice" and check_item is not None and state.now >= due_at:
        return ScheduleDecision(None, "No practice activity is available; an independent check is due.",
                                next_check_at)
    return ScheduleDecision(None, "No practice or unused independent check is available.")


def _select(item: Activity, policy_version: str, reason: str,
            evidence_ids: tuple[str, ...], due_at: datetime | None) -> ScheduleDecision:
    recommendation = Recommendation(item.id, policy_version, reason, evidence_ids, due_at)
    return ScheduleDecision(recommendation, reason, due_at)
