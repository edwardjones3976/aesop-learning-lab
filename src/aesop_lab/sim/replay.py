"""Replay a trajectory through the real MicroUnitEngine (in-memory SQLite) and compare to the fast path."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import sqlite3
import tempfile

from aesop_lab.contrast.protocol import ORDER_V1
from aesop_lab.micro.engine import MicroUnitEngine
from aesop_lab.sim import learner
from aesop_lab.storage.sqlite import SQLiteStore

_TEMPLATE: list[sqlite3.Connection] = []


def memory_store() -> SQLiteStore:
    """A store on a private in-memory copy of one migrated template (simulation only)."""
    if not _TEMPLATE:
        path = Path(tempfile.mkdtemp(prefix="aesop-sim-")) / "template.sqlite3"
        SQLiteStore(path).close()
        _TEMPLATE.append(sqlite3.connect(path))
    store = SQLiteStore.__new__(SQLiteStore)
    store.path = Path("simulated-learner")
    store.connection = sqlite3.connect(":memory:")
    _TEMPLATE[0].backup(store.connection)
    store.connection.row_factory = sqlite3.Row
    store.connection.execute("PRAGMA foreign_keys = ON")
    return store


def engine_judge(trajectory, units_per_day: int) -> dict:
    """Study and answer in time order on the real engine, then read contrast_status at day 28 + 1 h."""
    if not trajectory.units:
        return dict(outcome=None, winner=None, decision_day=None, looks=[])
    pack = learner.neutral_pack(units_per_day * learner.STUDY_SPAN_DAYS)  # replay is for v1 designs only
    clock = [learner.START]
    store = memory_store()
    try:
        store.confirm_consent(learner.START)
        with store.connection:
            store.connection.execute("INSERT INTO learner_identity VALUES (1, ?)", (trajectory.identity,))
        engine = MicroUnitEngine(pack, store, lambda: clock[0], daily_limit=units_per_day, contrast=ORDER_V1)
        if [u.id for u in engine._ordered_units()][:len(trajectory.units)] != [u.unit_id for u in trajectory.units]:
            raise AssertionError("simulated unit order differs from the engine's")
        events = [(u.studied_at, 0, u) for u in trajectory.units] + [(a.at, 1, a) for a in trajectory.answers]
        gloss = {u.id: u.target.gloss for u in pack.units}
        for at, kind, item in sorted(events, key=lambda e: (e[0], e[1])):
            clock[0] = at
            if kind == 0:
                lesson = engine.start_unit(item.unit_id)
                if lesson["method_id"] != ORDER_V1.method(item.role) and _is_judged(engine, at):
                    raise AssertionError(f"engine assigned {lesson['method_id']} to {item.unit_id}")
                engine.complete_unit(item.unit_id)
            else:
                engine.answer_check(item.unit_id, gloss[item.unit_id] if item.correct else "no idea",
                                    outside_study=item.outside_study)
        day_zero = min(u.studied_at for u in trajectory.units)
        clock[0] = day_zero + timedelta(days=28, hours=1)
        return engine.contrast_status()
    finally:
        store.close()


def _is_judged(engine, at) -> bool:
    """Before a terminal decision the engine must follow the frozen block roles exactly."""
    return engine.contrast_status()["outcome"] is None


def compare(fast: dict, slow: dict, tolerance: float = 1e-6) -> list[str]:
    """Differences between fast-path and engine judgements; empty means parity."""
    problems = []
    for key in ("outcome", "decision_day"):
        if fast[key] != slow[key]:
            problems.append(f"{key}: fast {fast[key]!r} vs engine {slow[key]!r}")
    winner = slow["winner"] and ("variant" if slow["winner"] == ORDER_V1.variant else "baseline")
    if fast["winner"] != winner:
        problems.append(f"winner: fast {fast['winner']!r} vs engine {winner!r}")
    if len(fast["looks"]) != len(slow["looks"]):
        problems.append(f"looks: fast {len(fast['looks'])} vs engine {len(slow['looks'])}")
    for f, s in zip(fast["looks"], slow["looks"]):
        if f["counts"] != s["counts"]:
            problems.append(f"day {f['day']} counts: fast {f['counts']} vs engine {s['counts']}")
        if f["excluded"] != s["excluded"]:
            problems.append(f"day {f['day']} exclusions: fast {f['excluded']} vs engine {s['excluded']}")
        for name, value in f["probabilities"].items():
            if name != "error" and abs(value - s["probabilities"][name]) > tolerance:
                problems.append(f"day {f['day']} {name}: {value} vs {s['probabilities'][name]}")
    return problems
