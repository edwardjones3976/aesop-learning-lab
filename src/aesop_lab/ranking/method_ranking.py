"""Pure, reproducible beta estimates for preclassified delayed outcomes.

This module does not classify attempts or change experimental assignments.
Weights are fractional likelihood powers, not independent sample counts.
Confidence describes the leader only, never the entire ordering.
"""

from dataclasses import dataclass
import math
import random
from collections.abc import Mapping, Sequence


@dataclass(frozen=True)
class MethodEstimate:
    method: str
    posterior_mean: float
    probability_best: float
    effective_checks: float
    alpha: float
    beta: float


@dataclass(frozen=True)
class Ranking:
    methods: tuple[MethodEstimate, ...]
    confidence: str
    show_ranking: bool


def rank_methods(
    outcomes: Mapping[str, Sequence[tuple[bool, float]]], *,
    seed: int = 0, draws: int = 2048,
) -> Ranking:
    """Rank N methods by posterior mean with independent Beta(1, 1) priors.

    Input must contain all available methods, including unobserved ones.
    Each tuple is (matched_key, weight); only fresh, unassisted, in-window
    delayed checks belong here. Callers must deduplicate families and cap
    correlated checks to total weight <= 1 per instructional unit.
    P(best) uses seeded Monte Carlo; default standard error <= 0.0111.
    Ties in means sort by method ID without claiming a meaningful difference.
    A label can downgrade on later observations. No global RNG is mutated.
    """
    if not outcomes:
        raise ValueError("at least one method is required")
    if isinstance(draws, bool) or not isinstance(draws, int) or draws < 256:
        raise ValueError("draws must be an integer >= 256")
    if any(not isinstance(name, str) or not name.strip() for name in outcomes):
        raise ValueError("method IDs must be nonempty strings")
    parameters = []
    for name in sorted(outcomes):
        successes, failures = [], []
        for correct, weight in outcomes[name]:
            if (not isinstance(correct, bool) or isinstance(weight, bool)
                    or not isinstance(weight, (int, float))
                    or not math.isfinite(weight) or not 0 <= weight <= 1):
                raise ValueError("outcomes need a bool and a finite weight in [0, 1]")
            (successes if correct else failures).append(weight)
        success, failure = math.fsum(successes), math.fsum(failures)
        parameters.append((name, 1 + success, 1 + failure, success + failure))
    rng = random.Random(seed)
    wins = [0] * len(parameters)
    for _ in range(draws):
        samples = [rng.betavariate(alpha, beta) for _, alpha, beta, _ in parameters]
        wins[max(range(len(samples)), key=samples.__getitem__)] += 1
    methods = tuple(sorted(
        (MethodEstimate(name, alpha / (alpha + beta), wins[i] / draws,
                        count, alpha, beta)
         for i, (name, alpha, beta, count) in enumerate(parameters)),
        key=lambda row: (-row.posterior_mean, row.method),
    ))
    minimum = min(row.effective_checks for row in methods)
    total = math.fsum(row.effective_checks for row in methods)
    show = total >= max(8, 2 * len(methods))
    confidence = "tentative"
    if show and len(methods) > 1:
        # A conservative MC margin reduces boundary flips; it is not a
        # frequentist guarantee, especially under correlated real outcomes.
        p = methods[0].probability_best
        lower = p - 2 * math.sqrt(p * (1 - p) / draws) - 1 / draws
        if minimum >= 20 and lower >= 0.99:
            confidence = "clear"
        elif minimum >= 5 and lower >= 0.80:
            confidence = "likely"
    return Ranking(methods, confidence, show)
