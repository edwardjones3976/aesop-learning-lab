"""Per-unit assignment and received-feedback ranking; no HTTP or UI dependencies."""
from dataclasses import asdict
from datetime import datetime, timedelta
import hashlib
import json
import random

from aesop_lab.assessment.items import normalize_answer
from aesop_lab.contrast import protocol
from aesop_lab.ranking.method_ranking import rank_methods

PROVISIONAL = "provisional (draft keys)"


class MicroUnitEngine:
    def __init__(self, pack, store, now, *, daily_limit=3, contrast=None):
        if type(daily_limit) is not int or daily_limit < 1:
            raise ValueError("daily_limit must be a positive integer")
        self.pack, self.store, self.now = pack, store, now
        self.daily_limit = daily_limit
        self.units = {u.id: u for u in pack.units}
        self.methods = sorted(m.id for m in pack.methods)
        if contrast is not None and not {contrast.baseline, contrast.variant} <= set(self.methods):
            raise ValueError("both contrast methods must be in the pack")
        # A frozen two-arm contrast replaces Thompson allocation for this pack.
        self.contrast = contrast

    def _time(self):
        at = self.now()
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("now must return an aware datetime")
        return at

    def _unit(self, unit):
        return self.units[unit if isinstance(unit, str) else unit.id]

    def _seed(self, unit_id):
        identity = self.store.learner_id()
        return int.from_bytes(hashlib.sha256(json.dumps(
            [identity, self.pack.pack_id, unit_id]).encode()).digest(), "big")

    def _exposures(self):
        return {r["unit_id"]: r for r in self.store.micro_exposures(self.pack.pack_id)}

    def _ordered_units(self):
        units = list(self.pack.units)
        random.Random(self._seed("unit-order")).shuffle(units)
        return units

    def choose_method(self, unit):
        return self._assignment(unit)[0]

    def _pack_version(self):
        return self.pack.schema_version + ":sha256:" + hashlib.sha256(repr(self.pack).encode()).hexdigest()

    def _block(self, index, ordered):
        """The frozen allocation block: the stored row if present, else computed (not stored)."""
        stored = {r["block_index"]: r for r in self.store.contrast_blocks(self.pack.pack_id, self.contrast.contrast_id)}
        if index in stored:
            return stored[index]["block_seed"], json.loads(stored[index]["allocation"])
        seed = protocol.block_seed(self.store.learner_id(), self.pack.pack_id, self.contrast.contrast_id, index)
        slots = ordered[4 * index:4 * index + 4]
        allocation = [[slots[p].id if p < len(slots) else None, self.contrast.method(role)]
                      for p, role in enumerate(protocol.block_roles(seed))]
        return seed, allocation

    def _contrast_assignment(self, unit, store):
        ordered = self._ordered_units()
        position = next(i for i, u in enumerate(ordered) if u.id == unit.id)
        index = position // 4
        provenance = dict(policy_version=protocol.POLICY_VERSION, pack_version=self._pack_version(),
                          eligible_choices=json.dumps([self.contrast.baseline, self.contrast.variant]))
        decided = self.contrast_status()
        if decided["outcome"] is not None:
            # After a terminal decision, new units get the future default and never enter the frozen finding.
            return decided["future_default"], dict(provenance, policy_branch="post-decision", assignment_seed=None)
        seed, allocation = self._block(index, ordered)
        if store:
            row = self.store.store_contrast_block(self.pack.pack_id, self.contrast.contrast_id, index, seed,
                                                  allocation, protocol.POLICY_VERSION, self._time())
            seed, allocation = row["block_seed"], json.loads(row["allocation"])
        return allocation[position % 4][1], dict(provenance, policy_branch="contrast-block",
                                                 assignment_seed=f"{seed}:{index}:{position % 4}")

    def _assignment(self, unit, store=False):
        """Read existing assignment, or compute one from current received history."""
        unit = self._unit(unit)
        exposures = self._exposures()
        if unit.id in exposures:
            return exposures[unit.id]["method_id"], None
        if self.contrast is not None:
            return self._contrast_assignment(unit, store)
        rng = random.Random(self._seed(unit.id))
        history = [r for uid, r in exposures.items()
                   if uid in self.units and self.units[uid].block == unit.block]
        counts = {m: sum(r["method_id"] == m for r in history) for m in self.methods}
        provenance = dict(assignment_seed=str(self._seed(unit.id)),
                          policy_version="thompson-80-20-warmup2-block-v1",
                          pack_version=self._pack_version())
        def assigned(method, branch, choices):
            return method, dict(provenance, policy_branch=branch,
                                eligible_choices=json.dumps(choices))
        least = min(counts.values())
        if least < 2:
            return assigned(rng.choice([m for m in self.methods if counts[m] == least]),
                            "warm-up", [m for m in self.methods if counts[m] == least])
        if rng.random() < .2:
            return assigned(rng.choice(self.methods), "uniform-20", self.methods)
        outcomes = self.outcomes_by_method()["outcomes"]
        samples = {}
        for method in self.methods:
            success = sum(correct for correct, _ in outcomes[method])
            samples[method] = rng.betavariate(1 + success, 1 + len(outcomes[method]) - success)
        return assigned(max(self.methods, key=samples.__getitem__), "thompson", self.methods)

    def _lesson(self, unit, row):
        self.store.mark_micro_unit(self.pack.pack_id, unit.id, self._time())
        return dict(kind="unit", unit_id=unit.id, method_id=row["method_id"],
                    lesson=unit.variants[row["method_id"]], provisional=PROVISIONAL)

    def next_activity(self):
        at = self._time()
        exposures = self._exposures()
        answered = {r["unit_id"] for r in self.store.micro_checks(self.pack.pack_id)}
        due = [r for r in exposures.values() if r["unit_id"] in self.units
               and r["completed_at"] and r["unit_id"] not in answered
               and at - datetime.fromisoformat(r["completed_at"]) >= timedelta(days=7)]
        if due:
            row = min(due, key=lambda r: (datetime.fromisoformat(r["completed_at"]), r["unit_id"]))
            unit = self.units[row["unit_id"]]
            return dict(kind="check", unit_id=unit.id, check_id=unit.check.id,
                        prompt=unit.check.prompt, provisional=PROVISIONAL)
        for unit in self._ordered_units():
            if unit.id in exposures and not exposures[unit.id]["completed_at"]:
                return self._lesson(unit, exposures[unit.id])
        if self._daily_count(at, exposures) >= self.daily_limit:
            return None
        for unit in self._ordered_units():
            if unit.id not in exposures:
                return dict(kind="unit", unit_id=unit.id, provisional=PROVISIONAL)
        return None

    def _daily_count(self, at, exposures):
        # A calendar day uses the timezone supplied by the caller's clock.
        return sum(datetime.fromisoformat(r["assigned_at"]).astimezone(at.tzinfo).date() == at.date()
                   for r in exposures.values())

    def start_unit(self, unit):
        self.store.require_active_learner()
        unit, at = self._unit(unit), self._time()
        self.store.learner_id()
        # Serialize assignment, warm-up counts and the daily cap across connections.
        with self.store.connection:
            self.store.connection.execute("BEGIN IMMEDIATE")
            exposures = self._exposures()
            if unit.id not in exposures and self._daily_count(at, exposures) >= self.daily_limit:
                raise ValueError("daily new-unit limit reached")
            if unit.id in exposures and exposures[unit.id]["completed_at"]:
                raise ValueError("completed unit cannot be replayed")
            method, provenance = self._assignment(unit, store=True)
            row = self.store.assign_micro_unit(self.pack.pack_id, unit.id, method, at, provenance=provenance)
            self.store.mark_micro_unit(self.pack.pack_id, unit.id, at)
        return self._lesson(unit, row)

    def complete_unit(self, unit):
        unit = self._unit(unit)
        self.store.mark_micro_unit(self.pack.pack_id, unit.id, self._time(), complete=True)
        return dict(unit_id=unit.id, provisional=PROVISIONAL)

    def answer_check(self, unit, answer, *, assisted=False, outside_study="unknown", previously_seen=False):
        unit = self._unit(unit)
        if not isinstance(answer, str) or type(assisted) is not bool:
            raise ValueError("answer must be text and assisted must be boolean")
        if outside_study not in ("none", "some", "unknown") or type(previously_seen) is not bool:
            raise ValueError("outside_study must be none, some or unknown; previously_seen must be boolean")
        # Vocabulary glosses ignore case ("Tremble" == "tremble"); spacing is normalized as elsewhere.
        match = normalize_answer(answer).casefold() in {
            normalize_answer(a).casefold() for a in unit.check.answer_key.accepted}
        row = self.store.record_micro_check(self.pack.pack_id, unit.id, unit.check.id, answer,
                                           "correct" if match else "incorrect", self._time(), assisted, outside_study, previously_seen)
        return dict(row, classification=self._classification(row, self._exposures()[unit.id]),
                    provisional=PROVISIONAL)

    @staticmethod
    def _classification(check, exposure):
        if (check.get("outside_study") == "some" or check.get("previously_seen")
                or exposure.get("reexposed_at")):
            return "contaminated"
        if check["assisted"]:
            return "assisted"
        elapsed = datetime.fromisoformat(check["occurred_at"]) - datetime.fromisoformat(exposure["completed_at"])
        if elapsed < timedelta(days=7):
            return "early"
        if elapsed > timedelta(days=14):
            return "late"
        return "eligible"

    def outcomes_by_method(self):
        outcomes = {m: [] for m in self.methods}
        excluded = {k: [] for k in ("early", "late", "assisted", "missing", "pending", "contaminated")}
        checks = {r["unit_id"]: r for r in self.store.micro_checks(self.pack.pack_id)}
        at = self._time()
        for uid, exposure in self._exposures().items():
            if uid not in self.units or not exposure["completed_at"]:
                continue
            check = checks.get(uid)
            if check:
                classification = self._classification(check, exposure)
            else:
                # Unanswered is only "missing" once the day-14 window has closed.
                open_window = at - datetime.fromisoformat(exposure["completed_at"]) <= timedelta(days=14)
                classification = "pending" if open_window else "missing"
            if classification == "eligible":
                outcomes[exposure["method_id"]].append((check["score_status"] == "correct", 1.0))
            else:
                excluded[classification].append(uid)
        return dict(outcomes=outcomes, excluded=excluded, provisional=PROVISIONAL)

    def contrast_status(self):
        """Judge the frozen contrast at each scheduled cutoff that has passed.

        Each look sees only completed units, answers and re-exposures recorded at or
        before its cutoff, so a late evaluation reproduces the on-time snapshot.
        """
        if self.contrast is None:
            raise ValueError("this engine has no contrast")
        at = self._time()
        exposures = [r for r in self._exposures().values()
                     if r["unit_id"] in self.units and r["policy_branch"] == "contrast-block"]
        checks = {r["unit_id"]: r for r in self.store.micro_checks(self.pack.pack_id)}
        roles = {self.contrast.baseline: protocol.BASELINE, self.contrast.variant: protocol.VARIANT}
        started = [datetime.fromisoformat(r["exposed_at"]) for r in exposures if r["exposed_at"]]
        day_zero = min(started) if started else None
        snapshots, excluded = {}, {}
        for day, _, _ in protocol.LOOKS:
            cutoff = day_zero and day_zero + timedelta(days=day)
            if cutoff is None or at < cutoff:
                break
            counts = {protocol.BASELINE: [0, 0], protocol.VARIANT: [0, 0]}
            dropped = {k: 0 for k in ("early", "late", "assisted", "contaminated", "unanswered")}
            for exposure in exposures:
                if not exposure["completed_at"] or datetime.fromisoformat(exposure["completed_at"]) > cutoff:
                    continue
                check = checks.get(exposure["unit_id"])
                if not check or datetime.fromisoformat(check["occurred_at"]) > cutoff:
                    dropped["unanswered"] += 1
                    continue
                known = dict(exposure)
                if known.get("reexposed_at") and datetime.fromisoformat(known["reexposed_at"]) > cutoff:
                    known["reexposed_at"] = None
                classification = self._classification(check, known)
                if classification != "eligible":
                    dropped[classification] += 1
                    continue
                counts[roles[exposure["method_id"]]][check["score_status"] != "correct"] += 1
            snapshots[day] = {role: tuple(c) for role, c in counts.items()}
            excluded[day] = dropped
        judged = protocol.judge(snapshots)
        for look in judged["looks"]:
            look["excluded"] = excluded[look["day"]]
            look["cutoff"] = (day_zero + timedelta(days=look["day"])).isoformat()
        winner = judged["winner"] and self.contrast.method(judged["winner"])
        pending = [d for d, _, _ in protocol.LOOKS if d not in snapshots]
        return dict(
            contrast_id=self.contrast.contrast_id, scope=self.contrast.scope, topic=self.pack.pack_id,
            policy_version=protocol.POLICY_VERSION, estimator_version=protocol.ESTIMATOR_VERSION,
            baseline=self.contrast.baseline, variant=self.contrast.variant,
            day_zero=day_zero and day_zero.isoformat(), looks=judged["looks"],
            outcome=judged["outcome"], winner=winner, decision_day=judged["decision_day"],
            next_look_day=None if judged["outcome"] else (pending[0] if pending else None),
            # Preference and override handling arrive with stored look snapshots (step 2b);
            # until then the default is the winner, else the strong baseline.
            future_default=(winner or self.contrast.baseline) if judged["outcome"] else None,
            provisional=PROVISIONAL,
        )

    def ranking(self):
        evidence = self.outcomes_by_method()
        result = asdict(rank_methods(evidence["outcomes"], seed=self._seed("ranking")))
        result.update(excluded=evidence["excluded"], provisional=PROVISIONAL)
        for method in result["methods"]:
            method["provisional"] = PROVISIONAL
        return result
