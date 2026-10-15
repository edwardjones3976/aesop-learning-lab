"""The five-concept learner journey on a fresh, restartable local record."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from aesop_lab.foreman import Preview


class FiveConceptJourney(unittest.TestCase):
    def test_fresh_returning_and_delayed_learner(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "learner.sqlite3"
            clock = [datetime(2026, 1, 1, 12, tzinfo=timezone.utc)]
            preview = Preview(db, now=lambda: clock[0])
            try:
                concepts = preview.pack.learning_order()
                self.assertEqual(len(concepts), 5)
                first_ids = []
                expected_counts = {}
                for concept in concepts:
                    lesson = preview.lesson(concept)
                    self.assertTrue(lesson["body"])
                    self.assertTrue(lesson["sources"])
                    preview.complete_lesson(concept)
                    independent_found = False
                    for _ in range(4):
                        offered = preview.session(concept)["activity"]
                        self.assertIsNotNone(offered)
                        item = next(item for item in preview.pack.items if item.id == offered["id"])
                        answer = item.answer_key.accepted[0] if item.answer_key else "My explanation"
                        draft_id = str(uuid4())
                        preview.first_answer({"conceptId": concept, "activityId": offered["id"],
                                              "draftId": draft_id, "answer": answer})
                        self.assertEqual(preview.session(concept)["draft"]["firstAnswer"], answer)
                        result = preview.submit({"draftId": draft_id})
                        self.assertFalse(result["assisted"])
                        if item.answer_key:
                            self.assertEqual(result["scoreStatus"], "correct")
                            first_ids.append(draft_id)
                            independent_found = True
                            break
                        self.assertEqual(result["scoreStatus"], "ungraded")
                    self.assertTrue(independent_found)

                    practice = preview.session(concept, mode="practice")["activity"]
                    self.assertIsNotNone(practice)
                    assisted_id = str(uuid4())
                    assisted_answer = practice["choices"][0] if practice["type"] == "choice" else "my first answer"
                    preview.first_answer({"conceptId": concept, "activityId": practice["id"],
                                          "draftId": assisted_id, "answer": assisted_answer,
                                          "mode": "practice"})
                    self.assertEqual([preview.hint({"draftId": assisted_id})["level"]
                                      for _ in range(3)],
                                     ["nudge", "targeted", "worked_solution"])
                    assisted = preview.submit({"draftId": assisted_id})
                    self.assertTrue(assisted["assisted"])
                    self.assertNotEqual(assisted["scoreStatus"], "correct")
                    expected_counts[concept] = len(preview.store.list_attempts(concept))

                exported = preview.store.export_all()
                self.assertEqual(len(exported["attempts"]), sum(expected_counts.values()))
                self.assertEqual(len(exported["hintEvents"]), 15)
                self.assertEqual({row["id"] for row in exported["attempts"] if row["id"] in first_ids},
                                 set(first_ids))
                preview.store.close()
                preview = Preview(db, now=lambda: clock[0])
                self.assertEqual(len(preview.store.export_all()["attempts"]), sum(expected_counts.values()))
                for concept in concepts:
                    signals = next(row["signals"] for row in preview.overview()["concepts"]
                                   if row["id"] == concept)
                    self.assertEqual(signals["attempts"], expected_counts[concept])
                    self.assertEqual(signals["unassistedCorrect"], 1)
                    self.assertEqual(signals["hintAssisted"], 1)
                    self.assertEqual(signals["evidence"]["delayedOutcome"], "insufficient_evidence")

                clock[0] += timedelta(days=1, minutes=1)
                due = preview.session(concepts[0])["activity"]
                self.assertTrue(due["heldOut"])
                self.assertEqual(due["checkDelayDays"], 1)
                self.assertIn("reason", preview.session(concepts[0])["recommendation"])
                check_item = next(item for item in preview.pack.items if item.id == due["id"])
                check_id = str(uuid4())
                preview.first_answer({"conceptId": concepts[0], "activityId": due["id"],
                                      "draftId": check_id,
                                      "answer": check_item.answer_key.accepted[0]})
                preview.submit({"draftId": check_id})
                self.assertEqual(preview.overview()["concepts"][0]["signals"]["evidence"]
                                 ["delayedOutcomeByDay"],
                                 {"1": "observed", "7": "insufficient_evidence"})
                self.assertEqual(len(preview.store.export_all()["attempts"]),
                                 sum(expected_counts.values()) + 1)
                clock[0] += timedelta(days=6)
                week = preview.session(concepts[0])["activity"]
                self.assertTrue(week["heldOut"])
                self.assertEqual(week["checkDelayDays"], 7)
                self.assertNotEqual(week["familyId"], due["familyId"])
                week_item = next(item for item in preview.pack.items if item.id == week["id"])
                week_id = str(uuid4())
                preview.first_answer({"conceptId": concepts[0], "activityId": week["id"],
                                      "draftId": week_id,
                                      "answer": week_item.answer_key.accepted[0]})
                preview.submit({"draftId": week_id})
                self.assertEqual(preview.overview()["concepts"][0]["signals"]["evidence"]
                                 ["delayedOutcomeByDay"], {"1": "observed", "7": "observed"})
            finally:
                preview.store.close()


if __name__ == "__main__":
    unittest.main()
