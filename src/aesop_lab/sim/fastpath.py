"""Judge a trajectory without SQLite, mirroring MicroUnitEngine.contrast_status exactly.

With the default design (protocol v1) the result equals the engine's; parity is checked on
every run (sim.replay). Other designs are fast-path only: they are candidates for a
protocol revision, measured before any change to the product.
"""
from __future__ import annotations

from datetime import timedelta

from aesop_lab.contrast import protocol
from aesop_lab.contrast.protocol import BASELINE, VARIANT
from aesop_lab.sim.scenario import DEFAULT_DESIGN

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


def decide(look: int, day: int, counts: dict, design: dict) -> dict:
    """Protocol section 5 precedence, parameterised; equals protocol.decide for the v1 design."""
    final = look == len(design["looks"]) - 1
    superiority, equivalence = design["superiority"][look], design["equivalence"][look]
    p = protocol.probabilities(counts, margin=design["margin"])
    result = dict(day=day, counts={r: tuple(c) for r, c in counts.items()}, probabilities=p,
                  status="continue", outcome=None, winner=None)
    if min(s + f for s, f in counts.values()) < design["minimum_per_arm"]:
        if final:
            result.update(status="terminal", outcome="insufficient evidence")
        return result
    if protocol._meets(p["variant_superior"], superiority, p["error"]):
        result.update(status="terminal", outcome="repeated benefit", winner=VARIANT)
    elif protocol._meets(p["baseline_superior"], superiority, p["error"]):
        result.update(status="terminal", outcome="repeated benefit", winner=BASELINE)
    elif protocol._meets(p["equivalent"], equivalence, p["error"]):
        result.update(status="terminal", outcome="no meaningful difference detected")
    elif final:
        if protocol._meets(p["variant_ahead"], design["promising"], p["error"]):
            # v1 records no winner for promising (it is variant-only); both-ways names the arm.
            result.update(status="terminal", outcome="promising",
                          winner=VARIANT if design["promising_both_ways"] else None)
        elif design["promising_both_ways"] and protocol._meets(1 - p["variant_ahead"], design["promising"], p["error"]):
            result.update(status="terminal", outcome="promising", winner=BASELINE)
        else:
            result.update(status="terminal", outcome="insufficient evidence")
    return result


def _quality_gaps(trajectory, answers, cutoff) -> tuple[float, float, float]:
    """Between-arm differences in missing checks (windows closed by the cutoff), declared outside
    study, and marking disputes (the measurement guard: one-arm scoring errors leave no other trace)."""
    missing, contaminated, disputed = {}, {}, {}
    for role in (BASELINE, VARIANT):
        closed = [u for u in trajectory.units if u.role == role and u.studied_at + WINDOW_CLOSE <= cutoff]
        given = [answers[u.unit_id] for u in trajectory.units
                 if u.role == role and u.unit_id in answers and answers[u.unit_id].at <= cutoff]
        missing[role] = (sum(1 for u in closed if u.unit_id not in answers or answers[u.unit_id].at > cutoff
                             or classify(answers[u.unit_id], u.studied_at) != "eligible") / len(closed)) if closed else 0.0
        contaminated[role] = (sum(a.outside_study == "some" for a in given) / len(given)) if given else 0.0
        disputed[role] = (sum(a.disputed for a in given) / len(given)) if given else 0.0
    return (abs(missing[BASELINE] - missing[VARIANT]), abs(contaminated[BASELINE] - contaminated[VARIANT]),
            abs(disputed[BASELINE] - disputed[VARIANT]))


def judge(trajectory, design: dict | None = None) -> dict:
    """Looks after the first exposure, each from events known at its cutoff."""
    design = design or DEFAULT_DESIGN
    if not trajectory.units:
        return dict(outcome=None, winner=None, decision_day=None, looks=[], abstained=False)
    day_zero = min(u.studied_at for u in trajectory.units)
    answers = {a.unit_id: a for a in trajectory.answers}
    looks, abstained = [], False
    for index, day in enumerate(design["looks"]):
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
        look = decide(index, day, counts, design)
        limits = design["abstain"]
        if limits and look["outcome"] not in (None, "insufficient evidence"):
            missing_gap, contamination_gap, dispute_gap = _quality_gaps(trajectory, answers, cutoff)
            if (missing_gap > limits.get("missing_gap", 1.0) or contamination_gap > limits.get("contamination_gap", 1.0)
                    or dispute_gap > limits.get("dispute_gap", 1.0)):
                # Data-quality abstention: unequal data between arms cannot support a verdict.
                abstained = True
                final = index == len(design["looks"]) - 1
                look.update(status="terminal" if final else "continue",
                            outcome="insufficient evidence" if final else None, winner=None, abstained=True)
        look["excluded"] = dropped
        looks.append(look)
        if look["status"] == "terminal":
            # The engine assigns a unit started exactly at a terminal cutoff as post-decision.
            if look["outcome"] is not None:
                dropped["unanswered"] -= sum(u.studied_at == cutoff for u in trajectory.units)
            break
    final = looks[-1] if looks and looks[-1]["status"] == "terminal" else None
    return dict(looks=looks, outcome=final and final["outcome"], winner=final and final["winner"],
                decision_day=final and final["day"], abstained=abstained)
