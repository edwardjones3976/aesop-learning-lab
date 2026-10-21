"""Run the contrast protocol v1 simulation gate on the real engine; write an HTML verdict plus JSON.

SIMULATION ONLY. Synthetic learners answer from the frozen data-generating model in
docs/contrast-protocol-v1.html section 4, which is independent of the estimator. The
result says whether the fixed two-arm policy controls wrong calls and detects large
gaps for one learner in 28 days. It is not evidence about how people learn.

The clock is simulated (UTC calendar days), so a full run takes minutes, not weeks.

    py scripts/simulate_contrast_gate.py --out DIR                 # acceptance run, seeds 1-10
    py scripts/simulate_contrast_gate.py --out DIR --rerun         # the one permitted rerun, seeds 11-20
    py scripts/simulate_contrast_gate.py --out DIR --learners 5 --scenarios null,plus20

Pinned details the protocol leaves open (Cursor review of #66):
- Answer times are continuous: completion + U(7, 10) days.
- A missed calendar day has no visit at all; an answer that falls on it moves to the
  same time on the next active day.
- A dropout learner does nothing on or after the drawn day D in 1..27.
- Wilson bounds are strict: an error bound must be below its limit and a detection bound
  above it, so a rate exactly on a threshold fails.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import random
import sqlite3
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aesop_lab.content.micro_unit import parse_micro_unit_pack  # noqa: E402
from aesop_lab.contrast import protocol  # noqa: E402
from aesop_lab.contrast.protocol import ContrastSpec  # noqa: E402
from aesop_lab.micro.engine import MicroUnitEngine  # noqa: E402
from aesop_lab.storage.sqlite import SQLiteStore  # noqa: E402

SPEC = ContrastSpec("order-v1", "worked_then_retrieve", "predict_first")
START = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
UNITS_PER_DAY = 3
LEARNERS_PER_SEED = 50
ACCEPTANCE_SEEDS, RERUN_SEEDS = range(1, 11), range(11, 21)
Z95 = 1.6448536269514722
# gap = p_variant - p_baseline on the probability scale; missed/dropout only in their own rows.
SCENARIOS = {
    "null": dict(gap=0.0),
    "plus3": dict(gap=0.03),
    "minus3": dict(gap=-0.03),
    "plus10": dict(gap=0.10),
    "minus10": dict(gap=-0.10),
    "plus20": dict(gap=0.20),
    "plus10_missed_days": dict(gap=0.10, missed=0.20),
    "plus10_dropout": dict(gap=0.10, dropout=0.10),
}


def neutral_pack(units: int):
    """A content-free pack: synthetic learners never read lessons, only the engine does."""
    return parse_micro_unit_pack({
        "kind": "micro_unit", "schema_version": "micro-unit-pack/1", "pack_id": "simulation-order-v1",
        "methods": [{"id": m, "name": m, "description": f"simulated {m}"} for m in (SPEC.baseline, SPEC.variant)],
        "units": [{
            "id": f"u{i:03d}", "target": {"word": f"w{i:03d}", "gloss": f"g{i:03d}"},
            "variants": {m: f"simulated {m} lesson {i}" for m in (SPEC.baseline, SPEC.variant)},
            "check": {"id": f"u{i:03d}-day7", "family_id": f"u{i:03d}-recall",
                      "prompt": f"Give the meaning of w{i:03d}.",
                      "answer_key": {"status": "candidate", "accepted": [f"g{i:03d}"]},
                      "check_delay_days": 7, "held_out": True},
        } for i in range(units)],
    })


PACK = neutral_pack(UNITS_PER_DAY * 22)


def learner_seed(scenario: str, seed: int, index: int) -> int:
    return int.from_bytes(hashlib.sha256(json.dumps([scenario, seed, index]).encode()).digest()[:8], "big")


_TEMPLATE: list[sqlite3.Connection] = []


def memory_store() -> SQLiteStore:
    """A store on a private in-memory copy of one migrated template (no files per learner)."""
    if not _TEMPLATE:
        path = Path(tempfile.mkdtemp(prefix="aesop-gate-")) / "template.sqlite3"
        SQLiteStore(path).close()
        _TEMPLATE.append(sqlite3.connect(path))
    store = SQLiteStore.__new__(SQLiteStore)
    store.path = Path("simulated-learner")
    store.connection = sqlite3.connect(":memory:")
    _TEMPLATE[0].backup(store.connection)
    store.connection.row_factory = sqlite3.Row
    store.connection.execute("PRAGMA foreign_keys = ON")
    return store


def simulate_learner(job: tuple[str, int, int]) -> dict:
    scenario_name, seed, index = job
    scenario = SCENARIOS[scenario_name]
    rng = random.Random(learner_seed(scenario_name, seed, index))
    base = rng.betavariate(12, 8)
    truth = {SPEC.baseline: base, SPEC.variant: min(0.98, max(0.02, base + scenario["gap"]))}
    # Calendar days 0..28; a skipped day has no visit, dropout ends all visits from day D.
    active = [rng.random() >= scenario.get("missed", 0.0) for _ in range(40)]
    dropout_day = rng.randint(1, 27) if rng.random() < scenario.get("dropout", 0.0) else None
    if dropout_day is not None:
        active[dropout_day:] = [False] * (40 - dropout_day)
    pack = PACK
    clock = [START]
    store = memory_store()
    try:
        store.confirm_consent(START)
        with store.connection:
            store.connection.execute("INSERT INTO learner_identity VALUES (1, ?)",
                                     (f"gate-{scenario_name}-{seed}-{index}",))
        engine = MicroUnitEngine(pack, store, lambda: clock[0], daily_limit=UNITS_PER_DAY, contrast=SPEC)
        answers = []  # (time, unit_id)
        order = [u.id for u in engine._ordered_units()]
        studied = 0
        # Units studied after day zero + 21 cannot be checked by the day-28 cutoff, so stop there.
        first_day = active.index(True) if True in active else len(active)
        for day in range(min(first_day + 22, len(active))):
            if not active[day]:
                continue
            for slot in range(UNITS_PER_DAY):
                clock[0] = START + timedelta(days=day, minutes=5 * slot)
                unit = order[studied]
                engine.start_unit(unit)
                engine.complete_unit(unit)
                studied += 1
                if rng.random() < 0.90:
                    answers.append((clock[0] + timedelta(days=rng.uniform(7, 10)), unit))
        day_zero = START + timedelta(days=first_day if first_day < len(active) else 0)
        for at, unit in sorted(answers):
            day = (at - START).days
            while day < len(active) and not active[day]:
                day, at = day + 1, at + timedelta(days=1)
            if day >= len(active) or at > day_zero + timedelta(days=28):
                continue  # never answered, or after the final cutoff: irrelevant to every look
            clock[0] = at
            method = engine._exposures()[unit]["method_id"]
            correct = rng.random() < truth[method]
            engine.answer_check(unit, engine.units[unit].target.gloss if correct else "no idea",
                                outside_study="none")
        clock[0] = day_zero + timedelta(days=28, hours=1)
        status = engine.contrast_status()
    finally:
        store.close()
    last = status["looks"][-1] if status["looks"] else None
    return {
        "scenario": scenario_name, "seed": seed, "index": index,
        "truth": truth, "dropout_day": dropout_day, "studied": studied,
        "outcome": status["outcome"], "winner": status["winner"], "decision_day": status["decision_day"],
        "eligible_at_decision": last and {r: sum(c) for r, c in last["counts"].items()},
        "probabilities_at_decision": last and last["probabilities"],
    }


def wilson(k: int, n: int) -> tuple[float, float]:
    """One-sided 95% Wilson (lower, upper) bounds."""
    p, z = k / n, Z95
    centre, half = p + z * z / (2 * n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - half) / (1 + z * z / n)), min(1.0, (centre + half) / (1 + z * z / n)))


def classify(row: dict) -> str:
    """'correct', 'wrong' or 'neutral' relative to the true gap."""
    better = row["truth"][SPEC.variant] - row["truth"][SPEC.baseline]
    claimed = None
    if row["outcome"] == "repeated benefit":
        claimed = row["winner"]
    elif row["outcome"] == "promising":
        claimed = SPEC.variant
    if claimed is None:
        return "neutral"
    gap = SCENARIOS[row["scenario"]]["gap"]
    truly_better = SPEC.variant if gap > 0 else SPEC.baseline if gap < 0 else None
    if truly_better is None:
        return "wrong"
    return "correct" if claimed == truly_better else "wrong"


def requirements(name: str, rows: list[dict]) -> list[dict]:
    n = len(rows)
    count = lambda pred: sum(1 for r in rows if pred(r))
    claims = count(lambda r: r["outcome"] in ("repeated benefit", "promising"))
    wrong = count(lambda r: classify(r) == "wrong")
    correct = count(lambda r: classify(r) == "correct")
    better = count(lambda r: r["outcome"] == "repeated benefit")
    quiet = count(lambda r: r["outcome"] in ("no meaningful difference detected", "insufficient evidence"))

    def limit(label, k, threshold):
        upper = wilson(k, n)[1]
        return dict(requirement=label, count=k, rate=k / n, bound="upper", value=upper,
                    threshold=threshold, passed=upper < threshold)

    def floor(label, k, threshold):
        lower = wilson(k, n)[0]
        return dict(requirement=label, count=k, rate=k / n, bound="lower", value=lower,
                    threshold=threshold, passed=lower > threshold)

    def report(label, k):
        return dict(requirement=label, count=k, rate=k / n, bound=None, value=None, threshold=None, passed=None)

    if name == "null":
        return [limit('Any "better" or "promising"', claims, 0.05)]
    if name in ("plus3", "minus3"):
        return [limit('"Better" call', better, 0.05),
                limit("Wrong-direction better or promising", wrong, 0.05),
                floor('"No meaningful difference" or "insufficient"', quiet, 0.90)]
    if name == "plus20":
        return [limit("Wrong-direction calls", wrong, 0.05),
                floor('Correct "better" or "promising" by day 28', correct, 0.20)]
    return [limit("Wrong-direction better or promising", wrong, 0.05),
            report("Correct better or promising (reported)", correct)]


def summarize(name: str, rows: list[dict]) -> dict:
    outcomes = {o: sum(r["outcome"] == o for r in rows) / len(rows) for o in protocol.OUTCOMES}
    decided = [r["decision_day"] for r in rows if r["outcome"] in ("repeated benefit", "no meaningful difference detected")]
    eligible = [min(r["eligible_at_decision"].values()) for r in rows if r["eligible_at_decision"]]
    per_seed = {}
    for r in rows:
        per_seed.setdefault(r["seed"], []).append(classify(r))
    checks = requirements(name, rows)
    return {
        "scenario": name, "gap": SCENARIOS[name]["gap"], "learners": len(rows),
        "missed": SCENARIOS[name].get("missed", 0.0), "dropout": SCENARIOS[name].get("dropout", 0.0),
        "outcome_shares": outcomes,
        "early_stops": sum(d in (14, 21) for d in decided),
        "median_min_eligible_per_arm": statistics.median(eligible) if eligible else None,
        "dropped": sum(r["dropout_day"] is not None for r in rows),
        "wrong_by_seed": {s: c.count("wrong") for s, c in sorted(per_seed.items())},
        "correct_by_seed": {s: c.count("correct") for s, c in sorted(per_seed.items())},
        "requirements": checks,
        "passed": all(c["passed"] is not False for c in checks),
    }


def pct(x) -> str:
    return "–" if x is None else f"{x:.1%}"


def report_html(summaries: list[dict], config: dict) -> str:
    gate = all(s["passed"] for s in summaries)
    complete = config["official"]
    verdict = ("PASS" if gate else "FAIL") + ("" if complete else " (partial or non-default run: not a gate result)")
    rows = []
    for s in summaries:
        for i, c in enumerate(s["requirements"]):
            head = (f'<th scope=row rowspan={len(s["requirements"])}>{html.escape(s["scenario"])}'
                    f'<div class=muted>gap {s["gap"]:+.2f}</div></th>') if i == 0 else ""
            mark = "reported" if c["passed"] is None else ("pass" if c["passed"] else "FAIL")
            rule = "–" if c["bound"] is None else f'{c["bound"]} {"&lt;" if c["bound"] == "upper" else "&gt;"} {c["threshold"]:.0%}'
            rows.append(f'<tr>{head}<td>{html.escape(c["requirement"])}</td><td>{c["count"]} / {s["learners"]} ({pct(c["rate"])})</td>'
                        f'<td>{pct(c["value"])}</td><td>{rule}</td><td class="{mark.lower()}">{mark}</td></tr>')
    shares = "".join(
        f'<tr><th scope=row>{html.escape(s["scenario"])}</th>'
        + "".join(f"<td>{pct(s['outcome_shares'][o])}</td>" for o in protocol.OUTCOMES)
        + f'<td>{s["early_stops"]}</td><td>{s["median_min_eligible_per_arm"]}</td><td>{s["dropped"]}</td></tr>'
        for s in summaries)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contrast Gate Report</title>
<style>
:root {{ --bg:#fbfbfa; --fg:#1d1d1f; --muted:#5f5f66; --rule:#e2e2e6; --pass:#1f7a4d; --fail:#b3261e; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#16161a; --fg:#ececf1; --muted:#a3a3ad; --rule:#2c2c33; --pass:#7fd1a3; --fail:#ff8a80; }} }}
body {{ background:var(--bg); color:var(--fg); font:16px/1.55 system-ui, sans-serif; margin:0; padding:24px 16px; }}
main {{ max-width:960px; margin:0 auto; }} h1 {{ font-size:1.6rem; margin:0 0 4px; }} .muted {{ color:var(--muted); font-size:.9em; }}
table {{ border-collapse:collapse; display:block; overflow-x:auto; margin:16px 0; }} th, td {{ border:1px solid var(--rule); padding:6px 10px; text-align:left; vertical-align:top; }}
.verdict {{ font-size:1.3rem; font-weight:700; padding:10px 14px; border:2px solid; border-radius:8px; display:inline-block; }}
.verdict.ok, .pass {{ color:var(--pass); }} .verdict.bad, .fail {{ color:var(--fail); font-weight:700; }}
</style></head><body><main>
<h1>Contrast protocol v1: simulation gate</h1>
<p class="verdict {'ok' if gate and complete else 'bad'}">Gate: {verdict}</p>
<p class="muted">Simulation only: synthetic learners on the real micro-unit engine in frozen contrast mode (<code>{SPEC.baseline}</code> vs <code>{SPEC.variant}</code>), simulated UTC clock. {config['learners_per_seed']} learners × seeds {config['seeds'][0]}–{config['seeds'][-1]} per scenario, {UNITS_PER_DAY} units a day. Data-generating model as frozen in protocol section 4: baseline recall from Beta(12, 8), variant = baseline + gap; 90% of checks answered at completion + U(7, 10) days. Bounds are one-sided 95% Wilson; a bound exactly on its threshold fails. The AI zero-shot pretest row is a separate run and is not part of this report. Ran in {config['seconds']:.0f} s.</p>
<h2>Gate requirements</h2>
<table><thead><tr><th>Scenario</th><th>Requirement</th><th>Count</th><th>Wilson bound</th><th>Rule</th><th>Result</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>What learners would be told on day 28</h2>
<table><thead><tr><th>Scenario</th>{''.join(f'<th>{html.escape(o)}</th>' for o in protocol.OUTCOMES)}<th>Stopped on day 14 or 21</th><th>Median eligible outcomes, smaller arm</th><th>Dropped out</th></tr></thead><tbody>{shares}</tbody></table>
<p class="muted">"Insufficient evidence, so your preference decides" is the expected common answer at this dose (about 28 outcomes per arm); see protocol section 4. Per-seed counts are in the JSON.</p>
</main></body></html>
"""


