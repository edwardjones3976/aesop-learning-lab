import gzip
import random
import sqlite3
import tempfile
import unittest
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, Mock

from aesop_lab.content.micro_unit import load_micro_unit_pack
from aesop_lab.micro.engine import MicroUnitEngine, PROVISIONAL
from aesop_lab.storage.sqlite import SQLiteStore

FIXTURES = Path(__file__).parent / "fixtures"


class MicroEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "learner.db"
        self.store = SQLiteStore(self.path)
        self.addCleanup(lambda: self.store.close())
        self.at = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
        self.store.confirm_consent(self.at)
        self.store.connection.execute("INSERT INTO learner_identity VALUES (1, 'synthetic-42')")
        self.store.connection.commit()
        self.pack = load_micro_unit_pack(FIXTURES / "micro-unit-sample.json")
        self.engine = MicroUnitEngine(self.pack, self.store, lambda: self.at)

    def learn(self, unit):
        lesson = self.engine.start_unit(unit)
        self.engine.complete_unit(unit)
        return lesson

    def expand(self, count):
        base = self.pack.units[0]
        units = tuple(replace(base, id=f"unit-{i}", check=replace(
            base.check, id=f"check-{i}", family_id=f"family-{i}")) for i in range(count))
        self.pack = replace(self.pack, units=units)
        self.engine = MicroUnitEngine(self.pack, self.store, lambda: self.at)

    def test_daily_cap(self):
        for u in self.pack.units[:3]:
            self.learn(u)
        self.assertIsNone(self.engine.next_activity())
        with self.assertRaises(ValueError):
            self.engine.start_unit(self.pack.units[3])
        self.at += timedelta(days=1)
        self.assertEqual(self.engine.next_activity()["unit_id"], self.pack.units[3].id)
        self.learn(self.pack.units[3])

    def test_window_and_due_priority(self):
        unit = self.pack.units[0]
        self.learn(unit)
        start = self.at
        self.at += timedelta(days=7, microseconds=-1)
        self.assertEqual(self.engine.next_activity()["kind"], "unit")
        self.at += timedelta(microseconds=1)
        self.assertEqual(self.engine.next_activity()["kind"], "check")
        for days, offset, expected in ((7, -1, "early"), (7, 0, "eligible"),
                                       (14, 0, "eligible"), (14, 1, "late")):
            check = dict(assisted=False, occurred_at=(start + timedelta(days=days, microseconds=offset)).isoformat())
            exposure = dict(completed_at=start.isoformat())
            self.assertEqual(self.engine._classification(check, exposure), expected)
        self.at = start + timedelta(days=15)
        self.assertEqual(self.engine.next_activity()["kind"], "check")
        self.assertEqual(self.engine.answer_check(unit, "river")["classification"], "late")

    def test_stable_exposure_restart(self):
        unit = self.pack.units[0]
        first = self.learn(unit)
        original = self.store.micro_exposures(self.pack.pack_id)
        self.store.close()
        self.store = SQLiteStore(self.path)
        self.engine = MicroUnitEngine(self.pack, self.store, lambda: self.at)
        self.at += timedelta(days=1)
        self.assertEqual(self.engine.start_unit(unit), first)
        self.engine.complete_unit(unit)
        self.assertEqual(self.store.micro_exposures(self.pack.pack_id), original)
        self.assertEqual(first["lesson"], unit.variants[first["method_id"]])
        self.assertNotIn("variants", first)

    def test_first_answer(self):
        unit = self.pack.units[0]
        self.learn(unit)
        self.at += timedelta(days=7)
        first = self.engine.answer_check(unit, "wrong")
        self.assertEqual(self.engine.answer_check(unit, "river"), first)
        self.assertEqual(first["score_status"], "incorrect")
        self.assertEqual(len(self.store.micro_checks(self.pack.pack_id)), 1)

    def test_seed_and_warmup(self):
        self.expand(9)
        choices = []
        for i, unit in enumerate(self.pack.units[:6]):
            if i and i % 3 == 0:
                self.at += timedelta(days=1)
            choice = self.engine.choose_method(unit)
            self.assertEqual(choice, MicroUnitEngine(self.pack, self.store, lambda: self.at).choose_method(unit))
            choices.append(self.learn(unit)["method_id"])
        self.assertEqual(sorted(Counter(choices).values()), [2, 2, 2])
        self.at += timedelta(days=1)
        # Same identity/history/pack/unit produces the same assignment on a copied database.
        other = SQLiteStore(Path(self.temp.name) / "copy.db")
        self.addCleanup(other.close)
        self.store.connection.backup(other.connection)
        self.assertEqual(self.engine.choose_method(self.pack.units[6]),
                         MicroUnitEngine(self.pack, other, lambda: self.at).choose_method(self.pack.units[6]))

    def test_policy_uses_received_feedback(self):
        self.expand(9)
        for i, unit in enumerate(self.pack.units[:6]):
            if i == 3:
                self.at += timedelta(days=1)
            self.learn(unit)
        rng = Mock()
        rng.random.return_value = .19
        rng.choice.return_value = self.engine.methods[-1]
        with patch("aesop_lab.micro.engine.random.Random", return_value=rng):
            self.assertEqual(self.engine.choose_method(self.pack.units[6]), self.engine.methods[-1])
        rng.betavariate.assert_not_called()
        rng.random.return_value = .2
        rng.betavariate.side_effect = [.1, .9, .2]
        with patch("aesop_lab.micro.engine.random.Random", return_value=rng):
            self.assertEqual(self.engine.choose_method(self.pack.units[6]), self.engine.methods[1])
        self.assertEqual([call.args for call in rng.betavariate.call_args_list], [(1, 1)] * 3)
        unit = self.pack.units[0]
        method = self.engine._exposures()[unit.id]["method_id"]
        self.at += timedelta(days=7)
        self.engine.answer_check(unit, "river")
        rng.reset_mock()
        rng.betavariate.side_effect = [.1, .9, .2]
        with patch("aesop_lab.micro.engine.random.Random", return_value=rng):
            self.engine.choose_method(self.pack.units[6])
        self.assertEqual([call.args for call in rng.betavariate.call_args_list],
                         [(2, 1) if m == method else (1, 1) for m in self.engine.methods])

    def test_eligible_only(self):
        self.expand(6)
        for i, unit in enumerate(self.pack.units):
            if i == 3:
                self.at += timedelta(days=1)
            self.learn(unit)
        exposures = self.engine._exposures()
        for i, unit in enumerate(self.pack.units[:5]):
            self.at = datetime.fromisoformat(exposures[unit.id]["completed_at"]) + timedelta(days=[6, 7, 14, 15, 7][i])
            self.engine.answer_check(unit, "  river  " if i != 2 else "wrong", assisted=i == 4)
        result = self.engine.outcomes_by_method()
        self.assertEqual(sorted(x for values in result["outcomes"].values() for x in values), [(False, 1), (True, 1)])
        self.assertEqual({k: len(v) for k, v in result["excluded"].items()},
                         dict(early=1, late=1, assisted=1, missing=0, pending=1))
        # The same unanswered unit becomes missing only after its day-14 window closes.
        self.at = datetime.fromisoformat(exposures[self.pack.units[5].id]["completed_at"]) + timedelta(days=14, seconds=1)
        later = self.engine.outcomes_by_method()["excluded"]
        self.assertEqual((len(later["missing"]), len(later["pending"])), (1, 0))
        with patch("aesop_lab.micro.engine.rank_methods", wraps=__import__(
                "aesop_lab.ranking.method_ranking", fromlist=["rank_methods"]).rank_methods) as rank:
            ranking = self.engine.ranking()
            self.assertEqual(rank.call_args.args[0], result["outcomes"])
        self.assertEqual(sum(m["effective_checks"] for m in ranking["methods"]), 2)
        self.assertEqual(ranking["provisional"], PROVISIONAL)
        self.assertFalse(ranking["show_ranking"])

    def test_vocabulary_answers_ignore_case(self):
        unit = self.pack.units[0]
        self.learn(unit)
        self.at = datetime.fromisoformat(self.engine._exposures()[unit.id]["completed_at"]) + timedelta(days=7)
        self.assertEqual(self.engine.answer_check(unit, "  RIVER ")["score_status"], "correct")

    def test_consent(self):
        self.store.delete_all()
        unit = self.pack.units[0]
        actions = [lambda: self.engine.start_unit(unit), lambda: self.engine.complete_unit(unit),
                   lambda: self.engine.answer_check(unit, "river"),
                   lambda: self.store.assign_micro_unit("p", "u", "m", self.at),
                   lambda: self.store.mark_micro_unit("p", "u", self.at),
                   lambda: self.store.record_micro_check("p", "u", "c", "a", "correct", self.at)]
        for action in actions:
            with self.assertRaises(Exception) as error:
                action()
            self.assertIn("consent", str(error.exception).lower())
        self.store.confirm_consent(self.at)
        self.store.delete_all(mark_deleted=True)
        with self.assertRaises(Exception):
            self.engine.start_unit(unit)

    def test_delete_export(self):
        self.learn(self.pack.units[0])
        self.at += timedelta(days=7)
        self.engine.answer_check(self.pack.units[0], "river")
        export = self.store.export_all()
        self.assertEqual(export["schemaVersion"], 17)
        self.assertEqual(len(export["microExposures"]), 1)
        self.assertEqual(len(export["microCheckAttempts"]), 1)
        self.store.delete_all()
        self.assertEqual(self.store.export_all()["microExposures"], [])
        self.assertEqual(self.store.export_all()["microCheckAttempts"], [])

    def test_v16_migration(self):
        path = Path(self.temp.name) / "v16.db"
        path.write_bytes(gzip.decompress((FIXTURES / "micro-v16.sqlite3.gz").read_bytes()))
        connection = sqlite3.connect(path)
        self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 16)
        tables = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        before = {t: connection.execute(f'SELECT * FROM "{t}"').fetchall() for t in tables}
        connection.close()
        migrated = SQLiteStore(path)
        self.addCleanup(migrated.close)
        self.assertEqual(migrated.connection.execute("PRAGMA user_version").fetchone()[0], 17)
        for table, rows in before.items():
            self.assertEqual([tuple(r) for r in migrated.connection.execute(f'SELECT * FROM "{table}"')], rows)
        self.assertTrue(migrated.has_consent())
        self.assertEqual(migrated.micro_exposures("p"), [])

    def test_synthetic_60_days(self):
        self.expand(180)
        rng = random.Random(20261021)
        probabilities = dict(zip(self.engine.methods, (.9, .5, .2)))
        for day in range(60):
            while (activity := self.engine.next_activity()) is not None:
                unit = self.engine.units[activity["unit_id"]]
                if activity["kind"] == "check":
                    method = self.engine._exposures()[unit.id]["method_id"]
                    self.engine.answer_check(unit, "river" if rng.random() < probabilities[method] else "wrong")
                else:
                    self.learn(unit)
            self.at += timedelta(days=1)
        result = self.engine.ranking()
        self.assertEqual(len(self.engine._exposures()), 180)
        self.assertEqual(sum(m["effective_checks"] for m in result["methods"]), 159)
        self.assertEqual(result["methods"][0]["method"], self.engine.methods[0])
        self.assertTrue(result["show_ranking"])
