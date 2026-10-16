"""SQLite implementation of the domain repository ports.

Content rows are immutable by ID and version after insertion. Learner records can
be exported or deleted without removing the reviewed content pack.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sqlite3

from aesop_lab.domain.models import (
    Activity, ActivityType, AnswerRevision, Attempt, Concept, CriterionReview, EvidenceKind,
    ExperimentAssignment, HintLevel, OutsideStudy, ReviewRating, ScoreStatus, SelfReview,
)


SCHEMA_VERSION = 5


class SQLiteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def __enter__(self) -> "SQLiteStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self.connection.close()

    def _migrate(self) -> None:
        current = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if current > SCHEMA_VERSION:
            raise RuntimeError(f"database schema {current} is newer than supported {SCHEMA_VERSION}")
        if current == SCHEMA_VERSION:
            return
        if current == 0:
            self.connection.executescript("""
                CREATE TABLE IF NOT EXISTS concepts (
                    id TEXT NOT NULL, content_version TEXT NOT NULL,
                    title TEXT NOT NULL, prerequisite_ids TEXT NOT NULL,
                    PRIMARY KEY (id, content_version)
                );
                CREATE TABLE IF NOT EXISTS activities (
                    id TEXT NOT NULL, content_version TEXT NOT NULL,
                    concept_id TEXT NOT NULL, family_id TEXT NOT NULL,
                    activity_type TEXT NOT NULL, evidence_kind TEXT NOT NULL,
                    held_out INTEGER NOT NULL,
                    PRIMARY KEY (id, content_version),
                    FOREIGN KEY (concept_id, content_version)
                        REFERENCES concepts(id, content_version)
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    id TEXT PRIMARY KEY, activity_id TEXT NOT NULL,
                    content_version TEXT NOT NULL, occurred_at TEXT NOT NULL,
                    first_answer TEXT NOT NULL, hint_level TEXT NOT NULL,
                    score_status TEXT NOT NULL, grading_method TEXT NOT NULL,
                    method_id TEXT NOT NULL, selection_reason TEXT NOT NULL,
                    confidence REAL, outside_study TEXT,
                    outside_study_detail TEXT, active_seconds INTEGER,
                    FOREIGN KEY (activity_id, content_version)
                        REFERENCES activities(id, content_version)
                );
                CREATE TABLE IF NOT EXISTS experiment_assignments (
                    protocol_id TEXT NOT NULL, protocol_version TEXT NOT NULL,
                    concept_id TEXT NOT NULL, item_family_id TEXT NOT NULL,
                    condition_id TEXT NOT NULL, seed INTEGER NOT NULL,
                    assigned_at TEXT NOT NULL,
                    PRIMARY KEY (protocol_id, protocol_version, item_family_id)
                );
                CREATE INDEX IF NOT EXISTS attempts_by_activity
                    ON attempts(activity_id, content_version, occurred_at);
            """)
            self.connection.execute("PRAGMA user_version = 1")
        if current < 3:
            with self.connection:
                self.connection.executescript("""
                CREATE TABLE IF NOT EXISTS lesson_completions (
                    concept_id TEXT NOT NULL, content_version TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    PRIMARY KEY (concept_id, content_version),
                    FOREIGN KEY (concept_id, content_version)
                        REFERENCES concepts(id, content_version)
                );
                CREATE TABLE IF NOT EXISTS self_reviews (
                    id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL,
                    rubric_id TEXT NOT NULL, rubric_version TEXT NOT NULL,
                    occurred_at TEXT NOT NULL, judgments TEXT NOT NULL,
                    confidence REAL,
                    FOREIGN KEY (attempt_id) REFERENCES attempts(id)
                );
                CREATE TABLE IF NOT EXISTS answer_revisions (
                    id TEXT PRIMARY KEY, review_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL, answer TEXT NOT NULL,
                    FOREIGN KEY (review_id) REFERENCES self_reviews(id)
                );
                CREATE INDEX IF NOT EXISTS reviews_by_attempt
                    ON self_reviews(attempt_id, occurred_at);
                CREATE INDEX IF NOT EXISTS revisions_by_review
                    ON answer_revisions(review_id, occurred_at);
                """)
                self.connection.execute("PRAGMA user_version = 3")
        if current < 4:
            with self.connection:
                self.connection.executescript("""
                CREATE TABLE IF NOT EXISTS practice_drafts (
                    id TEXT PRIMARY KEY,
                    activity_id TEXT NOT NULL,
                    content_version TEXT NOT NULL,
                    first_answer TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    submitted_attempt_id TEXT,
                    response_json TEXT,
                    FOREIGN KEY (activity_id, content_version)
                        REFERENCES activities(id, content_version),
                    FOREIGN KEY (submitted_attempt_id) REFERENCES attempts(id)
                );
                CREATE TABLE IF NOT EXISTS practice_hint_events (
                    draft_id TEXT NOT NULL,
                    level TEXT NOT NULL,
                    viewed_at TEXT NOT NULL,
                    PRIMARY KEY (draft_id, level),
                    FOREIGN KEY (draft_id) REFERENCES practice_drafts(id)
                );
                CREATE INDEX IF NOT EXISTS open_drafts_by_activity
                    ON practice_drafts(activity_id, content_version, submitted_attempt_id);
                """)
                self.connection.execute("PRAGMA user_version = 4")
        if current < 5:
            with self.connection:
                columns = {row[1] for row in self.connection.execute("PRAGMA table_info(activities)")}
                if "check_delay_days" not in columns:
                    self.connection.execute(
                        "ALTER TABLE activities ADD COLUMN check_delay_days INTEGER NOT NULL DEFAULT 0"
                    )
                    self.connection.execute(
                        "UPDATE activities SET check_delay_days = 1 WHERE held_out = 1"
                    )
                self.connection.execute("PRAGMA user_version = 5")

    def record_lesson_completion(self, concept_id: str, version: str,
                                 completed_at: datetime) -> datetime:
        if completed_at.tzinfo is None or completed_at.utcoffset() is None:
            raise ValueError("lesson completion requires a timezone")
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO lesson_completions VALUES (?, ?, ?)",
                (concept_id, version, completed_at.isoformat()),
            )
        recorded = self.lesson_completed_at(concept_id, version)
        assert recorded is not None
        return recorded

    def lesson_completed_at(self, concept_id: str, version: str) -> datetime | None:
        row = self.connection.execute(
            "SELECT completed_at FROM lesson_completions WHERE concept_id = ? "
            "AND content_version = ?", (concept_id, version),
        ).fetchone()
        return datetime.fromisoformat(row[0]) if row else None

    def add_concept(self, concept: Concept) -> None:
        values = (concept.id, concept.content_version, concept.title,
                  json.dumps(concept.prerequisite_ids))
        old = self.connection.execute(
            "SELECT id, content_version, title, prerequisite_ids FROM concepts "
            "WHERE id = ? AND content_version = ?", values[:2]
        ).fetchone()
        if old is not None:
            if tuple(old) != values:
                raise ValueError("content version is immutable")
            return
        with self.connection:
            self.connection.execute(
                "INSERT INTO concepts VALUES (?, ?, ?, ?)", values
            )

    def add_activity(self, activity: Activity) -> None:
        values = (activity.id, activity.content_version, activity.concept_id,
                  activity.family_id, activity.activity_type.value,
                  activity.evidence_kind.value, int(activity.held_out), activity.check_delay_days)
        old = self.connection.execute(
            "SELECT id, content_version, concept_id, family_id, activity_type, "
            "evidence_kind, held_out, check_delay_days FROM activities WHERE id = ? AND content_version = ?",
            values[:2],
        ).fetchone()
        if old is not None:
            if tuple(old) != values:
                raise ValueError("content version is immutable")
            return
        with self.connection:
            self.connection.execute("INSERT INTO activities VALUES (?, ?, ?, ?, ?, ?, ?, ?)", values)

    def get_concept(self, concept_id: str, version: str) -> Concept | None:
        row = self.connection.execute(
            "SELECT * FROM concepts WHERE id = ? AND content_version = ?",
            (concept_id, version),
        ).fetchone()
        if row is None:
            return None
        return Concept(row["id"], row["title"], row["content_version"],
                       tuple(json.loads(row["prerequisite_ids"])))

    def get_activity(self, activity_id: str, version: str) -> Activity | None:
        row = self.connection.execute(
            "SELECT * FROM activities WHERE id = ? AND content_version = ?",
            (activity_id, version),
        ).fetchone()
        return self._activity(row) if row is not None else None

    def list_activities(self, concept_id: str, version: str) -> tuple[Activity, ...]:
        rows = self.connection.execute(
            "SELECT * FROM activities WHERE concept_id = ? AND content_version = ? ORDER BY id",
            (concept_id, version),
        ).fetchall()
        return tuple(self._activity(row) for row in rows)

    @staticmethod
    def _activity(row: sqlite3.Row) -> Activity:
        return Activity(row["id"], row["concept_id"], row["content_version"],
                        row["family_id"], ActivityType(row["activity_type"]),
                        EvidenceKind(row["evidence_kind"]), bool(row["held_out"]),
                        row["check_delay_days"])

    def append_attempt(self, attempt: Attempt) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (attempt.id, attempt.activity_id, attempt.content_version,
                 attempt.occurred_at.isoformat(), attempt.first_answer,
                 attempt.hint_level.value, attempt.score_status.value,
                 attempt.grading_method, attempt.method_id, attempt.selection_reason,
                 attempt.confidence,
                 attempt.outside_study.value if attempt.outside_study else None,
                 attempt.outside_study_detail, attempt.active_seconds),
            )

    def list_attempts(self, concept_id: str) -> tuple[Attempt, ...]:
        rows = self.connection.execute(
            "SELECT t.* FROM attempts t JOIN activities a ON "
            "t.activity_id = a.id AND t.content_version = a.content_version "
            "WHERE a.concept_id = ?",
            (concept_id,),
        ).fetchall()
        # Stored ISO text sorts wrongly across UTC offsets; order by instant.
        rows.sort(key=lambda row: (datetime.fromisoformat(row["occurred_at"]), row["id"]))
        return tuple(Attempt(
            row["id"], row["activity_id"], row["content_version"],
            datetime.fromisoformat(row["occurred_at"]), row["first_answer"],
            HintLevel(row["hint_level"]), ScoreStatus(row["score_status"]),
            row["grading_method"], row["method_id"], row["selection_reason"],
            row["confidence"],
            OutsideStudy(row["outside_study"]) if row["outside_study"] else None,
            row["outside_study_detail"], row["active_seconds"]
        ) for row in rows)

    def open_draft(self, concept_id: str) -> sqlite3.Row | None:
        rows = self.connection.execute(
            "SELECT d.* FROM practice_drafts d JOIN activities a ON "
            "d.activity_id = a.id AND d.content_version = a.content_version "
            "WHERE a.concept_id = ? AND d.submitted_attempt_id IS NULL", (concept_id,),
        ).fetchall()
        return min(rows, default=None, key=lambda row: (
            datetime.fromisoformat(row["recorded_at"]), row["id"]))

    def get_draft(self, draft_id: str) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM practice_drafts WHERE id = ?", (draft_id,)).fetchone()

    def save_draft(self, draft_id: str, activity_id: str, version: str,
                   answer: str, recorded_at: datetime) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO practice_drafts "
                "(id, activity_id, content_version, first_answer, recorded_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (draft_id, activity_id, version, answer, recorded_at.isoformat()),
            )

    def hint_levels(self, draft_id: str) -> tuple[HintLevel, ...]:
        rows = self.connection.execute(
            "SELECT level FROM practice_hint_events WHERE draft_id = ? ORDER BY rowid",
            (draft_id,),
        ).fetchall()
        return tuple(HintLevel(row[0]) for row in rows)

    def save_hint(self, draft_id: str, level: HintLevel, viewed_at: datetime) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO practice_hint_events VALUES (?, ?, ?)",
                (draft_id, level.value, viewed_at.isoformat()),
            )

    def finish_draft(self, draft_id: str, response: dict[str, object]) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE practice_drafts SET submitted_attempt_id = ?, response_json = ? WHERE id = ?",
                (response["attemptId"], json.dumps(response), draft_id),
            )

    def append_self_review(self, review: SelfReview) -> None:
        attempt = self.connection.execute(
            "SELECT t.score_status, t.occurred_at, a.activity_type FROM attempts t "
            "JOIN activities a ON t.activity_id = a.id AND t.content_version = a.content_version "
            "WHERE t.id = ?", (review.attempt_id,),
        ).fetchone()
        if attempt is None or attempt["score_status"] != ScoreStatus.UNGRADED.value or \
                attempt["activity_type"] not in (ActivityType.EXPLANATION.value, ActivityType.CODE_DESIGN.value):
            raise ValueError("review requires an ungraded open-ended attempt")
        if review.occurred_at < datetime.fromisoformat(attempt["occurred_at"]):
            raise ValueError("review cannot precede the attempt")
        judgments = json.dumps([
            {"criterionId": item.criterion_id, "rating": item.rating.value, "evidence": item.evidence}
            for item in review.judgments
        ])
        values = (review.id, review.attempt_id, review.rubric_id, review.rubric_version,
                  review.occurred_at.isoformat(), judgments, review.confidence)
        old = self.connection.execute("SELECT * FROM self_reviews WHERE id = ?", (review.id,)).fetchone()
        if old is not None:
            if tuple(old) != values:
                raise ValueError("self review is immutable")
            return
        with self.connection:
            self.connection.execute(
                "INSERT INTO self_reviews VALUES (?, ?, ?, ?, ?, ?, ?)",
                values,
            )

    def list_self_reviews(self, attempt_id: str) -> tuple[SelfReview, ...]:
        rows = self.connection.execute(
            "SELECT * FROM self_reviews WHERE attempt_id = ?", (attempt_id,)
        ).fetchall()
        rows.sort(key=lambda row: (datetime.fromisoformat(row["occurred_at"]), row["id"]))
        return tuple(SelfReview(
            row["id"], row["attempt_id"], row["rubric_id"], row["rubric_version"],
            datetime.fromisoformat(row["occurred_at"]),
            tuple(CriterionReview(item["criterionId"], ReviewRating(item["rating"]), item["evidence"])
                  for item in json.loads(row["judgments"])), row["confidence"],
        ) for row in rows)

    def has_self_review(self, review_id: str) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM self_reviews WHERE id = ?", (review_id,)
        ).fetchone() is not None

    def append_revision(self, revision: AnswerRevision) -> None:
        review = self.connection.execute(
            "SELECT occurred_at FROM self_reviews WHERE id = ?", (revision.review_id,)
        ).fetchone()
        if review is None or revision.occurred_at < datetime.fromisoformat(review["occurred_at"]):
            raise ValueError("revision requires an earlier self review")
        values = (revision.id, revision.review_id, revision.occurred_at.isoformat(), revision.answer)
        old = self.connection.execute("SELECT * FROM answer_revisions WHERE id = ?", (revision.id,)).fetchone()
        if old is not None:
            if tuple(old) != values:
                raise ValueError("answer revision is immutable")
            return
        with self.connection:
            self.connection.execute(
                "INSERT INTO answer_revisions VALUES (?, ?, ?, ?)",
                values,
            )

    def list_revisions(self, review_id: str) -> tuple[AnswerRevision, ...]:
        rows = self.connection.execute(
            "SELECT * FROM answer_revisions WHERE review_id = ?", (review_id,)
        ).fetchall()
        rows.sort(key=lambda row: (datetime.fromisoformat(row["occurred_at"]), row["id"]))
        return tuple(AnswerRevision(row["id"], row["review_id"],
                                    datetime.fromisoformat(row["occurred_at"]), row["answer"])
                     for row in rows)

    def save_assignment(self, assignment: ExperimentAssignment) -> None:
        concept_exists = self.connection.execute(
            "SELECT 1 FROM concepts WHERE id = ? LIMIT 1", (assignment.concept_id,)
        ).fetchone()
        if concept_exists is None:
            raise ValueError("experiment assignment needs a known concept")
        values = (assignment.protocol_id, assignment.protocol_version,
                  assignment.concept_id, assignment.item_family_id,
                  assignment.condition_id, assignment.seed,
                  assignment.assigned_at.isoformat())
        old = self.connection.execute(
            "SELECT protocol_id, protocol_version, concept_id, item_family_id, "
            "condition_id, seed, assigned_at FROM experiment_assignments "
            "WHERE protocol_id = ? AND protocol_version = ? AND item_family_id = ?",
            (assignment.protocol_id, assignment.protocol_version, assignment.item_family_id),
        ).fetchone()
        if old is not None:
            if tuple(old) != values:
                raise ValueError("experiment assignment is immutable")
            return
        with self.connection:
            self.connection.execute(
                "INSERT INTO experiment_assignments VALUES (?, ?, ?, ?, ?, ?, ?)",
                values,
            )

    def list_assignments(self, protocol_id: str) -> tuple[ExperimentAssignment, ...]:
        rows = self.connection.execute(
            "SELECT * FROM experiment_assignments WHERE protocol_id = ?", (protocol_id,)
        ).fetchall()
        rows.sort(key=lambda row: (datetime.fromisoformat(row["assigned_at"]), row["item_family_id"]))
        return tuple(ExperimentAssignment(
            row["protocol_id"], row["protocol_version"], row["concept_id"],
            row["item_family_id"], row["condition_id"], row["seed"],
            datetime.fromisoformat(row["assigned_at"])
        ) for row in rows)

    def export_all(self) -> dict[str, object]:
        def by_instant(query: str, timestamp: str, tie_break: str) -> list[sqlite3.Row]:
            rows = self.connection.execute(query).fetchall()
            rows.sort(key=lambda row: (datetime.fromisoformat(row[timestamp]), row[tie_break]))
            return rows

        attempts = by_instant("SELECT * FROM attempts", "occurred_at", "id")
        assignments = by_instant("SELECT * FROM experiment_assignments", "assigned_at", "item_family_id")
        reviews = by_instant("SELECT * FROM self_reviews", "occurred_at", "id")
        revisions = by_instant("SELECT * FROM answer_revisions", "occurred_at", "id")
        return {
            "schemaVersion": SCHEMA_VERSION,
            "attempts": [dict(row) for row in attempts],
            "selfReviews": [dict(row) for row in reviews],
            "answerRevisions": [dict(row) for row in revisions],
            "experimentAssignments": [dict(row) for row in assignments],
            "lessonCompletions": [dict(row) for row in self.connection.execute(
                "SELECT * FROM lesson_completions ORDER BY concept_id, content_version")],
            "practiceDrafts": [dict(row) for row in by_instant(
                "SELECT id, activity_id, content_version, first_answer, recorded_at, "
                "submitted_attempt_id FROM practice_drafts", "recorded_at", "id")],
            "hintEvents": [dict(row) for row in by_instant(
                "SELECT * FROM practice_hint_events", "viewed_at", "draft_id")],
        }

    def learner_content_versions(self) -> frozenset[str]:
        """Versions referenced by learner events, excluding cached catalog rows."""
        versions = self.connection.execute("""
            SELECT content_version FROM attempts
            UNION SELECT content_version FROM lesson_completions
            UNION SELECT content_version FROM practice_drafts
        """).fetchall()
        return frozenset(row[0] for row in versions)

    def delete_all(self) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM practice_hint_events")
            self.connection.execute("DELETE FROM practice_drafts")
            self.connection.execute("DELETE FROM answer_revisions")
            self.connection.execute("DELETE FROM self_reviews")
            self.connection.execute("DELETE FROM attempts")
            self.connection.execute("DELETE FROM experiment_assignments")
            self.connection.execute("DELETE FROM lesson_completions")