def is_official(names, learners_per_seed) -> bool:
    """Only the full, pre-registered configuration is a gate result."""
    return set(names) == set(SCENARIOS) and learners_per_seed == LEARNERS_PER_SEED


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True, help="report folder, created if missing")
    parser.add_argument("--rerun", action="store_true", help="use the one permitted fresh seed set (11-20)")
    parser.add_argument("--learners", type=int, default=LEARNERS_PER_SEED, help="learners per seed (gate: 50)")
    parser.add_argument("--scenarios", default=",".join(SCENARIOS))
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    names = [n.strip() for n in args.scenarios.split(",") if n.strip()]
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown or args.learners < 1 or args.workers < 1:
        parser.error(f"unknown scenarios {unknown}" if unknown else "learners and workers must be positive")
    seeds = list(RERUN_SEEDS if args.rerun else ACCEPTANCE_SEEDS)
    if (args.out / "contrast-gate.json").exists():
        parser.error(f"{args.out} already holds a gate report: use a fresh folder")
    started = time.monotonic()
    summaries, learners = [], {}
    with ProcessPoolExecutor(args.workers) if args.workers > 1 else _Serial() as pool:
        for name in names:
            jobs = [(name, seed, i) for seed in seeds for i in range(args.learners)]
            rows = list(pool.map(simulate_learner, jobs))
            learners[name] = rows
            summaries.append(summarize(name, rows))
            print(f"{name}: {'pass' if summaries[-1]['passed'] else 'FAIL'} ({len(rows)} learners, "
                  f"{time.monotonic() - started:.0f} s)", flush=True)
    config = {"seeds": seeds, "learners_per_seed": args.learners, "scenarios": names,
              "policy_version": protocol.POLICY_VERSION, "estimator_version": protocol.ESTIMATOR_VERSION,
              "model": SCENARIOS, "seconds": time.monotonic() - started,
              "official": is_official(names, args.learners)}
    args.out.mkdir(parents=True, exist_ok=True)
    gate = all(s["passed"] for s in summaries) and config["official"]
    (args.out / "contrast-gate.json").write_text(json.dumps(
        {"gate_passed": gate, "config": config, "summaries": summaries, "learners": learners}, indent=1), encoding="utf-8")
    (args.out / "contrast-gate.html").write_text(report_html(summaries, config), encoding="utf-8")
    label = ("PASS" if gate else "FAIL") if config["official"] else "no gate verdict (partial or non-default run)"
    print(f"gate {label}: "
          f"{args.out / 'contrast-gate.html'} ({config['seconds']:.0f} s)", flush=True)
    # A failed official gate exits non-zero; exploratory runs report but do not fail.
    return 1 if config["official"] and not gate else 0


class _Serial:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    map = staticmethod(map)


if __name__ == "__main__":
    raise SystemExit(main())
