"""Exercise the real loopback HTTP boundary with an isolated learner record."""

import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from aesop_lab.foreman import HOST


class ForemanHttpJourney(unittest.TestCase):
    def test_lesson_saved_answer_hint_submit_and_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(__file__).resolve().parents[1]
            with socket.socket() as free_port:
                free_port.bind((HOST, 0))
                port = free_port.getsockname()[1]
            server = subprocess.Popen(
                [sys.executable, str(root / "scripts/run_foreman.py"),
                 "--port", str(port), "--db", str(Path(directory) / "learner.sqlite3")],
                cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            base = f"http://{HOST}:{port}"

            def request(path, body=None):
                headers = {}
                if body is not None:
                    headers = {"Content-Type": "application/json", "Origin": base}
                data = json.dumps(body).encode() if body is not None else None
                with urlopen(Request(base + path, data=data, headers=headers), timeout=5) as response:
                    return json.load(response)

            try:
                for _ in range(50):
                    try:
                        request("/api/v2/overview")
                        break
                    except OSError:
                        if server.poll() is not None:
                            self.fail("local preview exited before accepting requests")
                        time.sleep(.1)
                else:
                    self.fail("local preview did not start")
                overview = request("/api/v2/overview")
                self.assertEqual(len(overview["concepts"]), 5)
                concept = overview["concepts"][0]["id"]

                # Opening a lesson assigns a condition and records exposure.
                # A foreign page must not be able to do either with a GET or
                # a simple cross-origin POST to the loopback preview.
                def rejected(path, *, data=None, headers=None, status):
                    with self.assertRaises(HTTPError) as error:
                        urlopen(Request(base + path, data=data, headers=headers or {}), timeout=5)
                    self.assertEqual(error.exception.code, status)

                self.assertEqual(request("/api/v2/export")["experimentAssignments"], [])
                rejected(f"/api/v2/lesson?conceptId={concept}",
                         headers={"Referer": "https://foreign.example/"}, status=404)
                lesson_body = json.dumps({"conceptId": concept}).encode()
                rejected("/api/v2/lesson", data=lesson_body,
                         headers={"Content-Type": "text/plain", "Origin": "https://foreign.example"},
                         status=403)
                rejected("/api/v2/lesson", data=lesson_body,
                         headers={"Content-Type": "application/json", "Origin": "https://foreign.example"},
                         status=403)
                rejected("/api/v2/lesson", data=lesson_body,
                         headers={"Content-Type": "application/json"}, status=403)
                rejected("/api/v2/lesson", data=lesson_body,
                         headers={"Content-Type": "text/plain", "Origin": base}, status=415)
                before = request("/api/v2/export")
                self.assertEqual(before["experimentAssignments"], [])
                self.assertEqual(before["experimentExposures"], [])
                request("/api/v2/consent", {})
                lesson = request("/api/v2/lesson", {"conceptId": concept})
                self.assertTrue(lesson["body"])
                after = request("/api/v2/export")
                self.assertEqual(len(after["experimentAssignments"]), 1)
                self.assertEqual(len(after["experimentExposures"]), 1)
                request("/api/v2/lesson-completions", {"conceptId": concept})
                session = request(f"/api/v2/session?conceptId={concept}")
                activity = session["activity"]
                self.assertEqual(activity["conceptId"], concept)
                draft_id = str(uuid4())
                request("/api/v2/first-answers", {"conceptId": concept,
                    "activityId": activity["id"], "draftId": draft_id,
                    "answer": activity["choices"][0]})
                hint = request("/api/v2/hints", {"draftId": draft_id})
                self.assertEqual(hint["level"], "nudge")
                resumed = request(f"/api/v2/session?conceptId={concept}")
                self.assertEqual(resumed["draft"]["hintLevels"], ["nudge"])
                self.assertEqual(resumed["activity"]["hints"][0]["text"], hint["text"])
                result = request("/api/v2/attempts", {"draftId": draft_id})
                self.assertTrue(result["assisted"])
                self.assertEqual(result, request("/api/v2/attempts", {"draftId": draft_id}))
                overview = request("/api/v2/overview")
                history = overview["concepts"][0]["signals"]["recordedAttempts"]
                self.assertEqual(len(history), 1)
                self.assertEqual(history[0]["firstAnswer"], activity["choices"][0])
                self.assertTrue(history[0]["assisted"])
                exported = request("/api/v2/export")
                self.assertEqual(len(exported["attempts"]), 1)
                self.assertEqual(len(exported["hintEvents"]), 1)
                self.assertIn("derived", exported)
                self.assertEqual(exported["derived"]["overview"], overview)
                self.assertEqual(exported["derived"]["packVersion"], overview["packVersion"])
                self.assertTrue(exported["derived"]["computedAt"].endswith("Z"))
                request("/api/v2/delete", {})
                self.assertTrue(request("/api/v2/overview")["deleted"])
                for endpoint, body in [
                    ("lesson", {"conceptId": concept}),
                    ("personal-comparison/enroll", {}),
                    ("personal-comparison/start", {"unitId": "scope"}),
                    ("personal-comparison/open", {"unitId": "scope", "phase": "practice"}),
                ]:
                    with self.assertRaises(HTTPError) as error:
                        request("/api/v2/" + endpoint, body)
                    self.assertEqual(error.exception.code, 409)
                    self.assertEqual(json.load(error.exception)["error"], "learner_deleted")
                exported = request("/api/v2/export")
                for key in ("learnerIdentity", "experimentAssignments", "experimentExposures",
                            "personalAssignments", "personalExposures", "personalQuestionViews"):
                    self.assertEqual(exported[key], [])
                rejected("/api/v2/restart", data=b"{}",
                         headers={"Content-Type": "application/json", "Origin": "https://foreign.example"},
                         status=403)
                self.assertTrue(request("/api/v2/overview")["deleted"])
                request("/api/v2/restart", {})
                self.assertTrue(request("/api/v2/overview")["consentRequired"])
                request("/api/v2/consent", {})
                request("/api/v2/lesson", {"conceptId": concept})
                self.assertEqual(len(request("/api/v2/export")["learnerIdentity"]), 1)
            finally:
                server.terminate()
                server.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
