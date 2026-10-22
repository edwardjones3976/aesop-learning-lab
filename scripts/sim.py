"""One simulator for Aesop (simulation round 2): run scenario rows, check engine parity, write one report.

SIMULATION ONLY: synthetic learners from a model independent of the estimator.

    py scripts/sim.py run round1-gate hard-learner --out DIR [--workers 4] [--parity 50]
    py scripts/sim.py parity hard-learner --learners 100
    py scripts/sim.py list
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aesop_lab.contrast import protocol  # noqa: E402
from aesop_lab.sim import run as sim_run, scenario as scenarios  # noqa: E402


def pct(x) -> str:
    return "–" if x is None else f"{x:.1%}"


def report_html(summaries: list[dict], meta: dict) -> str:
    ok = all(s["wrong_ok"] and s["parity_ok"] for s in summaries)
    rows = "".join(
        f"<tr><th scope=row>{html.escape(s['id'])}</th><td>{s['true_gap_mean']:+.3f} ± {s['true_gap_sd']:.3f}"
        f"<div class=muted>{s['reversed_share']:.0%} reversed</div></td>"
        f"<td class={'ok' if s['wrong_ok'] else 'bad'}>{s['wrong']} / {s['learners']}<div class=muted>upper {pct(s['wrong_upper'])}</div></td>"
        f"<td>{s['correct']} ({pct(s['correct'] / s['learners'])})</td>"
        + "".join(f"<td>{pct(s['outcome_shares'][o])}</td>" for o in protocol.OUTCOMES)
        + f"<td>{s['median_decision_day'] or '–'}</td><td>{s['median_min_eligible']}</td>"
        f"<td class={'ok' if s['parity_ok'] else 'bad'}>{s['parity']['checked'] - len(s['parity']['mismatches'])}/{s['parity']['checked']}</td></tr>"
        for s in summaries)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Simulation Report</title>
<style>
:root {{ --bg:#fbfbfa; --fg:#1d1d1f; --muted:#5f5f66; --rule:#e2e2e6; --ok:#1f7a4d; --bad:#b3261e; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#16161a; --fg:#ececf1; --muted:#a3a3ad; --rule:#2c2c33; --ok:#7fd1a3; --bad:#ff8a80; }} }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, sans-serif; margin:0; padding:24px 16px; }}
main {{ max-width:1100px; margin:0 auto; }} .muted {{ color:var(--muted); font-size:.85em; }}
table {{ border-collapse:collapse; display:block; overflow-x:auto; margin:14px 0; }} th, td {{ border:1px solid var(--rule); padding:5px 8px; text-align:left; vertical-align:top; }}
.ok {{ color:var(--ok); }} .bad {{ color:var(--bad); font-weight:700; }} .verdict {{ font-size:1.2rem; font-weight:700; }}
</style></head><body><main>
<h1>Simulation report</h1>
<p class="verdict {'ok' if ok else 'bad'}">{'No row exceeds 5% wrong calls, and the engine agrees on every sampled learner' if ok else 'At least one row has too many wrong calls or an engine mismatch'}</p>
<p class="muted">Simulation only. A wrong call is judged against each learner's <i>own</i> true gap (decision section 3b): a directional call for the arm that is worse for them, or "no meaningful difference" when their gap is at least {protocol.MARGIN:.0%}. Bounds are one-sided 95% Wilson; a row passes when the upper bound is below 5%. Git {html.escape(meta['git'])}; policy {protocol.POLICY_VERSION}; {meta['learners']} learners in {meta['seconds']:.0f} s with {meta['workers']} workers.</p>
<table><thead><tr><th>Row</th><th>True gap (mean ± sd)</th><th>Wrong calls</th><th>Correct calls</th>{''.join(f'<th>{html.escape(o)}</th>' for o in protocol.OUTCOMES)}<th>Median decision day</th><th>Median eligible, smaller arm</th><th>Engine parity</th></tr></thead><tbody>{rows}</tbody></table>
<p class="muted">Each row's scenario hash, per-seed wrong counts and every learner are in report.json.</p>
</main></body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("scenarios", nargs="+")
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--workers", type=int, default=4)
    run.add_argument("--parity", type=int, default=50, help="engine-replayed learners per row (at least 50)")
    check = sub.add_parser("parity")
    check.add_argument("scenarios", nargs="+")
    check.add_argument("--learners", type=int, default=100)
    sub.add_parser("list")
    args = parser.parse_args()

    if args.command == "list":
        for name in scenarios.available():
            print(name, [s["id"] for s in scenarios.load(name)])
        return 0
    rows = [s for name in args.scenarios for s in scenarios.load(name)]
    if args.command == "parity":
        failed = 0
        for scenario in rows:
            result = sim_run.parity_sample(scenario, args.learners)
            failed += bool(result["mismatches"])
            print(f"{scenario['id']}: {result['checked'] - len(result['mismatches'])}/{result['checked']} agree")
            for m in result["mismatches"][:3]:
                print("  ", m)
        return 1 if failed else 0
    if args.parity < 50:
        parser.error("--parity must be at least 50 (decision section 2)")
    if (args.out / "report.json").exists():
        parser.error(f"{args.out} already holds a report: use a fresh folder")
    started = time.monotonic()
    summaries, learners = [], {}
    pool = sim_run.make_pool(args.workers)
    for scenario in rows:
        summary, learner_rows = sim_run.run_scenario(scenario, pool, args.parity)
        summaries.append(summary)
        learners[scenario["id"]] = learner_rows
        print(f"{scenario['id']}: wrong {summary['wrong']}/{summary['learners']} (upper {summary['wrong_upper']:.1%}), "
              f"parity {summary['parity']['checked'] - len(summary['parity']['mismatches'])}/{summary['parity']['checked']}, "
              f"{summary['seconds']:.0f} s", flush=True)
    if pool:
        pool.shutdown()
    meta = dict(git=sim_run.git_sha(), learners=sum(s["learners"] for s in summaries),
                seconds=time.monotonic() - started, workers=args.workers,
                scenarios={s["id"]: s for s in rows})
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_text(json.dumps(
        dict(meta=meta, summaries=summaries, learners=learners), indent=1, default=str), encoding="utf-8")
    (args.out / "report.html").write_text(report_html(summaries, meta), encoding="utf-8")
    print(f"report: {args.out / 'report.html'} ({meta['seconds']:.0f} s)")
    # 2: the fast path disagreed with the engine; 3: a row's wrong-call bound reached 5%.
    if not all(s["parity_ok"] for s in summaries):
        return 2
    return 0 if all(s["wrong_ok"] for s in summaries) else 3


if __name__ == "__main__":
    raise SystemExit(main())
