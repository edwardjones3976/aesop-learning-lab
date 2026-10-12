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
    Activity, ActivityType, Attempt, Concept, EvidenceKind,
    ExperimentAssignment, HintLevel, OutsideStudy, ScoreStatus,
)


SCHEMA_VERSION = 1


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
        with self.connection:
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
            self.connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

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
                  activity.evidence_kind.value, int(activity.held_out))
        old = self.connection.execute(
            "SELECT id, content_version, concept_id, family_id, activity_type, "
            "evidence_kind, held_out FROM activities WHERE id = ? AND content_version = ?",
            values[:2],
        ).fetchone()
        if old is not None:
            if tuple(old) != values:
                raise ValueError("content version is immutable")
            return
        with self.connection:
            self.connection.execute("INSERT INTO activities VALUES (?, ?, ?, ?, ?, ?, ?)", values)

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
                        EvidenceKind(row["evidence_kind"]), bool(row["held_out"]))

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
            "WHERE a.concept_id = ? ORDER BY t.occurred_at, t.id",
            (concept_id,),
        ).fetchall()
        return tuple(Attempt(
            row["id"], row["activity_id"], row["content_version"],
            datetime.fromisoformat(row["occurred_at"]), row["first_answer"],
            HintLevel(row["hint_level"]), ScoreStatus(row["score_status"]),
            row["grading_method"], row["method_id"], row["selection_reason"],
            row["confidence"],
            OutsideStudy(row["outside_study"]) if row["outside_study"] else None,
            row["outside_study_detail"], row["active_seconds"]
        ) for row in rows)

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
            "SELECT * FROM experiment_assignments WHERE protocol_id = ? "
            "ORDER BY assigned_at, item_family_id", (protocol_id,)
        ).fetchall()
        return tuple(ExperimentAssignment(
            row["protocol_id"], row["protocol_version"], row["concept_id"],
            row["item_family_id"], row["condition_id"], row["seed"],
            datetime.fromisoformat(row["assigned_at"])
        ) for row in rows)

    def export_all(self) -> dict[str, object]:
        attempts = self.connection.execute("SELECT * FROM attempts ORDER BY occurred_at, id").fetchall()
        assignments = self.connection.execute(
            "SELECT * FROM experiment_assignments ORDER BY assigned_at, item_family_id"
        ).fetchall()
        return {
            "schemaVersion": SCHEMA_VERSION,
            "attempts": [dict(row) for row in attempts],
            "experimentAssignments": [dict(row) for row in assignments],
        }

    def delete_all(self) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM attempts")
            self.connection.execute("DELETE FROM experiment_assignments")
