"""End-to-end service and WSGI checks with a persisted local database."""

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sqlite3
import unittest

from aesop_lab.api import ApiError, LearningService
from aesop_lab.api.dev_fixture import CONCEPT, fixture_items
from aesop_lab.api.http import make_app
from aesop_lab.storage.sqlite import SQLiteStore


START = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


def answer(activity_id: str, first_answer: str, hint: str = "none") -> dict[str, object]:
    return {
        "activityId": activity_id, "contentVersion": "dev-v1",
        "firstAnswer": first_answer, "hintLevel": hint,
        "confidence": None, "outsideStudy": None, "outsideStudyDetail": None,
        "activeSeconds": 12,
    }


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "learner.sqlite3"
        self.clock = [START]
        self.store = SQLiteStore(self.path)
        self.service = self.open_service()
        self.service.complete_lesson()

    def tearDown(self) -> None:
        self.store.close()
        self.temp.cleanup()

    def open_service(self) -> LearningService:
        return LearningService(
            self.store, CONCEPT, fixture_items(), reviewed=False,
            allow_development_fixtures=True, now=lambda: self.clock[0],
        )

    def test_fixture_requires_explicit_opt_in_and_never_claims_reviewed(self) -> None:
        with self.assertRaisesRegex(ValueError, "opt-in"):
            LearningService(self.store, CONCEPT, fixture_items(), reviewed=False)
        with self.assertRaisesRegex(ValueError, "receipt verification"):
            LearningService(self.store, CONCEPT, fixture_items(), reviewed=True)
        self.assertTrue(self.service.next_session(20)["developmentOnly"])

    def test_get_does_not_advance_and_refresh_retains_attempt_and_lesson_time(self) -> None:
        first = self.service.next_session(20)
        self.assertEqual(first, self.service.next_session(20))
        self.assertEqual(first["activity"]["id"], "dev-trace-a")
        saved = self.service.submit_attempt(answer("dev-trace-a", "1"))
        self.assertEqual(saved["scoreStatus"], "correct")
        self.store.close()
        self.clock[0] += timedelta(hours=2)
        self.store = SQLiteStore(self.path)
        self.service = self.open_service()
        self.assertEqual(self.service.complete_lesson(), START)
        next_one = self.service.next_session(20)
        self.assertEqual(next_one["activity"]["id"], "dev-trace-b")
        self.assertEqual(next_one["nextCheckAt"], "2026-01-02T12:00:00Z")
        self.assertEqual(self.store.list_attempts(CONCEPT.id)[0].first_answer, "1")

    def test_due_check_and_practice_choice_do_not_consume_each_other(self) -> None:
        self.service.submit_attempt(answer("dev-trace-a", "1"))
        self.clock[0] += timedelta(hours=25)
        practice = self.service.next_session(20, "practice")
        self.assertEqual(practice["activity"]["id"], "dev-trace-b")
        self.assertEqual(practice["nextCheckAt"], "2026-01-02T12:00:00Z")
        check = self.service.next_session(20)
        self.assertEqual(check["activity"]["id"], "dev-check-d")
        self.service.submit_attempt(answer("dev-check-d", "24"))
        self.assertEqual(self.service.next_session(20)["activity"]["id"], "dev-trace-b")
        with self.assertRaisesRegex(ApiError, "not available"):
            self.service.submit_attempt(answer("dev-check-d", "24"))

    def test_assistance_cannot_open_check_and_first_answer_is_preserved(self) -> None:
        saved = self.service.submit_attempt(answer("dev-trace-a", "1", "nudge"))
        self.assertTrue(saved["assisted"])
        self.clock[0] += timedelta(hours=25)
        self.assertNotEqual(self.service.next_session(20)["activity"]["id"], "dev-check-d")
        attempt = self.store.list_attempts(CONCEPT.id)[0]
        self.assertEqual(attempt.first_answer, "1")
        self.assertEqual(attempt.hint_level.value, "nudge")

    def test_held_out_check_rejected_before_due_and_errors_do_not_write(self) -> None:
        with self.assertRaises(ApiError) as problem:
            self.service.submit_attempt(answer("dev-check-d", "24"))
        self.assertEqual(problem.exception.status, 409)
        for body in (answer("dev-trace-a", " "), answer("dev-trace-a", "1", "bad"),
                     {**answer("dev-trace-a", "1"), "activeSeconds": -1}):
            with self.assertRaises(ApiError):
                self.service.submit_attempt(body)
        self.assertEqual(self.store.list_attempts(CONCEPT.id), ())

    def test_v1_migration_and_delete_clear_lesson_without_deleting_content(self) -> None:
        self.store.close()
        connection = sqlite3.connect(self.path)
        connection.execute("DROP TABLE lesson_completions")
        connection.execute("PRAGMA user_version = 1")
        connection.close()
        self.store = SQLiteStore(self.path)
        self.service = self.open_service()
        self.assertIsNone(self.store.lesson_completed_at(CONCEPT.id, CONCEPT.content_version))
        self.service.complete_lesson()
        self.service.submit_attempt(answer("dev-trace-a", "1"))
        self.assertEqual(len(self.store.export_all()["lessonCompletions"]), 1)
        self.store.delete_all()
        self.assertEqual(self.store.export_all()["lessonCompletions"], [])
        self.assertIsNotNone(self.store.get_activity("dev-trace-a", "dev-v1"))

    def test_wsgi_contract_and_json_errors(self) -> None:
        app = make_app(self.service)

        def request(method: str, path: str, data: bytes = b"", query: str = ""):
            captured = []
            result = app({"REQUEST_METHOD": method, "PATH_INFO": path,
                          "QUERY_STRING": query, "CONTENT_LENGTH": str(len(data)),
                          "wsgi.input": BytesIO(data)},
                         lambda status, headers: captured.append((status, headers)))
            return captured[0][0], json.loads(b"".join(result))

        status, response = request("GET", "/api/v1/session/next",
                                   query="availableMinutes=20&mode=practice")
        self.assertEqual(status, "200 OK")
        self.assertEqual(response["mode"], "practice")
        status, response = request("POST", "/api/v1/attempts",
                                   json.dumps(answer("dev-trace-a", "1")).encode())
        self.assertEqual(status, "201 Created")
        self.assertEqual(response["scoreStatus"], "correct")
        status, response = request("GET", "/api/v1/session/next",
                                   query="availableMinutes=bad")
        self.assertEqual(status, "400 Bad Request")
        self.assertEqual(response["code"], "validation_error")


if __name__ == "__main__":
    unittest.main()
