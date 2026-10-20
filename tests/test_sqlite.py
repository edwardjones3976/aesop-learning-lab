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
    def test_exposure_and_override_survive_restart_export_and_delete(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "learner.db"
            at = datetime(2026, 10, 15, tzinfo=timezone.utc)
            with SQLiteStore(path) as store:
                store.record_exposure("c1", "v4", "p", "v1", "text", at, ("example-a",))
                store.record_exposure("c1", "v4", "p", "v1", "text", at, ("example-a",))
                store.complete_exposure("c1", "v4", "p", "v1", at)
                store.record_override("o1", "c1", "v4", "practice", "learner_choice", at,
                                      recommended_activity_id="review", recommended_reason="Due now",
                                      selected_activity_id="practice", learner_reason="More time",
                                      recommended_concept_id="c2", recommended_action="delayed_check",
                                      selected_concept_id="c1")
            with SQLiteStore(path) as store:
                exported = store.export_all()
                self.assertEqual(len(exported["experimentExposures"]), 1)
                self.assertEqual(exported["experimentExposures"][0]["condition_id"], "text")
                self.assertEqual(len(exported["recommendationOverrides"]), 1)
                self.assertEqual(exported["recommendationOverrides"][0]["recommended_activity_id"],
                                 "review")
                self.assertEqual(exported["recommendationOverrides"][0]["selected_activity_id"],
                                 "practice")
                self.assertEqual(exported["recommendationOverrides"][0]["learner_reason"],
                                 "More time")
                self.assertEqual(exported["recommendationOverrides"][0]["recommended_concept_id"],
                                 "c2")
                self.assertEqual(exported["recommendationOverrides"][0]["recommended_action"],
                                 "delayed_check")
                self.assertEqual(exported["recommendationOverrides"][0]["selected_concept_id"],
                                 "c1")
                store.delete_all()
                self.assertEqual(store.export_all()["experimentExposures"], [])
                self.assertEqual(store.export_all()["recommendationOverrides"], [])

    def test_v4_held_out_rows_gain_one_day_delay(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.db"
            with SQLiteStore(path) as store:
                store.add_concept(Concept("c1", "Concept", "v2"))
                store.add_activity(Activity("old-check", "c1", "v2", "family",
                                            ActivityType.TRACE, EvidenceKind.TRANSFER, True, 1))
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("ALTER TABLE activities DROP COLUMN check_delay_days")
                connection.execute("PRAGMA user_version = 4")
                connection.commit()
            with SQLiteStore(path) as store:
                check = store.get_activity("old-check", "v2")
                self.assertEqual(check.check_delay_days, 1)
                self.assertEqual(store.connection.execute("PRAGMA user_version").fetchone()[0], 10)

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
                self.assertEqual(store.connection.execute("PRAGMA user_version").fetchone()[0], 10)

    def test_lists_order_by_instant_not_offset_text(self) -> None:
        from datetime import timedelta
        plus5 = timezone(timedelta(hours=5))
        earlier = datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc)   # text "...T06:00..+00:00"
        later = datetime(2026, 1, 1, 10, 0, tzinfo=plus5)            # 05:00 UTC, text "...T10:00..+05:00"
        self.assertLess(later, earlier)
        with TemporaryDirectory() as directory, SQLiteStore(Path(directory) / "learning.db") as store:
            store.add_concept(Concept("c1", "Concept", "v1"))
            store.add_activity(Activity("a1", "c1", "v1", "family-a",
                                        ActivityType.TRACE, EvidenceKind.APPLICATION))
            for attempt_id, when in (("t-utc", earlier), ("t-plus5", later)):
                store.append_attempt(Attempt(attempt_id, "a1", "v1", when, "2", HintLevel.NONE,
                                             ScoreStatus.CORRECT, "reviewed_exact_key",
                                             "assessment-v1", "practice"))
            self.assertEqual([a.id for a in store.list_attempts("c1")], ["t-plus5", "t-utc"])
            store.save_draft("d-utc", "a1", "v1", "x", earlier)
            store.save_draft("d-plus5", "a1", "v1", "y", later)
            self.assertEqual(store.open_draft("c1")["id"], "d-plus5")
            store.save_hint("d-plus5", HintLevel.NUDGE, later)
            store.save_hint("d-plus5", HintLevel.TARGETED, earlier)
            self.assertEqual(store.hint_levels("d-plus5"),
                             (HintLevel.NUDGE, HintLevel.TARGETED))
            exported = store.export_all()
            self.assertEqual([row["id"] for row in exported["attempts"]],
                             ["t-plus5", "t-utc"])
            self.assertEqual([row["id"] for row in exported["practiceDrafts"]],
                             ["d-plus5", "d-utc"])
    def test_either_v2_branch_migrates_to_combined_schema(self) -> None:
        for absent_tables in (("lesson_completions",),
                              ("answer_revisions", "self_reviews")):
            with self.subTest(absent_tables=absent_tables), TemporaryDirectory() as directory:
                path = Path(directory) / "learning.db"
                with SQLiteStore(path) as store:
                    store.add_concept(Concept("c1", "Concept", "v1"))
                with closing(sqlite3.connect(path)) as connection:
                    for table in absent_tables:
                        connection.execute(f"DROP TABLE {table}")
                    connection.execute("PRAGMA user_version = 2")
                    connection.commit()
                with SQLiteStore(path) as store:
                    self.assertEqual(store.connection.execute("PRAGMA user_version").fetchone()[0], 10)
                    self.assertEqual(store.export_all()["selfReviews"], [])
                    self.assertEqual(store.export_all()["lessonCompletions"], [])
                    self.assertEqual(store.get_concept("c1", "v1").title, "Concept")
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
                self.assertEqual(store.connection.execute("PRAGMA user_version").fetchone()[0], 10)

    def test_merged_master_v3_upgrades_without_losing_learner_records(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "learning.db"
            now = datetime.now(timezone.utc)
            with SQLiteStore(path) as store:
                store.add_concept(Concept("c1", "Concept", "v1"))
                store.add_activity(Activity("a1", "c1", "v1", "family-a",
                                            ActivityType.TRACE, EvidenceKind.APPLICATION))
                store.record_lesson_completion("c1", "v1", now)
                store.append_attempt(Attempt("t1", "a1", "v1", now, "2", HintLevel.NONE,
                                             ScoreStatus.CORRECT, "reviewed_exact_key", "assessment-v1",
                                             "practice"))
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("DROP TABLE practice_hint_events")
                connection.execute("DROP TABLE practice_drafts")
                connection.execute("ALTER TABLE activities DROP COLUMN check_delay_days")
                connection.execute("PRAGMA user_version = 3")
                connection.commit()
            with SQLiteStore(path) as store:
                self.assertEqual(store.connection.execute("PRAGMA user_version").fetchone()[0], 10)
                self.assertEqual(store.lesson_completed_at("c1", "v1"), now)
                self.assertEqual(store.list_attempts("c1")[0].id, "t1")
                self.assertIn("check_delay_days", {row[1] for row in
                              store.connection.execute("PRAGMA table_info(activities)")})

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
