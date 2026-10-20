"""Synthetic five-concept return journey; controlled time is not real retention."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from aesop_lab.foreman import Preview


class PersonalPilotJourneyTests(unittest.TestCase):
    def test_new_v7_learner_returns_for_two_distinct_delayed_checks(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-learner.db"
            clock = [datetime(2026, 1, 1, 12, tzinfo=timezone.utc)]

            def answer(preview, cid, *, assisted=False, wrong=False):
                activity = preview.session(cid)["activity"]
                self.assertIsNotNone(activity)
                item = next(item for item in preview.pack.items if item.id == activity["id"])
                self.assertIsNotNone(item.answer_key)
                candidate = item.answer_key.accepted[0]
                if wrong:
                    candidate = next(choice for choice in activity["choices"]
                                     if choice != candidate)
                attempt_id = str(uuid4())
                preview.first_answer({"conceptId": cid, "activityId": activity["id"],
                                      "draftId": attempt_id, "answer": candidate,
                                      "confidence": .75})
                if assisted:
                    preview.hint({"draftId": attempt_id})
                result = preview.submit({"draftId": attempt_id, "outsideStudy": "unknown"})
                return activity, result

            preview = Preview(path, now=lambda: clock[0])
            concepts = preview.pack.learning_order()
            self.assertEqual(len(concepts), 5)
            self.assertEqual(preview.pack.pack_version, "m2-draft.7")
            for cid in concepts:
                lesson = preview.lesson(cid)
                self.assertGreater(len(lesson["body"]), 1400)
                self.assertIn("## How it works", lesson["body"])
                self.assertIn("## Common misconceptions", lesson["body"])
                self.assertIn("```python", lesson["body"])
                self.assertEqual(lesson["method"]["protocolVersion"], "v4")
                preview.complete_lesson(cid)
                exposure = next(row for row in preview.store.list_exposures()
                                if row["concept_id"] == cid)
                self.assertTrue(exposure["encountered_family_ids"])
                initial_activity = preview.session(cid)["activity"]
                self.assertNotIn(initial_activity["familyId"],
                                 preview.services[cid].encountered_family_ids)
                first_activity, first_result = answer(preview, cid,
                    assisted=(cid == concepts[0]), wrong=(cid == concepts[0]))
                if cid == concepts[0]:
                    self.assertTrue(first_result["assisted"])
                    self.assertEqual(preview.overview()["concepts"][0]["signals"]["unassistedCorrect"], 0)
                    _, independent = answer(preview, cid)
                    self.assertFalse(independent["assisted"])
                else:
                    self.assertFalse(first_result["assisted"])
                self.assertFalse(first_activity["heldOut"])

            before = preview.overview()
            self.assertEqual(len(preview.store.export_all()["experimentAssignments"]), 5)
            self.assertTrue(all(row["signals"]["attempts"] for row in before["concepts"]))
            self.assertEqual(before["concepts"][0]["signals"]["reviewSchedule"]["status"], "upcoming")
            attempts_before = preview.store.export_all()["attempts"]
            preview.store.close()

            preview = Preview(path, now=lambda: clock[0])
            try:
                self.assertEqual(preview.store.export_all()["attempts"], attempts_before)
                self.assertEqual(preview.overview()["concepts"][0]["signals"]["hintAssisted"], 1)
                clock[0] += timedelta(days=1, minutes=1)
                self.assertEqual(preview.overview()["pathRecommendation"]["action"], "delayed_check")
                preview.override({"conceptId": concepts[0], "mode": "practice",
                                  "reason": "learner_choice"})
                self.assertFalse(preview.session(concepts[0], mode="practice")["activity"]["heldOut"])
                day_one, result = answer(preview, concepts[0])
                self.assertTrue(day_one["heldOut"])
                self.assertEqual(day_one["checkDelayDays"], 1)
                self.assertFalse(result["assisted"])
                clock[0] += timedelta(days=6)
                week, result = answer(preview, concepts[0])
                self.assertEqual(week["checkDelayDays"], 7)
                self.assertNotEqual(week["familyId"], day_one["familyId"])
                self.assertFalse(result["assisted"])
                evidence = preview.overview()["concepts"][0]["signals"]["evidence"]
                self.assertEqual(evidence["delayedOutcomeByDay"], {"1": "observed", "7": "observed"})
                self.assertEqual([row["independentSuccess"] for row in evidence["delayedChecks"]],
                                 [True, True])
                self.assertEqual([row["familiarityStatus"] for row in evidence["delayedChecks"]],
                                 ["unfamiliar", "unfamiliar"])
                self.assertTrue(all(row["actualDelayDays"] >= row["checkDelayDays"]
                                    for row in evidence["delayedChecks"]))
                finding = preview.overview()["experiment"]
                self.assertEqual(finding["protocol"]["version"], "v4")
                self.assertEqual(finding["status"], "insufficient_evidence")
                self.assertLessEqual(finding["independentLearnersTotal"], 1)
                self.assertEqual(sum(arm["eligible"] for arm in finding["arms"].values()), 0)
                self.assertEqual(sum(arm["provisional"] for arm in finding["arms"].values()), 1)
                self.assertEqual(len(preview.store.export_all()["attempts"]), len(attempts_before) + 2)
                self.assertEqual(len(preview.store.export_all()["recommendationOverrides"]), 1)
            finally:
                preview.store.close()


if __name__ == "__main__":
    unittest.main()
