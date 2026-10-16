from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from aesop_lab.domain.models import (
    Activity, ActivityType, AnswerRevision, Attempt, Concept, CriterionReview, EvidenceKind,
    ExperimentAssignment, HintLevel, OutsideStudy, ReviewRating, ScoreStatus, SelfReview,
)
from aesop_lab.storage.sqlite import SQLiteStore


class SQLiteStoreTests(unittest.TestCase):
    def test_v1_database_adds_review_tables_without_losing_attempts(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "learning.db"
            now = datetime.now(timezone.utc)
            with SQLiteStore(path) as store:
                store.add_concept(Concept("c1", "Concept", "v1"))
                store.add_activity(Activity("a1", "c1", "v1", "family-a",
                                            ActivityType.TRACE, EvidenceKind.APPLICATION))
                store.append_attempt(Attempt("t1", "a1", "v1", now, "2", HintLevel.NONE,
                                             ScoreStatus.CORRECT, "reviewed_exact_key", "assessment-v1",
                                             "practice"))
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("DROP TABLE answer_revisions")
                connection.execute("DROP TABLE self_reviews")
                connection.execute("PRAGMA user_version = 1")
                connection.commit()
            with SQLiteStore(path) as store:
                self.assertEqual(store.list_attempts("c1")[0].id, "t1")
                self.assertEqual(store.export_all()["selfReviews"], [])
                self.assertEqual(store.connection.execute("PRAGMA user_version").fetchone()[0], 3)

    def test_v2_database_adds_lesson_completion_without_losing_reviews(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "learning.db"
            now = datetime.now(timezone.utc)
            with SQLiteStore(path) as store:
                store.add_concept(Concept("c1", "Concept", "v1"))
                store.add_activity(Activity("a1", "c1", "v1", "family-a",
                                            ActivityType.EXPLANATION, EvidenceKind.EXPLANATION))
                store.append_attempt(Attempt("t1", "a1", "v1", now, "Reason", HintLevel.NONE,
                                             ScoreStatus.UNGRADED, "ungraded_pending_review", "assessment-v1",
                                             "practice"))
                review = SelfReview("r1", "t1", "rubric-1", "v1", now,
                                    (CriterionReview("reason", ReviewRating.SHOWN, "Reason"),))
                store.append_self_review(review)
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("DROP TABLE lesson_completions")
                connection.execute("PRAGMA user_version = 2")
                connection.commit()
            with SQLiteStore(path) as store:
                self.assertEqual(store.list_attempts("c1")[0].id, "t1")
                self.assertEqual(store.list_self_reviews("t1"), (review,))
                self.assertEqual(store.record_lesson_completion("c1", "v1", now), now)
                self.assertEqual(store.connection.execute("PRAGMA user_version").fetchone()[0], 3)

    def test_reviews_and_revisions_are_append_only_exported_and_deleted(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "learning.db"
            now = datetime.now(timezone.utc)
            with SQLiteStore(path) as store:
                store.add_concept(Concept("base-case", "Base case", "v1"))
                store.add_activity(Activity("explain-1", "base-case", "v1", "family-a",
                                            ActivityType.EXPLANATION, EvidenceKind.EXPLANATION))
                store.append_attempt(Attempt("attempt-open", "explain-1", "v1", now,
                                             "n == 0 returns 1", HintLevel.NONE, ScoreStatus.UNGRADED,
                                             "ungraded_pending_review", "assessment-v1", "practice"))
                review = SelfReview("review-1", "attempt-open", "rubric-1", "v1", now,
                                    (CriterionReview("stopping", ReviewRating.SHOWN, "n == 0"),))
                revision = AnswerRevision("revision-1", "review-1", now,
                                          "The n == 0 branch returns 1 without another call.")
                store.append_self_review(review)
                store.append_revision(revision)
                store.append_self_review(review)
                store.append_revision(revision)
                with self.assertRaisesRegex(ValueError, "immutable"):
                    store.append_self_review(SelfReview("review-1", "attempt-open", "rubric-1", "v2", now,
                                                        review.judgments))
                with self.assertRaisesRegex(ValueError, "immutable"):
                    store.append_revision(AnswerRevision("revision-1", "review-1", now, "Changed"))
                self.assertEqual(store.list_self_reviews("attempt-open"), (review,))
                self.assertEqual(store.list_revisions("review-1"), (revision,))
                exported = store.export_all()
                self.assertEqual(len(exported["selfReviews"]), 1)
                self.assertEqual(len(exported["answerRevisions"]), 1)
            with SQLiteStore(path) as store:
                self.assertEqual(store.list_self_reviews("attempt-open"), (review,))
                self.assertEqual(store.list_revisions("review-1"), (revision,))
                self.assertIs(store.list_attempts("base-case")[0].score_status, ScoreStatus.UNGRADED)
                store.delete_all()
                self.assertEqual(store.export_all()["selfReviews"], [])
                self.assertEqual(store.export_all()["answerRevisions"], [])

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

    def test_assignment_retry_is_idempotent_but_reassignment_is_rejected(self) -> None:
        with TemporaryDirectory() as directory, SQLiteStore(Path(directory) / "db.sqlite3") as store:
            store.add_concept(Concept("c1", "Original", "v1"))
            now = datetime.now(timezone.utc)
            assignment = ExperimentAssignment("p1", "v1", "c1", "family-a", "text", 42, now)
            store.save_assignment(assignment)
            store.save_assignment(assignment)
            self.assertEqual(store.list_assignments("p1"), (assignment,))
            with self.assertRaisesRegex(ValueError, "immutable"):
                store.save_assignment(ExperimentAssignment(
                    "p1", "v1", "c1", "family-a", "diagram", 42, now
                ))

    def test_assignment_rejects_unknown_concept(self) -> None:
        with TemporaryDirectory() as directory, SQLiteStore(Path(directory) / "db.sqlite3") as store:
            with self.assertRaisesRegex(ValueError, "known concept"):
                store.save_assignment(ExperimentAssignment(
                    "p1", "v1", "missing", "family-a", "text", 42,
                    datetime.now(timezone.utc),
                ))


if __name__ == "__main__":
    unittest.main()
