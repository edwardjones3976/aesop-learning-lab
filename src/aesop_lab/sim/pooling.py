"""Population-informed ordered lists (round-2 findings option 2): partial pooling, simulated.

Each learner's personal estimate of the gap (variant minus baseline delayed recall) is shrunk
toward a population estimate learned from *other* learners (leave-seed-out, so a learner never
informs their own prior). The shrinkage weight is the label's "personal share". Compared with
individual-only and population-only orders against each learner's own true order.
Display only: decision 3 forbids pooled estimates from minting official per-person verdicts.
"""
from __future__ import annotations

from datetime import timedelta
import math
import statistics

from aesop_lab.contrast.protocol import BASELINE, VARIANT
from aesop_lab.sim import fastpath, learner

TIE = 0.01  # true gaps under 1 point are ties: any order is acceptable


def personal_estimate(counts: dict) -> tuple[float, float]:
    """Posterior mean difference and its variance from Beta(1+s, 1+f) per arm."""
    means, variances = {}, {}
    for role in (BASELINE, VARIANT):
        s, f = counts[role]
        a, b = 1 + s, 1 + f
        means[role] = a / (a + b)
        variances[role] = a * b / ((a + b) ** 2 * (a + b + 1))
    return means[VARIANT] - means[BASELINE], variances[VARIANT] + variances[BASELINE]


def counts_at(trajectory, day: int) -> dict:
    """Eligible (successes, failures) per arm at a cutoff, with the engine's eligibility rules."""
    counts = {BASELINE: [0, 0], VARIANT: [0, 0]}
    if not trajectory.units:
        return counts
    cutoff = min(u.studied_at for u in trajectory.units) + timedelta(days=day)
    answers = {a.unit_id: a for a in trajectory.answers}
    for unit in trajectory.units:
        answer = answers.get(unit.unit_id)
        if unit.studied_at > cutoff or answer is None or answer.at > cutoff:
            continue
        if fastpath.classify(answer, unit.studied_at) == "eligible":
            counts[unit.role][not answer.correct] += 1
    return counts


def population(others: list[tuple[float, float]]) -> tuple[float, float]:
    """Method-of-moments mean and between-person variance tau^2 of the gap."""
    estimates = [d for d, _ in others]
    mu = statistics.fmean(estimates)
    tau2 = max(1e-6, statistics.pvariance(estimates) - statistics.fmean(v for _, v in others))
    return mu, tau2


def dispute_flag(cohort: list, z_limit: float = 2.576) -> bool:
    """Population measurement guard: dispute shares differ between arms (two-proportion z, p < 0.01).

    cohort: per learner, (disputes, answers) per arm. Pooled across many learners, a one-arm
    scoring bias shows up long before any single learner's guard could see it."""
    d = {r: sum(c[r][0] for c in cohort) for r in (BASELINE, VARIANT)}
    n = {r: sum(c[r][1] for c in cohort) for r in (BASELINE, VARIANT)}
    if min(n.values()) == 0:
        return False
    p1, p2 = d[BASELINE] / n[BASELINE], d[VARIANT] / n[VARIANT]
    pooled = (d[BASELINE] + d[VARIANT]) / (n[BASELINE] + n[VARIANT])
    se = math.sqrt(pooled * (1 - pooled) * (1 / n[BASELINE] + 1 / n[VARIANT]))
    return se > 0 and abs(p1 - p2) / se > z_limit


def disputes_at(trajectory, day: int) -> dict:
    """(disputes, answers) per arm among answers given by the cutoff."""
    out = {BASELINE: [0, 0], VARIANT: [0, 0]}
    if not trajectory.units:
        return out
    cutoff = min(u.studied_at for u in trajectory.units) + timedelta(days=day)
    roles = {u.unit_id: u.role for u in trajectory.units}
    for a in trajectory.answers:
        if a.at <= cutoff and a.unit_id in roles:
            out[roles[a.unit_id]][0] += a.disputed
            out[roles[a.unit_id]][1] += 1
    return out


def evaluate(scenario: dict, day: int = 28) -> dict:
    """Order accuracy for individual-only, population-only and pooled lists at one look day."""
    seeds, per_seed = scenario["learners"]["seeds"], scenario["learners"]["per_seed"]
    learners, disputes = {}, {}
    for seed in seeds:
        for index in range(per_seed):
            t = learner.simulate(scenario, seed, index)
            learners[(seed, index)] = (t.true_gap, personal_estimate(counts_at(t, day)))
            disputes[(seed, index)] = disputes_at(t, day)
    by_seed = {s: [v[1] for k, v in learners.items() if k[0] != s] for s in seeds}
    priors = {s: population(by_seed[s]) for s in seeds}
    flagged = {s: dispute_flag([v for k, v in disputes.items() if k[0] != s]) for s in seeds}
    tally = {"individual": 0, "population": 0, "pooled": 0}
    scored, weights, pooled_hits_by_weight = 0, [], {"low": [0, 0], "high": [0, 0]}
    for (seed, _), (truth, (d, var)) in learners.items():
        if abs(truth) < TIE:
            continue
        scored += 1
        mu, tau2 = priors[seed]
        weight = tau2 / (tau2 + var)
        pooled = weight * d + (1 - weight) * mu
        right = lambda estimate: (estimate > 0) == (truth > 0)
        tally["individual"] += right(d)
        tally["population"] += right(mu)
        tally["pooled"] += right(pooled)
        weights.append(weight)
        band = "high" if weight >= 0.5 else "low"
        pooled_hits_by_weight[band][0] += right(pooled)
        pooled_hits_by_weight[band][1] += 1
    return dict(
        id=scenario["id"], day=day, scored=scored,
        accuracy={k: v / scored for k, v in tally.items()} if scored else {},
        median_personal_weight=statistics.median(weights) if weights else None,
        pooled_accuracy_by_weight={b: (h / n if n else None) for b, (h, n) in pooled_hits_by_weight.items()},
        withheld_share=sum(flagged.values()) / len(flagged),
        population_mean=statistics.fmean(p[0] for p in priors.values()),
        population_sd=math.sqrt(statistics.fmean(p[1] for p in priors.values())),
        true_gap_mean=statistics.fmean(v[0] for v in learners.values()))
