"""Synthetic learners: event streams from a model that is independent of the estimator.

A trajectory is everything the product would see (study times, answers, declarations)
plus the truth the product never sees (each learner's own causal gap). The same
trajectory is judged by the fast path and replayed through the real engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import json
import math
import random

from aesop_lab.content.micro_unit import parse_micro_unit_pack
from aesop_lab.contrast import protocol
from aesop_lab.contrast.protocol import BASELINE, VARIANT, ORDER_V1

START = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
PACK_ID = "simulation-order-v1"
STUDY_SPAN_DAYS = 22  # protocol v1: nothing studied after day zero + 21 can be checked by the day-28 cutoff


def study_span(design: dict) -> int:
    """Days of study that can still reach the final look: last look - 7 + 1."""
    return design["looks"][-1] - CHECK_DAY + 1
CHECK_DAY = 7


@dataclass
class Unit:
    unit_id: str
    position: int
    role: str
    studied_at: datetime
    p_baseline: float  # truth: delayed recall at day 7 under each method, before behaviour
    p_variant: float


@dataclass
class Answer:
    unit_id: str
    at: datetime
    correct: bool
    outside_study: str  # "none" or "some", as the learner declares it
    disputed: bool = False  # the learner flags the marking as wrong (the product can observe this)


@dataclass
class Trajectory:
    scenario_id: str
    seed: int
    index: int
    identity: str
    units: list[Unit] = field(default_factory=list)
    answers: list[Answer] = field(default_factory=list)
    dropout_day: int | None = None

    @property
    def true_gap(self) -> float:
        """This learner's own causal gap, variant minus baseline, in recall probability."""
        if not self.units:
            return 0.0
        return math.fsum(u.p_variant - u.p_baseline for u in self.units) / len(self.units)


