"""Frozen two-arm contrast policy and four-outcome estimator (docs/contrast-protocol-v1.html).

Pure functions only: deterministic block allocation, posterior probabilities of the
arm difference by numerical integration (no Monte Carlo), and the scheduled-look
decision. Nothing here reads the clock, the store or learner outcomes.
"""
from dataclasses import dataclass
import hashlib
import json
import math

POLICY_VERSION = "contrast-order-v1-policy-1"
ESTIMATOR_VERSION = "beta11-simpson-v1"
MARGIN = 0.05
MINIMUM_PER_ARM = 8
# (elapsed day, superiority threshold, equivalence threshold); day 28 is also the final call.
LOOKS = ((14, 0.999, 0.97), (21, 0.999, 0.95), (28, 0.999, 0.90))
PROMISING = 0.98
TOLERANCE = 1e-6

BASELINE, VARIANT = "baseline", "variant"
OUTCOMES = ("repeated benefit", "no meaningful difference detected", "promising", "insufficient evidence")


@dataclass(frozen=True)
class ContrastSpec:
    contrast_id: str
    baseline: str
    variant: str
    scope: str = "delayed-recall"

    def __post_init__(self):
        if not self.contrast_id or not self.baseline or not self.variant or self.baseline == self.variant:
            raise ValueError("a contrast needs an ID and two distinct method IDs")

    def method(self, role):
        return {BASELINE: self.baseline, VARIANT: self.variant}[role]


ORDER_V1 = ContrastSpec("order-v1", "worked_then_retrieve", "predict_first")


def block_seed(learner_id, pack_id, contrast_id, block_index):
    if not isinstance(learner_id, str) or not isinstance(pack_id, str) or type(block_index) is not int or block_index < 0:
        raise ValueError("learner and pack IDs must be strings and the block index a non-negative integer")
    payload = json.dumps([learner_id, pack_id, contrast_id, block_index], separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def block_roles(seed):
    """Roles for positions 0-3: the two lowest position digests get BASELINE."""
    ranked = sorted(range(4), key=lambda p: (hashlib.sha256(f"{seed}:{p}".encode("ascii")).hexdigest(), p))
    roles = [VARIANT] * 4
    for position in ranked[:2]:
        roles[position] = BASELINE
    return tuple(roles)


def _beta_fraction(x, a, b):
    """Continued fraction for the incomplete beta (modified Lentz), converged to 1e-15."""
    tiny = 1e-300
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1)
    d = 1.0 / (d if abs(d) > tiny else tiny)
    value = d
    for m in range(1, 10_000):
        for numerator in (m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m)),
                          -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))):
            d = 1.0 + numerator * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + numerator / c
            c = c if abs(c) > tiny else tiny
            value *= c * d
        if abs(c * d - 1.0) < 1e-15:
            return value
    raise ArithmeticError("incomplete beta did not converge")


