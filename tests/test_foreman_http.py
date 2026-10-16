"""Exercise the real loopback HTTP boundary with an isolated learner record."""

import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
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
                lesson = request(f"/api/v2/lesson?conceptId={concept}")
                self.assertTrue(lesson["body"])
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
                history = request("/api/v2/overview")["concepts"][0]["signals"]["recordedAttempts"]
                self.assertEqual(len(history), 1)
                self.assertEqual(history[0]["firstAnswer"], activity["choices"][0])
                self.assertTrue(history[0]["assisted"])
                exported = request("/api/v2/export")
                self.assertEqual(len(exported["attempts"]), 1)
                self.assertEqual(len(exported["hintEvents"]), 1)
            finally:
                server.terminate()
                server.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
