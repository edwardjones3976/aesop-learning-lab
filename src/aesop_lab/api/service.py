"""Application service: versioned content, scheduling, assessment, persistence."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable, Mapping
from uuid import uuid4

from aesop_lab.assessment.engine import assess, build_attempt
from aesop_lab.assessment.errors import AssessmentError
from aesop_lab.assessment.items import ItemSpec
from aesop_lab.assessment.review import build_self_review
from aesop_lab.domain.models import AnswerRevision, Concept, CriterionReview, HintLevel, OutsideStudy, ReviewRating, ScoreStatus
from aesop_lab.scheduler import LearnerState, recommend
from aesop_lab.storage.sqlite import SQLiteStore


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass(frozen=True, slots=True)
class CatalogItem:
    spec: ItemSpec
    prompt: str
    body: str = ""
    learning_objective: str | None = None
    difficulty: str | None = None
    explanation: str | None = None
    common_mistakes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("an activity prompt is required")

    def public(self) -> dict[str, object]:
        activity = self.spec.activity
        return {
            "id": activity.id, "conceptId": activity.concept_id,
            "contentVersion": activity.content_version, "familyId": activity.family_id,
            "type": activity.activity_type.value, "evidenceKind": activity.evidence_kind.value,
            "heldOut": activity.held_out,
            "checkDelayDays": activity.check_delay_days,
            "prompt": self.prompt, "body": self.body,
            "learningObjective": self.learning_objective, "difficulty": self.difficulty,
            "choices": list(self.spec.choices),
            "hints": [{"level": hint.level.value, "text": hint.text}
                      for hint in self.spec.hints.hints],
        }


class LearningService:
    """One local learner and one concept version.

    Unreviewed catalog items are accepted only with an explicit development
    fixture opt-in. That opt-in is also exposed in responses.
    """

    def __init__(self, store: SQLiteStore, concept: Concept,
                 items: tuple[CatalogItem, ...], *, reviewed: bool,
                 allow_development_fixtures: bool = False,
                 encountered_family_ids: frozenset[str] = frozenset(),
                 now: Callable[[], datetime] | None = None,
                 policy_version: str = "pilot-v1") -> None:
        if reviewed:
            raise ValueError("reviewed pack loader and receipt verification are not integrated")
        if not reviewed and not allow_development_fixtures:
            raise ValueError("unreviewed content requires development fixture opt-in")
        if not items or len({item.spec.activity.id for item in items}) != len(items):
            raise ValueError("catalog needs distinct activity IDs")
        if any(item.spec.activity.concept_id != concept.id or
               item.spec.activity.content_version != concept.content_version
               for item in items):
            raise ValueError("catalog items must match the concept version")
        self.store, self.concept = store, concept
        self.items: Mapping[str, CatalogItem] = {
            item.spec.activity.id: item for item in items
        }
        self.development_only = not reviewed
        self.encountered_family_ids = encountered_family_ids
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.policy_version = policy_version
        store.add_concept(concept)
        for item in items:
            store.add_activity(item.spec.activity)

    def complete_lesson(self) -> datetime:
        """Record a real lesson event once; restarts cannot restart its clock."""
        return self.store.record_lesson_completion(
            self.concept.id, self.concept.content_version, self.now())

    def _state(self) -> LearnerState:
        completed = self.store.lesson_completed_at(
            self.concept.id, self.concept.content_version)
        if completed is None:
            raise ApiError("lesson_required", "Complete the lesson before practice.", 409)
        return LearnerState(
            self.concept.id, self.concept.content_version, completed, self.now(),
            tuple(item.spec.activity for item in self.items.values()),
            tuple(attempt for attempt in self.store.list_attempts(self.concept.id)
                  if attempt.content_version == self.concept.content_version),
            self.encountered_family_ids,
        )

    def next_session(self, available_minutes: int, mode: str = "recommended") -> dict[str, object]:
        if type(available_minutes) is not int or available_minutes < 1:
            raise ApiError("validation_error", "availableMinutes must be a positive whole number.")
        if mode not in ("recommended", "practice"):
            raise ApiError("validation_error", "mode must be recommended or practice.")
        learner_state = self._state()
        decision = recommend(learner_state, available_minutes, self.policy_version, mode)
        selected = decision.recommendation
        selected_item = self.items[selected.activity_id] if selected else None
        first_by_family = {}
        for attempt in sorted(learner_state.attempts, key=lambda a: (a.occurred_at, a.id)):
            family = self.items[attempt.activity_id].spec.activity.family_id
            first_by_family.setdefault(family, attempt)
        independent_by_kind = {}
        for attempt in first_by_family.values():
            if attempt.score_status is ScoreStatus.CORRECT and attempt.unassisted:
                kind = self.items[attempt.activity_id].spec.activity.evidence_kind.value
                independent_by_kind[kind] = independent_by_kind.get(kind, 0) + 1
        missing = None
        if selected_item:
            kind = selected_item.spec.activity.evidence_kind.value
            if selected_item.spec.activity.held_out:
                missing = "No first independent response to this held-out family has been recorded."
            else:
                count = independent_by_kind.get(kind, 0)
                missing = (f"{count} distinct first-attempt families have an independent "
                           f"candidate-key match in {kind}; this activity gathers another observation.")
        result: dict[str, object] = {
            "mode": mode,
            "nextCheckAt": _iso(decision.next_check_at),
            "activity": self.items[selected.activity_id].public() if selected else None,
            "recommendation": ({
                "policyVersion": selected.policy_version, "reason": selected.reason,
                "evidenceAttemptIds": list(selected.evidence_attempt_ids),
                "aim": selected_item.learning_objective or f"Practice {kind} independently.",
                "evidenceGap": missing,
            } if selected else None),
            "developmentOnly": self.development_only,
        }
        if selected is None:
            result["reason"] = decision.reason
        return result

    def submit_attempt(self, body: object, *, attempt_id: str | None = None) -> dict[str, object]:
        if not isinstance(body, dict):
            raise ApiError("validation_error", "Attempt body must be an object.")
        required = ("activityId", "contentVersion", "firstAnswer", "hintLevel",
                    "confidence", "outsideStudy", "outsideStudyDetail", "activeSeconds")
        if any(key not in body for key in required):
            raise ApiError("validation_error", "Attempt body is missing required fields.")
        if not isinstance(body["activityId"], str) or not isinstance(body["contentVersion"], str):
            raise ApiError("validation_error", "Activity ID and content version must be text.")
        item = self.items.get(body["activityId"])
        if item is None or body["contentVersion"] != self.concept.content_version:
            raise ApiError("not_found", "Activity version was not found.", 404)
        if not isinstance(body["firstAnswer"], str) or not body["firstAnswer"].strip():
            raise ApiError("validation_error", "A first answer is required.")
        try:
            hint = HintLevel(body["hintLevel"])
        except (ValueError, TypeError):
            raise ApiError("validation_error", "Unknown hint level.") from None
        confidence = body["confidence"]
        if confidence is not None and (type(confidence) not in (int, float) or
                                       not 0 <= confidence <= 1):
            raise ApiError("validation_error", "Confidence must be between 0 and 1 or null.")
        try:
            outside = (OutsideStudy(body["outsideStudy"])
                       if body["outsideStudy"] is not None else None)
        except (ValueError, TypeError):
            raise ApiError("validation_error", "Unknown outsideStudy value.") from None
        detail = body["outsideStudyDetail"]
        if detail is not None and not isinstance(detail, str):
            raise ApiError("validation_error", "outsideStudyDetail must be text or null.")
        seconds = body["activeSeconds"]
        if type(seconds) is not int or seconds < 0:
            raise ApiError("validation_error", "activeSeconds must be a nonnegative whole number.")
        available_minutes = body.get("availableMinutes", 20)
        if type(available_minutes) is not int or available_minutes < 1:
            raise ApiError("validation_error", "availableMinutes must be a positive whole number.")
        state = self._state()
        activity = item.spec.activity
        if activity.held_out:
            decision = recommend(state, available_minutes, self.policy_version)
            if decision.recommendation is None or decision.recommendation.activity_id != activity.id:
                raise ApiError("check_unavailable", "This independent check is not available.", 409)
            reason = decision.reason
        else:
            reason = recommend(state, 20, self.policy_version, "practice").reason
        try:
            result = assess(item.spec, body["firstAnswer"], hint)
        except AssessmentError as exc:
            raise ApiError(exc.code, str(exc)) from exc
        if self.development_only and result.grading_method == "reviewed_exact_key":
            result = replace(
                result,
                grading_method="development_fixture_exact_key",
                reason=result.reason.replace("reviewed key", "development fixture key"),
                scope="Development fixture key only; no human review or learner claim.",
            )
        attempt = build_attempt(
            item.spec, result, attempt_id=attempt_id or str(uuid4()), occurred_at=self.now(),
            first_answer=body["firstAnswer"], selection_reason=reason,
            confidence=confidence, outside_study=outside, outside_study_detail=detail,
            active_seconds=seconds,
        )
        self.store.append_attempt(attempt)
        response: dict[str, object] = {
            "attemptId": attempt.id, "scoreStatus": result.score_status.value,
            "gradingMethod": result.grading_method, "assisted": result.assisted,
            "nextReason": result.reason, "developmentOnly": self.development_only,
        }
        if item.spec.rubric is not None:
            rubric = item.spec.rubric
            response["rubric"] = {
                "id": rubric.id, "version": rubric.version,
                "criteria": [{"id": criterion.id, "description": criterion.description,
                              "shownDescription": criterion.shown_description,
                              "partialDescription": criterion.partial_description}
                             for criterion in rubric.criteria],
            }
        return response

    def submit_self_review(self, body: object) -> dict[str, object]:
        if not isinstance(body, dict):
            raise ApiError("validation_error", "Self review body must be an object.")
        attempt_id = body.get("attemptId")
        if not isinstance(attempt_id, str):
            raise ApiError("validation_error", "attemptId is required.")
        attempt = next((a for a in self.store.list_attempts(self.concept.id)
                        if a.id == attempt_id), None)
        if attempt is None:
            raise ApiError("not_found", "Attempt was not found.", 404)
        item = self.items.get(attempt.activity_id)
        if item is None or item.spec.rubric is None:
            raise ApiError("validation_error", "Attempt has no self review rubric.")
        rubric = item.spec.rubric
        if body.get("rubricId") != rubric.id or body.get("rubricVersion") != rubric.version:
            raise ApiError("validation_error", "The rubric version does not match.")
        raw = body.get("judgments")
        if not isinstance(raw, list):
            raise ApiError("validation_error", "Review every rubric criterion.")
        confidence = body.get("confidence")
        if confidence is not None and (type(confidence) not in (int, float) or not 0 <= confidence <= 1):
            raise ApiError("validation_error", "Review confidence must be between 0 and 1 or null.")
        try:
            judgments = tuple(CriterionReview(j["criterionId"], ReviewRating(j["rating"]),
                                               j.get("evidence", "")) for j in raw)
            review = build_self_review(item.spec, attempt, review_id=str(uuid4()),
                                       occurred_at=self.now(), judgments=judgments,
                                       confidence=confidence)
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiError("validation_error", str(exc)) from exc
        self.store.append_self_review(review)
        return {"reviewId": review.id, "nextStep": review.next_step,
                "comparison": {"annotatedExample": rubric.annotated_example,
                               "commonMistakes": list(rubric.common_mistakes)},
                "developmentOnly": self.development_only}

    def submit_revision(self, body: object) -> dict[str, object]:
        if not isinstance(body, dict) or not isinstance(body.get("reviewId"), str):
            raise ApiError("validation_error", "reviewId is required.")
        answer = body.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ApiError("validation_error", "A revision answer is required.")
        review_id = body["reviewId"]
        if not self.store.has_self_review(review_id):
            raise ApiError("not_found", "Review was not found.", 404)
        revision = AnswerRevision(str(uuid4()), review_id, self.now(), answer)
        self.store.append_revision(revision)
        return {"revisionId": revision.id, "developmentOnly": self.development_only}

    def export_data(self) -> dict[str, object]:
        return self.store.export_all()

    def delete_data(self) -> dict[str, object]:
        self.store.delete_all()
        return {"deleted": True}


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value else None
