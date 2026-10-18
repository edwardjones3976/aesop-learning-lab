"""Descriptive learner evidence; no inferred mastery or calibrated probability."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping

from aesop_lab.domain.models import Activity, Attempt, EvidenceKind, ScoreStatus


def summarize_evidence(activities: Mapping[str, Activity], attempts: tuple[Attempt, ...],
                       lesson_completed_at: datetime | None) -> dict[str, object]:
    """Summarize observed attempts without promoting draft keys to mastery claims."""
    kinds = {kind.value: {"attempts": 0, "unassistedCorrect": 0,
                          "assistedCorrect": 0, "incorrect": 0, "ungraded": 0}
             for kind in EvidenceKind}
    delayed: list[dict[str, object]] = []
    confidence_pairs = 0
    misses_by_item: dict[str, list[str]] = {}
    for attempt in attempts:
        activity = activities.get(attempt.activity_id)
        if activity is None or activity.content_version != attempt.content_version:
            continue
        row = kinds[activity.evidence_kind.value]
        row["attempts"] += 1
        if attempt.score_status is ScoreStatus.CORRECT:
            row["unassistedCorrect" if attempt.unassisted else "assistedCorrect"] += 1
        elif attempt.score_status is ScoreStatus.INCORRECT:
            row["incorrect"] += 1
            misses_by_item.setdefault(activity.id, []).append(attempt.id)
        else:
            row["ungraded"] += 1
        if (attempt.confidence is not None and attempt.unassisted and
                attempt.score_status is not ScoreStatus.UNGRADED):
            confidence_pairs += 1
        if (activity.held_out and lesson_completed_at is not None and
                attempt.occurred_at >= lesson_completed_at + timedelta(days=activity.check_delay_days)):
            delayed.append({
                "attemptId": attempt.id,
                "activityId": activity.id,
                "evidenceKind": activity.evidence_kind.value,
                "checkDelayDays": activity.check_delay_days,
                "occurredAt": attempt.occurred_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "scoreStatus": attempt.score_status.value,
                "assisted": not attempt.unassisted,
                "independentSuccess": attempt.unassisted and attempt.score_status is ScoreStatus.CORRECT,
                "familiarityStatus": "not_verified",
            })
    delayed.sort(key=lambda row: (str(row["occurredAt"]), str(row["attemptId"])))
    expected_intervals = sorted({activity.check_delay_days for activity in activities.values()
                                 if activity.held_out})
    interval_outcomes = {
        str(day): "observed" if any(row["checkDelayDays"] == day for row in delayed)
        else "insufficient_evidence" for day in expected_intervals
    }
    return {
        "byKind": kinds,
        "delayedChecks": delayed,
        "delayedOutcome": "observed" if delayed else "insufficient_evidence",
        "delayedOutcomeByDay": interval_outcomes,
        "confidenceOutcomePairs": confidence_pairs,
        "contentQualityCandidates": [
            {"activityId": item_id, "attemptIds": ids,
             "reason": "Repeated misses on one item warrant a wording/key check; this is not proof of a defective item or learner misconception."}
            for item_id, ids in sorted(misses_by_item.items()) if len(ids) >= 2
        ],
        "interpretation": "Development candidate-key observations only; no mastery or learning-effect claim.",
    }
