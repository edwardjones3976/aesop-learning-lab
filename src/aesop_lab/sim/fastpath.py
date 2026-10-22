"""Judge a trajectory without SQLite, mirroring MicroUnitEngine.contrast_status exactly.

Parity with the engine is checked on every run (sim.replay); any label difference fails it.
"""
from __future__ import annotations

from datetime import timedelta

from aesop_lab.contrast import protocol
from aesop_lab.contrast.protocol import BASELINE, VARIANT

WINDOW_OPEN, WINDOW_CLOSE = timedelta(days=7), timedelta(days=14)


def classify(answer, completed_at) -> str:
    """The engine's eligibility rule (_classification); assistance and re-exposure are not simulated."""
    if answer.outside_study == "some":
        return "contaminated"
    elapsed = answer.at - completed_at
    if elapsed < WINDOW_OPEN:
        return "early"
    if elapsed > WINDOW_CLOSE:
        return "late"
    return "eligible"


def judge(trajectory) -> dict:
    """Looks at days 14, 21 and 28 after the first exposure, each from events known at its cutoff."""
    if not trajectory.units:
        return dict(outcome=None, winner=None, decision_day=None, looks=[])
    day_zero = min(u.studied_at for u in trajectory.units)
    answers = {a.unit_id: a for a in trajectory.answers}
    snapshots, excluded = {}, {}
    for day, _, _ in protocol.LOOKS:
        cutoff = day_zero + timedelta(days=day)
        counts = {BASELINE: [0, 0], VARIANT: [0, 0]}
        dropped = {k: 0 for k in ("early", "late", "assisted", "contaminated", "unanswered")}
        for unit in trajectory.units:
            # The simulator completes a unit at the moment it is studied.
            if unit.studied_at > cutoff:
                continue
            answer = answers.get(unit.unit_id)
            if answer is None or answer.at > cutoff:
                dropped["unanswered"] += 1
                continue
            label = classify(answer, unit.studied_at)
            if label != "eligible":
                dropped[label] += 1
                continue
            counts[unit.role][not answer.correct] += 1
        snapshots[day] = {role: tuple(c) for role, c in counts.items()}
        excluded[day] = dropped
    judged = protocol.judge(snapshots)
    for look in judged["looks"]:
        look["excluded"] = excluded[look["day"]]
    return judged
