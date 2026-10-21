"""Loopback-only development preview of the draft Python content pack."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

from aesop_lab.api.service import ApiError, CatalogItem, LearningService
from aesop_lab.api.personal_comparison import PersonalComparison, CONCEPT_ID as PERSONAL_CONCEPT_ID
from aesop_lab.api.personal_comparison_v1 import PersonalComparison as LegacyPersonalComparison
from aesop_lab.assessment import AnswerKey, Hint, HintLadder, ItemSpec, Rubric, RubricCriterion, assess
from aesop_lab.content import load_pack
from aesop_lab.domain.models import ExperimentAssignment, HintLevel
from aesop_lab.evidence import summarize_evidence
from aesop_lab.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ComparisonSpec:
    module: str
    protocol_name: str
    assign_name: str
    exposure_name: str
    analyze_name: str

    def load(self):
        """Resolve protocol symbols only when a comparison is requested."""
        module = import_module(self.module)
        return tuple(getattr(module, name) for name in (
            self.protocol_name, self.assign_name, self.exposure_name, self.analyze_name))


@dataclass(frozen=True)
class ContentVersion:
    content_version: str
    pack_path: Path
    comparison: ComparisonSpec | None
    assignment_protocol_version: str | None
    policy_version: str
    plain_language: bool
    report_study_target: bool
    descriptive_analysis: bool


_PACK_DIR = ROOT / "content/packs/python-functions-recursion"
# Ordered oldest to newest. All version-dependent preview behavior lives here.
VERSION_REGISTRY = (
    ContentVersion("v1", _PACK_DIR / "pack.json",
                   None,
                   None, "pilot-v1", False, False, False),
    ContentVersion("v2", _PACK_DIR / "pack-m1-draft.2.json",
                   None,
                   None, "pilot-v1", False, False, False),
    ContentVersion("v3", _PACK_DIR / "pack-m1-draft.3.json",
                   None,
                   None, "pilot-v2", False, False, False),
    ContentVersion("v4", _PACK_DIR / "pack-m2-draft.4.json",
                   ComparisonSpec("aesop_lab.experiment", "PROTOCOL", "assign_condition", "Exposure", "analyze"),
                   "v1", "pilot-v2", False, False, False),
    ContentVersion("v5", _PACK_DIR / "pack-m2-draft.5.json",
                   ComparisonSpec("aesop_lab.experiment.descriptive_v2", "DESCRIPTIVE_V2", "assign_condition_v2", "ExposureV2", "analyze_v2"),
                   "v2", "pilot-v4", False, True, True),
    ContentVersion("v6", _PACK_DIR / "pack-m2-draft.6.json",
                   ComparisonSpec("aesop_lab.experiment.descriptive_v3", "DESCRIPTIVE_V3", "assign_condition_v3", "ExposureV3", "analyze_v3"),
                   "v3", "pilot-v4", False, True, True),
    ContentVersion("v7", _PACK_DIR / "pack-m2-draft.7.json",
                   ComparisonSpec("aesop_lab.experiment.descriptive_v4", "DESCRIPTIVE_V4", "assign_condition_v4", "ExposureV4", "analyze_v4"),
                   "v4", "pilot-v4", False, True, True),
    ContentVersion("v8", _PACK_DIR / "pack-m2-draft.8.json",
                   ComparisonSpec("aesop_lab.experiment.descriptive_v5", "DESCRIPTIVE_V5", "assign_condition_v5", "ExposureV5", "analyze_v5"),
                   "v5", "pilot-v4", False, True, True),
    ContentVersion("v9", _PACK_DIR / "pack-m2-draft.9.json",
                   ComparisonSpec("aesop_lab.experiment.descriptive_v6", "DESCRIPTIVE_V6", "assign_condition_v6", "ExposureV6", "analyze_v6"),
                   "v6", "pilot-v4", False, True, True),
    ContentVersion("v10", _PACK_DIR / "pack-m2-draft.10.json",
                   ComparisonSpec("aesop_lab.experiment.descriptive_v7", "DESCRIPTIVE_V7", "assign_condition_v7", "ExposureV7", "analyze_v7"),
                   "v7", "pilot-v5", True, True, True),
    ContentVersion("v11", _PACK_DIR / "pack-m2-draft.11.json",
                   ComparisonSpec("aesop_lab.experiment.descriptive_v8", "DESCRIPTIVE_V8", "assign_condition_v8", "ExposureV8", "analyze_v8"),
                   "v8", "pilot-v5", True, True, True),
)
VERSION_BY_CONTENT = {row.content_version: row for row in VERSION_REGISTRY}
PACK_BY_VERSION = {row.content_version: row.pack_path for row in VERSION_REGISTRY}
CONTENT_BY_ASSIGNMENT_PROTOCOL = {
    row.assignment_protocol_version: row.content_version for row in VERSION_REGISTRY
    if row.assignment_protocol_version is not None
}
CURRENT_PACK_PATH = VERSION_REGISTRY[-1].pack_path
# Compatibility aliases for existing preview callers and historical fixtures.
PACK_PATH = PACK_BY_VERSION["v1"]
REVISED_PACK_PATH = PACK_BY_VERSION["v2"]
WEEK_PACK_PATH = PACK_BY_VERSION["v3"]
ADAPTIVE_PACK_PATH = PACK_BY_VERSION["v4"]
V5_PACK_PATH = PACK_BY_VERSION["v5"]
V6_PACK_PATH = PACK_BY_VERSION["v6"]
V7_PACK_PATH = PACK_BY_VERSION["v7"]
V8_PACK_PATH = PACK_BY_VERSION["v8"]
V9_PACK_PATH = PACK_BY_VERSION["v9"]
V10_PACK_PATH = PACK_BY_VERSION["v10"]
WEB = ROOT / "foreman_web"
DB = ROOT / ".local/foreman.sqlite3"
HOST = "127.0.0.1"
PORT = 8775


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _catalog_item(item) -> CatalogItem:
    rubric = None
    if item.rubric:
        rubric = Rubric(item.rubric.id, tuple(
            RubricCriterion(c.id, c.description) for c in item.rubric.criteria
        ), annotated_example=item.rubric.annotated_example,
            common_mistakes=item.rubric.common_mistakes)
    spec = ItemSpec(
        item.activity, choices=item.choices,
        answer_key=AnswerKey(item.answer_key.accepted) if item.answer_key else None,
        rubric=rubric,
        hints=HintLadder(tuple(Hint(h.level, h.text) for h in item.hints)),
    )
    return CatalogItem(spec, item.prompt, item.body, item.learning_objective,
                       item.difficulty, item.explanation, item.common_mistakes)


class Preview:
    def __init__(self, db: Path = DB, *, now: Callable[[], datetime] = _now) -> None:
        self.now = now
        self.store = SQLiteStore(db)
        versions = set(self.store.learner_content_versions())
        # A process can stop between saving a fixed assignment and its first
        # exposure. Even that partial enrollment must keep its original pack.
        for assignment in self.store.list_assignments("text-vs-labeled-diagram"):
            assigned_version = CONTENT_BY_ASSIGNMENT_PROTOCOL.get(assignment.protocol_version)
            if assigned_version is None:
                versions.add("unknown")
            else:
                versions.add(assigned_version)
        if versions - PACK_BY_VERSION.keys() or len(versions) > 1:
            self.store.close()
            raise RuntimeError("Learner records span incompatible content versions; resolve them before opening this preview")
        self._activate_pack(PACK_BY_VERSION[next(iter(versions))] if versions else CURRENT_PACK_PATH)

    def personal_comparison(self) -> PersonalComparison | LegacyPersonalComparison:
        self.store.require_active_learner()
        prior = bool(self.store.list_attempts(PERSONAL_CONCEPT_ID)) or bool(
            self.store.connection.execute(
                "SELECT 1 FROM lesson_completions WHERE concept_id = ? LIMIT 1",
                (PERSONAL_CONCEPT_ID,)).fetchone()) or bool(
            self.store.connection.execute(
                "SELECT 1 FROM experiment_exposures WHERE concept_id = ? LIMIT 1",
                (PERSONAL_CONCEPT_ID,)).fetchone()) or bool(
            self.store.connection.execute(
                "SELECT 1 FROM practice_drafts d JOIN activities a "
                "ON a.id = d.activity_id AND a.content_version = d.content_version "
                "WHERE a.concept_id = ? LIMIT 1", (PERSONAL_CONCEPT_ID,)).fetchone())
        versions = {row[0] for row in self.store.connection.execute(
            "SELECT DISTINCT protocol_version FROM personal_assignments WHERE protocol_id = ?",
            ("scope-text-diagram-single-learner",))}
        if len(versions) > 1 or versions - {"v1", "v2"}:
            raise ApiError("comparison_version_conflict",
                           "Comparison assignments contain incompatible versions.", 409)
        comparison = LegacyPersonalComparison if "v1" in versions else PersonalComparison
        return comparison(self.store, self.now, prior_concept_exposure=prior)

    def reveal_comparison_solution(self, unit_id: object, phase: object) -> dict:
        comparison = self.personal_comparison()
        if isinstance(comparison, LegacyPersonalComparison):
            raise ApiError("comparison_version_conflict",
                           "Solution-opening records are unavailable for this historical protocol version.", 409)
        return comparison.reveal_solution(unit_id, phase)

    def _activate_pack(self, path: Path) -> None:
        self.pack = load_pack(path)
        self.version = VERSION_BY_CONTENT[self.pack.concepts[0].content_version]
        if self.pack.status != "draft" or any(
            item.answer_key and item.answer_key.status != "candidate" for item in self.pack.items
        ):
            raise RuntimeError("This preview is only for a draft pack with candidate keys")
        self.services = {
            concept.id: LearningService(
                self.store, concept,
                tuple(_catalog_item(item) for item in self.pack.items_for(concept.id)),
                reviewed=False, allow_development_fixtures=True,
                encountered_family_ids=frozenset(next(
                    lesson.encountered_family_ids for lesson in self.pack.lessons
                    if lesson.concept_id == concept.id)),
                now=self.now,
                policy_version=VERSION_BY_CONTENT[concept.content_version].policy_version,
            ) for concept in self.pack.concepts
        }

    def overview(self) -> dict:
        if self.store.learner_deleted():
            return {"deleted": True, "packVersion": self.pack.pack_version}
        order = self.pack.learning_order()
        def summary(cid: str) -> dict:
            service = self.services[cid]
            attempts = tuple(a for a in self.store.list_attempts(cid)
                             if a.content_version == service.concept.content_version)
            first_by_family = {}
            for attempt in sorted(attempts, key=lambda a: (a.occurred_at, a.id)):
                family = service.items[attempt.activity_id].spec.activity.family_id
                first_by_family.setdefault(family, attempt)
            independent_fresh = sum(
                attempt.score_status.value == "correct" and attempt.unassisted
                for family, attempt in first_by_family.items()
                if family not in service.encountered_family_ids
            )
            completed = self.store.lesson_completed_at(cid, service.concept.content_version)
            session = service.next_session(20) if completed else None
            next_check = session.get("nextCheckAt") if session else None
            due = datetime.fromisoformat(next_check.replace("Z", "+00:00")) if next_check else None
            if due is None:
                review_status = "none"
            elif self.now() < due:
                review_status = "upcoming"
            elif self.now() < due + timedelta(days=1):
                review_status = "due"
            else:
                review_status = "overdue"
            draft = self.store.open_draft(cid)
            return {
                "attempts": len(attempts),
                "unassistedCorrect": sum(a.score_status.value == "correct" and a.unassisted for a in attempts),
                "freshUnassistedCorrect": independent_fresh,
                "encounteredFamilyIds": sorted(service.encountered_family_ids),
                "hintAssisted": sum(not a.unassisted for a in attempts),
                "needsReview": sum(a.score_status.value == "ungraded" for a in attempts),
                "recentOutcome": attempts[-1].score_status.value if attempts else None,
                "recordedAttempts": [
                    {"id": attempt.id, "activityId": attempt.activity_id,
                     "familyId": service.items[attempt.activity_id].spec.activity.family_id,
                     "contentVersion": attempt.content_version,
                     "evidenceKind": service.items[attempt.activity_id].spec.activity.evidence_kind.value,
                     "occurredAt": attempt.occurred_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                     "firstAnswer": attempt.first_answer,
                     "scoreStatus": attempt.score_status.value,
                     "gradingMethod": attempt.grading_method,
                     "confidence": attempt.confidence,
                     "outsideStudy": attempt.outside_study.value if attempt.outside_study else None,
                     "hintLevel": attempt.hint_level.value,
                     "assisted": not attempt.unassisted}
                    for attempt in reversed(attempts)
                ],
                "evidence": summarize_evidence(
                    {item.spec.activity.id: item.spec.activity for item in service.items.values()},
                    attempts, completed, service.encountered_family_ids),
                "reviewSchedule": {"dueAt": next_check, "status": review_status,
                                   "reason": (("A new question is scheduled from the time you finished this lesson."
                                               if due else "No new later question is scheduled.")
                                              if self.version.plain_language else
                                              (f"Held-out independent review for {cid} "
                                               "is scheduled from the recorded lesson completion."
                                               if due else "No eligible unused delayed check is scheduled."))},
                "openDraft": ({"activityId": draft["activity_id"],
                               "savedAt": draft["recorded_at"],
                               "hintLevel": (self.store.hint_levels(draft["id"])[-1].value
                                             if self.store.hint_levels(draft["id"]) else "none")}
                              if draft else None),
            }
        concepts = [{"id": cid, "title": self.pack.concept(cid).title,
                     "lessonComplete": self.store.lesson_completed_at(
                         cid, self.pack.concept(cid).content_version) is not None,
                     "signals": summary(cid)} for cid in order]
        return {"developmentOnly": True, "packStatus": self.pack.status,
                "packVersion": self.pack.pack_version,
                "concepts": concepts, "pathRecommendation": self._path_recommendation(concepts),
                "experiment": self.experiment_findings()}

    def export(self) -> dict:
        raw = self.store.export_all()
        computed_at = self.now().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        overview = self.overview()
        return {
            **raw,
            "derived": {
                "computedAt": computed_at,
                "packVersion": self.pack.pack_version,
                "overview": overview,
            },
        }

    def delete_data(self) -> dict:
        self.store.delete_all(mark_deleted=True)
        self._activate_pack(CURRENT_PACK_PATH)
        return {"deleted": True, "packVersion": self.pack.pack_version}

    def restart(self) -> dict:
        self.store.restart_learner()
        return {"deleted": False}

    def _path_recommendation(self, concepts: list[dict]) -> dict:
        by_id = {concept["id"]: concept for concept in concepts}
        # Resume a locked answer before offering another activity.
        for concept in concepts:
            if self.store.open_draft(concept["id"]):
                return {"conceptId": concept["id"], "action": "resume",
                        "reason": "Finish your saved first answer before starting another activity."}
        for concept in concepts:
            if concept["lessonComplete"]:
                session = self.services[concept["id"]].next_session(20)
                if session["activity"] and session["activity"]["heldOut"]:
                    return {"conceptId": concept["id"], "action": "delayed_check",
                            "reason": session["recommendation"]["reason"]}
        for concept in concepts:
            if (concept["lessonComplete"] and
                    concept["signals"]["freshUnassistedCorrect"] == 0):
                return {"conceptId": concept["id"], "action": "practice",
                        "reason": ("Try a new question without help before moving on. "
                                   "A match with a draft answer key is only practice feedback."
                                   if self.version.plain_language else
                                   "Build one unassisted candidate-key match on a new item family before moving on.")}
        for concept in concepts:
            if not concept["lessonComplete"] and all(
                by_id[parent]["lessonComplete"] and
                by_id[parent]["signals"]["freshUnassistedCorrect"] > 0
                for parent in self.pack.prerequisites_of(concept["id"])):
                return {"conceptId": concept["id"], "action": "lesson",
                        "reason": ("Read the next lesson. It builds on what you studied before."
                                   if self.version.plain_language else
                                   "Read the next lesson in prerequisite order.")}
        for concept in concepts:
            if concept["lessonComplete"]:
                return {"conceptId": concept["id"], "action": "practice",
                        "reason": ("Keep practicing while you wait for a later question without help."
                                   if self.version.plain_language else
                                   "Continue practice while waiting for an independent delayed check.")}
        return {"conceptId": concepts[0]["id"], "action": "lesson",
                "reason": "Begin with the first lesson."}

    def lesson(self, cid: str) -> dict:
        self.store.require_active_learner()
        service = self._service(cid)
        lesson = next(x for x in self.pack.lessons if x.concept_id == cid)
        sources = {s.id: s for s in self.pack.sources}
        method = self._method_for(cid)
        if method:
            self.store.record_exposure(cid, service.concept.content_version,
                                       method["protocolId"], method["protocolVersion"],
                                       method["conditionId"], self.now(), lesson.encountered_family_ids)
        return {"conceptId": cid, "title": lesson.title, "body": lesson.body,
                "diagram": lesson.diagram if method and method["conditionId"] == "diagram" else None,
                "method": method,
                "experimentNotice": "Draft instructional comparison; no method benefit has been established." if method else None,
                "completed": self.store.lesson_completed_at(
                    cid, service.concept.content_version) is not None,
                "sources": [{"title": sources[sid].title, "url": sources[sid].url}
                            for sid in lesson.source_ids]}

    def complete_lesson(self, cid: str) -> dict:
        service = self._service(cid)
        method = self._method_for(cid)
        existing_exposure = next((row for row in self.store.list_exposures()
                                  if row["concept_id"] == cid and
                                  row["content_version"] == service.concept.content_version), None)
        if method and not existing_exposure:
            raise ApiError("lesson_required", "Open the assigned lesson before marking it read.", 409)
        stamp = service.complete_lesson()
        if method and existing_exposure:
            self.store.complete_exposure(cid, service.concept.content_version,
                                         method["protocolId"], method["protocolVersion"], stamp)
        return {"completedAt": stamp.isoformat(), "developmentOnly": True}

    def _method_for(self, cid: str) -> dict | None:
        self.store.require_active_learner()
        version = self.pack.concept(cid).content_version
        spec = VERSION_BY_CONTENT[version]
        if spec.comparison is None:
            return None
        protocol, assign, _, _ = spec.comparison.load()
        assignment = next((a for a in self.store.list_assignments(protocol.id)
                           if a.concept_id == cid and a.protocol_version == protocol.version), None)
        if assignment is None:
            assignment = ExperimentAssignment(protocol.id, protocol.version, cid, cid,
                                              assign(cid, self.store.learner_id()), protocol.seed, self.now())
            self.store.save_assignment(assignment)
        method = {"conditionId": assignment.condition_id, "protocolId": protocol.id,
                  "protocolVersion": protocol.version}
        if spec.report_study_target:
            method["studyTargetMinutes"] = protocol.target_exposure_minutes
        return method

    def experiment_findings(self) -> dict:
        version = self.pack.concepts[0].content_version
        spec = VERSION_BY_CONTENT[version]
        if spec.comparison is None:
            return {"status": "insufficient_evidence", "reason": "This content version predates the fixed comparison."}
        protocol, _, Exposure, analyze = spec.comparison.load()
        exposures = tuple(Exposure(
            row["concept_id"], row["content_version"], row["condition_id"],
            datetime.fromisoformat(row["exposed_at"]),
            tuple(json.loads(row["encountered_family_ids"])),
            row["protocol_id"], row["protocol_version"],
            datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        ) for row in self.store.list_exposures()
            if row["protocol_id"] == protocol.id and row["protocol_version"] == protocol.version)
        attempts = tuple(a for concept in self.pack.concepts
                         for a in self.store.list_attempts(concept.id))
        activities = {item.activity.id: item.activity for item in self.pack.items}
        assignments = tuple(a for a in self.store.list_assignments(protocol.id)
                            if a.protocol_version == protocol.version)
        if spec.descriptive_analysis:
            # Without an identity there cannot be assignments to validate.
            return analyze(assignments, exposures, attempts, activities,
                           learner_id=self.store.existing_learner_id() or "unassigned", now=self.now())
        return analyze(assignments, exposures, attempts, activities, now=self.now())

    def override(self, body: dict) -> dict:
        cid = body.get("conceptId")
        service = self._service(cid)
        if body.get("mode") != "practice" or body.get("reason") != "learner_choice":
            raise ApiError("validation_error", "Choose a valid practice override.")
        learner_reason = body.get("learnerReason")
        if learner_reason is not None and (not isinstance(learner_reason, str) or
                                           len(learner_reason) > 500):
            raise ApiError("validation_error", "An override note must be at most 500 characters.")
        normalized_note = learner_reason.strip() or None if learner_reason is not None else None
        path = self.overview()["pathRecommendation"]
        recommended = (self._service(path["conceptId"]).next_session(20, "recommended")
                       if path["action"] in ("practice", "delayed_check") else None)
        selected = service.next_session(20, "practice")
        event_id = str(uuid4())
        self.store.record_override(event_id, cid, service.concept.content_version,
                                   "practice", "learner_choice", self.now(),
                                   recommended_activity_id=((recommended or {}).get("activity") or {}).get("id"),
                                   recommended_reason=path["reason"],
                                   selected_activity_id=(selected.get("activity") or {}).get("id"),
                                   learner_reason=normalized_note,
                                   recommended_concept_id=path["conceptId"],
                                   recommended_action=path["action"],
                                   selected_concept_id=cid)
        return {"id": event_id, "saved": True,
                "selectedActivityId": (selected.get("activity") or {}).get("id")}

    def session(self, cid: str, mode: str = "recommended", available_minutes: int = 20) -> dict:
        service = self._service(cid)
        if mode not in ("recommended", "practice"):
            raise ApiError("validation_error", "Unknown practice mode.")
        if type(available_minutes) is not int or not 5 <= available_minutes <= 60:
            raise ApiError("validation_error", "Choose a session length from 5 to 60 minutes.")
        if self.store.lesson_completed_at(cid, service.concept.content_version) is None:
            return {"lessonRequired": True, "activity": None}
        draft = self.store.open_draft(cid)
        if draft:
            item = service.items[draft["activity_id"]]
            result = {"activity": item.public(), "recommendation": {"reason": "Resume your saved answer"},
                      "draft": {"id": draft["id"], "firstAnswer": draft["first_answer"],
                                "confidence": draft["confidence"],
                                "hintLevels": [x.value for x in self.store.hint_levels(draft["id"])]}}
        else:
            result = service.next_session(available_minutes, mode)
            result["draft"] = None
        if result.get("activity"):
            viewed = set(result["draft"]["hintLevels"]) if result["draft"] else set()
            for hint in result["activity"]["hints"]:
                if hint["level"] not in viewed:
                    hint.pop("text")
        return result

    def first_answer(self, body: dict) -> dict:
        cid, aid, did, answer = (body.get(k) for k in
                                 ("conceptId", "activityId", "draftId", "answer"))
        service = self._service(cid)
        try:
            UUID(did, version=4)
        except (TypeError, ValueError, AttributeError):
            raise ApiError("validation_error", "A UUID draftId is required.") from None
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 12000:
            raise ApiError("validation_error", "Enter an answer (up to 12,000 characters).")
        confidence = body.get("confidence")
        if confidence is not None and (type(confidence) not in (int, float) or
                                       not 0 <= confidence <= 1):
            raise ApiError("validation_error", "Confidence must be between 0 and 1 or null.")
        existing = self.store.get_draft(did)
        if existing:
            if (existing["activity_id"], existing["first_answer"], existing["confidence"]) != (aid, answer, confidence):
                raise ApiError("conflict", "This answer ID already belongs to another answer.", 409)
            return {"draftId": did, "saved": True}
        if self.store.open_draft(cid):
            raise ApiError("conflict", "Finish your saved answer first.", 409)
        session = self.session(cid, body.get("mode", "recommended"),
                               body.get("availableMinutes", 20))
        if not session.get("activity") or session["activity"]["id"] != aid:
            raise ApiError("activity_unavailable", "Choose the activity currently offered.", 409)
        item = service.items[aid]
        if item.spec.choices and answer not in item.spec.choices:
            raise ApiError("validation_error", "Choose one of the listed options.")
        self.store.save_draft(did, aid, service.concept.content_version, answer, self.now(), confidence)
        return {"draftId": did, "saved": True}

    def hint(self, body: dict) -> dict:
        draft, service, item = self._draft_item(body.get("draftId"))
        if draft["submitted_attempt_id"]:
            raise ApiError("conflict", "This answer is already submitted.", 409)
        viewed = self.store.hint_levels(draft["id"])
        current = viewed[-1] if viewed else HintLevel.NONE
        next_level = item.spec.hints.next_level(current)
        if next_level is None:
            raise ApiError("hint_exhausted", "All hints are open.", 409)
        self.store.save_hint(draft["id"], next_level, self.now())
        revealed = next(h for h in item.spec.hints.hints if h.level == next_level)
        return {"level": next_level.value, "text": revealed.text}

    def submit(self, body: dict) -> dict:
        draft, service, item = self._draft_item(body.get("draftId"))
        if draft["response_json"]:
            return json.loads(draft["response_json"])
        levels = self.store.hint_levels(draft["id"])
        hint = levels[-1] if levels else HintLevel.NONE
        existing = next((a for a in self.store.list_attempts(service.concept.id)
                         if a.id == draft["id"]), None)
        if existing is not None:
            result = assess(item.spec, draft["first_answer"], hint)
            response = {"attemptId": existing.id, "scoreStatus": existing.score_status.value,
                        "gradingMethod": existing.grading_method,
                        "assisted": not existing.unassisted,
                        "nextReason": result.reason, "developmentOnly": True}
            self._add_scored_solution(response, item)
            if item.spec.rubric:
                rubric = item.spec.rubric
                response["rubric"] = {"id": rubric.id, "version": rubric.version,
                                      "criteria": [{"id": c.id, "description": c.description}
                                                   for c in rubric.criteria]}
            self.store.finish_draft(draft["id"], response)
            return response
        response = service.submit_attempt({
            "activityId": item.spec.activity.id,
            "contentVersion": item.spec.activity.content_version,
            "firstAnswer": draft["first_answer"], "hintLevel": hint.value,
            "confidence": draft["confidence"], "outsideStudy": body.get("outsideStudy"),
            "outsideStudyDetail": body.get("outsideStudyDetail"), "activeSeconds": body.get("activeSeconds", 0),
        }, attempt_id=draft["id"])
        self._add_scored_solution(response, item)
        self.store.finish_draft(draft["id"], response)
        return response

    @staticmethod
    def _add_scored_solution(response: dict, item: CatalogItem) -> None:
        # Never expose candidate keys through lesson or session payloads.
        # This helper is called only after the locked first answer is graded.
        if item.spec.answer_key is None:
            return
        if item.explanation:
            response["explanation"] = item.explanation
        response["solution"] = {
            "kind": "candidate_key",
            "answer": item.spec.answer_key.accepted[0],
            "reasoning": item.explanation or "Candidate key supplied without a reviewed explanation.",
            "misconception": " ".join(item.common_mistakes) if item.common_mistakes else None,
        }

    def _service(self, cid) -> LearningService:
        if not isinstance(cid, str) or cid not in self.services:
            raise ApiError("not_found", "Concept was not found.", 404)
        return self.services[cid]

    def _draft_item(self, did):
        if not isinstance(did, str):
            raise ApiError("validation_error", "draftId is required.")
        draft = self.store.get_draft(did)
        if draft is None:
            raise ApiError("not_found", "Saved answer was not found.", 404)
        activity = self.store.get_activity(draft["activity_id"], draft["content_version"])
        service = self._service(activity.concept_id)
        return draft, service, service.items[activity.id]


def make_handler(preview: Preview, *, port: int = PORT):
    class Handler(BaseHTTPRequestHandler):
        def _check_origin(self) -> bool:
            host = self.headers.get("Host", "")
            if host not in (f"{HOST}:{port}", f"localhost:{port}"):
                self._json(403, {"error": "Invalid host"})
                return False
            if self.command == "POST" and self.headers.get("Origin") != f"http://{host}":
                self._json(403, {"error": "Invalid origin"})
                return False
            return True

        def _json(self, status: int, data: dict):
            payload = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _dispatch(self):
            if not self._check_origin():
                return
            path = urlsplit(self.path).path
            query = parse_qs(urlsplit(self.path).query)
            try:
                if self.command == "GET":
                    if path == "/api/v2/overview":
                        return self._json(200, preview.overview())
                    if path == "/api/v2/session":
                        raw_minutes = query.get("availableMinutes", ["20"])[0]
                        if not raw_minutes.isdecimal():
                            raise ApiError("validation_error", "Session length must be a whole number.")
                        return self._json(200, preview.session(query.get("conceptId", [None])[0],
                                                               query.get("mode", ["recommended"])[0],
                                                               int(raw_minutes)))
                    if path == "/api/v2/export":
                        return self._json(200, preview.export())
                    if path == "/api/v2/personal-comparison":
                        return self._json(200, preview.personal_comparison().report())
                    files = {"/": ("index.html", "text/html"),
                             "/app.js": ("app.js", "text/javascript"),
                             "/theme-init.js": ("theme-init.js", "text/javascript"),
                             "/style.css": ("style.css", "text/css"),
                             "/icon.svg": ("icon.svg", "image/svg+xml")}
                    if path in files:
                        name, mime = files[path]
                        content = (WEB / name).read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", mime + "; charset=utf-8")
                        self.send_header("Content-Length", str(len(content)))
                        self.send_header("X-Content-Type-Options", "nosniff")
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        self.wfile.write(content)
                        return
                if self.command == "POST" and path.startswith("/api/v2/"):
                    if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                        raise ApiError("validation_error", "Send JSON.", 415)
                    size = int(self.headers.get("Content-Length", "0"))
                    if size < 2 or size > 30000:
                        raise ApiError("validation_error", "JSON body size is invalid.")
                    body = json.loads(self.rfile.read(size))
                    if not isinstance(body, dict):
                        raise ApiError("validation_error", "JSON body must be an object.")
                    routes = {"/api/v2/lesson": lambda: preview.lesson(body.get("conceptId")),
                              "/api/v2/lesson-completions": lambda: preview.complete_lesson(body.get("conceptId")),
                              "/api/v2/first-answers": lambda: preview.first_answer(body),
                              "/api/v2/hints": lambda: preview.hint(body),
                              "/api/v2/attempts": lambda: preview.submit(body),
                              "/api/v2/self-reviews": lambda: preview._service(body.get("conceptId")).submit_self_review(body),
                              "/api/v2/revisions": lambda: preview._service(body.get("conceptId")).submit_revision(body),
                              "/api/v2/overrides": lambda: preview.override(body),
                              "/api/v2/personal-comparison/enroll": lambda: preview.personal_comparison().enroll(),
                              "/api/v2/personal-comparison/start": lambda: preview.personal_comparison().start_exposure(body.get("unitId")),
                              "/api/v2/personal-comparison/complete": lambda: preview.personal_comparison().complete_exposure(body.get("unitId"), body.get("outsideStudy")),
                              "/api/v2/personal-comparison/open": lambda: preview.personal_comparison().open_question(body.get("unitId"), body.get("phase")),
                              "/api/v2/personal-comparison/hint": lambda: preview.personal_comparison().hint(body.get("unitId")),
                              "/api/v2/personal-comparison/answer": lambda: preview.personal_comparison().answer(body.get("unitId"), body.get("phase"), body.get("answer"), body.get("outsideStudy"), body.get("confidence")),
                              "/api/v2/personal-comparison/reveal": lambda: preview.reveal_comparison_solution(body.get("unitId"), body.get("phase")),
                              "/api/v2/personal-comparison/override": lambda: preview.personal_comparison().override(body.get("recommendedUnitId"), body.get("recommendedStage"), body.get("selectedUnitId"), body.get("selectedStage"), body.get("learnerReason")),
                              "/api/v2/delete": preview.delete_data,
                              "/api/v2/restart": preview.restart}
                    if path in routes:
                        return self._json(200, routes[path]())
            except (ApiError, ValueError, json.JSONDecodeError) as exc:
                if isinstance(exc, ApiError):
                    return self._json(exc.status, {"error": exc.code, "message": exc.message})
                return self._json(400, {"error": "validation_error", "message": str(exc)})
            self._json(404, {"error": "not_found"})

        def do_GET(self):
            self._dispatch()

        def do_POST(self):
            self._dispatch()

    return Handler


def main(*, port: int = PORT, db: Path = DB) -> None:
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    preview = Preview(db)
    print(f"Foreman preview: http://{HOST}:{port}/ ({preview.pack.pack_version})", flush=True)
    HTTPServer((HOST, port), make_handler(preview, port=port)).serve_forever()


if __name__ == "__main__":
    main()
