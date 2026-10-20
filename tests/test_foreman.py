"""The local preview keeps the learner's first answer and hint history durable."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from aesop_lab.api.service import ApiError
from aesop_lab.content import load_pack
from aesop_lab.foreman import Preview
from aesop_lab.foreman import PACK_PATH as ORIGINAL_PACK_PATH
from aesop_lab.foreman import ADAPTIVE_PACK_PATH, REVISED_PACK_PATH, WEEK_PACK_PATH, V5_PACK_PATH, V6_PACK_PATH, V7_PACK_PATH, V8_PACK_PATH
from aesop_lab.storage.sqlite import SQLiteStore


class ForemanPreviewTests(unittest.TestCase):
    def test_fresh_overview_and_findings_do_not_create_learner_identity(self):
        preview = Preview(Path(self.temp.name) / "fresh.db")
        self.addCleanup(preview.store.close)
        self.assertEqual(preview.overview()["experiment"]["status"], "insufficient_evidence")
        self.assertEqual(preview.experiment_findings()["status"], "insufficient_evidence")
        self.assertIsNone(preview.store.existing_learner_id())
        self.assertEqual(preview.store.connection.execute(
            "SELECT COUNT(*) FROM learner_identity").fetchone()[0], 0)

    def test_current_cannot_complete_experimental_exposure_without_opening_lesson(self):
        path = Path(self.temp.name) / "unopened.db"
        preview = Preview(path)
        self.addCleanup(preview.store.close)
        cid = preview.pack.learning_order()[0]
        with self.assertRaisesRegex(ApiError, "Open the assigned lesson"):
            preview.complete_lesson(cid)
        self.assertEqual(preview.store.list_exposures(), ())
        preview.lesson(cid)
        self.assertTrue(preview.store.list_exposures()[0]["encountered_family_ids"])
        preview.complete_lesson(cid)
        self.assertIsNotNone(preview.store.list_exposures()[0]["completed_at"])

    def test_v9_five_concepts_assignment_confidence_and_restart(self):
        clock = [datetime(2026, 10, 15, 12, tzinfo=timezone.utc)]
        path = Path(self.temp.name) / "adaptive.db"
        preview = Preview(path, now=lambda: clock[0])
        self.addCleanup(preview.store.close)
        self.assertEqual(preview.overview()["packVersion"], "m2-draft.9")
        methods = {}
        for cid in preview.pack.learning_order():
            lesson = preview.lesson(cid)
            method = lesson["method"]
            self.assertEqual(method["protocolVersion"], "v6")
            self.assertIn(method["conditionId"], ("text", "diagram"))
            self.assertEqual(bool(lesson["diagram"]), method["conditionId"] == "diagram")
            self.assertGreater(len(lesson["body"]), 1000)
            methods[cid] = method["conditionId"]
            preview.complete_lesson(cid)
            activity = preview.session(cid)["activity"]
            key = next(item.answer_key.accepted[0] for item in preview.pack.items
                       if item.id == activity["id"])
            did = str(uuid4())
            preview.first_answer({"conceptId": cid, "activityId": activity["id"],
                                  "draftId": did, "answer": key, "confidence": .6})
            if cid == preview.pack.learning_order()[0]:
                preview.hint({"draftId": did})
            preview.submit({"draftId": did, "outsideStudy": "none"})
        initial = preview.store.export_all()
        self.assertEqual(len(initial["attempts"]), 5)
        self.assertEqual(len(initial["experimentAssignments"]), 5)
        self.assertEqual(len(initial["experimentExposures"]), 5)
        self.assertEqual(initial["attempts"][0]["confidence"], .6)
        self.assertEqual(preview.overview()["experiment"]["status"], "insufficient_evidence")
        first = preview.pack.learning_order()[0]
        preview.override({"conceptId": first, "mode": "practice", "reason": "learner_choice",
                          "learnerReason": "More independent practice"})
        preview.store.close()
        reopened = Preview(path, now=lambda: clock[0])
        self.addCleanup(reopened.store.close)
        self.assertEqual(reopened.store.export_all()["attempts"], initial["attempts"])
        self.assertEqual(reopened.store.export_all()["experimentAssignments"], initial["experimentAssignments"])
        self.assertEqual(len(reopened.store.export_all()["recommendationOverrides"]), 1)
        override = reopened.store.export_all()["recommendationOverrides"][0]
        self.assertEqual(override["learner_reason"], "More independent practice")
        self.assertTrue(override["recommended_reason"])
        self.assertTrue(override["selected_activity_id"])
        self.assertEqual(override["selected_concept_id"], first)
        self.assertEqual({cid: reopened.lesson(cid)["method"]["conditionId"]
                          for cid in methods}, methods)
        self.assertEqual(len(reopened.store.export_all()["experimentExposures"]), 5)

    def test_override_records_the_displayed_path_not_a_local_practice_surrogate(self):
        self.preview.complete_lesson(self.concept)
        activity = self.preview.session(self.concept)["activity"]
        key = next(item.answer_key.accepted[0] for item in self.preview.pack.items
                   if item.id == activity["id"])
        draft_id = str(uuid4())
        self.preview.first_answer({"conceptId": self.concept, "activityId": activity["id"],
                                   "draftId": draft_id, "answer": key})
        self.preview.submit({"draftId": draft_id})
        displayed = self.preview.overview()["pathRecommendation"]
        self.assertEqual(displayed["action"], "lesson")
        self.assertNotEqual(displayed["conceptId"], self.concept)
        self.preview.override({"conceptId": self.concept, "mode": "practice",
                               "reason": "learner_choice", "learnerReason": "One more"})
        recorded = self.preview.store.export_all()["recommendationOverrides"][0]
        self.assertEqual(recorded["recommended_concept_id"], displayed["conceptId"])
        self.assertEqual(recorded["recommended_action"], displayed["action"])
        self.assertEqual(recorded["recommended_reason"], displayed["reason"])
        self.assertIsNone(recorded["recommended_activity_id"])
        self.assertEqual(recorded["selected_concept_id"], self.concept)
        self.assertEqual(recorded["learner_reason"], "One more")

    def test_blank_override_note_and_other_concepts_recommendation_persist(self):
        first = self.concept
        selected = self.preview.pack.learning_order()[1]
        self.preview.lesson(selected)
        self.preview.complete_lesson(selected)
        displayed = self.preview.overview()["pathRecommendation"]
        self.assertEqual(displayed["conceptId"], first)
        self.assertEqual(displayed["action"], "practice")
        expected = self.preview.session(first)["activity"]["id"]
        self.preview.override({"conceptId": selected, "mode": "practice",
                               "reason": "learner_choice", "learnerReason": "   "})
        saved = self.preview.store.export_all()["recommendationOverrides"][0]
        self.assertIsNone(saved["learner_reason"])
        self.assertEqual(saved["recommended_activity_id"], expected)
        self.assertEqual(saved["recommended_concept_id"], first)
        self.assertEqual(saved["selected_concept_id"], selected)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "learner.db"
        self.preview = Preview(self.path)
        self.addCleanup(lambda: self.preview.store.close())
        self.concept = self.preview.pack.learning_order()[0]
        self.preview.lesson(self.concept)
        self.preview.complete_lesson(self.concept)

    def test_first_answer_and_hint_survive_restart_and_retry(self):
        offered = self.preview.session(self.concept)
        self.assertTrue(offered["recommendation"]["aim"])
        self.assertIn("first-attempt", offered["recommendation"]["evidenceGap"])
        activity = offered["activity"]
        self.assertNotIn("solution", activity)
        self.assertNotIn("answerKey", activity)
        draft_id = str(uuid4())
        answer = next(c for c in activity["choices"] if c != "return total")
        body = {"conceptId": self.concept, "activityId": activity["id"],
                "draftId": draft_id, "answer": answer}
        self.preview.first_answer(body)
        self.assertNotIn("text", self.preview.session(self.concept)["activity"]["hints"][0])
        first_hint = self.preview.hint({"draftId": draft_id})
        self.assertEqual(first_hint["level"], "nudge")
        self.preview.store.close()
        self.preview = Preview(self.path)
        session = self.preview.session(self.concept)
        self.assertEqual(session["draft"]["firstAnswer"], answer)
        self.assertEqual(session["draft"]["hintLevels"], ["nudge"])
        self.assertEqual(session["activity"]["hints"][0]["text"], first_hint["text"])
        with self.assertRaises(ApiError):
            self.preview.first_answer({**body, "answer": "changed"})
        result = self.preview.submit({"draftId": draft_id, "activeSeconds": 10})
        self.assertEqual(result["solution"]["kind"], "candidate_key")
        self.assertTrue(result["solution"]["answer"])
        self.assertEqual(result["solution"]["reasoning"], result["explanation"])
        self.assertTrue(result["solution"]["misconception"])
        self.assertEqual(result, self.preview.submit({"draftId": draft_id}))
        self.assertEqual(result["attemptId"], draft_id)
        attempts = self.preview.store.list_attempts(self.concept)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0].first_answer, answer)
        self.assertEqual(attempts[0].hint_level.value, "nudge")
        exported = self.preview.store.export_all()
        self.assertEqual(len(exported["practiceDrafts"]), 1)
        self.assertEqual(len(exported["hintEvents"]), 1)
        self.preview.store.delete_all()
        self.assertEqual(self.preview.store.export_all()["practiceDrafts"], [])

    def test_existing_v1_learner_is_pinned_until_explicit_delete(self):
        path = Path(self.temp.name) / "legacy.db"
        old = load_pack(ORIGINAL_PACK_PATH)
        with SQLiteStore(path) as store:
            concept = old.concepts[0]
            store.add_concept(concept)
            store.record_lesson_completion(concept.id, concept.content_version,
                                           datetime(2026, 1, 1, tzinfo=timezone.utc))
            self.assertEqual(store.learner_content_versions(), frozenset({"v1"}))
        legacy = Preview(path)
        self.addCleanup(legacy.store.close)
        self.assertEqual(legacy.overview()["packVersion"], "m1-draft.1")
        self.assertTrue(legacy.lesson(concept.id)["completed"])
        exported = legacy.store.export_all()
        self.assertEqual(exported["lessonCompletions"][0]["content_version"], "v1")
        self.assertEqual(legacy.delete_data()["packVersion"], "m2-draft.9")
        self.assertEqual(legacy.store.export_all()["lessonCompletions"], [])
        self.assertEqual(legacy.overview()["packVersion"], "m2-draft.9")

    def test_fresh_learner_keeps_v9_on_restart_and_mixed_history_is_rejected(self):
        self.assertEqual(self.preview.overview()["packVersion"], "m2-draft.9")
        self.assertEqual(self.preview.store.learner_content_versions(), frozenset({"v9"}))
        restarted = Preview(self.path)
        try:
            self.assertEqual(restarted.overview()["packVersion"], "m2-draft.9")
        finally:
            restarted.store.close()
        old = load_pack(ORIGINAL_PACK_PATH)
        self.preview.store.add_concept(old.concepts[0])
        self.preview.store.record_lesson_completion(old.concepts[0].id, "v1",
                                                  datetime(2026, 1, 1, tzinfo=timezone.utc))
        with self.assertRaisesRegex(RuntimeError, "incompatible content versions"):
            Preview(self.path)

    def test_existing_v2_learner_remains_on_v2(self):
        path = Path(self.temp.name) / "prior-v2.db"
        concept = load_pack(REVISED_PACK_PATH).concepts[0]
        with SQLiteStore(path) as store:
            store.add_concept(concept)
            store.record_lesson_completion(concept.id, "v2",
                                           datetime(2026, 1, 1, tzinfo=timezone.utc))
        prior = Preview(path)
        self.addCleanup(prior.store.close)
        self.assertEqual(prior.overview()["packVersion"], "m1-draft.2")
        self.assertEqual(prior.store.learner_content_versions(), frozenset({"v2"}))

    def test_existing_v4_assignment_and_analysis_stay_on_protocol_v1(self):
        path = Path(self.temp.name) / "prior-v4.db"
        concept = load_pack(ADAPTIVE_PACK_PATH).concepts[0]
        with SQLiteStore(path) as store:
            store.add_concept(concept)
            store.record_lesson_completion(concept.id, "v4",
                                           datetime(2026, 1, 1, tzinfo=timezone.utc))
        prior = Preview(path)
        self.addCleanup(prior.store.close)
        self.assertEqual(prior.overview()["packVersion"], "m2-draft.4")
        self.assertEqual(prior.lesson(concept.id)["method"]["protocolVersion"], "v1")
        self.assertEqual(prior.overview()["experiment"]["protocol"]["version"], "v1")
        self.assertEqual(prior.store.export_all()["experimentAssignments"][0]["protocol_version"], "v1")

    def test_existing_v5_assignment_stays_on_protocol_v2(self):
        path = Path(self.temp.name) / "prior-v5.db"
        viewed = Preview(path)
        viewed._activate_pack(V5_PACK_PATH)
        cid = viewed.pack.learning_order()[0]
        original = viewed.lesson(cid)["method"]
        self.assertEqual(original["protocolVersion"], "v2")
        viewed.store.close()
        resumed = Preview(path)
        try:
            self.assertEqual(resumed.pack.pack_version, "m2-draft.5")
            self.assertEqual(resumed.lesson(cid)["method"], original)
            self.assertEqual(resumed.overview()["experiment"]["protocol"]["version"], "v2")
        finally:
            resumed.store.close()

    def test_existing_v6_assignment_stays_on_protocol_v3_and_v6_pack(self):
        path = Path(self.temp.name) / "prior-v6.db"
        viewed = Preview(path)
        viewed._activate_pack(V6_PACK_PATH)
        cid = viewed.pack.learning_order()[0]
        original = viewed.lesson(cid)["method"]
        self.assertEqual(original["protocolVersion"], "v3")
        self.assertEqual(viewed.store.learner_content_versions(), frozenset({"v6"}))
        viewed.store.close()
        resumed = Preview(path)
        try:
            self.assertEqual(resumed.pack.pack_version, "m2-draft.6")
            self.assertEqual(resumed.lesson(cid)["method"], original)
            self.assertEqual(resumed.overview()["experiment"]["protocol"]["version"], "v3")
        finally:
            resumed.store.close()

    def test_existing_v7_assignment_stays_on_protocol_v4_and_v7_pack(self):
        path = Path(self.temp.name) / "prior-v7.db"
        viewed = Preview(path)
        viewed._activate_pack(V7_PACK_PATH)
        cid = viewed.pack.learning_order()[0]
        original = viewed._method_for(cid)
        self.assertEqual(original["protocolVersion"], "v4")
        self.assertEqual(viewed.store.list_exposures(), ())
        viewed.store.close()
        resumed = Preview(path)
        try:
            self.assertEqual(resumed.pack.pack_version, "m2-draft.7")
            self.assertEqual(resumed.lesson(cid)["method"], original)
            self.assertEqual(resumed.overview()["experiment"]["protocol"]["version"], "v4")
        finally:
            resumed.store.close()

    def test_existing_v8_assignment_stays_on_protocol_v5_and_v8_pack(self):
        path = Path(self.temp.name) / "prior-v8.db"
        viewed = Preview(path)
        viewed._activate_pack(V8_PACK_PATH)
        cid = viewed.pack.learning_order()[0]
        original = viewed._method_for(cid)
        self.assertEqual(original["protocolVersion"], "v5")
        self.assertEqual(viewed.store.list_exposures(), ())
        before = viewed.store.export_all()["experimentAssignments"]
        viewed.store.close()
        resumed = Preview(path)
        try:
            self.assertEqual(resumed.pack.pack_version, "m2-draft.8")
            self.assertEqual(resumed.lesson(cid)["method"], original)
            self.assertEqual(resumed.overview()["experiment"]["protocol"]["version"], "v5")
            self.assertEqual(resumed.store.export_all()["experimentAssignments"], before)
        finally:
            resumed.store.close()

    def test_v9_assignment_only_restart_keeps_protocol_v6(self):
        path = Path(self.temp.name) / "assigned-v9.db"
        viewed = Preview(path)
        cid = viewed.pack.learning_order()[0]
        original = viewed._method_for(cid)
        self.assertEqual(original["protocolVersion"], "v6")
        self.assertEqual(viewed.store.list_exposures(), ())
        before = viewed.store.export_all()["experimentAssignments"]
        viewed.store.close()
        resumed = Preview(path)
        try:
            self.assertEqual(resumed.pack.pack_version, "m2-draft.9")
            self.assertEqual(resumed.lesson(cid)["method"], original)
            self.assertEqual(resumed.overview()["experiment"]["protocol"]["version"], "v6")
            self.assertEqual(resumed.store.export_all()["experimentAssignments"], before)
        finally:
            resumed.store.close()

    def test_v6_assignment_only_interruption_stays_on_v6_pack(self):
        path = Path(self.temp.name) / "assigned-v6.db"
        viewed = Preview(path)
        viewed._activate_pack(V6_PACK_PATH)
        cid = viewed.pack.learning_order()[0]
        original = viewed._method_for(cid)
        self.assertEqual(viewed.store.list_exposures(), ())
        viewed.store.close()
        resumed = Preview(path)
        try:
            self.assertEqual(resumed.pack.pack_version, "m2-draft.6")
            self.assertEqual(resumed.lesson(cid)["method"], original)
        finally:
            resumed.store.close()

    def test_opened_v4_lesson_stays_v4_after_interrupted_session(self):
        path = Path(self.temp.name) / "viewed-v4.db"
        viewed = Preview(path)
        viewed._activate_pack(ADAPTIVE_PACK_PATH)
        cid = viewed.pack.learning_order()[0]
        original = viewed.lesson(cid)["method"]
        self.assertEqual(original["protocolVersion"], "v1")
        self.assertEqual(viewed.store.learner_content_versions(), frozenset({"v4"}))
        self.assertIsNone(viewed.store.lesson_completed_at(cid, "v4"))
        viewed.store.close()
        resumed = Preview(path)
        try:
            self.assertEqual(resumed.pack.pack_version, "m2-draft.4")
            self.assertEqual(resumed.lesson(cid)["method"], original)
            self.assertEqual(len(resumed.store.export_all()["experimentAssignments"]), 1)
            self.assertEqual(len(resumed.store.export_all()["experimentExposures"]), 1)
        finally:
            resumed.store.close()

    def test_assignment_only_interruption_keeps_its_protocol_version(self):
        path = Path(self.temp.name) / "assigned-v4.db"
        viewed = Preview(path)
        viewed._activate_pack(ADAPTIVE_PACK_PATH)
        cid = viewed.pack.learning_order()[0]
        original = viewed._method_for(cid)
        self.assertEqual(viewed.store.list_exposures(), ())
        viewed.store.close()
        resumed = Preview(path)
        try:
            self.assertEqual(resumed.pack.pack_version, "m2-draft.4")
            self.assertEqual(resumed.lesson(cid)["method"], original)
        finally:
            resumed.store.close()

    def test_answer_requires_offered_activity_and_lesson(self):
        other = self.preview.pack.learning_order()[1]
        self.assertTrue(self.preview.session(other)["lessonRequired"])
        with self.assertRaises(ApiError):
            self.preview.first_answer({"conceptId": other, "activityId": "unknown",
                                       "draftId": str(uuid4()), "answer": "x"})

    def test_personalization_reports_observed_signals_and_keeps_policy_floor(self):
        initial = self.preview.overview()["concepts"][0]["signals"]
        self.assertEqual(initial["attempts"], 0)
        self.assertEqual(initial["reviewSchedule"]["status"], "none")
        self.assertIsNone(initial["openDraft"])
        self.assertIsNotNone(self.preview.session(self.concept, available_minutes=5)["activity"])
        with self.assertRaises(ApiError):
            self.preview.session(self.concept, available_minutes=4)
        with self.assertRaises(ApiError):
            self.preview.session(self.concept, available_minutes=True)
        activity = self.preview.session(self.concept)["activity"]
        draft_id = str(uuid4())
        self.preview.first_answer({"conceptId": self.concept, "activityId": activity["id"],
                                   "draftId": draft_id, "answer": activity["choices"][0],
                                   "availableMinutes": 5})
        self.preview.hint({"draftId": draft_id})
        open_draft = self.preview.overview()["concepts"][0]["signals"]["openDraft"]
        self.assertEqual(open_draft["activityId"], activity["id"])
        self.assertEqual(open_draft["hintLevel"], "nudge")
        self.preview.submit({"draftId": draft_id})
        signals = self.preview.overview()["concepts"][0]["signals"]
        self.assertEqual(signals["attempts"], 1)
        self.assertEqual(signals["hintAssisted"], 1)
        self.assertEqual(signals["unassistedCorrect"], 0)
        self.assertIsNone(signals["openDraft"])

    def test_evidence_path_and_delayed_outcome_journey(self):
        clock = [datetime(2026, 1, 1, 12, tzinfo=timezone.utc)]
        preview = Preview(Path(self.temp.name) / "journey.db", now=lambda: clock[0])
        # Keep the established v3 journey fixture stable while v4 adds open-ended items.
        preview._activate_pack(WEEK_PACK_PATH)
        self.addCleanup(preview.store.close)
        first = preview.pack.learning_order()[0]
        initial = preview.overview()
        self.assertEqual(initial["pathRecommendation"]["action"], "lesson")
        self.assertEqual(initial["concepts"][0]["signals"]["evidence"]["delayedOutcome"],
                         "insufficient_evidence")
        preview.complete_lesson(first)
        self.assertEqual(preview.overview()["pathRecommendation"]["action"], "practice")

        activity = preview.session(first)["activity"]
        key = next(item.answer_key.accepted[0] for item in preview.pack.items
                   if item.id == activity["id"])
        assisted_id = str(uuid4())
        preview.first_answer({"conceptId": first, "activityId": activity["id"],
                              "draftId": assisted_id, "answer": key})
        self.assertEqual(preview.overview()["pathRecommendation"]["action"], "resume")
        preview.hint({"draftId": assisted_id})
        preview.submit({"draftId": assisted_id, "confidence": .8})
        self.assertEqual(preview.overview()["concepts"][0]["signals"]["unassistedCorrect"], 0)
        self.assertFalse(preview.session(first)["activity"]["heldOut"])

        next_activity = preview.session(first)["activity"]
        next_key = next(item.answer_key.accepted[0] for item in preview.pack.items
                        if item.id == next_activity["id"])
        independent_id = str(uuid4())
        preview.first_answer({"conceptId": first, "activityId": next_activity["id"],
                              "draftId": independent_id, "answer": next_key, "confidence": .7})
        preview.submit({"draftId": independent_id, "confidence": .7})
        before = preview.overview()["concepts"][0]["signals"]["evidence"]
        self.assertEqual(before["byKind"][activity["evidenceKind"]]["assistedCorrect"], 1)
        self.assertEqual(before["byKind"][next_activity["evidenceKind"]]["unassistedCorrect"], 1)
        self.assertEqual(before["delayedOutcome"], "insufficient_evidence")
        self.assertEqual(before["delayedOutcomeByDay"],
                         {"1": "insufficient_evidence", "7": "insufficient_evidence"})
        self.assertEqual(preview.overview()["concepts"][0]["signals"]["reviewSchedule"]["status"],
                         "upcoming")
        self.assertFalse(preview.session(first)["activity"]["heldOut"])
        self.assertEqual(preview.overview()["pathRecommendation"]["action"], "lesson")

        clock[0] += timedelta(days=1, minutes=1)
        self.assertEqual(preview.overview()["concepts"][0]["signals"]["reviewSchedule"]["status"],
                         "due")
        due = preview.overview()["pathRecommendation"]
        self.assertEqual((due["conceptId"], due["action"]), (first, "delayed_check"))
        check = preview.session(first)["activity"]
        self.assertTrue(check["heldOut"])
        check_key = next(item.answer_key.accepted[0] for item in preview.pack.items
                         if item.id == check["id"])
        check_id = str(uuid4())
        preview.first_answer({"conceptId": first, "activityId": check["id"],
                              "draftId": check_id, "answer": check_key})
        preview.submit({"draftId": check_id})
        evidence = preview.overview()["concepts"][0]["signals"]["evidence"]
        self.assertEqual(evidence["delayedOutcome"], "observed")
        self.assertEqual(evidence["delayedChecks"][0]["attemptId"], check_id)
        self.assertEqual(evidence["delayedChecks"][0]["checkDelayDays"], 1)
        self.assertEqual(evidence["delayedOutcomeByDay"]["7"], "insufficient_evidence")
        self.assertTrue(evidence["delayedChecks"][0]["independentSuccess"])
        self.assertEqual(evidence["delayedChecks"][0]["familiarityStatus"], "unfamiliar")
        self.assertEqual(evidence["delayedChecks"][0]["dueAt"], "2026-01-02T12:00:00Z")
        self.assertGreater(evidence["delayedChecks"][0]["actualDelayDays"], 1)
        self.assertEqual(evidence["confidenceOutcomePairs"], 1)
        self.assertNotEqual(preview.overview()["pathRecommendation"]["action"], "delayed_check")
        clock[0] += timedelta(days=5)
        waiting = preview.session(first)
        self.assertEqual(waiting["nextCheckAt"], "2026-01-08T12:00:00Z")
        self.assertFalse(waiting["activity"]["heldOut"])
        clock[0] += timedelta(days=1)
        week = preview.session(first)["activity"]
        self.assertTrue(week["heldOut"])
        self.assertEqual(week["checkDelayDays"], 7)
        self.assertNotEqual(week["familyId"], check["familyId"])
        week_key = next(item.answer_key.accepted[0] for item in preview.pack.items
                        if item.id == week["id"])
        week_id = str(uuid4())
        preview.first_answer({"conceptId": first, "activityId": week["id"],
                              "draftId": week_id, "answer": week_key})
        preview.submit({"draftId": week_id})
        evidence = preview.overview()["concepts"][0]["signals"]["evidence"]
        self.assertEqual([row["checkDelayDays"] for row in evidence["delayedChecks"]], [1, 7])
        self.assertTrue(evidence["delayedChecks"][1]["independentSuccess"])
        self.assertEqual(evidence["delayedOutcomeByDay"]["7"], "observed")
        self.assertEqual(len(preview.store.export_all()["attempts"]), 4)
        preview.store.delete_all()
        self.assertEqual(preview.overview()["concepts"][0]["signals"]["evidence"]["delayedOutcome"],
                         "insufficient_evidence")


if __name__ == "__main__":
    unittest.main()
