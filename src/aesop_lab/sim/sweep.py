"""Compare candidate designs across scenario rows (decision section 3: the design sweep).

The decider: among designs whose wrong-call Wilson upper bound stays below 5% on every
row, prefer the one that gives the most learners a correct, usable answer on realistic
gaps, then the earliest median decision day. Symmetry (+g vs -g) is reported beside it.
"""
from __future__ import annotations

import copy
import re
import json
import statistics
from pathlib import Path

from aesop_lab.sim.scenario import ScenarioError, normalize

DESIGN_DIR = Path(__file__).parent / "designs"


def load_designs(name_or_path: str | Path) -> dict:
    path = Path(name_or_path)
    if not path.suffix:
        path = DESIGN_DIR / f"{name_or_path}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "sim-designs/1" or not data.get("designs"):
        raise ScenarioError("a designs file needs schema sim-designs/1 and a designs list")
    return data


def apply_design(row: dict, design_id: str, overrides: dict) -> dict:
    """The row under a candidate design; the result is validated like any scenario."""
    raw = copy.deepcopy(row)
    raw["id"] = f"{design_id}::{row['id']}"
    raw["design"] = {**raw["design"], **overrides}
    return normalize(raw)


def summarize(design_id: str, summaries: list[dict]) -> dict:
    """One design across rows: the worst wrong-call bound, and usable correct answers on realistic rows."""
    rows = {s["id"].split("::", 1)[1]: s for s in summaries}
    worst = max(summaries, key=lambda s: s["wrong_upper"])
    # Gap rows (gapN / minusN) from any suite measure usable answers; other rows are traps.
    realistic = {rid.split("/", 1)[1]: s for rid, s in rows.items()
                 if re.fullmatch(r"(gap|minus)\d+", rid.split("/", 1)[-1])}
    usable = {name: s["usable"] for name, s in realistic.items()}
    symmetry = {g: abs(usable.get(f"gap{g}", 0) - usable.get(f"minus{g}", 0))
                for g in (5, 10) if f"gap{g}" in usable and f"minus{g}" in usable}
    days = [s["median_decision_day"] for name, s in realistic.items() if s["median_decision_day"] and name != "gap0"]
    return dict(
        design=design_id, safe=all(s["wrong_ok"] for s in summaries),
        worst_row=worst["id"].split("::", 1)[1], worst_wrong_upper=worst["wrong_upper"],
        usable=usable, mean_usable_nonzero=statistics.fmean(v for k, v in usable.items() if k != "gap0") if usable else 0.0,
        symmetry_gap=symmetry, median_decision_day=statistics.median(days) if days else None,
        abstained=sum(s["abstained"] for s in summaries), learners=sum(s["learners"] for s in summaries))


def rank(designs: list[dict]) -> list[dict]:
    """Safe designs first, then the most usable answers, then the earliest decisions."""
    return sorted(designs, key=lambda d: (not d["safe"], -d["mean_usable_nonzero"], d["median_decision_day"] or 999))
