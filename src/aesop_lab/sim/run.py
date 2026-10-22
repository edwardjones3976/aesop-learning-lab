"""Run scenario rows on the fast path in parallel, with an engine parity sample on every run."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import math
import statistics
import subprocess
import time
from pathlib import Path

from aesop_lab.contrast import protocol
from aesop_lab.sim import fastpath, learner, replay
from aesop_lab.sim.scenario import is_v1, scenario_hash

Z95 = 1.6448536269514722
CHUNK = 25


def wilson(k: int, n: int) -> tuple[float, float]:
    """One-sided 95% Wilson (lower, upper) bounds."""
    if n == 0:
        return 0.0, 1.0
    p, z = k / n, Z95
    centre, half = p + z * z / (2 * n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - half) / (1 + z * z / n)), min(1.0, (centre + half) / (1 + z * z / n))


def verdict_class(result: dict, true_gap: float) -> str:
    """Section 3b: judged against this learner's own causal gap, never the observed one."""
    outcome = result["outcome"]
    if outcome in (None, "insufficient evidence"):
        return "neutral"
    if outcome == "no meaningful difference detected":
        return "wrong" if abs(true_gap) >= protocol.MARGIN else "correct"
    # v1 "promising" carries no winner because it can only favour the variant.
    favoured = result["winner"] or protocol.VARIANT
    if true_gap == 0:
        return "wrong"
    better = protocol.VARIANT if true_gap > 0 else protocol.BASELINE
    return "correct" if favoured == better else "wrong"


def _chunk(job: tuple[dict, int, int, int]) -> list[dict]:
    scenario, seed, start, stop = job
    rows = []
    for index in range(start, stop):
        trajectory = learner.simulate(scenario, seed, index)
        result = fastpath.judge(trajectory, scenario["design"])
        last = result["looks"][-1] if result["looks"] else None
        rows.append(dict(
            seed=seed, index=index, true_gap=trajectory.true_gap, outcome=result["outcome"],
            winner=result["winner"], decision_day=result["decision_day"],
            verdict=verdict_class(result, trajectory.true_gap), abstained=result["abstained"],
            eligible=last and {r: sum(c) for r, c in last["counts"].items()},
            studied=len(trajectory.units), answered=len(trajectory.answers),
            dropout_day=trajectory.dropout_day))
    return rows


def _parity_one(job: tuple[dict, int, int]) -> dict | None:
    scenario, seed, index = job
    trajectory = learner.simulate(scenario, seed, index)
    problems = replay.compare(fastpath.judge(trajectory),
                              replay.engine_judge(trajectory, scenario["design"]["units_per_day"]))
    return dict(seed=seed, index=index, problems=problems) if problems else None


def parity_sample(scenario: dict, count: int, pool=None) -> dict:
    """Replay a stratified sample (spread over seeds and indices) through the real engine."""
    seeds, per_seed = scenario["learners"]["seeds"], scenario["learners"]["per_seed"]
    count = min(count, len(seeds) * per_seed)
    # Round-robin over every seed; within a seed, indices spread evenly. Distinct by construction.
    rounds = -(-count // len(seeds)) if count else 0
    stride = max(1, per_seed // rounds) if rounds else 1
    picks = [(scenario, seeds[k % len(seeds)], ((k // len(seeds)) * stride) % per_seed) for k in range(count)]
    results = (pool.map(_parity_one, picks) if pool else map(_parity_one, picks))
    return dict(checked=len(picks), mismatches=[r for r in results if r])


def summarize(scenario: dict, rows: list[dict], parity: dict, seconds: float) -> dict:
    n = len(rows)
    count = lambda pred: sum(1 for r in rows if pred(r))
    wrong, correct = count(lambda r: r["verdict"] == "wrong"), count(lambda r: r["verdict"] == "correct")
    decided = sorted(r["decision_day"] for r in rows if r["outcome"] not in (None, "insufficient evidence"))
    eligible = [min(r["eligible"].values()) for r in rows if r["eligible"]]
    gaps = [r["true_gap"] for r in rows]
    by_seed = {}
    for r in rows:
        by_seed.setdefault(r["seed"], []).append(r["verdict"])
    return dict(
        id=scenario["id"], hash=scenario_hash(scenario), learners=n,
        outcome_shares={o: count(lambda r, o=o: r["outcome"] == o) / n for o in protocol.OUTCOMES},
        wrong=wrong, wrong_upper=wilson(wrong, n)[1], correct=correct, correct_lower=wilson(correct, n)[0],
        wrong_ok=wilson(wrong, n)[1] < 0.05, abstained=count(lambda r: r["abstained"]),
        usable=correct / n,
        median_decision_day=statistics.median(decided) if decided else None,
        median_min_eligible=statistics.median(eligible) if eligible else None,
        true_gap_mean=statistics.fmean(gaps), true_gap_sd=statistics.pstdev(gaps),
        reversed_share=count(lambda r: r["true_gap"] < 0) / n,
        dropped=count(lambda r: r["dropout_day"] is not None),
        wrong_by_seed={s: v.count("wrong") for s, v in sorted(by_seed.items())},
        parity=parity, parity_ok=not parity["mismatches"], seconds=seconds)


def run_scenario(scenario: dict, pool=None, parity: int = 50) -> tuple[dict, list[dict]]:
    """One row. Pass one ProcessPoolExecutor for a whole run so worker caches stay warm."""
    started = time.monotonic()
    per_seed = scenario["learners"]["per_seed"]
    jobs = [(scenario, seed, start, min(start + CHUNK, per_seed))
            for seed in scenario["learners"]["seeds"] for start in range(0, per_seed, CHUNK)]
    chunks = pool.map(_chunk, jobs) if pool else map(_chunk, jobs)
    rows = [r for chunk in chunks for r in chunk]
    if parity and is_v1(scenario):
        checked = parity_sample(scenario, parity, pool)
    else:
        # Candidate designs exist only in the fast path; v1 rows carry the engine check.
        checked = dict(checked=0, mismatches=[], skipped="design is not protocol v1")
    return summarize(scenario, rows, checked, time.monotonic() - started), rows


def make_pool(workers: int):
    return ProcessPoolExecutor(workers) if workers > 1 else None


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              cwd=Path(__file__).resolve().parents[3]).stdout.strip() or "unknown"
    except OSError:
        return "unknown"
