"""Seeded recovery under ideal independent outcomes; no human efficacy claim.

Run: PYTHONPATH=src python scripts/method_ranking_recovery.py
One new unit per day (explicit pacing assumption), first fresh check at day 7.
Only received checks update assignment; seven assignments can be pending.
"""

import argparse
from collections import deque
import math
import random

from aesop_lab.ranking.method_ranking import rank_methods


CHECKPOINTS = (8, 16, 32, 64, 128, 256, 512, 1024)
SCENARIOS = {
    "large": (0.80, 0.60, 0.45, 0.30),
    "medium": (0.80, 0.65, 0.55, 0.45),
    "small": (0.65, 0.60, 0.55, 0.50),
}


def choose_method(alpha, beta, assigned, rng):
    """Two assignments per arm, then 20% uniform + 80% Thompson sampling."""
    least = min(assigned)
    if least < 2:
        return rng.choice([i for i, count in enumerate(assigned) if count == least])
    if rng.random() < 0.2:
        return rng.randrange(len(alpha))
    samples = [rng.betavariate(a, b) for a, b in zip(alpha, beta)]
    return max(range(len(samples)), key=samples.__getitem__)


def wilson(successes, total):
    if not total:
        return "n/a"
    p, z = successes / total, 1.96
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    lower, upper = max(0.0, center - half), min(1.0, center + half)
    return f"{100 * p:.1f}% [{100 * lower:.1f}, {100 * upper:.1f}]"


def recover(probabilities, learners, seed, draws, units_per_day=1):
    correct = {n: 0 for n in CHECKPOINTS}
    clear = {n: 0 for n in CHECKPOINTS}
    wrong_clear = {n: 0 for n in CHECKPOINTS}
    ever_clear = ever_wrong = 0
    first_clear_wrong = first_clear_count = 0
    # Rotate true-best identity to prevent sorted-ID tie breaking helping recovery.
    for learner in range(learners):
        shift = learner % len(probabilities)
        truth = probabilities[shift:] + probabilities[:shift]
        best = truth.index(max(truth))
        rng = random.Random(seed + learner * 100003)
        alpha, beta = [1.0] * len(truth), [1.0] * len(truth)
        assigned = [0] * len(truth)
        histories = {str(i): [] for i in range(len(truth))}
        pending = deque()
        count = day = 0
        had_clear = had_wrong = False
        while count < CHECKPOINTS[-1]:
            while pending and pending[0][0] <= day and count < CHECKPOINTS[-1]:
                _, method = pending.popleft()
                match = rng.random() < truth[method]
                histories[str(method)].append((match, 1.0))
                alpha[method] += match
                beta[method] += not match
                count += 1
                if count in correct:
                    result = rank_methods(histories, seed=seed + learner * 31 + count,
                                          draws=draws)
                    right = int(result.methods[0].method) == best
                    correct[count] += right
                    if result.confidence == "clear":
                        clear[count] += 1
                        wrong_clear[count] += not right
                        if not had_clear:
                            first_clear_count += 1
                            first_clear_wrong += not right
                        had_clear = True
                        had_wrong |= not right
            for _ in range(units_per_day):
                method = choose_method(alpha, beta, assigned, rng)
                assigned[method] += 1
                pending.append((day + 7, method))
            day += 1
        ever_clear += had_clear
        ever_wrong += had_wrong
    return correct, clear, wrong_clear, ever_clear, ever_wrong, first_clear_count, first_clear_wrong


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--learners", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20261021)
    parser.add_argument("--draws", type=int, default=2048)
    parser.add_argument("--units-per-day", type=int, default=1)
    args = parser.parse_args()
    if args.learners < 1 or args.draws < 256 or args.units_per_day < 1:
        parser.error("positive learners/units-per-day and draws >= 256 required")
    print(f"learners={args.learners}, seed={args.seed}, draws={args.draws}, "
          f"units/day={args.units_per_day}; day zero = first study", flush=True)
    print("| Gap | Checks | Day | True best ranked first (95% Wilson) | Clear labels | Wrong / clear |", flush=True)
    print("|---|---:|---:|---|---:|---|", flush=True)
    for index, (name, probabilities) in enumerate(SCENARIOS.items()):
        correct, clear, wrong, ever, ever_wrong, first, first_wrong = recover(
            probabilities, args.learners, args.seed + index * 10000019,
            args.draws, args.units_per_day)
        for n in CHECKPOINTS:
            day = 7 + (n - 1) // args.units_per_day
            print(f"| {name} | {n} | {day} | {wilson(correct[n], args.learners)} | "
                  f"{clear[n]} | {wilson(wrong[n], clear[n])} |", flush=True)
        sustained = next((n for n in CHECKPOINTS if all(
            correct[k] / args.learners >= .8 for k in CHECKPOINTS if k >= n)), None)
        print(f"{name} truth={probabilities}; first sustained >=80% checkpoint={sustained}; "
              f"learners ever clear={ever}/{args.learners}; ever wrong clear={ever_wrong}/{args.learners}; "
              f"first-clear error={wilson(first_wrong, first)}", flush=True)


if __name__ == "__main__":
    main()
