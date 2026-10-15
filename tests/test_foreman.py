"""The local preview keeps the learner's first answer and hint history durable."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from aesop_lab.api.service import ApiError
from aesop_lab.foreman import Preview


class ForemanPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "learner.db"
        self.preview = Preview(self.path)
        self.addCleanup(lambda: self.preview.store.close())
        self.concept = self.preview.pack.learning_order()[0]
        self.preview.complete_lesson(self.concept)

    def test_first_answer_and_hint_survive_restart_and_retry(self):
        activity = self.preview.session(self.concept)["activity"]
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

    def test_answer_requires_offered_activity_and_lesson(self):
        other = self.preview.pack.learning_order()[1]
        self.assertTrue(self.preview.session(other)["lessonRequired"])
        with self.assertRaises(ApiError):
            self.preview.first_answer({"conceptId": other, "activityId": "unknown",
                                       "draftId": str(uuid4()), "answer": "x"})

    def test_personalization_reports_observed_signals_and_keeps_policy_floor(self):
        initial = self.preview.overview()["concepts"][0]["signals"]
        self.assertEqual(initial["attempts"], 0)
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
        self.preview.submit({"draftId": draft_id})
        signals = self.preview.overview()["concepts"][0]["signals"]
        self.assertEqual(signals["attempts"], 1)
        self.assertEqual(signals["hintAssisted"], 1)
        self.assertEqual(signals["unassistedCorrect"], 0)

    def test_evidence_path_and_delayed_outcome_journey(self):
        clock = [datetime(2026, 1, 1, 12, tzinfo=timezone.utc)]
        preview = Preview(Path(self.temp.name) / "journey.db", now=lambda: clock[0])
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
                              "draftId": independent_id, "answer": next_key})
        preview.submit({"draftId": independent_id, "confidence": .7})
        before = preview.overview()["concepts"][0]["signals"]["evidence"]
        self.assertEqual(before["byKind"][activity["evidenceKind"]]["assistedCorrect"], 1)
        self.assertEqual(before["byKind"][next_activity["evidenceKind"]]["unassistedCorrect"], 1)
        self.assertEqual(before["delayedOutcome"], "insufficient_evidence")
        self.assertFalse(preview.session(first)["activity"]["heldOut"])
        self.assertEqual(preview.overview()["pathRecommendation"]["action"], "lesson")

        clock[0] += timedelta(days=1, minutes=1)
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
        self.assertTrue(evidence["delayedChecks"][0]["independentSuccess"])
        self.assertEqual(evidence["delayedChecks"][0]["familiarityStatus"], "not_verified")
        self.assertEqual(evidence["confidenceOutcomePairs"], 1)
        self.assertNotEqual(preview.overview()["pathRecommendation"]["action"], "delayed_check")
        self.assertEqual(len(preview.store.export_all()["attempts"]), 3)
        preview.store.delete_all()
        self.assertEqual(preview.overview()["concepts"][0]["signals"]["evidence"]["delayedOutcome"],
                         "insufficient_evidence")


if __name__ == "__main__":
    unittest.main()
