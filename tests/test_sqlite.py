from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aesop_lab.domain.models import (
    Activity, ActivityType, Attempt, Concept, EvidenceKind,
    ExperimentAssignment, HintLevel, OutsideStudy, ScoreStatus,
)
from aesop_lab.storage.sqlite import SQLiteStore


class SQLiteStoreTests(unittest.TestCase):
    def test_round_trip_export_and_delete_preserve_content(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "learning.db"
            now = datetime.now(timezone.utc)
            with SQLiteStore(path) as store:
                concept = Concept("base-case", "Base case", "v1")
                activity = Activity("trace-1", "base-case", "v1", "family-a",
                                    ActivityType.TRACE, EvidenceKind.APPLICATION)
                store.add_concept(concept)
                store.add_activity(activity)
                store.append_attempt(Attempt(
                    "attempt-1", "trace-1", "v1", now, "2", HintLevel.NONE,
                    ScoreStatus.CORRECT, "reviewed_exact_key", "baseline",
                    "due review", 0.7, OutsideStudy.NONE,
                ))
                store.save_assignment(ExperimentAssignment(
                    "p1", "v1", "base-case", "family-a", "diagram", 42, now
                ))
                self.assertEqual(store.get_concept("base-case", "v1"), concept)
                self.assertEqual(store.get_activity("trace-1", "v1"), activity)
                self.assertEqual(len(store.list_attempts("base-case")), 1)
                self.assertEqual(len(store.list_assignments("p1")), 1)
                self.assertEqual(len(store.export_all()["attempts"]), 1)
            with SQLiteStore(path) as store:
                self.assertEqual(len(store.list_attempts("base-case")), 1)
                store.delete_all()
                self.assertEqual(store.export_all()["attempts"], [])
                self.assertEqual(store.export_all()["experimentAssignments"], [])
                self.assertEqual(store.get_activity("trace-1", "v1"), activity)

    def test_content_version_cannot_be_rewritten(self) -> None:
        with TemporaryDirectory() as directory, SQLiteStore(Path(directory) / "db.sqlite3") as store:
            store.add_concept(Concept("c1", "Original", "v1"))
            with self.assertRaisesRegex(ValueError, "immutable"):
                store.add_concept(Concept("c1", "Changed", "v1"))


if __name__ == "__main__":
    unittest.main()