def learner_rng(scenario_id: str, seed: int, index: int) -> random.Random:
    digest = hashlib.sha256(json.dumps([scenario_id, seed, index]).encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


@lru_cache(maxsize=8)
def neutral_pack(units: int):
    methods = (ORDER_V1.baseline, ORDER_V1.variant)
    return parse_micro_unit_pack({
        "kind": "micro_unit", "schema_version": "micro-unit-pack/1", "pack_id": PACK_ID,
        "methods": [{"id": m, "name": m, "description": f"simulated {m}"} for m in methods],
        "units": [{
            "id": f"u{i:03d}", "target": {"word": f"w{i:03d}", "gloss": f"g{i:03d}"},
            "variants": {m: f"simulated {m} lesson {i}" for m in methods},
            "check": {"id": f"u{i:03d}-day7", "family_id": f"u{i:03d}-recall",
                      "prompt": f"Give the meaning of w{i:03d}.",
                      "answer_key": {"status": "candidate", "accepted": [f"g{i:03d}"]},
                      "check_delay_days": 7, "held_out": True},
        } for i in range(units)],
    })


def engine_order(identity: str, units: int) -> list[str]:
    """The engine's per-learner shuffled unit order (MicroUnitEngine._ordered_units)."""
    ids = [u.id for u in neutral_pack(units).units]
    seed = int.from_bytes(hashlib.sha256(json.dumps([identity, PACK_ID, "unit-order"]).encode()).digest(), "big")
    random.Random(seed).shuffle(ids)
    return ids


def engine_roles(identity: str, count: int) -> list[str]:
    """Frozen block roles for positions 0..count-1 (protocol section 3)."""
    roles = []
    for block in range((count + 3) // 4):
        roles.extend(protocol.block_roles(protocol.block_seed(identity, PACK_ID, ORDER_V1.contrast_id, block)))
    return roles[:count]


def invlogit(x: float) -> float:
    return 1 / (1 + math.exp(-x))


class RecallModel:
    """P(correct at delay) per arm for one learner; draws its own latent traits."""

    def __init__(self, spec: dict, rng: random.Random):
        self.kind = spec["kind"]
        self.spec = spec
        if self.kind == "bernoulli":
            base = rng.betavariate(*spec.get("baseline", [12, 8]))
            gap = spec.get("gap_points", 0.0)
            self.fixed = {BASELINE: base, VARIANT: min(0.98, max(0.02, base + gap))}
            return
        self.ability = rng.gauss(0, spec.get("ability_sd", 0.8))
        effect = rng.gauss(spec.get("method_logit_mean", 0.0), spec.get("method_logit_sd", 0.3))
        if rng.random() < spec.get("reversed_share", 0.0):
            effect = -effect
        self.effect = effect
        lo, hi = spec.get("half_life_days", [7, 21])
        self.half_life = math.exp(rng.uniform(math.log(lo), math.log(hi)))
        self.decay = rng.uniform(*spec.get("decay", [0.2, 0.5]))
        self.concepts: dict[int, float] = {}
        self.rng = rng

    def item(self, position: int, role: str) -> tuple[float, float]:
        """(difficulty, concept effect) for the unit at an engine position.

        arm_difficulty_shift makes the items that land in the variant arm harder: an item
        imbalance, not a method effect, so it changes both arms' truth for that unit equally.
        """
        if self.kind == "bernoulli":
            return 0.0, 0.0
        size = self.spec.get("concept_size", 4)
        concept = position // size
        if concept not in self.concepts:
            self.concepts[concept] = self.rng.gauss(0, self.spec.get("concept_sd", 0.3))
        shift = self.spec.get("arm_difficulty_shift", 0.0) if role == VARIANT else 0.0
        return self.rng.gauss(0, self.spec.get("difficulty_sd", 0.8)) + shift, self.concepts[concept]

    def recall(self, role: str, delay_days: float, item: tuple[float, float], studied_rank: int,
               boost: float = 0.0) -> float:
        if self.kind == "bernoulli":
            return self.fixed[role]
        difficulty, concept = item
        effect = 0.0
        if role == VARIANT:
            # Expertise drift: the gap moves as the learner studies more units.
            # Novelty: an extra boost for the first units that fades with half-life in units.
            novelty = self.spec.get("novelty_logit", 0.0) * 2 ** (
                -studied_rank / self.spec.get("novelty_half_life_units", 15))
            effect = self.effect + self.spec.get("drift_logit_per_unit", 0.0) * studied_rank + novelty
        strength = self.spec.get("intercept_logit", 1.0) + self.ability - difficulty - concept + effect + boost
        if self.kind == "half-life":
            ratio = self.spec.get("variant_half_life_ratio", 1.0) if role == VARIANT else 1.0
            return 2 ** (-delay_days / (self.half_life * ratio)) * invlogit(strength)
        return invlogit(strength - self.decay * math.log1p(delay_days))


def simulate(scenario: dict, seed: int, index: int) -> Trajectory:
    """One learner's full event stream; deterministic in (scenario id, seed, index)."""
    rng = learner_rng(scenario["id"], seed, index)
    behaviour, per_day = scenario["behaviour"], scenario["design"]["units_per_day"]
    identity = f"sim-{scenario['id']}-{seed}-{index}"
    model = RecallModel(scenario["model"], rng)
    span = study_span(scenario["design"])
    total = per_day * span
    order, roles = engine_order(identity, total), engine_roles(identity, total)
    trajectory = Trajectory(scenario["id"], seed, index, identity)

    # Long enough that even a late first active day keeps its full study span and check window.
    horizon = 4 * span + 30
    active = [rng.random() >= behaviour["missed_day_rate"] for _ in range(horizon)]
    first = active.index(True) if True in active else horizon
    recent: list[bool] = []
    unit_items: dict[str, tuple[float, float]] = {}
    pending: list[tuple[datetime, Unit, float]] = []
    studied = 0
    for day in range(horizon):
        if not active[day]:
            continue
        # Dropout is drawn at the start of an active day; that day is not studied.
        hazard = behaviour["dropout_hazard"] + behaviour["frustration_hazard"] * (
            sum(not c for c in recent[-3:]) / 3 if recent else 0.0)
        if day > first and rng.random() < hazard:
            trajectory.dropout_day = day
            break
        day_start = START + timedelta(days=day)
        # Answers that fell on missed days arrive at the same time on this active day.
        due = sorted((a for a in pending if a[0] < day_start + timedelta(days=1)), key=lambda a: a[0])
        for at, unit, boost in due:
            pending.remove((at, unit, boost))
            if at < day_start:
                at += timedelta(days=(day_start.date() - at.date()).days)
            delay = (at - unit.studied_at).total_seconds() / 86400
            p = model.recall(unit.role, delay, unit_items[unit.unit_id], unit.position, boost)
            correct = rng.random() < p
            rejected = False
            if correct and rng.random() < behaviour["false_negative_rate"][unit.role]:
                correct, rejected = False, True
            declared = "some" if boost and rng.random() < behaviour["outside_declared_share"] else "none"
            # Disputes draw only when enabled, so existing scenarios replay unchanged.
            disputed = False
            if rejected and behaviour["dispute_rate"]:
                disputed = rng.random() < behaviour["dispute_rate"]
            elif not correct and not rejected and behaviour["dispute_false_rate"]:
                disputed = rng.random() < behaviour["dispute_false_rate"]
            trajectory.answers.append(Answer(unit.unit_id, at, correct, declared, disputed))
            recent.append(correct)
        if day > first + span - 1 or studied >= total:
            continue
        for slot in range(per_day):
            if studied >= total:
                break
            at = day_start + timedelta(minutes=5 * slot)
            role = roles[studied]
            item = model.item(studied, role)
            unit = Unit(order[studied], studied, role, at,
                        model.recall(BASELINE, CHECK_DAY, item, studied),
                        model.recall(VARIANT, CHECK_DAY, item, studied))
            unit_items[unit.unit_id] = item
            trajectory.units.append(unit)
            studied += 1
            expected = unit.p_variant if role == VARIANT else unit.p_baseline
            skip = (1 - behaviour["answer_rate"]) + behaviour["mnar_slope"] * (1 - expected) + behaviour["arm_skip"][role]
            if rng.random() < skip:
                continue
            late = rng.random() < behaviour["late_rate"]
            lo, hi = behaviour["late_delay_days" if late else "answer_delay_days"]
            boost = behaviour["outside_boost_logit"] if rng.random() < behaviour["outside_study_rate"][role] else 0.0
            pending.append((at + timedelta(days=rng.uniform(lo, hi)), unit, boost))
    return trajectory