def _beta_cdf(x, a, b):
    """Regularized incomplete beta I_x(a, b) for a, b >= 1."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    log_front = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                 + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return math.exp(log_front) * _beta_fraction(x, a, b) / a
    return 1.0 - math.exp(log_front) * _beta_fraction(1 - x, b, a) / b


def _beta_pdf(x, a, b):
    if x <= 0:
        return float(b) if a == 1 else 0.0  # Beta(1, b) density at 0 is b
    if x >= 1:
        return float(a) if b == 1 else 0.0
    return math.exp((a - 1) * math.log(x) + (b - 1) * math.log1p(-x)
                    + math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b))


def _simpson(f, lo, hi, intervals):
    h = (hi - lo) / intervals
    total = f(lo) + f(hi) + math.fsum((4 if i % 2 else 2) * f(lo + i * h) for i in range(1, intervals))
    return total * h / 3


def _integrate(f, lo, hi):
    """Composite Simpson, doubled until successive estimates agree; returns (value, error)."""
    if hi <= lo:
        return 0.0, 0.0
    intervals, previous = 128, _simpson(f, lo, hi, 64)
    while True:
        current = _simpson(f, lo, hi, intervals)
        error = abs(current - previous) / 15
        if error <= TOLERANCE / 10 or intervals >= 1 << 15:
            return current, error
        intervals, previous = intervals * 2, current


def p_diff_greater(baseline, variant, c):
    """P(p_variant - p_baseline > c) for independent Beta posteriors given as (alpha, beta) integers.

    Returns (probability, error estimate)."""
    ab, bb = baseline
    av, bv = variant
    integrand = lambda x: _beta_pdf(x, ab, bb) * (1 - _beta_cdf(x + c, av, bv))
    # Baseline mass beyond 40 SD of its mean is far below TOLERANCE even for Beta(1, b)
    # tails, so integrating only that window keeps peaked posteriors fast.
    mean = ab / (ab + bb)
    spread = 40 * math.sqrt(ab * bb / ((ab + bb) ** 2 * (ab + bb + 1)))
    window = (max(0.0, mean - spread), min(1.0, mean + spread))
    if c >= 0:
        value, error = _integrate(integrand, window[0], min(window[1], 1.0 - c))
        return min(1.0, max(0.0, value)), error
    # Below x = -c the variant always exceeds x + c, so that part is the baseline CDF.
    value, error = _integrate(integrand, max(window[0], -c), window[1])
    return min(1.0, max(0.0, _beta_cdf(-c, ab, bb) + value)), error


def probabilities(counts, margin=MARGIN):
    """counts: {"baseline": (successes, failures), "variant": (...)} -> probabilities and errors."""
    posterior = {role: (1 + s, 1 + f) for role, (s, f) in counts.items()}
    above, e1 = p_diff_greater(posterior[BASELINE], posterior[VARIANT], margin)
    above_low, e2 = p_diff_greater(posterior[BASELINE], posterior[VARIANT], -margin)
    ahead, e3 = p_diff_greater(posterior[BASELINE], posterior[VARIANT], 0.0)
    return dict(
        variant_superior=above, baseline_superior=1 - above_low,
        equivalent=max(0.0, above_low - above), variant_ahead=ahead,
        error=max(e1 + e2, e3),
    )


def _meets(probability, threshold, error):
    if abs(probability - threshold) <= error:
        raise ArithmeticError("posterior probability is within numerical error of a threshold")
    return probability >= threshold


def decide(day, counts):
    """Apply the frozen precedence at one scheduled look.

    Returns dict(status="continue"|"terminal", outcome, winner, probabilities, counts).
    """
    looks = {d: (sup, eq) for d, sup, eq in LOOKS}
    if day not in looks:
        raise ValueError("looks happen only on days 14, 21 and 28")
    superiority, equivalence = looks[day]
    final = day == LOOKS[-1][0]
    p = probabilities(counts)
    result = dict(day=day, counts={r: tuple(c) for r, c in counts.items()}, probabilities=p,
                  status="continue", outcome=None, winner=None)
    if min(s + f for s, f in counts.values()) < MINIMUM_PER_ARM:
        if final:
            result.update(status="terminal", outcome="insufficient evidence")
        return result
    if _meets(p["variant_superior"], superiority, p["error"]):
        result.update(status="terminal", outcome="repeated benefit", winner=VARIANT)
    elif _meets(p["baseline_superior"], superiority, p["error"]):
        result.update(status="terminal", outcome="repeated benefit", winner=BASELINE)
    elif _meets(p["equivalent"], equivalence, p["error"]):
        result.update(status="terminal", outcome="no meaningful difference detected")
    elif final:
        promising = _meets(p["variant_ahead"], PROMISING, p["error"])
        result.update(status="terminal", outcome="promising" if promising else "insufficient evidence")
    return result


def judge(counts_by_day):
    """Run the looks in order on {day: counts} snapshots; stop at the first terminal look."""
    looks = []
    for day, _, _ in LOOKS:
        if day not in counts_by_day:
            break
        looks.append(decide(day, counts_by_day[day]))
        if looks[-1]["status"] == "terminal":
            break
    final = looks[-1] if looks and looks[-1]["status"] == "terminal" else None
    return dict(looks=looks, outcome=final and final["outcome"], winner=final and final["winner"],
                decision_day=final and final["day"])
