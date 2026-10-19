"""Prospective, local-only comparison of four scope and parameter micro-units.

One learner supplies repeated, dependent observations. Nothing here estimates a
population effect or executes learner-submitted Python.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
from typing import Callable

from aesop_lab.storage.sqlite import SQLiteStore


PROTOCOL_ID = "scope-text-diagram-single-learner"
PROTOCOL_VERSION = "v1"
CONTENT_VERSION = "scope-comparison-draft.1"
SEED = 20261018
CONCEPT_ID = "parameters-and-local-scope"
DELAY_DAYS = 7
WINDOW_DAYS = 14
# Nonauthor AI engineering review verified the fixed snippets, keys and diagrams.
# Content stays draft without qualified human subject-matter validation.
CONTENT_REVIEW_STATUS = "engineering_reviewed"


@dataclass(frozen=True, slots=True)
class Unit:
    id: str
    pair: int
    name: str
    worked_code: str
    worked_answer: str
    worked_steps: tuple[str, ...]
    diagram: str
    practice_code: str
    practice_answer: str
    practice_steps: tuple[str, ...]
    delayed_code: str
    delayed_answer: str
    delayed_steps: tuple[str, ...]

    def family(self, phase: str) -> str:
        return f"{self.id}-{phase}-family-{CONTENT_VERSION}"


UNITS = (
    Unit("scope-a", 1, "Local bonus A",
         "bonus = 50\ndef add(base, bonus=2):\n    return base + bonus\nresult = add(10, bonus=3)",
         "13, 50", ("The keyword argument binds this call's local bonus to 3, replacing the default 2.",
                    "The call returns 10 + 3 = 13, so result is 13.",
                    "The global bonus remains 50 because the parameter is local to the call."),
         "global bonus: 50  |  call add(10, bonus=3)\n"
         "                         v\nlocal base: 10; local bonus: 3\n"
         "                         v\nreturn 13 -> result: 13; global bonus: 50",
         "bonus = 40\ndef award(points, bonus=1):\n    return points + bonus\nscore = award(8, bonus=4)",
         "12, 40", ("The keyword value 4 replaces the local default 1.",
                    "The call returns 8 + 4 = 12, so score is 12.", "The global bonus stays 40."),
         "bonus = 90\ndef credit(points, bonus=2):\n    bonus = bonus + 1\n    return points - bonus\nreceipt = credit(11, bonus=5)",
         "5, 90", ("The keyword binds local bonus to 5; the function then rebinds it to 6.",
                   "credit returns 11 - 6 = 5.", "Rebinding the local parameter leaves global bonus at 90.")),
    Unit("scope-b", 1, "Local bonus B",
         "bonus = 60\ndef add(base, bonus=4):\n    return base + bonus\nresult = add(12, bonus=5)",
         "17, 60", ("The keyword argument binds this call's local bonus to 5, replacing the default 4.",
                    "The call returns 12 + 5 = 17, so result is 17.",
                    "The global bonus remains 60 because the parameter is local to the call."),
         "global bonus: 60  |  call add(12, bonus=5)\n"
         "                         v\nlocal base: 12; local bonus: 5\n"
         "                         v\nreturn 17 -> result: 17; global bonus: 60",
         "bonus = 30\ndef award(points, bonus=2):\n    return points + bonus\nscore = award(9, bonus=6)",
         "15, 30", ("The keyword value 6 replaces the local default 2.",
                    "The call returns 9 + 6 = 15, so score is 15.", "The global bonus stays 30."),
         "bonus = 80\ndef credit(points, bonus=3):\n    points = points + bonus\n    return points - bonus\nreceipt = credit(13, bonus=4)",
         "13, 80", ("The keyword binds local bonus to 4; local points starts at 13.",
                    "Local points becomes 17, then credit returns 17 - 4 = 13.",
                    "Changing points inside the call leaves global bonus at 80.")),
    Unit("scope-c", 2, "Local step C",
         "step = 70\ndef advance(start, step=2):\n    return start + step\nfinish = advance(14, step=4)",
         "18, 70", ("The explicit step 4 replaces the default 2 inside this call.",
                    "The call returns 14 + 4 = 18, so finish is 18.",
                    "The global step remains 70; the parameter is a different binding."),
         "global step: 70  |  call advance(14, step=4)\n"
         "                         v\nlocal start: 14; local step: 4\n"
         "                         v\nreturn 18 -> finish: 18; global step: 70",
         "step = 35\ndef move(position, step=1):\n    return position + step\nend = move(7, step=5)",
         "12, 35", ("The local step is 5 rather than the default 1.",
                    "The call returns 7 + 5 = 12, so end is 12.", "The global step remains 35."),
         "step = 95\ndef shift(position, step=2):\n    step = step * 2\n    return position + step\nend = shift(15)",
         "19, 95", ("No step argument is supplied, so the local parameter starts at its default 2.",
                    "The function rebinds local step to 4 and returns 15 + 4 = 19.",
                    "The global step stays 95.")),
    Unit("scope-d", 2, "Local step D",
         "step = 80\ndef advance(start, step=3):\n    return start + step\nfinish = advance(16, step=6)",
         "22, 80", ("The explicit step 6 replaces the default 3 inside this call.",
                    "The call returns 16 + 6 = 22, so finish is 22.",
                    "The global step remains 80; the parameter is a different binding."),
         "global step: 80  |  call advance(16, step=6)\n"
         "                         v\nlocal start: 16; local step: 6\n"
         "                         v\nreturn 22 -> finish: 22; global step: 80",
         "step = 45\ndef move(position, step=2):\n    return position + step\nend = move(8, step=7)",
         "15, 45", ("The local step is 7 rather than the default 2.",
                    "The call returns 8 + 7 = 15, so end is 15.", "The global step remains 45."),
         "step = 85\ndef shift(position, step=4):\n    position = position + step\n    return position * 2\nend = shift(17)",
         "42, 85", ("No step argument is supplied, so local step starts at its default 4.",
                    "Local position becomes 17 + 4 = 21; the return is 21 * 2 = 42.",
                    "The global step stays 85.")),
)
UNIT_BY_ID = {unit.id: unit for unit in UNITS}


def assigned_conditions(learner_id: str) -> tuple[str, ...]:
    """One text and one diagram unit in each pair; reverse order in pair two."""
    payload = f"{PROTOCOL_ID}\0{PROTOCOL_VERSION}\0{SEED}\0{learner_id}".encode()
    first = sha256(payload).digest()[0] & 1
    return ("diagram", "text", "text", "diagram") if first else (
        "text", "diagram", "diagram", "text")


def _iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("comparison clock must include a timezone")
    return value.isoformat()


def _answer(value: object) -> str:
    if not isinstance(value, str) or len(value) > 100 or not value.strip():
        raise ValueError("Enter the two values as number, number.")
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2 or any(not part.lstrip("-").isdigit() for part in parts):
        raise ValueError("Enter exactly two whole numbers as number, number.")
    return ", ".join(str(int(part)) for part in parts)


class PersonalComparison:
    def __init__(self, store: SQLiteStore, now: Callable[[], datetime], *,
                 prior_concept_exposure: bool) -> None:
        self.store = store
        self.now = now
        self.prior_concept_exposure = prior_concept_exposure

    def _rows(self, table: str) -> dict[str, dict]:
        if table not in ("personal_assignments", "personal_exposures"):
            raise ValueError("unknown comparison table")
        return {row["unit_id"]: dict(row) for row in self.store.connection.execute(
            f"SELECT * FROM {table} WHERE protocol_id = ? AND protocol_version = ?",
            (PROTOCOL_ID, PROTOCOL_VERSION))}

    def _responses(self) -> dict[tuple[str, str], dict]:
        return {(row["unit_id"], row["phase"]): dict(row)
                for row in self.store.connection.execute(
                    "SELECT rowid AS event_order, * FROM personal_responses WHERE protocol_id = ? AND protocol_version = ?",
                    (PROTOCOL_ID, PROTOCOL_VERSION))}

    def _views(self) -> dict[tuple[str, str], dict]:
        return {(row["unit_id"], row["phase"]): dict(row)
                for row in self.store.connection.execute(
                    "SELECT * FROM personal_question_views WHERE protocol_id = ? AND protocol_version = ?",
                    (PROTOCOL_ID, PROTOCOL_VERSION))}

    def enroll(self) -> dict:
        if self._rows("personal_assignments"):
            return self.report()
        if self.store.connection.execute(
                "SELECT 1 FROM personal_assignments WHERE protocol_id = ? "
                "AND protocol_version <> ? LIMIT 1",
                (PROTOCOL_ID, PROTOCOL_VERSION)).fetchone():
            raise ValueError("This learner already has a comparison assignment on another protocol version.")
        if self.prior_concept_exposure:
            raise ValueError("This concept already has learner history; a prospective comparison must start before its lesson or practice.")
        conditions = assigned_conditions(self.store.learner_id())
        at = _iso(self.now())
        with self.store.connection:
            for index, (unit, condition) in enumerate(zip(UNITS, conditions, strict=True)):
                self.store.connection.execute(
                    "INSERT INTO personal_assignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (PROTOCOL_ID, PROTOCOL_VERSION, CONTENT_VERSION, unit.id,
                     unit.pair, index, condition, at))
        return self.report()

    def _assigned(self, unit_id: str) -> dict:
        if unit_id not in UNIT_BY_ID:
            raise ValueError("Unknown comparison unit.")
        row = self._rows("personal_assignments").get(unit_id)
        if row is None:
            raise ValueError("Enroll before opening a comparison unit.")
        return row

    def start_exposure(self, unit_id: str) -> dict:
        assignment = self._assigned(unit_id)
        exposures = self._rows("personal_exposures")
        responses = self._responses()
        position = assignment["position"]
        for prior in UNITS[:position]:
            if (prior.id, "practice") not in responses:
                raise ValueError("Finish the earlier unit's practice first.")
        if unit_id not in exposures:
            with self.store.connection:
                self.store.connection.execute(
                    "INSERT INTO personal_exposures VALUES (?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL)",
                    (PROTOCOL_ID, PROTOCOL_VERSION, CONTENT_VERSION, unit_id,
                     assignment["condition_id"], _iso(self.now()),
                     json.dumps([UNIT_BY_ID[unit_id].family("worked")])))
        return self.report()

    def complete_exposure(self, unit_id: str, outside_study: str | None = None) -> dict:
        self._assigned(unit_id)
        if outside_study not in (None, "none", "some", "unknown"):
            raise ValueError("Outside study must be none, some, unknown, or absent.")
        row = self._rows("personal_exposures").get(unit_id)
        if row is None:
            raise ValueError("Open the worked example first.")
        if row["completed_at"] is None:
            with self.store.connection:
                self.store.connection.execute(
                    "UPDATE personal_exposures SET completed_at = ?, outside_study = ? "
                    "WHERE protocol_id = ? AND protocol_version = ? AND unit_id = ?",
                    (_iso(self.now()), outside_study, PROTOCOL_ID, PROTOCOL_VERSION, unit_id))
        return self.report()

    def hint(self, unit_id: str) -> dict:
        self._assigned(unit_id)
        row = self._rows("personal_exposures").get(unit_id)
        if row is None or row["completed_at"] is None:
            raise ValueError("Study the worked example before practice support.")
        if (unit_id, "practice") not in self._views():
            raise ValueError("Open the practice question before using a hint.")
        if (unit_id, "practice") in self._responses():
            raise ValueError("Practice was already submitted.")
        with self.store.connection:
            self.store.connection.execute(
                "UPDATE personal_exposures SET hint_opened_at = COALESCE(hint_opened_at, ?) "
                "WHERE protocol_id = ? AND protocol_version = ? AND unit_id = ?",
                (_iso(self.now()), PROTOCOL_ID, PROTOCOL_VERSION, unit_id))
        return {"hint": "Track the value of the local keyword parameter inside the call, then the unchanged global name.",
                "assisted": True}

    def open_question(self, unit_id: str, phase: str) -> dict:
        self._assigned(unit_id)
        if phase not in ("practice", "delayed"):
            raise ValueError("Unknown comparison response phase.")
        exposure = self._rows("personal_exposures").get(unit_id)
        if exposure is None or exposure["completed_at"] is None:
            raise ValueError("Complete the worked example before opening a question.")
        if phase == "delayed":
            if (unit_id, "practice") not in self._responses():
                raise ValueError("Complete practice before a delayed check.")
            if self.now() < datetime.fromisoformat(exposure["completed_at"]) + timedelta(days=DELAY_DAYS):
                raise ValueError("The unfamiliar delayed check is not due yet.")
        if (unit_id, phase) in self._responses():
            raise ValueError("That first response has already been recorded.")
        with self.store.connection:
            self.store.connection.execute(
                "INSERT OR IGNORE INTO personal_question_views VALUES (?, ?, ?, ?, ?, ?, ?)",
                (PROTOCOL_ID, PROTOCOL_VERSION, CONTENT_VERSION, unit_id, phase,
                 UNIT_BY_ID[unit_id].family(phase), _iso(self.now())))
            if phase == "practice":
                families = json.loads(exposure["encountered_family_ids"])
                family = UNIT_BY_ID[unit_id].family("practice")
                if family not in families:
                    families.append(family)
                    self.store.connection.execute(
                        "UPDATE personal_exposures SET encountered_family_ids = ? "
                        "WHERE protocol_id = ? AND protocol_version = ? AND unit_id = ?",
                        (json.dumps(families), PROTOCOL_ID, PROTOCOL_VERSION, unit_id))
        return self.report()

    def answer(self, unit_id: str, phase: str, response: object,
               outside_study: str | None = None, confidence: float | None = None) -> dict:
        self._assigned(unit_id)
        if phase not in ("practice", "delayed"):
            raise ValueError("Unknown comparison response phase.")
        if outside_study not in (None, "none", "some", "unknown"):
            raise ValueError("Outside study must be none, some, unknown, or absent.")
        answer = _answer(response)
        unit = UNIT_BY_ID[unit_id]
        exposures = self._rows("personal_exposures")
        exposure = exposures.get(unit_id)
        if exposure is None or exposure["completed_at"] is None:
            raise ValueError("Complete the worked example before answering.")
        responses = self._responses()
        if (unit_id, phase) not in self._views():
            raise ValueError("Open the question before submitting its answer.")
        prior = responses.get((unit_id, phase))
        if prior is not None:
            if prior["first_answer"] != answer:
                raise ValueError("The first answer is locked and cannot be replaced.")
            return self.report()
        if phase == "delayed":
            if (unit_id, "practice") not in responses:
                raise ValueError("Complete independent practice before the delayed check.")
            if self.now() < datetime.fromisoformat(exposure["completed_at"]) + timedelta(days=DELAY_DAYS):
                raise ValueError("The unfamiliar delayed check is not due yet.")
        key = unit.practice_answer if phase == "practice" else unit.delayed_answer
        assisted = phase == "practice" and exposure["hint_opened_at"] is not None
        with self.store.connection:
            self.store.connection.execute(
                "INSERT INTO personal_responses "
                "(protocol_id, protocol_version, content_version, unit_id, phase, "
                "family_id, first_answer, assisted, candidate_match, occurred_at, "
                "outside_study) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (PROTOCOL_ID, PROTOCOL_VERSION, CONTENT_VERSION, unit_id, phase,
                 unit.family(phase), answer, int(assisted), int(answer == key),
                 _iso(self.now()), outside_study))
        return self.report()

    def report(self) -> dict:
        assignments = self._rows("personal_assignments")
        exposures = self._rows("personal_exposures")
        responses = self._responses()
        views = self._views()
        other_learning = [row[0] for row in self.store.connection.execute(
            "SELECT a.occurred_at FROM attempts a JOIN activities i "
            "ON i.id = a.activity_id AND i.content_version = a.content_version "
            "WHERE i.concept_id = ? UNION ALL "
            "SELECT completed_at FROM lesson_completions WHERE concept_id = ? UNION ALL "
            "SELECT exposed_at FROM experiment_exposures WHERE concept_id = ? UNION ALL "
            "SELECT d.recorded_at FROM practice_drafts d JOIN activities i "
            "ON i.id = d.activity_id AND i.content_version = d.content_version "
            "WHERE i.concept_id = ?",
            (CONCEPT_ID, CONCEPT_ID, CONCEPT_ID, CONCEPT_ID))]
        units = []
        counts = {arm: {"assigned": 0, "completedExposures": 0, "eligible": 0,
                        "correct": 0, "missing": 0, "contaminated": 0,
                        "early": 0, "late": 0, "provisional": 0,
                        "outsideStudyUnknown": 0, "assistedPractice": 0}
                  for arm in ("text", "diagram")}
        seen = set()
        for unit in UNITS:
            assignment = assignments.get(unit.id)
            if assignment is None:
                continue
            if (assignment["content_version"], assignment["pair"], assignment["position"],
                    assignment["condition_id"]) != (
                    CONTENT_VERSION, unit.pair, UNITS.index(unit),
                    assigned_conditions(self.store.learner_id())[UNITS.index(unit)]):
                raise ValueError("Persisted comparison assignment differs from the fixed protocol.")
            arm = assignment["condition_id"]
            counts[arm]["assigned"] += 1
            exposure = exposures.get(unit.id)
            practice = responses.get((unit.id, "practice"))
            delayed = responses.get((unit.id, "delayed"))
            if exposure and exposure["completed_at"]:
                counts[arm]["completedExposures"] += 1
            if practice and practice["assisted"]:
                counts[arm]["assistedPractice"] += 1
            classification = "missing"
            actual_delay_days = None
            if delayed and exposure and exposure["completed_at"]:
                actual_delay_days = round((datetime.fromisoformat(delayed["occurred_at"]) -
                                           datetime.fromisoformat(exposure["completed_at"])).total_seconds() / 86400, 3)
                cross_path = any(datetime.fromisoformat(assignment["assigned_at"]) <=
                                 datetime.fromisoformat(at) <=
                                 datetime.fromisoformat(delayed["occurred_at"])
                                 for at in other_learning)
                contaminated = (cross_path or delayed["family_id"] in seen or
                                delayed["family_id"] in json.loads(exposure["encountered_family_ids"]) or
                                delayed["assisted"] or delayed["outside_study"] == "some" or
                                exposure["outside_study"] == "some" or
                                (datetime.fromisoformat(delayed["occurred_at"]) -
                                 datetime.fromisoformat(views[(unit.id, "delayed")]["first_viewed_at"]))
                                > timedelta(minutes=30))
                if contaminated:
                    classification = "contaminated"
                elif exposure["outside_study"] != "none" or delayed["outside_study"] != "none":
                    classification = "outsideStudyUnknown"
                elif actual_delay_days < DELAY_DAYS:
                    classification = "early"
                elif actual_delay_days > WINDOW_DAYS:
                    classification = "late"
                elif CONTENT_REVIEW_STATUS != "engineering_reviewed":
                    classification = "provisional"
                else:
                    classification = "eligible"
            if classification in counts[arm]:
                counts[arm][classification] += 1
            if classification == "eligible" and delayed and delayed["candidate_match"]:
                counts[arm]["correct"] += 1
            seen.add(unit.family("worked"))
            if practice or (unit.id, "practice") in views:
                seen.add(unit.family("practice"))
            if delayed:
                seen.add(unit.family("delayed"))
            units.append({"id": unit.id, "pair": unit.pair, "name": unit.name,
                          "condition": arm, "exposureStartedAt": exposure["started_at"] if exposure else None,
                          "exposureCompletedAt": exposure["completed_at"] if exposure else None,
                          "encounteredFamilyIds": json.loads(exposure["encountered_family_ids"]) if exposure else [],
                          "exposureDurationVerified": False,
                          "interrupted": bool(exposure and not exposure["completed_at"]),
                          "practiceAnswered": bool(practice), "practiceAssisted": bool(practice and practice["assisted"]),
                          "practiceCandidateMatch": bool(practice and practice["candidate_match"]),
                          "delayedAnswered": bool(delayed),
                          "delayedCandidateMatch": bool(delayed and delayed["candidate_match"]),
                          "delayedOutsideStudy": delayed["outside_study"] if delayed else None,
                          "otherConceptLearningBeforeDelayed": bool(
                              delayed and any(datetime.fromisoformat(assignment["assigned_at"]) <=
                                              datetime.fromisoformat(at) <=
                                              datetime.fromisoformat(delayed["occurred_at"])
                                              for at in other_learning)),
                          "delayedFirstViewedAt": views[(unit.id, "delayed")]["first_viewed_at"]
                          if (unit.id, "delayed") in views else None,
                          "actualDelayDays": actual_delay_days,
                          "classification": classification})
        next_step = None
        if assignments:
            for unit in UNITS:
                exposure = exposures.get(unit.id)
                if (exposure and exposure["completed_at"] and
                        (unit.id, "practice") in responses and
                        (unit.id, "delayed") not in responses and
                        self.now() >= datetime.fromisoformat(exposure["completed_at"]) +
                        timedelta(days=DELAY_DAYS)):
                    next_step = (unit.id, "delayed")
                    break
        if assignments and next_step is None:
            for unit in UNITS:
                exposure = exposures.get(unit.id)
                if exposure is None or exposure["completed_at"] is None:
                    next_step = (unit.id, "study")
                    break
                if (unit.id, "practice") not in responses:
                    next_step = (unit.id, "practice")
                    break
            if next_step is None:
                next_step = (None, "waiting")
        active = UNIT_BY_ID[next_step[0]] if next_step and next_step[0] else None
        active_assignment = assignments.get(active.id) if active else None
        active_exposure = exposures.get(active.id) if active else None
        active_response = responses.get((active.id, next_step[1])) if active else None
        instruction = None
        if active and next_step[1] == "study" and active_exposure:
            instruction = {"workedCode": active.worked_code, "workedAnswer": active.worked_answer,
                           "steps": active.worked_steps,
                           "misconceptions": ("The global and local names are the same binding.",
                                              "A supplied keyword argument is added to the default instead of replacing it."),
                           "diagram": active.diagram if active_assignment["condition_id"] == "diagram" else None,
                           "studyTargetMinutes": 10,
                           "source": "https://docs.python.org/3.12/tutorial/controlflow.html#keyword-arguments"}
        question = None
        if active and next_step[1] in ("practice", "delayed") and (active.id, next_step[1]) in views:
            phase = next_step[1]
            question = {"phase": phase, "prompt": "What are the final values of the assigned result and the global bonus or step? Answer number, number.",
                        "code": active.practice_code if phase == "practice" else active.delayed_code,
                        "familyId": active.family(phase),
                        "hintAvailable": phase == "practice" and active_exposure["hint_opened_at"] is None,
                        "hintOpened": phase == "practice" and active_exposure["hint_opened_at"] is not None}
        last_feedback = []
        for unit in UNITS:
            for phase in ("practice", "delayed"):
                row = responses.get((unit.id, phase))
                if row:
                    last_feedback.append(((datetime.fromisoformat(row["occurred_at"]), row["event_order"]), {"unitId": unit.id, "phase": phase,
                                          "candidateMatch": bool(row["candidate_match"]),
                                          "assisted": bool(row["assisted"]),
                                          "answer": unit.practice_answer if phase == "practice" else unit.delayed_answer,
                                          "steps": unit.practice_steps if phase == "practice" else unit.delayed_steps}))
        descriptive = {arm: {"observed": sum(row["condition"] == arm and row["delayedAnswered"]
                                              for row in units),
                             "candidateMatches": sum(row["condition"] == arm and row["delayedCandidateMatch"]
                                                     for row in units),
                             "eligibleCandidateMatches": counts[arm]["correct"]} for arm in counts}
        return {"protocol": {"id": PROTOCOL_ID, "version": PROTOCOL_VERSION,
                             "contentVersion": CONTENT_VERSION, "conceptId": CONCEPT_ID,
                             "seed": SEED, "assignmentUnit": "instructional micro-unit",
                             "assignmentMethod": "Seeded ABBA or BAAB across two matched pairs; fixed unit order.",
                             "primaryOutcome": "First unassisted unfamiliar delayed trace response per unit at days 7-14.",
                             "analysisUnit": "one learner with four dependent units",
                             "contentReviewStatus": CONTENT_REVIEW_STATUS},
                "enrolled": bool(assignments), "priorConceptExposure": self.prior_concept_exposure,
                "status": "insufficient_evidence",
                "reason": "Four dependent units from one learner cannot separate method from unit, order, prior knowledge, or carryover. No causal superiority claim.",
                "uncertainty": "No meaningful confidence interval or independent-learner estimate is available; exposure time and attentive study are unverified.",
                "units": units, "arms": counts, "descriptive": descriptive,
                "next": {"unitId": next_step[0], "stage": next_step[1]} if next_step else None,
                "instruction": instruction, "question": question,
                "feedback": max(last_feedback, key=lambda item: item[0])[1] if last_feedback else None}
